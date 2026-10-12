"""Lister les documents d'une rubrique par le CODE de sa catégorie (#1841).

Ma résidence chargeait sa Fiche en trois vagues : les catégories d'abord, puis
les plans, le règlement et les CR d'AG par l'IDENTIFIANT de leur catégorie,
qu'il fallait connaître. `GET /documents?categorie=<code>` rend la même liste
sans l'attendre — les trois rubriques partent avec la vague 1.

Ce que ces tests tiennent : le code filtre comme l'identifiant, un code inconnu
ne rend rien (jamais toute la bibliothèque), et la lecture reste celle de
`document_visible` — le code n'ouvre aucune porte.
"""

from __future__ import annotations

import json

import pytest

from app.models.core import (
    CategorieDocument,
    Document,
    ProfilAccesDocument,
    RoleUtilisateur,
    StatutUtilisateur,
)
from app.routers import documents
from tests.aides_base import compte


@pytest.fixture()
def bibliotheque(session):
    admin = compte(session, prefixe="admin", role=RoleUtilisateur.admin, roles_json="admin")
    locataire = compte(
        session, prefixe="locataire", roles_json="résident", statut=StatutUtilisateur.locataire
    )
    profil = ProfilAccesDocument(
        code="proprietaires", libelle="Propriétaires", roles_autorises=json.dumps(["propriétaire"])
    )
    session.add(profil)
    session.commit()
    plans = CategorieDocument(code="plan_residence", libelle="Plans", profil_acces_id=profil.id)
    ag = CategorieDocument(code="pv_ag", libelle="CR d'AG", profil_acces_id=profil.id)
    session.add_all([plans, ag])
    session.commit()
    for titre, categorie in (("Plan de masse", plans), ("PV 2025", ag)):
        session.add(
            Document(
                titre=titre,
                fichier_nom="f.pdf",
                categorie_id=categorie.id,
                publie_par_id=admin.id,
            )
        )
    session.commit()
    return {"admin": admin, "locataire": locataire, "plans": plans}


def _titres(session, user, **filtres) -> list[str]:
    return [d.titre for d in documents.list_documents(session=session, user=user, **filtres)]


def test_le_code_filtre_comme_l_identifiant(session, bibliotheque):
    admin = bibliotheque["admin"]
    par_code = _titres(session, admin, categorie="plan_residence")
    assert par_code == ["Plan de masse"]
    assert par_code == _titres(session, admin, categorie_id=bibliotheque["plans"].id)
    assert _titres(session, admin, categorie="pv_ag") == ["PV 2025"]


def test_un_code_inconnu_ne_rend_rien(session, bibliotheque):
    #  Cas zéro : sans filtre, la bibliothèque n'est pas vide.
    assert len(_titres(session, bibliotheque["admin"])) == 2
    assert _titres(session, bibliotheque["admin"], categorie="inconnue") == []


def test_le_code_n_ouvre_aucune_porte(session, bibliotheque):
    #  Le profil des plans n'admet que les propriétaires.
    assert _titres(session, bibliotheque["locataire"], categorie="plan_residence") == []
