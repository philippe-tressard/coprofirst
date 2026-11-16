r"""Répondre à un ticket par courriel — la décision, éprouvée sur des messages forgés.

## 🔴 Ce que ce fichier protège (#703)

**SMTP n'authentifie pas l'expéditeur.** N'importe qui peut écrire à
`noreply@5hostachy.fr` en mettant l'adresse du syndic dans le `From:`. Sans
vérification, son message deviendrait un commentaire officiel sur un ticket,
visible des résidents, **signé du syndic**.

C'est le seul endroit du site où un texte venu de l'extérieur, écrit par un
inconnu, peut atterrir dans une donnée que d'autres liront comme officielle. La
moitié des cas ci-dessous sont donc des messages **hostiles** : c'est la seule
manière de vérifier un filtre.

## Pourquoi la décision est PURE, et testée ici sans IMAP

`courriel_ingestion.examiner` ne touche ni au réseau ni à la base : elle reçoit
des en-têtes et rend un verdict. On peut donc lui présenter le message qu'on
veut, y compris ceux qu'aucune boîte réelle ne produirait.

Le dépôt a payé l'inverse : *« je testais la décision, pas le tuyau qui la
nourrit »* (check-reliability, 11/08/2026). Ici les deux sont séparés — et
`traiter()` est éprouvée en base, sans IMAP non plus.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.utils.courriel_entrant import jeton_dans, nouveau_jeton
from app.utils.courriel_ingestion import ACCEPTE, IGNORE, REFUSE, examiner
from tests.aides_courriel import _AUTH_OK, _adresse_a_jeton, _entetes_reponse


# ── Le jeton ──────────────────────────────────────────────────────────────────


def test_deux_jetons_ne_se_ressemblent_pas():
    """Un jeton dérivé de l'identifiant se devinerait ; celui-ci se tire au sort.

    Vérifié sur un lot, pas sur deux : deux tirages identiques par malchance sont
    improbables, mais un générateur cassé rendrait la même valeur à chaque appel
    et deux comparaisons suffiraient à le manquer une fois sur deux.
    """
    jetons = {nouveau_jeton() for _ in range(200)}
    assert len(jetons) == 200
    assert all(len(j) == 32 and all(c in "0123456789abcdef" for c in j) for j in jetons)


def test_le_jeton_se_relit_dans_les_en_tetes_qui_le_portent():
    jeton = nouveau_jeton()
    adresse = _adresse_a_jeton(jeton)
    assert jeton_dans(adresse) == jeton
    assert jeton_dans(f"Conseil syndical <{adresse.upper()}>") == jeton
    assert jeton_dans(None, "", "autre@ailleurs.test") is None
    #  Une adresse trop courte n'est pas un jeton tronqué acceptable.
    assert jeton_dans("tickets+abc@5hostachy.fr") is None


# ── 🔴 L'authentification ─────────────────────────────────────────────────────


def test_un_message_authentifie_est_accepte():
    v = examiner(
        _entetes_reponse(nouveau_jeton()), recu_le=datetime(2026, 9, 3), authentification=_AUTH_OK
    )
    assert v.decision == ACCEPTE


@pytest.mark.parametrize(
    "authentification, cas",
    [
        (None, "aucune vérification"),
        ((False, "le message ne porte aucune signature DKIM"), "non signé"),
        ((False, "le message est signé par autre.test, et non par syndic.test"), "non aligné"),
    ],
)
def test_un_message_NON_authentifie_est_refuse(authentification, cas):
    """🔴 Le cœur du fichier — un message non authentifié ne s'écrit jamais.

    Le cas `None` est le plus important et le moins évident : un message qu'on
    n'a pas vérifié n'a pas *échoué*, il est **invérifié**. Le traiter comme un
    succès reviendrait à faire confiance à tout message dont la vérification
    n'aurait simplement pas eu lieu.
    """
    v = examiner(
        _entetes_reponse(nouveau_jeton()),
        recu_le=datetime(2026, 9, 3),
        authentification=authentification,
    )
    assert v.decision == REFUSE, f"accepté alors que {cas}"
    assert v.motif, "un refus sans motif est un silence"


@pytest.mark.parametrize(
    "entete",
    [
        "mx.ovh.net; spf=pass smtp.mailfrom=syndic.test; dkim=pass; dmarc=pass",
        "5hostachy.fr; spf=pass; dkim=pass; dmarc=pass",
    ],
)
def test_un_Authentication_Results_ECRIT_PAR_L_EXPEDITEUR_ne_prouve_rien(entete):
    """🔴 Le trou fermé le 28/09/2026.

    Le contrôle lisait `Authentication-Results` dans le message. OVH ne pose pas
    cet en-tête : celui qu'on trouvait, c'est l'expéditeur qui l'avait écrit — et
    un usurpateur n'avait qu'à écrire « pass » trois fois. Aucun en-tête, quel
    qu'il soit, ne tient lieu de vérification.
    """
    entetes = {**_entetes_reponse(nouveau_jeton()), "Authentication-Results": entete}
    v = examiner(entetes, recu_le=datetime(2026, 9, 3))
    assert v.decision == REFUSE, "un en-tête écrit par l'expéditeur a été cru"


def test_un_message_sans_rapport_est_IGNORE_et_non_refuse():
    """La nuance qui évite de noyer le conseil syndical.

    Un prospectus arrivé dans la boîte n'est pas une tentative d'usurpation :
    le confondre avec un refus produirait une notification par publicité reçue,
    et le filtre deviendrait lui-même la nuisance. On finirait par ne plus le lire.
    """
    v = examiner(
        {"From": "pub@ailleurs.test", "To": "noreply@5hostachy.fr"}, recu_le=datetime(2026, 9, 3)
    )
    assert v.decision == IGNORE


def test_le_sujet_rattache_en_REPLI_quand_le_jeton_manque():
    """🔴 REVIREMENT du 05/09/2026 — et il a une raison, pas une lassitude.

    Ce test disait l'inverse : « le sujet ne rattache JAMAIS un ticket », parce
    qu'un sujet se réécrit et se falsifie. Le raisonnement était bon, sur une
    hypothèse fausse — *que l'adresse à jeton achemine*. Elle n'achemine pas :
    *« cette adresse pour le suivi du syndic ne semble pas marcher »*.

    Une voie sûre qui ne transporte rien ne protège personne : elle perd la
    réponse du syndic, en silence. Le sujet devient donc un REPLI — jamais le
    premier choix (voir le test suivant), et payé par un contrôle que le jeton
    n'exigeait pas (`correspondant_du_ticket`).
    """
    v = examiner(
        {
            "From": "gestion@syndic.test",
            "To": "noreply@5hostachy.fr",
            "Subject": "Re: Ticket #TK-482910 — Fuite au 3e",
        },
        recu_le=datetime(2026, 9, 3),
        authentification=_AUTH_OK,
    )
    assert v.decision == ACCEPTE
    assert v.numero == "TK-482910"
    assert v.jeton is None


def test_le_jeton_PRIME_toujours_sur_le_sujet():
    """L'adresse prouve, le sujet désigne : le second ne doit jamais l'emporter.

    Un fil transféré porte souvent l'ancien sujet et la nouvelle adresse. Lire
    les deux ferait dépendre le rattachement de l'ordre des tests.
    """
    jeton = nouveau_jeton()
    v = examiner(
        {
            "From": "gestion@syndic.test",
            "To": f"tickets+{jeton}@5hostachy.fr",
            "Subject": "Re: Ticket #TK-000001 — un AUTRE dossier",
        },
        recu_le=datetime(2026, 9, 3),
        authentification=_AUTH_OK,
    )
    assert v.jeton == jeton
    assert v.numero is None, "le sujet ne doit même pas être lu quand le jeton est là"


def test_un_numero_sans_le_mot_ticket_ne_rattache_rien():
    """Le motif exige « Ticket » devant : sinon une référence quelconque —
    facture, commande, lot — rattacherait un message au hasard.
    """
    v = examiner(
        {
            "From": "quelquun@ailleurs.test",
            "To": "noreply@5hostachy.fr",
            "Subject": "Re: votre facture TK-482910",
        },
        recu_le=datetime(2026, 9, 3),
        authentification=_AUTH_OK,
    )
    assert v.decision == IGNORE


# ── La date plancher ──────────────────────────────────────────────────────────


def test_les_messages_anterieurs_au_2_septembre_sont_ignores():
    """Arbitrage du 02/09/2026 : sans plancher, la première relève déverserait
    des mois d'archives dans les tickets.
    """
    v = examiner(
        _entetes_reponse(nouveau_jeton()), recu_le=datetime(2026, 8, 31), authentification=_AUTH_OK
    )
    assert v.decision == IGNORE
    v = examiner(
        _entetes_reponse(nouveau_jeton()),
        recu_le=datetime(2026, 9, 2, 0, 1),
        authentification=_AUTH_OK,
    )
    assert v.decision == ACCEPTE


def test_la_date_est_examinee_AVANT_le_reste():
    """Un vieux message NON authentifié ne doit pas notifier le conseil syndical.

    Si l'ordre était inversé, la première relève d'une boîte de plusieurs mois
    produirait une notification par ancien message douteux — un réveil brutal
    pour une fonction qu'on vient d'activer.
    """
    v = examiner(_entetes_reponse(nouveau_jeton()), recu_le=datetime(2026, 1, 1))
    assert v.decision == IGNORE


# ── #1168 : le repli reconnaît NOS sujets, tels que les modèles les écrivent ──
#
#  🔴 Le motif exigeait « Ticket » ; depuis v2.10.4 (#1137) les modèles disent
#  « Affaire #TK-… ». Une réponse du syndic hors adresse à jeton — le cas courant —
#  ne se rattachait plus, et aucun test ne le voyait : ils éprouvaient le motif
#  sur des sujets RECOPIÉS dans le test, qui disaient encore « Ticket ».
#  Celui-ci rend les sujets des modèles semés : un renommage futur les suivra.


def _sujets_a_numero() -> list[tuple[str, str]]:
    from jinja2 import ChainableUndefined, Environment

    from app.seed.emails import EMAIL_TEMPLATES

    env = Environment(undefined=ChainableUndefined)
    rendus = []
    for code, _libelle, sujet, *_ in EMAIL_TEMPLATES:
        if "ticket.numero" in sujet:
            rendus.append(
                (
                    code,
                    env.from_string(sujet).render(
                        ticket={"numero": "TK-482910", "titre": "Fuite au 3e"},
                        residence={"nom": "Les Hostachys"},
                    ),
                )
            )
    return rendus


def test_le_repli_reconnait_chaque_sujet_que_nous_envoyons():
    from app.utils.courriel_entrant import numero_dans_sujet

    rendus = _sujets_a_numero()
    #  Cas zéro : sans sujet à numéro, ce test serait vert sans rien avoir lu.
    assert len(rendus) >= 3, f"Seulement {len(rendus)} modèle(s) à numéro relevé(s)."
    manques = [
        f"{code} : « Re: {sujet} »"
        for code, sujet in rendus
        if numero_dans_sujet(f"Re: {sujet}") != "TK-482910"
    ]
    assert not manques, "Le repli par sujet ne reconnaît pas :\n  " + "\n  ".join(manques)


def test_un_ancien_sujet_ticket_reste_reconnu():
    """Les courriels déjà partis disent « Ticket #TK-… » : on y répond encore."""
    from app.utils.courriel_entrant import numero_dans_sujet

    assert numero_dans_sujet("Re: Ticket #TK-482910 — Fuite") == "TK-482910"
    assert numero_dans_sujet("Re: votre facture TK-482910") is None
