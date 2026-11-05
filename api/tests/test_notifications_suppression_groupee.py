"""Supprimer ses notifications en UNE requête (#2535).

L'API ne savait en supprimer qu'une à la fois (`DELETE /notifications/{id}`) : l'app
iOS envoyait 134 requêtes pour vider les lues d'un compte de 146 alertes. Deux routes :

- `POST /notifications/supprimer-lues` — toutes les LUES du destinataire, le pendant
  de `tout-marquer-lu` ; le site et l'app l'offrent sous « Supprimer les lues » ;
- `POST /notifications/supprimer-selection` `{"ids": [...]}` — une sélection (l'app iOS).

🔴 Une notification n'appartient qu'à son destinataire (`auth/deps.mes_notifications`) :
l'identifiant d'une notification d'autrui est IGNORÉ, jamais supprimé, et le compte rendu
ne dit que les siennes. Les routes passent par la VRAIE authentification (`aides_http`).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.models.core import Notification, RoleUtilisateur
from app.routers.notifications_schemas import SuppressionNotifications
from tests.aides_base import compte
from tests.aides_http import base_http, client_http


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _poser(moteur, destinataire_id: int, *, lue: bool) -> int:
    with Session(moteur) as s:
        n = Notification(destinataire_id=destinataire_id, type="system", titre="Avis", lue=lue)
        s.add(n)
        s.commit()
        s.refresh(n)
        return n.id


def _restantes(moteur, destinataire_id: int) -> set[int]:
    with Session(moteur) as s:
        return set(
            s.exec(select(Notification.id).where(Notification.destinataire_id == destinataire_id))
        )


def _autrui(moteur) -> int:
    with Session(moteur) as s:
        return compte(s, prefixe="voisin").id


def test_un_anonyme_ne_supprime_rien(moteur):
    http, _ = client_http(moteur, None)
    assert http.post("/notifications/supprimer-lues").status_code == 401
    assert http.post("/notifications/supprimer-selection", json={"ids": [1]}).status_code == 401


def test_supprimer_les_lues_garde_les_non_lues_et_celles_d_autrui(moteur):
    http, moi = client_http(moteur, RoleUtilisateur.propriétaire)
    voisin = _autrui(moteur)
    lues = {_poser(moteur, moi, lue=True) for _ in range(3)}
    non_lue = _poser(moteur, moi, lue=False)
    chez_le_voisin = _poser(moteur, voisin, lue=True)

    r = http.post("/notifications/supprimer-lues")

    assert r.status_code == 200, r.text
    assert r.json() == {"supprimees": len(lues)}
    assert _restantes(moteur, moi) == {non_lue}
    assert _restantes(moteur, voisin) == {chez_le_voisin}, "jamais les lues d'un autre"


def test_supprimer_les_lues_sans_rien_a_supprimer(moteur):
    http, moi = client_http(moteur, RoleUtilisateur.résident)
    non_lue = _poser(moteur, moi, lue=False)
    r = http.post("/notifications/supprimer-lues")
    assert r.status_code == 200 and r.json() == {"supprimees": 0}
    assert _restantes(moteur, moi) == {non_lue}


def test_supprimer_une_selection_ignore_celles_d_autrui(moteur):
    http, moi = client_http(moteur, RoleUtilisateur.propriétaire)
    voisin = _autrui(moteur)
    a, b = _poser(moteur, moi, lue=False), _poser(moteur, moi, lue=True)
    gardee = _poser(moteur, moi, lue=True)
    chez_le_voisin = _poser(moteur, voisin, lue=False)

    r = http.post(
        "/notifications/supprimer-selection", json={"ids": [a, b, chez_le_voisin, 999_999]}
    )

    assert r.status_code == 200, r.text
    assert r.json() == {"supprimees": 2}, "le compte ne dit que les siennes"
    assert _restantes(moteur, moi) == {gardee}
    assert _restantes(moteur, voisin) == {chez_le_voisin}


@pytest.mark.parametrize("corps", [{}, {"ids": []}, {"ids": list(range(1, 502))}])
def test_une_selection_vide_ou_demesuree_est_refusee(moteur, corps):
    http, moi = client_http(moteur, RoleUtilisateur.propriétaire)
    gardee = _poser(moteur, moi, lue=True)
    assert http.post("/notifications/supprimer-selection", json=corps).status_code == 422
    assert _restantes(moteur, moi) == {gardee}


def test_une_selection_de_cinq_cents_passe():
    """La borne est 500 : elle dépasse ce qu'un compte réel accumule (146 au 05/11/2026)."""
    assert SuppressionNotifications(ids=list(range(1, 501))).ids[-1] == 500
