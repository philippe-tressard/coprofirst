"""Une réponse inscrite au fil porte le TEXTE du message (05/10/2026).

`add_message` journalisait l'entrée `reponse` sans contenu : la carte de liste,
qui ne rend que l'Historique, montrait un en-tête de réponse sans corps alors que
la fiche (fil de bulles) et le courriel de notification citaient le message.

Deux gestes : l'écriture (`add_message`) et le rattrapage des entrées déjà vides
(migration 0264).
"""

from __future__ import annotations


from fastapi import BackgroundTasks
from sqlmodel import select

import pytest

from app.models.core import RoleUtilisateur, Ticket, TicketEvolution, Utilisateur
from app.routers.tickets import messages
from app.routers.tickets.messages_schemas import MessageCreate
from tests.aides_affaire import _compte, _creer, session  # noqa: F401  (fixture)
from tests.aides_purge import purger_ligne


@pytest.fixture()
def propre(session):  # noqa: F811
    """La base de l'application est PARTAGÉE : ce que le test y écrit en part avec lui.

    Une affaire et un compte laissés derrière ressortaient dans les tests qui
    cherchent un numéro (versement de courriels : deux affaires pour un repère).
    """
    tickets = set(session.exec(select(Ticket.id)).all())
    comptes = set(session.exec(select(Utilisateur.id)).all())
    yield session
    session.rollback()
    for modele, avant in ((Ticket, tickets), (Utilisateur, comptes)):
        for ligne_id in session.exec(select(modele.id)).all():
            if ligne_id not in avant:
                purger_ligne(session, modele, ligne_id)


def _poster(base, user, ticket_id, **champs):
    corps = MessageCreate(**champs)
    return messages.add_message(ticket_id, corps, BackgroundTasks(), session=base, user=user)


def _reponses(base, ticket_id) -> list[TicketEvolution]:
    return list(
        base.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket_id, TicketEvolution.type == "reponse"
            )
        ).all()
    )


def test_le_message_public_ecrit_son_texte_dans_le_fil(propre):
    auteur = _compte(propre)
    ticket = _creer(propre, auteur, categorie="panne")
    _poster(propre, auteur, ticket.id, contenu="<p>L'étiquette doit être au nom de X.</p>")
    (reponse,) = _reponses(propre, ticket.id)
    assert reponse.contenu == "<p>L'étiquette doit être au nom de X.</p>"


def test_le_message_interne_ne_livre_pas_son_texte_au_fil(propre):
    cs = _compte(propre, role=RoleUtilisateur.conseil_syndical)
    ticket = _creer(propre, cs, categorie="panne")
    _poster(propre, cs, ticket.id, contenu="Note réservée au conseil.", interne=True)
    (reponse,) = _reponses(propre, ticket.id)
    assert reponse.contenu == "Message interne"
    assert "réservée" not in (reponse.contenu or "")
