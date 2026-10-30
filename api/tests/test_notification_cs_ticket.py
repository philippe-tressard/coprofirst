"""Le conseil syndical est prévenu PAR COURRIEL d'un nouveau ticket (08/09/2026).

## Le défaut, vérifié à la demande

`_notifier_cs_creation` ne posait qu'une `Notification` **dans l'application**,
et sa docstring le disait en toutes lettres :

    \"\"\"Notification in-app à tout le CS, plus le syndic si le ticket est urgent.\"\"\"

Aucun courriel ne partait. Un conseiller qui n'ouvre pas le site ne voyait donc
jamais passer un signalement — au moment précis où quelqu'un attend une
réaction. Et la notification allait à **tout** le conseil, quel que soit le
bâtiment concerné.

## Les deux portées, et pourquoi elles diffèrent

- la notification **in-app** va à tout le CS : une liste se parcourt, et un
  conseiller peut vouloir un œil sur l'ensemble ;
- le **courriel** va au CS du **périmètre** du ticket. Ce qui est tolérable dans
  une liste ne l'est pas dans une boîte aux lettres.

C'est la distinction que le tableau « Destinataires CS » de `CLAUDE.md` porte
depuis le 31/08/2026, et que ce circuit n'appliquait pas.

⚠️ Ces tests regardent **qui est visé**, pas si `send_email_group` a été appelée.
Un test qui se contente de compter les appels passerait au vert sur un envoi
adressé au mauvais conseiller.
"""

from __future__ import annotations

import json

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models.core import MembreCS, Notification
from app.routers.tickets.arrivee import (
    _envoyer_email_cs_creation,
    _notifier_cs_creation,
)
from tests.aides_base import compte


class _Tampon:
    """Une `BackgroundTasks` de test — elle retient au lieu d'exécuter."""

    def __init__(self):
        self.taches = []

    def add_task(self, fonction, *args, **kwargs):
        self.taches.append((fonction, args, kwargs))


class _Ticket:
    """Le minimum qu'`_envoyer_email_cs_creation` lit d'un ticket."""

    def __init__(self, perimetre: list[str]):
        self.id = 1
        self.numero = 42
        self.titre = "Ferme-porte hors service"
        self.description = "Le ferme-porte du hall ne retient plus la porte."
        self.categorie = "panne"
        self.perimetre_cible = json.dumps(perimetre)
        self.jeton_courriel = None
        #  🔴 « Réservé au conseil syndical » — sur un ticket, la case est
        #  branchée sur cette colonne. Elle ne doit RIEN changer à l'envoi.
        self.confidentiel = False


@pytest.fixture()
def conseil(batiments):
    """Un conseiller par bâtiment, sur l'arbre réel des périmètres.

    ⚠️ La fixture `batiments` du `conftest` sème l'arborescence : les codes de
    périmètre viennent de l'ARBRE, pas d'un format `bat:<id>` inventé. Ma
    première rédaction en fabriquait un — `batiments_du_perimetre` rendait alors
    `None`, donc « tout le conseil », et le test passait au vert **en visant
    tout le monde**. C'est la forme la plus courante du faux vert : une donnée
    d'essai qui ne ressemble pas à la vraie.
    """
    from app.utils.perimetres import perimetre_du_batiment

    with Session(engine) as session:
        comptes, membres = [], []
        for suffixe, bat_id in (("a", batiments[0]), ("b", batiments[1])):
            u = compte(
                session,
                prefixe=f"cs-{suffixe}",
                prenom=f"C{suffixe.upper()}",
                nom="CONSEIL",
                roles_json="conseil_syndical",
            )
            membre = MembreCS(
                genre="mme",
                prenom=u.prenom,
                nom=u.nom,
                batiment_id=bat_id,
                user_id=u.id,
            )
            session.add(membre)
            comptes.append(u)
            membres.append(membre)
        session.commit()
        for u in comptes:
            session.refresh(u)

        noeud = perimetre_du_batiment(batiments[0])
        assert noeud is not None, "l'arbre ne connaît pas ce bâtiment — fixture cassée"

        yield session, batiments[0], noeud.code, comptes[0], comptes[1], comptes[0]

        for membre in membres:
            session.delete(membre)
        #  ⚠️ Les notifications AVANT les comptes : les clés sont vérifiées
        #  dans les tests (#546), et supprimer un compte qui en porte encore fait
        #  échouer le nettoyage — pas le test, ce qui le rend difficile à lire.
        for notif in session.exec(
            select(Notification).where(
                Notification.destinataire_id.in_([c.id for c in comptes])  # type: ignore
            )
        ).all():
            session.delete(notif)
        #  …et dans un flush À PART : entre deux tables sans `Relationship`,
        #  SQLAlchemy ordonne les DELETE d'un même flush par le nom qualifié de la
        #  classe. `core.Notification` passait avant `core.Utilisateur` par
        #  l'alphabet ; `notifications.Notification` passe après (#2316).
        session.flush()
        for u in comptes:
            session.delete(u)
        session.commit()


