"""Cocher « Nouvel arrivant » ouvre un ticket de SUIVI (#821).

## Le cas concret qui a produit ce fichier (07/09/2026)

> *« J'ai l'exemple concret où le syndic n'a rien fait depuis deux semaines et le
> locataire a créé lui-même un ticket. »*

Le parcours d'accueil envoyait une notification au conseil et un e-mail au
syndic — **et rien d'autre**. Aucun de ces deux messages ne se suit : la
notification quitte la pile après lecture, l'e-mail tombe dans une boîte, le
résident n'a aucune trace, et personne ne voit que ça traîne.

🔴 C'est `standards/04` §14 pris à l'envers : *observer la chose, pas son
enregistrement*. Le message parti est l'enregistrement ; la démarche faite est la
chose. Rien ne mesurait la chose.

⚠️ Ce fichier vérifie le **fait en base** — un ticket existe, avec ses
destinataires et son bénéficiaire — et non le code de retour de l'endpoint.
Un `{"ok": true}` ne dit pas qu'un ticket a été créé.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Batiment,
    Copropriete,
    MembreCS,
    MembreSyndic,
    Notification,
    RoleUtilisateur,
    StatutUtilisateur,
    Ticket,
    Utilisateur,
)
from app.routers.admin.arrivants import AccueilArrivantBody, _declencher_accueil_arrivant
from app.utils.ticket_arrivant import TITRE, corps_demarches
from tests.aides_base import compte
from tests.aides_purge import purger_ligne


@pytest.fixture()
def arrivant() -> Utilisateur:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        u = compte(
            session,
            prefixe="arrivant",
            prenom="Alix",
            nom="Mercier",
            role=RoleUtilisateur.résident,
            statut=StatutUtilisateur.locataire,
        )
        yield u
        session.rollback()
        for tk in session.exec(select(Ticket).where(Ticket.saisi_pour_user_id == u.id)).all():
            purger_ligne(session, Ticket, tk.id)
        for n in session.exec(
            select(Notification).where(Notification.destinataire_id == u.id)
        ).all():
            session.delete(n)
        session.commit()
        purger_ligne(session, Utilisateur, u.id)
        session.commit()


def _accueillir(session: Session, u: Utilisateur, **kw):
    return _declencher_accueil_arrivant(
        u, AccueilArrivantBody(**kw), BackgroundTasks(), session, allow_repeat=True
    )


def _ticket(session: Session, user_id: int) -> Ticket | None:
    return session.exec(
        select(Ticket).where(Ticket.saisi_pour_user_id == user_id, Ticket.titre == TITRE)
    ).first()


def test_l_accueil_ouvre_un_ticket_de_suivi(arrivant):
    """Le fait, pas le code de retour : le ticket existe-t-il en base ?"""
    with Session(engine) as session:
        u = session.get(Utilisateur, arrivant.id)
        retour = _accueillir(session, u, batiment="Bât. A", ancien_resident="M. Ancien")

        tk = _ticket(session, u.id)
        assert tk is not None, (
            "Cocher « Nouvel arrivant » doit ouvrir un ticket de suivi. Sans lui, "
            "les démarches n'ont ni statut, ni relance, ni visibilité pour celui "
            "qui attend — c'est le cas signalé le 07/09/2026."
        )
        assert tk.categorie == "acces_accueil", tk.categorie
        assert tk.statut == "ouvert"
        assert retour["ticket_suivi"] == tk.numero


def test_l_ARRIVANT_voit_son_propre_ticket(arrivant):
    """🔴 Sans `saisi_pour_user_id`, on reproduirait le défaut sous une autre forme.

    Un objet de suivi que l'intéressé ne voit pas ne vaut pas mieux qu'une
    notification qu'il a lue une fois : dans les deux cas il ne sait pas où ça en
    est, et c'est ce qui l'a poussé à ouvrir un ticket lui-même.
    """
    with Session(engine) as session:
        u = session.get(Utilisateur, arrivant.id)
        _accueillir(session, u, batiment="Bât. A")
        tk = _ticket(session, u.id)
        assert tk.saisi_pour_user_id == u.id
        assert tk.auteur_id == u.id


def test_le_ticket_vise_les_destinataires_des_DEUX_demarches(arrivant):
    """Un seul ticket, deux destinataires — c'est la raison de n'en faire qu'un.

    Le syndic pose l'étiquette de boîte aux lettres, le conseil ajoute le nom sur
    l'interphone. Un ticket qui n'en viserait qu'un laisserait l'autre démarche
    sans destinataire, ce qui est le défaut d'origine appliqué à moitié.
    """
    with Session(engine) as session:
        u = session.get(Utilisateur, arrivant.id)
        #  🔴 Le RATTACHEMENT compte : le parcours d'accueil choisit les membres du
        #  conseil par `batiment_id`. Sans lui, aucun CS n'est trouvé — voir le
        #  test suivant, qui documente ce cas et sa conséquence.
        copro = Copropriete(nom=f"Copro-{uuid.uuid4().hex[:4]}", adresse="1 rue Test")
        session.add(copro)
        session.commit()
        bat = Batiment(numero=uuid.uuid4().hex[:3], copropriete_id=copro.id)
        session.add(bat)
        session.commit()
        session.refresh(bat)
        u.batiment_id = bat.id

        syndic = MembreSyndic(
            genre="mr", nom="Syndic", prenom="Le", email="syndic@exemple.test", est_principal=True
        )
        session.add(syndic)
        #  INACTIF, comme le compte que ce test créait avant #1495 : actif, il
        #  deviendrait notifiable, les consignes partiraient au conseil ET au
        #  résident, et le ticket ne viserait plus ni le syndic ni le conseil —
        #  ce n'est pas ce cas-là que ce test éprouve.
        membre_cs = compte(
            session,
            prefixe="cs",
            prenom="Camille",
            nom="Sorel",
            role=RoleUtilisateur.conseil_syndical,
            actif=False,
        )
        mc = MembreCS(
            user_id=membre_cs.id, genre="mme", nom="Sorel", prenom="Camille", batiment_id=bat.id
        )
        session.add(mc)
        session.commit()

        _accueillir(session, u, batiment=f"Bât. {bat.numero}")
        tk = _ticket(session, u.id)
        assert tk.destinataire_syndic is True, "l'étiquette de BAL revient au syndic"
        assert tk.destinataire_cs is True, "l'interphone revient au conseil"

        for n in session.exec(
            select(Notification).where(Notification.destinataire_id == membre_cs.id)
        ).all():
            session.delete(n)
        tk.batiment_id = None
        u.batiment_id = None
        session.commit()
        purger_ligne(session, MembreCS, mc.id)
        purger_ligne(session, Utilisateur, membre_cs.id)
        purger_ligne(session, MembreSyndic, syndic.id)
        purger_ligne(session, Batiment, bat.id)
        purger_ligne(session, Copropriete, copro.id)
        session.commit()


def test_un_arrivant_SANS_batiment_ne_vise_pas_le_conseil(arrivant):
    """🔴 Un comportement EXISTANT, mis au jour par le ticket — et il compte.

    Le parcours d'accueil choisit les membres du conseil par le `batiment_id` de
    l'arrivant. Quand ce champ est vide — et il l'est tant que personne n'a
    rattaché le compte à un bâtiment — **aucun membre du conseil n'est trouvé** :
    ni notification, ni destinataire sur le ticket. Seul le syndic reste visé.

    Ce n'est pas introduit ici, c'est révélé : la notification interphone
    n'était déjà envoyée à personne dans ce cas, sans que rien ne le dise. Le
    ticket, lui, le rend VISIBLE — il apparaît dans la liste avec le conseil
    non destinataire, et quelqu'un peut le corriger.

    ⚠️ Ce test fige le comportement d'aujourd'hui, il ne l'approuve pas. Le
    remède serait de refuser l'accueil d'un compte sans bâtiment, ou de replier
    sur le conseil entier — deux décisions qui ne sont pas les miennes.
    """
    with Session(engine) as session:
        u = session.get(Utilisateur, arrivant.id)
        assert u.batiment_id is None
        _accueillir(session, u, batiment="Bât. A")
        tk = _ticket(session, u.id)
        assert tk.destinataire_cs is False, (
            "Sans rattachement, le parcours ne trouve aucun membre du conseil."
        )


def test_relancer_l_accueil_ne_cree_PAS_un_second_ticket(arrivant):
    """Le cas zéro de la garde anti-doublon.

    `accueil-arrivant` est rejouable par un membre du conseil
    (`allow_repeat=True`). Sans garde, relancer l'accueil ouvrirait un second
    ticket en silence, et le premier resterait ouvert à côté — deux lignes pour
    une même démarche, dont une que personne ne fermera.
    """
    with Session(engine) as session:
        u = session.get(Utilisateur, arrivant.id)
        _accueillir(session, u, batiment="Bât. A")
        premier = _ticket(session, u.id).numero

        retour = _accueillir(session, u, batiment="Bât. A")

        tous = session.exec(
            select(Ticket).where(Ticket.saisi_pour_user_id == u.id, Ticket.titre == TITRE)
        ).all()
        assert len(tous) == 1, f"{len(tous)} tickets pour un seul emménagement"
        assert tous[0].numero == premier
        assert retour["ticket_suivi"] is None, (
            "Le second appel ne doit pas annoncer un ticket qu'il n'a pas créé."
        )


def test_la_description_ECHAPPE_ce_que_l_utilisateur_a_saisi():
    """Le nom de l'ancien résident est saisi librement, et rendu en HTML.

    La description d'un ticket passe par un assainisseur côté front, mais la
    règle du projet est d'échapper à l'écriture ET d'assainir à la lecture : une
    seule des deux barrières laisse passer le jour où l'autre change.
    """
    corps = corps_demarches(
        "Alix Mercier",
        "Bât. <script>",
        '"><img src=x onerror=alert(1)>',
        ["• Étiquette BAL"],
    )
    assert "<script>" not in corps, corps
    assert "onerror" not in corps or "&lt;img" in corps, corps
    assert "&lt;script&gt;" in corps


def test_l_arrivant_ne_rejoue_pas_sa_demarche_en_effacant_sa_notification(arrivant):
    """#2163 : la garde lisait une notification que son destinataire peut supprimer.

    Supprimée, la démarche se redéclenchait : courriels au syndic et au conseil,
    notifications au conseil, à nouveau. L'affaire de suivi, elle, n'est pas à lui.
    """
    from fastapi import HTTPException

    with Session(engine) as session:
        u = session.get(Utilisateur, arrivant.id)
        _declencher_accueil_arrivant(
            u, AccueilArrivantBody(batiment="Bât. A"), BackgroundTasks(), session
        )
        for n in session.exec(select(Notification).where(Notification.destinataire_id == u.id)):
            session.delete(n)
        session.commit()
        taches = BackgroundTasks()
        with pytest.raises(HTTPException) as refus:
            _declencher_accueil_arrivant(u, AccueilArrivantBody(batiment="Bât. A"), taches, session)
        assert refus.value.status_code == 409
        assert taches.tasks == [], "un second envoi a été programmé"
