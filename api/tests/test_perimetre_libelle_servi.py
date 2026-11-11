"""Le lieu d'un contenu est SERVI avec lui — et nommé pour une saisie (#2633).

Le site composait le badge 🔹 dans son front (`perimetreLabel`) ; il est servi par
chaque schéma qui porte un périmètre (`perimetres.servi.AvecPerimetreLibelle`) et,
pour une saisie en cours, par `POST /perimetres/libelle`. La règle du libellé
elle-même est tenue par `test_libelle_perimetre*` ; ici, qu'elle est SERVIE.
"""

from __future__ import annotations

import pytest

from app.models.core import RoleUtilisateur
from app.routers.acces.vues import AccesPorteur
from app.routers.annonces import AnnonceRead
from app.routers.annonces_hall_schemas import AnnonceHallRead
from app.routers.documents_schemas import DocumentRead
from app.routers.idees import IdeeRead
from app.routers.sondages.commun import SondageRead
from app.routers.suivi_affaires import AffaireOuverteRead
from app.utils.perimetres.libelles import perimetre_badge
from app.utils.perimetres.servi import AvecPerimetreLibelle, codes_de, libelle_complet
from tests.aides_http import base_http, client_http


@pytest.mark.parametrize(
    "schema",
    [
        AccesPorteur,
        AnnonceRead,
        AnnonceHallRead,
        DocumentRead,
        IdeeRead,
        SondageRead,
        AffaireOuverteRead,
    ],
)
def test_chaque_contenu_a_badge_sert_son_lieu(schema):
    """Le cas fautif : un contenu dont le badge se composerait encore à l'écran."""
    assert issubclass(schema, AvecPerimetreLibelle)
    assert "perimetre_libelle" in schema.model_computed_fields


@pytest.mark.parametrize("perimetre", [None, "", "[]", '["bat:1"]', ["bat:1", "bat:2"]])
def test_le_badge_est_la_regle_du_badge(perimetre):
    class Contenu(AvecPerimetreLibelle):
        perimetre_cible: object = None

    servi = Contenu(perimetre_cible=perimetre).model_dump()["perimetre_libelle"]
    assert servi == perimetre_badge(codes_de(perimetre))


def test_un_lieu_complet_se_nomme_meme_par_defaut_et_se_tait_sans_code():
    assert libelle_complet([]) == "" and libelle_complet(None) == ""


def test_la_route_nomme_une_selection():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        corps = http.post("/perimetres/libelle", json={"codes": ["bat:1"]}).json()
        anonyme, _ = client_http(moteur, None)
        refus = anonyme.post("/perimetres/libelle", json={"codes": []}).status_code
    assert corps == {"libelle": libelle_complet(["bat:1"]), "badge": perimetre_badge(["bat:1"])}
    assert refus == 401