def test_le_CS_du_BATIMENT_concerne_est_vise(conseil):
    """🔴 Le cas qui motive tout : un courriel part, et il part au bon conseiller."""
    session, bat_id, code, cs_a, cs_b, auteur = conseil
    tampon = _Tampon()

    vises = _envoyer_email_cs_creation(
        session,
        _Ticket([code]),
        auteur,
        urgence=False,
        background_tasks=tampon,
    )

    assert cs_a.email in vises, (
        "le conseiller du bâtiment concerné n'est pas prévenu par courriel : "
        "un conseiller qui n'ouvre pas le site ne voit jamais passer le ticket."
    )
    assert cs_b.email not in vises, (
        "le conseiller d'un AUTRE bâtiment est prévenu. Ce qui est tolérable "
        "dans une liste ne l'est pas dans une boîte aux lettres."
    )
    assert tampon.taches, "aucun envoi n'a été programmé"
    _, _, kwargs = tampon.taches[0]
    assert kwargs["code"] == "ticket_nouveau_cs"


def test_un_perimetre_GLOBAL_vise_tout_le_conseil(conseil):
    """Un ticket qui concerne la résidence entière n'a pas de bâtiment à cibler.

    ⚠️ `batiments_du_perimetre` rend alors `None`, et `membres_cs_notifiables`
    lit ce `None` comme « tout le conseil ». Sans ce test, un resserrement futur
    du ciblage rendrait muets les tickets les plus généraux — le pire endroit où
    se tromper, et le plus discret.
    """
    session, bat_id, code, cs_a, cs_b, auteur = conseil
    tampon = _Tampon()

    vises = _envoyer_email_cs_creation(
        session,
        _Ticket([]),
        auteur,
        urgence=False,
        background_tasks=tampon,
    )

    assert cs_a.email in vises and cs_b.email in vises, (
        f"un ticket sans périmètre ne vise pas tout le conseil : {vises}"
    )


def test_la_PREFERENCE_est_laissee_a_send_email_group(conseil):
    """🔴 `batiments_concernes` est passé — c'est CE paramètre qui l'applique.

    La préférence « e-mails de mon bâtiment / des autres » est vérifiée
    destinataire par destinataire par `send_email_group`. La relire ici ferait
    une seconde façon d'être en désaccord avec ce que le résident a demandé
    (`utils/preferences_mail`, dont l'en-tête raconte les trois copies
    précédentes).

    Ce test ne vérifie donc pas le filtrage : il vérifie qu'on **passe la main**.
    """
    session, bat_id, code, _, _, auteur = conseil
    tampon = _Tampon()

    _envoyer_email_cs_creation(
        session,
        _Ticket([code]),
        auteur,
        urgence=False,
        background_tasks=tampon,
    )

    _, _, kwargs = tampon.taches[0]
    assert kwargs.get("batiments_concernes") == {bat_id}, (
        "sans `batiments_concernes`, la préférence de chacun n'est pas "
        "appliquée : le courriel part à qui l'a refusé."
    )


