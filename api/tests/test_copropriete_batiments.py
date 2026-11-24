"""La liste des bâtiments : `GET /copropriete/batiments` (#2914).

Aucun test n'appelait cette route : le contrôle des routeurs nommés la croyait
couverte par une docstring. Elle est ouverte à tout compte connecté (le patrimoine
physique est public dans la copropriété), refusée à l'anonyme, et rend chaque
bâtiment avec ses chiffres.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.core import Batiment, Copropriete, RoleUtilisateur
from tests.aides_http import base_http, client_http

URL = "/copropriete/batiments"


@pytest.fixture
def moteur():
    with base_http() as moteur:
        with Session(moteur) as s:
            copro = Copropriete(nom="Résidence d'essai", adresse="1 rue de l'Essai")
            s.add(copro)
            s.flush()
            s.add(Batiment(copropriete_id=copro.id, numero="A", nb_etages=5, nb_caves=12))
            s.add(Batiment(copropriete_id=copro.id, numero="B", nb_appartements=9))
            s.commit()
        yield moteur


def test_un_anonyme_est_refuse(moteur):
    anonyme, _ = client_http(moteur, None)

    assert anonyme.get(URL).status_code == 401


@pytest.mark.parametrize("role", [RoleUtilisateur.résident, RoleUtilisateur.externe])
def test_tout_compte_connecte_lit_les_batiments(moteur, role):
    http, _ = client_http(moteur, role)

    r = http.get(URL)

    assert r.status_code == 200, r.text
    par_numero = {b["numero"]: b for b in r.json()}
    assert sorted(par_numero) == ["A", "B"]
    assert (par_numero["A"]["nb_etages"], par_numero["A"]["nb_caves"]) == (5, 12)
    assert par_numero["B"]["nb_appartements"] == 9
