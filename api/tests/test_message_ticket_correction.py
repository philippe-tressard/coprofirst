"""Corriger ou retirer sa réponse (#2722) : son auteur, tant que l'affaire est ouverte."""

import pytest
from sqlmodel import Session, select

from app.models.core import (
    MessageTicket,
    RoleUtilisateur,
    StatutTicket,
    Ticket,
    TicketEvolution,
)
from app.utils.horloge import maintenant
from tests.aides_http import base_http, client_http
from tests.aides_affaire import affaire_en_base


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _clore(moteur, ticket_id: int) -> None:
    with Session(moteur) as s:
        t = s.get(Ticket, ticket_id)
        t.statut = StatutTicket.résolu
        s.add(t)
        s.commit()


def _ecrire(client, ticket_id: int, texte: str = "Toujours cassée.") -> int:
    r = client.post(f"/tickets/{ticket_id}/messages", json={"contenu": texte})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _historique(moteur, ticket_id: int) -> list[str]:
    with Session(moteur) as s:
        return [
            e.contenu
            for e in s.exec(
                select(TicketEvolution).where(
                    TicketEvolution.ticket_id == ticket_id, TicketEvolution.type == "reponse"
                )
            )
        ]


def test_l_auteur_corrige_son_message_et_l_historique_suit(moteur):
    resident, resident_id = client_http(moteur, RoleUtilisateur.propriétaire)
    ticket_id = affaire_en_base(moteur, resident_id)
    msg_id = _ecrire(resident, ticket_id)

    r = resident.patch(f"/tickets/{ticket_id}/messages/{msg_id}", json={"contenu": "Réparée ?"})

    assert r.status_code == 200, r.text
    assert r.json()["contenu"] == "Réparée ?"
    assert _historique(moteur, ticket_id) == ["Réparée ?"]


def test_l_auteur_supprime_son_message_et_son_miroir(moteur):
    resident, resident_id = client_http(moteur, RoleUtilisateur.propriétaire)
    ticket_id = affaire_en_base(moteur, resident_id)
    msg_id = _ecrire(resident, ticket_id)

    assert resident.delete(f"/tickets/{ticket_id}/messages/{msg_id}").status_code == 204

    assert resident.get(f"/tickets/{ticket_id}/messages").json() == []
    assert _historique(moteur, ticket_id) == []


@pytest.mark.parametrize("geste", ["patch", "delete"])
def test_un_autre_compte_ne_touche_pas_au_message(moteur, geste):
    resident, resident_id = client_http(moteur, RoleUtilisateur.propriétaire)
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    ticket_id = affaire_en_base(moteur, resident_id)
    msg_id = _ecrire(resident, ticket_id)

    url = f"/tickets/{ticket_id}/messages/{msg_id}"
    r = cs.patch(url, json={"contenu": "Réécrit."}) if geste == "patch" else cs.delete(url)

    assert r.status_code == 403, r.text
    assert resident.get(f"/tickets/{ticket_id}/messages").json()[0]["contenu"] == "Toujours cassée."


@pytest.mark.parametrize("geste", ["patch", "delete"])
def test_apres_la_cloture_rien_ne_change(moteur, geste):
    resident, resident_id = client_http(moteur, RoleUtilisateur.propriétaire)
    ticket_id = affaire_en_base(moteur, resident_id)
    msg_id = _ecrire(resident, ticket_id)
    _clore(moteur, ticket_id)

    url = f"/tickets/{ticket_id}/messages/{msg_id}"
    r = (
        resident.patch(url, json={"contenu": "Trop tard."})
        if geste == "patch"
        else resident.delete(url)
    )

    assert r.status_code == 409, r.text
    with Session(moteur) as s:
        assert s.get(MessageTicket, msg_id).contenu == "Toujours cassée."


def test_un_message_d_une_autre_affaire_se_lit_comme_absent(moteur):
    resident, resident_id = client_http(moteur, RoleUtilisateur.propriétaire)
    ticket_id = affaire_en_base(moteur, resident_id)
    msg_id = _ecrire(resident, ticket_id)
    with Session(moteur) as s:
        autre = Ticket(
            numero="TK-AUTRE",
            titre="Autre",
            description="Autre.",
            categorie="panne",
            auteur_id=resident_id,
            cree_le=maintenant(),
            mis_a_jour_le=maintenant(),
        )
        s.add(autre)
        s.commit()
        autre_id = autre.id

    r = resident.patch(f"/tickets/{autre_id}/messages/{msg_id}", json={"contenu": "x"})

    assert r.status_code == 404, r.text
