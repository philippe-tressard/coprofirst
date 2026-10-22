"""Les comptes techniques ne se montrent pas dans un choix de personne (#1985).

L'administrateur et l'opérateur du seed (`admin_technique`) n'habitent pas la
résidence. Sur la démo publique, un visiteur entré comme conseil syndical les
voyait — adresse comprise — dans Délégations, « Saisi pour » et les porteurs de
badges (`GET /admin/utilisateurs`), et un copropriétaire les trouvait en cherchant
un locataire (`GET /bailleur/search-locataire`). Ces routes passent par la PORTE
réelle, avec le vrai seed : un compte technique ajouté demain y serait couvert.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur, StatutUtilisateur
from tests.aides_base import compte
from tests.aides_http import base_http, client_http

TECHNIQUES = {"admin@localhost", "operateur@localhost"}


@pytest.fixture
def moteur():
    import app.seed as module_seed

    with base_http() as moteur:
        with Session(moteur) as session:
            module_seed._admin_initial(session)
            session.commit()
            compte(
                session,
                nom="Durand",
                prenom="Site",
                email="durand@exemple.test",
                statut=StatutUtilisateur.locataire,
            )
        yield moteur


def _adresses(reponse) -> set[str]:
    assert reponse.status_code == 200, reponse.text
    return {u["email"] for u in reponse.json()}


def _trouves(reponse) -> set[str]:
    """La recherche de locataire rend l'adresse MASQUÉE (#2153) : on lit les noms."""
    assert reponse.status_code == 200, reponse.text
    return {f"{u['prenom']} {u['nom']}" for u in reponse.json()}


def test_le_conseil_ne_recoit_pas_les_comptes_techniques(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    vus = _adresses(http.get("/admin/utilisateurs"))
    assert not vus & TECHNIQUES
    assert "durand@exemple.test" in vus, "le filtre ne doit écarter que les comptes techniques"


def test_l_administration_les_garde_pour_les_gerer(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    assert TECHNIQUES <= _adresses(http.get("/admin/utilisateurs"))


@pytest.mark.parametrize(
    "q", ["Site", "Admin", "Opérateur", "admin@localhost", "operateur@localhost"]
)
def test_la_recherche_de_locataire_ne_les_trouve_jamais(moteur, q):
    http, _ = client_http(
        moteur, RoleUtilisateur.propriétaire, statut=StatutUtilisateur.copropriétaire_bailleur
    )
    trouves = _trouves(http.get("/bailleur/search-locataire", params={"q": q}))
    assert trouves <= {"Site Durand"}, trouves


@pytest.mark.parametrize("q", ["Durand", "durand@exemple.test"])
def test_la_recherche_trouve_toujours_un_habitant(moteur, q):
    """Témoin : « Site » est aussi le prénom de cet habitant, qui reste trouvé."""
    http, _ = client_http(
        moteur, RoleUtilisateur.propriétaire, statut=StatutUtilisateur.copropriétaire_bailleur
    )
    assert _trouves(http.get("/bailleur/search-locataire", params={"q": q})) == {"Site Durand"}