def test_le_CONFIDENTIEL_ne_change_rien_a_l_envoi(conseil):
    """🔴 Ce test tient un TEXTE autant qu'un comportement (#1147, 22/09/2026).

    Signalé à l'écran : *« la Visibilité réservée au conseil syndical sans
    Diffusion envoie une diffusion au CS : c'est anormal ! »*

    Le comportement est juste — le courriel vient de la CRÉATION du ticket, pas
    de la case — mais l'aide de l'option annonçait *« aucun envoi n'est
    déclenché »*, ce qui a fait conclure à une anomalie. Les textes ont été
    réécrits ; ce test **les attache au comportement**.

    ⚠️ Le jour où quelqu'un conditionnera l'envoi à `confidentiel` — ce qui est
    une décision défendable — il échouera, et c'est exactement ce qu'on veut :
    la correction devra passer par les textes, pas seulement par le code.
    """
    session, _, code, _, _, auteur = conseil

    ouvert = _Ticket([code])
    reserve = _Ticket([code])
    reserve.confidentiel = True

    vises = {}
    for nom, ticket in (("ouvert", ouvert), ("reserve", reserve)):
        tampon = _Tampon()
        _envoyer_email_cs_creation(
            session,
            ticket,
            auteur,
            urgence=False,
            background_tasks=tampon,
        )
        vises[nom] = sorted(
            email for _, email in (tampon.taches[0][2]["to_recipients"] if tampon.taches else [])
        )

    assert vises["reserve"] == vises["ouvert"], (
        "« Réservé au conseil syndical » change les destinataires du courriel de "
        "création. C'est peut-être voulu — mais alors l'aide de l'option et la "
        "section Diffusion doivent le dire, et elles ne le disent pas."
        f"ouvert={vises['ouvert']}  réservé={vises['reserve']}"
    )
    assert vises["ouvert"], "le cas zéro : sans destinataire, le test ne compare rien"


def test_cas_zero_sans_conseil_aucun_envoi(conseil):
    """Un envoi programmé sans destinataire encombrerait l'historique pour rien."""
    session, bat_id, code, _, _, auteur = conseil
    for membre in session.exec(select(MembreCS)).all():
        session.delete(membre)
    session.commit()
    tampon = _Tampon()

    vises = _envoyer_email_cs_creation(
        session,
        _Ticket([code]),
        auteur,
        urgence=False,
        background_tasks=tampon,
    )

    assert vises == []
    assert tampon.taches == [], "un envoi a été programmé sans aucun destinataire"


def test_l_urgence_atteint_le_modele(conseil):
    """`urgent` conditionne le liseré rouge et la mention URGENT dans le corps.

    ⚠️ Jinja évalue une variable indéfinie à **faux sans rien signaler** : un
    `urgent` non fourni ferait disparaître la mention en silence. C'est le défaut
    qui a motivé `test_email_templates.EXPECTED_VARS`, et il se vérifie ici au
    point d'appel — l'endroit où la variable est réellement fournie.
    """
    session, bat_id, code, _, _, auteur = conseil
    tampon = _Tampon()

    _envoyer_email_cs_creation(
        session,
        _Ticket([code]),
        auteur,
        urgence=True,
        background_tasks=tampon,
    )

    _, _, kwargs = tampon.taches[0]
    contexte = kwargs["context"]
    assert contexte["urgent"] is True
    assert set(contexte) >= {"ticket", "auteur", "urgent"}, (
        f"le contexte ne fournit pas ce que le modèle interroge : {sorted(contexte)}"
    )


