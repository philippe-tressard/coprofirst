"""« Prénom NOM » est SERVI avec la personne — et rendu pour une saisie (#2633).

Le site composait le nom dans son front (`nomAffiche`) ; il est servi par chaque
schéma qui nomme une personne (`schemas_nom_servi.NomServi`, ou un champ calculé
quand la personne est aplatie dans son porteur) et, pour une saisie en cours, par
`POST /noms/affiche`. La règle elle-même est tenue par `test_noms_affichage.py` ;
ici, qu'elle est SERVIE, partout où un écran nomme quelqu'un.
"""

from __future__ import annotations

import pytest

from app.models.core import RoleUtilisateur
from app.routers.admin.inscription import ContactLu, VueInscription
from app.routers.bailleur.acces import BailLocataireOut
from app.routers.bailleur.baux import LocataireInfo
from app.routers.bailleur.commun import BailOut
from app.routers.points_conseil_schemas import MembreRead, PresentRead
from app.routers.prestataires_schemas import (
    PrestataireContact,
    PrestataireContactLu,
    PrestataireCreate,
    PrestataireRead,
)
from app.schemas import UserRead
from app.schemas_nom_servi import NomServi
from app.utils.noms import nom_affiche
from tests.aides_http import base_http, client_http
from tests.aides_noms import CAS


@pytest.mark.parametrize(
    "schema", [UserRead, LocataireInfo, PresentRead, MembreRead, PrestataireContactLu, ContactLu]
)
def test_chaque_personne_lue_sert_son_nom(schema):
    """Le cas fautif : une personne qu'un écran nommerait encore lui-même."""
    assert issubclass(schema, NomServi)
    assert "nom_affiche" in schema.model_computed_fields


@pytest.mark.parametrize(
    ("schema", "champ"),
    [
        (BailOut, "locataire_nom_affiche"),
        (BailLocataireOut, "bailleur_nom_affiche"),
        (UserRead, "nom_aide_affiche"),
    ],
)
def test_une_personne_aplatie_dans_son_porteur_sert_son_nom(schema, champ):
    assert champ in schema.model_computed_fields


@pytest.mark.parametrize(("prenom", "nom", "attendu"), CAS)
def test_le_nom_servi_est_la_regle(prenom, nom, attendu):
    class Personne(NomServi):
        prenom: str
        nom: str

    assert Personne(prenom=prenom, nom=nom).model_dump()["nom_affiche"] == attendu
    assert MembreRead(id=1, prenom=prenom, nom=nom).nom_affiche == nom_affiche(prenom, nom)


def test_le_contact_saisi_ne_stocke_pas_le_nom_calcule():
    """`contacts_json` reçoit le contact SAISI : un champ calculé n'a rien à y faire."""
    saisi = PrestataireCreate(
        nom="Ascenseurs", specialite="ascenseur", contacts=[{"prenom": "Anne", "nom": "lo"}]
    )
    assert "nom_affiche" not in saisi.model_dump()["contacts"][0]
    assert not issubclass(PrestataireContact, NomServi)
    lu = PrestataireRead.model_fields["contacts"].annotation
    assert "PrestataireContactLu" in str(lu)


def test_la_vue_d_inscription_nomme_son_contact():
    champ = VueInscription.model_fields["contact"].annotation
    assert "ContactLu" in str(champ)


def test_les_comptes_de_l_administration_sont_nommes():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        comptes = http.get("/admin/utilisateurs").json()
        moi = http.get("/auth/me").json()
    assert comptes and all(c["nom_affiche"] == nom_affiche(c["prenom"], c["nom"]) for c in comptes)
    assert moi["nom_affiche"] == nom_affiche(moi["prenom"], moi["nom"])
    assert "nom_aide_affiche" in moi


@pytest.mark.parametrize(("prenom", "nom", "attendu"), CAS)
def test_la_route_nomme_une_saisie(prenom, nom, attendu):
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        corps = http.post("/noms/affiche", json={"prenom": prenom, "nom": nom}).json()
    assert corps == {"nom_affiche": attendu}


def test_la_route_refuse_l_anonyme_et_l_abus():
    with base_http() as moteur:
        anonyme, _ = client_http(moteur, None)
        refus = anonyme.post("/noms/affiche", json={"prenom": "A", "nom": "B"}).status_code
        http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
        trop_long = http.post("/noms/affiche", json={"nom": "x" * 500}).status_code
        vide = http.post("/noms/affiche", json={}).json()
    assert refus == 401
    assert trop_long == 422
    assert vide == {"nom_affiche": ""}
