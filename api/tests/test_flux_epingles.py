"""Le compte du bandeau « Épinglé » : `GET /flux/epingles` (#2914).

Aucun test n'appelait cette route : le contrôle des routeurs nommés la croyait
couverte parce que « epingles.py » était la clé d'une table d'un AUTRE contrôle.
Elle sert l'avertissement de plafond affiché au moment d'épingler ; ce fichier
tient sa porte (le conseil syndical et l'administration) et ce qu'elle compte :
les actualités épinglées non archivées — ni une affaire d'une autre nature, ni
une actualité archivée.
"""

from __future__ import annotations

import pytest

from app.models.core import RoleUtilisateur
from app.utils.nature_affaire import ACTUALITE
from tests.aides_http import base_http, client_http
from tests.aides_suivi import affaire_ouverte

URL = "/flux/epingles"


@pytest.fixture
def moteur():
    with base_http() as moteur:
        yield moteur


def test_un_anonyme_est_refuse(moteur):
    anonyme, _ = client_http(moteur, None)

    assert anonyme.get(URL).status_code == 401


@pytest.mark.parametrize("role", [RoleUtilisateur.résident, RoleUtilisateur.propriétaire])
def test_un_habitant_ne_compte_pas_les_epingles(moteur, role):
    http, _ = client_http(moteur, role)

    assert http.get(URL).status_code == 403


@pytest.mark.parametrize("role", [RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin])
def test_sans_epingle_le_compte_est_nul(moteur, role):
    http, _ = client_http(moteur, role)

    r = http.get(URL)

    assert r.status_code == 200, r.text
    assert r.json() == {"total": 0, "publications": 0, "evenements": 0}


def test_seules_les_actualites_epinglees_non_archivees_comptent(moteur):
    affaire_ouverte(moteur, "Coupure d'eau jeudi", categorie=ACTUALITE, epingle=True)
    affaire_ouverte(moteur, "Ravalement", categorie=ACTUALITE, epingle=True)
    affaire_ouverte(moteur, "Ancienne", categorie=ACTUALITE, epingle=True, archive_manuel=True)
    affaire_ouverte(moteur, "Non épinglée", categorie=ACTUALITE, epingle=False)
    affaire_ouverte(moteur, "Panne épinglée", epingle=True)
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    assert http.get(URL).json() == {"total": 2, "publications": 2, "evenements": 0}
