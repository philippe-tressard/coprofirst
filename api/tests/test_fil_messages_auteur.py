"""Le fil de MESSAGES d'une affaire nomme l'auteur de chaque message (#2680).

## Le défaut (relevé pendant #2633, 11/11/2026)

`MessageRead` ne servait que `auteur_id` et `auteur_qualite` ; l'écran lisait un
objet `auteur` que personne n'envoyait. Sur `/tickets/{id}`, chaque bulle avait un
nom VIDE, et ses propres messages n'étaient jamais marqués comme les siens.

## Ce qui est tenu

Le nom est SERVI, comme le reste des noms (#2633) : `auteur_nom`, calculé par
`utils/noms.nom_auteur` — « Prénom NOM », la qualité d'un auteur détaché par la
conservation (#2014), « Ancien résident » quand le compte n'existe plus. Le front
le lit ; il ne compose rien. « Ce message est-il le mien ? » est servi de même
(`est_auteur`, `auth/deps.est_auteur`) : l'écran ne compare pas les identifiants. On le relit par HTTP : c'est la sérialisation de la
réponse qui perdait le champ, un appel direct de la route ne l'aurait pas vu.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.core import MessageTicket, RoleUtilisateur, Ticket, Utilisateur
from app.utils.horloge import maintenant
from app.utils.noms import ANCIEN_RESIDENT, QUALITES_AUTEUR
from tests.aides_http import base_http, client_http


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _renommer(moteur, ident: int, prenom: str, nom: str) -> None:
    """`client_http` nomme ses comptes d'après leur rôle : on leur donne un nom inventé."""
    with Session(moteur) as s:
        u = s.get(Utilisateur, ident)
        u.prenom, u.nom = prenom, nom
        s.add(u)
        s.commit()


def _affaire(moteur, auteur_id: int) -> int:
    with Session(moteur) as s:
        t = Ticket(
            numero=f"TK-{auteur_id:06d}",
            titre="Porte du hall",
            description="Elle ne ferme plus.",
            categorie="panne",
            auteur_id=auteur_id,
            cree_le=maintenant(),
            mis_a_jour_le=maintenant(),
        )
        s.add(t)
        s.commit()
        return t.id


def _message_detache(moteur, ticket_id: int, qualite: str | None) -> None:
    """Un message dont l'auteur a été détaché (#2014) ou dont le compte n'existe plus."""
    with Session(moteur) as s:
        s.add(MessageTicket(ticket_id=ticket_id, contenu="Ancien.", auteur_qualite=qualite))
        s.commit()


def test_chaque_message_du_fil_porte_le_nom_de_son_auteur(moteur):
    resident, resident_id = client_http(moteur, RoleUtilisateur.propriétaire)
    cs, cs_id = client_http(moteur, RoleUtilisateur.conseil_syndical)
    _renommer(moteur, resident_id, "Alice", "Durand")
    _renommer(moteur, cs_id, "Bruno", "martin")  # la casse saisie : le nom part en capitales
    ticket_id = _affaire(moteur, resident_id)

    envoye = resident.post(f"/tickets/{ticket_id}/messages", json={"contenu": "Toujours cassée."})
    assert envoye.status_code == 201, envoye.text
    #  La réponse au POST est elle-même rendue dans le fil (le front l'y ajoute).
    assert envoye.json()["auteur_nom"] == "Alice DURAND"
    assert envoye.json()["auteur_id"] == resident_id
    assert envoye.json()["est_auteur"] is True
    assert cs.post(f"/tickets/{ticket_id}/messages", json={"contenu": "Vu."}).status_code == 201

    fil = resident.get(f"/tickets/{ticket_id}/messages")
    assert fil.status_code == 200, fil.text
    lus = [(m["auteur_id"], m["auteur_nom"], m["est_auteur"]) for m in fil.json()]
    assert lus == [
        (resident_id, "Alice DURAND", True),
        (cs_id, "Bruno MARTIN", False),
    ]
    #  Le même fil lu par le conseil : chacun ne reconnaît que les siens.
    assert [m["est_auteur"] for m in cs.get(f"/tickets/{ticket_id}/messages").json()] == [
        False,
        True,
    ]


@pytest.mark.parametrize(
    ("qualite", "attendu"),
    [
        ("conseil", QUALITES_AUTEUR["conseil"]),
        ("resident", QUALITES_AUTEUR["resident"]),
        (None, ANCIEN_RESIDENT),
    ],
)
def test_un_auteur_detache_se_nomme_par_sa_qualite(moteur, qualite, attendu):
    resident, resident_id = client_http(moteur, RoleUtilisateur.propriétaire)
    ticket_id = _affaire(moteur, resident_id)
    _message_detache(moteur, ticket_id, qualite)

    (message,) = resident.get(f"/tickets/{ticket_id}/messages").json()
    assert message["auteur_id"] is None
    assert message["auteur_nom"] == attendu
    assert message["est_auteur"] is False  # un auteur détaché n'est personne
