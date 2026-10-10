"""Supprimer un compte laisse ses affaires — l'auteur devient « Ancien résident » (#1688).

Le défaut, rejoué : `supprimer_compte` passe par la purge référentielle, qui
SUPPRIME toute ligne dont la référence au compte est obligatoire. L'auteur d'une
affaire, de son fil et de ses messages l'était : un résident qui avait signalé
une panne emportait l'affaire, les réponses des autres et l'entrée du carnet
d'entretien — par la suppression de l'administrateur aujourd'hui, par la purge
des comptes inactifs demain. Arbitrage du 10/10/2026 : le contenu COLLECTIF
reste, sans nom ; ce qui n'appartient qu'à la personne part avec elle.

La décision tient dans le modèle : une référence FACULTATIVE est déliée par la
purge au lieu d'emporter la ligne. Le test le vérifie par le geste réel.
"""

from __future__ import annotations

from sqlmodel import select

from app.models.core import RoleUtilisateur, Ticket, TicketEvolution, Utilisateur
from app.models.tickets import MessageTicket
from app.routers.tickets.commun import evol_read, ticket_read
from app.utils.noms import ANCIEN_RESIDENT
from app.utils.suppression_compte import supprimer_compte
from tests.aides_affaire import _compte, _corriger, _creer, _suite, session  # noqa: F401


def test_l_affaire_de_l_auteur_supprime_reste_et_son_fil_aussi(session):  # noqa: F811
    auteur = _compte(session)
    conseil = _compte(session, role=RoleUtilisateur.conseil_syndical)
    affaire = _creer(session, auteur, categorie="panne")
    _suite(session, auteur, affaire.id, contenu="<p>L'ascenseur s'arrête au 3ᵉ.</p>")
    _suite(session, conseil, affaire.id, contenu="<p>Le prestataire passe jeudi.</p>")
    session.add(MessageTicket(ticket_id=affaire.id, auteur_id=auteur.id, contenu="Merci."))
    session.add(MessageTicket(ticket_id=affaire.id, auteur_id=conseil.id, contenu="Noté."))
    session.commit()
    auteur_id, affaire_id = auteur.id, affaire.id

    supprimer_compte(session, auteur_id)
    session.commit()
    session.expire_all()

    assert session.get(Utilisateur, auteur_id) is None
    restee = session.get(Ticket, affaire_id)
    assert restee is not None, "l'affaire est partie avec le compte de son auteur"
    assert restee.auteur_id is None

    fil = session.exec(select(TicketEvolution).where(TicketEvolution.ticket_id == affaire_id)).all()
    contenus = {e.contenu: e.auteur_id for e in fil}
    assert contenus["<p>L'ascenseur s'arrête au 3ᵉ.</p>"] is None
    assert contenus["<p>Le prestataire passe jeudi.</p>"] == conseil.id

    messages = session.exec(
        select(MessageTicket).where(MessageTicket.ticket_id == affaire_id)
    ).all()
    assert {m.contenu: m.auteur_id for m in messages} == {"Merci.": None, "Noté.": conseil.id}

    #  …et l'écran le dit, sans nom ni « ? ».
    assert ticket_read(restee, session, conseil).auteur_nom == ANCIEN_RESIDENT
    anonyme = next(e for e in fil if e.auteur_id is None)
    assert evol_read(anonyme, session).auteur_nom == ANCIEN_RESIDENT


def test_l_affaire_anonyme_avance_encore(session):  # noqa: F811
    """Le conseil la fait avancer : « prévenir l'auteur » n'a plus personne à prévenir."""
    auteur = _compte(session)
    conseil = _compte(session, role=RoleUtilisateur.conseil_syndical)
    affaire = _creer(session, auteur, categorie="panne")
    affaire_id = affaire.id
    supprimer_compte(session, auteur.id)
    session.commit()

    _suite(session, conseil, affaire_id, type="etat", nouveau_statut="en_cours", notifier=True)
    _suite(session, conseil, affaire_id, contenu="<p>Relancé.</p>", notifier=True)
    #  Corriger le contenu reste à l'auteur ou à l'administration : sans auteur,
    #  c'est l'administration.
    admin = _compte(session, role=RoleUtilisateur.admin)
    _corriger(session, admin, affaire_id, titre="Ascenseur à l'arrêt")

    assert session.get(Ticket, affaire_id).titre == "Ascenseur à l'arrêt"


def test_ce_qui_n_appartient_qu_a_la_personne_part_toujours(session):  # noqa: F811
    """L'anonymisation ne garde que le contenu collectif : la purge reste une purge."""
    from app.models.core import Notification

    personne = _compte(session)
    session.add(Notification(destinataire_id=personne.id, type="info", titre="t"))
    session.commit()
    pid = personne.id

    supprimer_compte(session, pid)
    session.commit()

    assert not session.exec(select(Notification).where(Notification.destinataire_id == pid)).all()
