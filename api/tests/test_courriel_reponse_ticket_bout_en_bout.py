"""Ce qui est ÉCRIT quand une réponse par courriel arrive (#703, #752).

Sorti de `test_courriel_reponse_ticket.py` le 05/09/2026, sur refus du contrôle
de modularité — 548 lignes. La coupure suit celle du code, et c'est ce qui la
rend juste : `courriel_ingestion` rend un **verdict** sans toucher à rien (testé
là-bas, sur des chaînes), `courriel_boite` **écrit** — un commentaire dans un
fil, une notification au conseil syndical, rien du tout. Ici, on regarde ce qui
reste en base.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import select

from app.models.core import (
    StatutTicket,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.models.courriel import RelanceCourriel
from app.utils.courriel_boite import traiter
from app.utils.courriel_entrant import nouveau_jeton
from app.utils.courriel_ingestion import A_CLASSER, ACCEPTE, IGNORE, REFUSE, RELANCE
from tests.aides_base import compte
from tests.aides_courriel import (  # noqa: F401 — `scene` est une fixture
    _AUTH_OK,
    _entetes_reponse,
    _evolutions,
    _notifs,
    scene,
)
from tests.aides_purge import purger_ligne


# ── Ce qui est écrit en base ──────────────────────────────────────────────────


def test_une_reponse_authentifiee_rejoint_le_fil(scene):
    session, ticket, syndic, _cs = scene
    decision = traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
        "Nous intervenons jeudi.",
        datetime(2026, 9, 3),
        authentification=_AUTH_OK,
    )
    assert decision == ACCEPTE
    evols = _evolutions(session, ticket)
    assert len(evols) == 1
    #  Depuis #1322 la Suite est en HTML, précédée de « Réponse de … le … ».
    assert evols[0].contenu.endswith("<p>Nous intervenons jeudi.</p>")
    assert evols[0].auteur_id == syndic.id, "l'entrée doit être signée de son auteur réel"


def test_le_syndic_repond_SANS_jeton_et_sa_reponse_rejoint_le_fil(scene):
    """Le cas qui a motivé le repli : l'adresse à jeton n'achemine pas.

    Le message ne porte que le sujet — celui que le site a écrit lui-même. Il
    doit rejoindre le fil, signé du syndic.
    """
    session, ticket, syndic, _cs = scene
    decision = traiter(
        session,
        {
            "From": syndic.email,
            "To": "noreply@5hostachy.fr",
            "Subject": f"Re: Ticket #{ticket.numero} — Fuite — Les Hostachys",
        },
        "Le plombier passe jeudi.",
        datetime(2026, 9, 3),
        authentification=_AUTH_OK,
    )
    assert decision == ACCEPTE
    evols = _evolutions(session, ticket)
    assert len(evols) == 1
    assert evols[0].auteur_id == syndic.id


def test_un_TIERS_ne_commente_pas_un_ticket_en_ecrivant_son_numero(scene):
    """🔴 Le prix du repli, et la raison pour laquelle il n'est pas gratuit.

    Le numéro figure dans tous les courriels déjà envoyés. Sans contrôle, tout
    titulaire de compte pourrait écrire sur n'importe quel dossier en le citant
    dans un sujet — un droit que l'écran ne donne pas.

    Ici l'expéditeur est authentifié, il a un compte, et il n'est **ni** l'auteur
    du ticket, **ni** du conseil syndical, **ni** le syndic : rien n'est écrit, et
    le conseil est prévenu.
    """
    session, ticket, _syndic, cs = scene
    tiers = compte(session, prefixe="voisin", prenom="V", nom="O", roles_json="résident")
    try:
        decision = traiter(
            session,
            {
                "From": tiers.email,
                "To": "noreply@5hostachy.fr",
                "Subject": f"Re: Ticket #{ticket.numero} — Fuite",
            },
            "Je confirme que c'est réglé.",
            datetime(2026, 9, 3),
            authentification=_AUTH_OK,
        )
        assert decision == REFUSE
        assert _evolutions(session, ticket) == []
        assert _notifs(session, cs), "le conseil syndical doit savoir qu'un message attend"
    finally:
        purger_ligne(session, Utilisateur, tiers.id)
        session.commit()


def test_un_message_USURPE_n_ecrit_RIEN_et_previent_le_conseil(scene):
    """🔴 Le scénario complet, de bout en bout.

    Quelqu'un se fait passer pour le syndic. Deux choses doivent arriver, et les
    deux comptent autant : **rien** dans le ticket, et **quelqu'un est prévenu**.
    Le silence est ce qui rend un filtre dangereux — un filtre qu'on n'entend
    jamais finit par être cru parfait.
    """
    session, ticket, syndic, cs = scene
    decision = traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
        "Le problème est réglé, fermez le ticket.",
        datetime(2026, 9, 3),
    )
    assert decision == REFUSE
    assert _evolutions(session, ticket) == [], "un message usurpé a été écrit dans le fil"
    notifs = _notifs(session, cs)
    assert notifs, "personne n'a été prévenu : le refus est silencieux"
    assert ticket.numero in notifs[0].titre
    #  Le corps doit porter la RAISON, pas seulement l'alerte : une notification
    #  qui dit « un message a été refusé » sans dire pourquoi renvoie le lecteur
    #  à la boîte pour comprendre, et il n'ira pas.
    assert syndic.email in notifs[0].corps
    assert "attribué avec certitude" in notifs[0].corps


def test_un_expediteur_authentifie_SANS_COMPTE_ne_signe_rien(scene):
    """`TicketEvolution.auteur_id` est obligatoire : pas de compte, pas d'entrée.

    L'alternative — un compte de service — ferait signer « 5Hostachy » un texte
    écrit par un tiers. Le conseil syndical est prévenu et recopie s'il veut.
    """
    session, ticket, _syndic, cs = scene
    decision = traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de="inconnu@syndic.fr"),
        "Bonjour, c'est noté.",
        datetime(2026, 9, 3),
        authentification=_AUTH_OK,
    )
    assert decision == REFUSE
    assert _evolutions(session, ticket) == []
    assert any("compte" in n.corps for n in _notifs(session, cs))


def test_un_jeton_FORGE_ne_touche_a_aucun_ticket(scene):
    """Deviner un jeton ne mène nulle part — et ne réveille personne.

    D'un INCONNU : d'un correspondant connu et authentifié, qui ne peut pas être
    forgé, le message attend d'être classé (#2555, `test_courriel_a_classer`).
    """
    session, ticket, _syndic, cs = scene
    decision = traiter(
        session,
        _entetes_reponse(nouveau_jeton(), de="inconnu@ailleurs.test"),
        "Fermez ce ticket.",
        datetime(2026, 9, 3),
        authentification=_AUTH_OK,
    )
    assert decision == IGNORE
    assert _evolutions(session, ticket) == []
    assert _notifs(session, cs) == [], "un jeton forgé ne doit pas produire de bruit"


def test_la_citation_du_message_precedent_n_entre_pas_dans_le_fil(scene):
    """Sans ça, chaque échange recopierait tout l'échange dans le ticket."""
    session, ticket, syndic, _cs = scene
    traiter(
        session,
        _entetes_reponse(ticket.jeton_courriel, de=syndic.email),
        "C'est noté.\n\nLe 2 septembre, Conseil syndical a écrit :\n> Bonjour,\n> merci de…",
        datetime(2026, 9, 3),
        authentification=_AUTH_OK,
    )
    evols = _evolutions(session, ticket)
    assert len(evols) == 1
    assert evols[0].contenu.endswith("<p>C'est noté.</p>")


