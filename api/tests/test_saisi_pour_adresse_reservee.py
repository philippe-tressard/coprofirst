"""L'adresse d'une personne « saisie pour » ne sort qu'au conseil (22/10/2026, #2140).

## Le défaut

Une affaire saisie par le conseil pour une personne sans compte — ou née d'un
courriel transféré — porte l'adresse de cette personne (`saisi_pour_email`).
L'écran ne la montrait qu'au conseil (`CorpsCarteTicket`, `$isCS`), mais la
réponse de TOUTE lecture de l'affaire la portait : un copropriétaire qui lisait
la fiche ou la liste la recevait dans le JSON. Une protection posée au seul
rendu n'en est pas une (`standards/03` §2).

## Ce qu'on regarde

Ce que la route rend, fiche ET liste, à un lecteur hors du conseil — et le cas
zéro : le conseil, lui, la reçoit toujours.
"""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session

import app.routers.tickets.crud as crud
from app.database import engine
from app.models.core import RoleUtilisateur
from app.schemas import TicketCreate
from app.utils.perimetres import arbre
from app.utils.visibility import ticket_visible
from tests.aides_base import compte

ADRESSE = "personne-sans-compte@exemple.test"


@pytest.fixture()
def affaire(batiments):
    arbre()
    with Session(engine) as s:
        cs = compte(s, prefixe="cs", roles_json=RoleUtilisateur.conseil_syndical.value)
        voisin = compte(s, prefixe="voisin", roles_json=RoleUtilisateur.propriétaire.value)
        corps = TicketCreate(
            titre="Haie à tailler côté rue",
            description="Signalé par téléphone.",
            categorie="espaces_verts",
            saisi_pour_nom="Personne Sans-Compte",
            saisi_pour_email=ADRESSE,
        )
        lu = crud.create_ticket(corps, BackgroundTasks(), session=s, user=cs)
        yield s, cs, voisin, lu.id


def test_un_voisin_ne_recoit_pas_l_adresse(affaire):
    s, _cs, voisin, ticket_id = affaire
    fiche = crud.get_ticket(ticket_id, session=s, user=voisin)
    assert fiche.saisi_pour_email is None, "l'adresse d'un tiers partait dans la fiche"
    assert fiche.proprietaire_nom == "Personne Sans-Compte", "le nom signe la carte, pour tous"
    (dans_la_liste,) = [t for t in crud.list_tickets(session=s, user=voisin) if t.id == ticket_id]
    assert dans_la_liste.saisi_pour_email is None, "l'adresse d'un tiers partait dans la liste"


def test_le_voisin_lit_bien_l_affaire(affaire):
    """Sans quoi le test précédent serait vert pour une mauvaise raison."""
    s, _cs, voisin, ticket_id = affaire
    from app.models.core import Ticket

    assert ticket_visible(s.get(Ticket, ticket_id), voisin)


def test_le_conseil_recoit_l_adresse(affaire):
    """Le cas zéro : le conseil écrit à la personne — il garde l'adresse."""
    s, cs, _voisin, ticket_id = affaire
    assert crud.get_ticket(ticket_id, session=s, user=cs).saisi_pour_email == ADRESSE
    (dans_la_liste,) = [t for t in crud.list_tickets(session=s, user=cs) if t.id == ticket_id]
    assert dans_la_liste.saisi_pour_email == ADRESSE