def test_le_point_d_APPEL_declenche_bien_le_courriel(conseil):
    """🔴 Le tuyau, pas seulement la décision.

    Les tests ci-dessus appellent `_envoyer_email_cs_creation` directement. J'ai
    neutralisé son appel dans `_notifier_cs_creation` pour éprouver le cas zéro :
    **ils sont tous restés verts**. Le courriel aurait cessé de partir sans qu'un
    seul test ne bouge.

    C'est la leçon du 06/09/2026 — *« je testais la décision, pas le tuyau qui la
    nourrit »* — et elle se rejouait ici, dans le fichier même qui corrige un
    envoi manquant.
    """
    session, _, code, cs_a, _, auteur = conseil
    ticket = _Ticket([code])
    ticket.description = "Le ferme-porte du hall ne retient plus la porte."
    tampon = _Tampon()

    _notifier_cs_creation(
        session,
        ticket,
        urgence=False,
        auteur=auteur,
        background_tasks=tampon,
    )

    codes = [kwargs.get("code") for _, _, kwargs in tampon.taches]
    assert "ticket_nouveau_cs" in codes, (
        "le point d'appel ne programme aucun courriel : la fonction d'envoi peut "
        f"être parfaite, personne ne la lira. Tâches programmées : {codes}"
    )


def test_sans_tache_de_fond_aucun_courriel_n_est_PRETENDU(conseil):
    """Un appelant qui ne fournit pas de `BackgroundTasks` n'envoie rien.

    ⚠️ Et il ne doit pas lever : la notification in-app, elle, doit passer. Le
    courriel est un ajout, pas une condition — un appelant historique qui n'a pas
    été mis à jour continue de prévenir le conseil dans l'application.
    """
    session, _, code, _, _, auteur = conseil
    _notifier_cs_creation(session, _Ticket([code]), urgence=False)


# ── La Diffusion du conseil est RESPECTÉE (03/10/2026) ───────────────────────
#
#  Signalé à l'écran sur TK-264069, une affaire créée par un membre du conseil sans
#  cocher « Conseil syndical » : quatre conseillers ont reçu « Nouvelle affaire ».
#  *« Si CS n'est pas sélectionné, il ne doit pas envoyer au CS. »* Un résident, lui,
#  n'a aucune case : le conseil est toujours prévenu.


def _creer_affaire(session, auteur, code, **champs):
    from fastapi import BackgroundTasks

    from app.models.core import Ticket
    from app.routers.tickets import crud
    from app.schemas import TicketCreate

    taches = BackgroundTasks()
    corps = TicketCreate(
        titre="Bruit",
        description="Musique tard.",
        categorie="panne",
        perimetre_cible=[code],
        **champs,
    )
    lu = crud.create_ticket(corps, taches, session=session, user=auteur)
    codes = [t.kwargs.get("code") for t in taches.tasks]
    session.delete(session.get(Ticket, lu.id))
    session.commit()
    return codes


def test_un_membre_du_conseil_sans_la_case_CS_ne_previent_pas_le_conseil_par_courriel(conseil):
    session, _, code, _, _, cs = conseil
    codes = _creer_affaire(session, cs, code, destinataire_cs=False)
    assert "ticket_nouveau_cs" not in codes, (
        "le conseil a été prévenu par courriel alors que « Conseil syndical » n'était pas coché "
        f"dans la Diffusion : {codes}"
    )
    assert "ticket_syndic" not in codes


def test_avec_la_case_CS_le_conseil_recoit_UN_courriel_pas_deux(conseil):
    session, _, code, _, _, cs = conseil
    codes = _creer_affaire(session, cs, code, destinataire_cs=True)
    assert codes.count("ticket_syndic") == 1
    assert "ticket_nouveau_cs" not in codes, (
        "deux courriels pour un même fait (« jamais deux fois »)"
    )


def test_un_resident_n_a_pas_de_case_le_conseil_est_toujours_prevenu(conseil):
    session, _, code, _, _, _ = conseil
    resident = compte(session, prefixe="res-cs", roles_json="résident")
    try:
        codes = _creer_affaire(session, resident, code)
        assert "ticket_nouveau_cs" in codes
    finally:
        session.delete(resident)
        session.commit()