# ── 🔴 La relance GROUPÉE : un envoi, N tickets, aucune réponse à ventiler ────


def test_une_reponse_a_une_relance_groupee_va_au_CONSEIL_et_dans_aucun_fil(scene):
    """🔴 La stratégie du 03/09/2026, éprouvée de bout en bout.

    Question posée : *« quelle stratégie si un retour de mail traite de plusieurs
    tickets relancés ? »*. Avant ce lot, la relance partait SANS `Reply-To` — un
    seul message pour N dossiers n'a pas de jeton de ticket — et la réponse du
    syndic était ignorée **en silence**. Le seul cas où l'on perdait une
    information qu'on avait soi-même sollicitée.

    Deux choses doivent arriver, et les deux comptent autant :

    - **rien dans les fils** : « pour le TK-123 on intervient jeudi, le TK-456 est
      clos » recopié dans quatre fils serait faux dans trois d'entre eux ;
    - **le conseil reçoit le texte ENTIER, avec la liste des dossiers** — il est
      déjà en copie de la relance, c'est le bon récepteur.
    """
    import json as _json

    session, ticket, syndic, cs = scene
    #  Un second ticket : une relance GROUPÉE en porte plusieurs, et le test ne
    #  distinguerait rien s'il n'y en avait qu'un.
    second = Ticket(
        numero=f"TK-{uuid.uuid4().hex[:6]}",
        titre="Autre",
        description="…",
        categorie="panne",
        auteur_id=cs.id,
        statut=StatutTicket.ouvert,
        jeton_courriel=nouveau_jeton(),
    )
    session.add(second)
    session.commit()
    session.refresh(second)
    vises = [ticket, second]
    relance = RelanceCourriel(
        jeton=nouveau_jeton(),
        tickets_json=_json.dumps([t.id for t in vises]),
    )
    session.add(relance)
    session.commit()

    decision = traiter(
        session,
        _entetes_reponse(relance.jeton, de=syndic.email),
        "Pour le premier on intervient jeudi ; le second est clos.",
        datetime(2026, 9, 3),
        authentification=_AUTH_OK,
    )
    try:
        #  RELANCE et non REFUSE (04/09/2026) : rien n'a été refusé — la
        #  réponse est reçue, conservée et notifiée, seulement pas ventilée.
        #  Le journal disait « refusées=1 » sur un traitement réussi.
        assert decision == RELANCE, "une réponse groupée ne s'écrit pas dans un fil"
        for t in vises:
            assert _evolutions(session, t) == [], (
                f"la réponse a été recopiée dans le fil de {t.numero} — elle parle "
                "de plusieurs dossiers, elle y serait fausse"
            )
        notifs = _notifs(session, cs)
        assert notifs, "personne n'a été prévenu : la réponse est perdue"
        corps = notifs[0].corps
        assert "intervient jeudi" in corps, "le texte du syndic n'est pas transmis"
        for t in vises:
            assert t.numero in corps, (
                "la notification ne dit pas quels dossiers étaient relancés — le "
                "conseil ne saurait pas où reporter"
            )
    finally:
        session.delete(relance)
        for evol in session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == second.id)
        ).all():
            session.delete(evol)
        session.delete(second)
        session.commit()


def test_un_message_authentifie_qui_repond_SANS_jeton_ne_se_perd_plus(scene):
    """Le second trou que la question a mis au jour.

    Un message authentifié qui cite une référence — donc qui répond visiblement à
    un envoi du site — mais qu'aucun jeton ne rattache était traité comme un
    prospectus : `IGNORE`, en silence. La règle qui évite de notifier le conseil
    pour chaque publicité était trop large, et elle avalait les vraies réponses :
    un fil transféré, un client qui réécrit le destinataire, une passerelle qui
    perd le `To`.

    Depuis #2555, il attend d'être classé par le conseil — rattaché, ou une
    affaire créée — au lieu d'un refus qui le perdait pour le site.
    """
    session, _ticket, syndic, cs = scene
    entetes = {
        "From": syndic.email,
        "To": "noreply@5hostachy.fr",
        "In-Reply-To": "<TK-000000.abc@5hostachy.fr>",
    }
    decision = traiter(
        session, entetes, "C'est noté.", datetime(2026, 9, 3), authentification=_AUTH_OK
    )
    assert decision == A_CLASSER
    notifs = _notifs(session, cs)
    assert notifs, "une réponse authentifiée non rattachable disparaît encore"
    assert "classé" in notifs[0].titre


def test_un_prospectus_ne_reveille_toujours_personne(scene):
    """La contrepartie, sans laquelle le remède serait pire que le mal.

    Si tout message non rattachable notifiait le conseil, la boîte deviendrait
    une source d'alertes sur des publicités — et le filtre finirait par ne plus
    être lu. Un message sans référence ET sans jeton reste ignoré.
    """
    session, _ticket, _syndic, cs = scene
    decision = traiter(
        session,
        {
            "From": "pub@ailleurs.fr",
            "To": "noreply@5hostachy.fr",
        },
        "Profitez de nos offres !",
        datetime(2026, 9, 3),
        authentification=_AUTH_OK,
    )
    assert decision == IGNORE
    assert _notifs(session, cs) == []


def test_le_syndic_peut_repondre_PLUSIEURS_FOIS_a_la_meme_relance(scene):
    """Signalé le 03/09/2026 : *« le syndic peut peut-être faire plusieurs mails »*.

    C'est le cas normal, pas l'exception : un message par dossier, ou une
    précision le lendemain. Le jeton ne s'épuise donc pas — il n'est ni consommé,
    ni daté, ni à usage unique.

    ⚠️ Et chaque réponse produit sa PROPRE notification. Dédoublonner serait le
    défaut inverse : la deuxième réponse est une information neuve, et la taire
    au motif qu'on a déjà prévenu ferait exactement ce que ce lot corrige —
    perdre une réponse qu'on a sollicitée.
    """
    import json as _json

    session, ticket, syndic, cs = scene
    relance = RelanceCourriel(jeton=nouveau_jeton(), tickets_json=_json.dumps([ticket.id]))
    session.add(relance)
    session.commit()
    try:
        for texte in ("Le premier point est réglé.", "Pour le second, on passe lundi."):
            assert (
                traiter(
                    session,
                    _entetes_reponse(relance.jeton, de=syndic.email),
                    texte,
                    datetime(2026, 9, 3),
                    authentification=_AUTH_OK,
                )
                == RELANCE
            )

        corps = [n.corps for n in _notifs(session, cs)]
        assert len(corps) == 2, (
            f"{len(corps)} notification(s) pour deux réponses : la seconde a été "
            "dédoublonnée, donc perdue"
        )
        assert any("réglé" in c for c in corps)
        assert any("lundi" in c for c in corps)
        assert _evolutions(session, ticket) == [], "toujours rien dans les fils"
    finally:
        session.delete(relance)
        session.commit()
