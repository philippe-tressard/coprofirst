"""Le canal et la vague, de l'opérateur à la mise à jour nocturne (#2210).

Les deux côtés parlent pour de vrai (`aides_registre.installation_branchee`) :
l'opérateur règle la distribution à la référence, la réplique renouvelle son bail —
réellement signé, puis vérifié —, et `POST /admin/maintenance/bail`, que lit
`deploiement/standard/mise-a-jour.sh`, rend la version à installer.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import get_settings
from app.inscription import client
from app.inscription.depot import Contact
from app.main import app
from app.models.core import RoleUtilisateur
from app.models.roles import ROLE_OPERATEUR
from app.registre import canaux, migrer
from app.utils import horloge
from tests.aides_http import base_http, client_http
from tests.aides_registre import installation_branchee

CONTACT = Contact(prenom="Alix", nom="Durand", courriel="alix@example.org")
REPLIQUE = "CF-000002"
CLE = "cle-de-test-du-bail"

#: Les versions publiées, et leur âge en jours.
PUBLIEES = {"2.169.0": 30, "2.170.0": 20, "2.171.0": 10, "2.171.1": 2, "2.172.0": 1}


@pytest.fixture
def operateur(monkeypatch, tmp_path):
    """La référence, une réplique inscrite en 2.170.0, les versions publiées lues."""
    monkeypatch.setattr(get_settings(), "coprofirst_version", "2.170.0")
    monkeypatch.setattr(get_settings(), "maintenance_key", CLE)
    with installation_branchee(monkeypatch, tmp_path) as registre, base_http() as moteur:
        maintenant = horloge.maintenant()
        lues = [canaux.Publication(v, maintenant - timedelta(days=j)) for v, j in PUBLIEES.items()]
        with Session(registre) as s:
            migrer.inscrire_reference(s)
            canaux.relire_versions(s, lues, maintenant)
            s.commit()
        client.inscrire(CONTACT)
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}")
        yield http, registre


def _bail_pour_la_maj() -> dict:
    r = TestClient(app).post("/admin/maintenance/bail", headers={"x-maintenance-key": CLE})
    assert r.status_code == 200, r.text
    return r.json()


def _distribuer(http, **corps):
    return http.put(
        f"/admin/installations/{REPLIQUE}/distribution",
        json={"canal": "urgence", "vague": canaux.VAGUE_PILOTE, "motif": "essai", **corps},
    )


def _valider(http):
    r = http.post(
        f"/admin/installations/{REPLIQUE}/decisions", json={"geste": "valider", "motif": "ok"}
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_sans_cle_le_bail_ne_se_lit_pas(operateur):
    assert TestClient(app).post("/admin/maintenance/bail").status_code in (401, 403)


def test_en_attente_aucune_version_a_installer(operateur):
    """D18 : pas de mise à jour automatique sans inscription validée."""
    lu = _bail_pour_la_maj()
    assert lu["etat"] == "limitee" and lu["version_cible"] is None


def test_validee_elle_suit_standard(operateur):
    """Une inscription neuve suit Urgence en vague Standard : la mineure qui précède la
    dernière (2.172 → 2.171), à son dernier correctif de plus de 7 jours (2.171.0)."""
    http, _ = operateur
    fiche = _valider(http)
    assert (fiche["canal"], fiche["vague"], fiche["version_cible"]) == (
        "urgence",
        canaux.VAGUE_STANDARD,
        "2.171.0",
    )
    lu = _bail_pour_la_maj()
    assert lu == {**lu, "etat": "active", "canal": "urgence", "version_cible": "2.171.0"}


@pytest.mark.parametrize(
    "vague, attendue",
    [(canaux.VAGUE_URGENCE, "2.172.0"), (canaux.VAGUE_PILOTE, "2.171.0")],
)
def test_les_vagues_du_canal_urgence_partent_dans_le_bail(operateur, vague, attendue):
    http, _ = operateur
    _valider(http)
    r = _distribuer(http, vague=vague, motif="correctif attendu")
    assert r.status_code == 200, r.text
    assert r.json()["version_cible"] == attendue
    assert _bail_pour_la_maj()["version_cible"] == attendue
    journal = r.json()["decisions"][0]
    assert journal["geste"] == canaux.GESTE_DISTRIBUTION
    assert (
        journal["motif"]
        == f"correctif attendu — canal Urgence, vague {canaux.VAGUES[vague].libelle}"
    )


def test_l_operateur_fixe_une_version_puis_ordonne_le_retour(operateur):
    http, _ = operateur
    _valider(http)
    r = _distribuer(http, canal="2.169.0", vague=canaux.VAGUE_FIXE, motif="régression du 2.170")
    assert r.status_code == 200, r.text
    fiche = r.json()
    assert (fiche["canal"], fiche["vague"], fiche["version_cible"]) == (
        "2.169.0",
        canaux.VAGUE_FIXE,
        "2.169.0",
    )
    assert "version 2.169.0, vague Fixe" in fiche["decisions"][0]["motif"]
    #  Le bail signé porte l'ordre ; le script le lit comme un retour.
    assert _bail_pour_la_maj()["version_cible"] == "2.169.0"
    #  Une version de moins de 7 jours attend son tour : rien ne bouge.
    r = _distribuer(http, canal="2.171.1", vague=canaux.VAGUE_FIXE)
    assert r.json()["version_cible"] == "2.170.0"


@pytest.mark.parametrize(
    "corps, raison",
    [
        ({"canal": "main"}, "référence seule"),
        ({"canal": "replica"}, "Urgence, ou une version"),
        ({"canal": "2.150.0", "vague": canaux.VAGUE_FIXE}, "Version non publiée"),
        ({"canal": "2.170.0", "vague": canaux.VAGUE_PILOTE}, "vague Fixe"),
        ({"vague": canaux.VAGUE_FIXE}, "Urgence, Pilote ou Standard"),
        ({"vague": 7}, "Vague inconnue"),
    ],
)
def test_une_distribution_fautive_est_refusee(operateur, corps, raison):
    http, _ = operateur
    r = _distribuer(http, **corps)
    assert r.status_code == 409 and raison in r.json()["detail"]


def test_la_reference_ne_se_distribue_pas(operateur):
    http, _ = operateur
    r = http.put(
        "/admin/installations/CF-000000/distribution",
        json={"canal": "urgence", "vague": canaux.VAGUE_PILOTE, "motif": "essai"},
    )
    assert r.status_code == 409


def test_la_liste_montre_les_versions_et_les_vagues(operateur):
    http, _ = operateur
    liste = http.get("/admin/installations").json()
    versions = liste["versions"]
    assert [v["version"] for v in versions["proposees"]] == [
        "2.172.0",
        "2.171.1",
        "2.170.0",
        "2.169.0",
    ]
    assert versions["lues_le"] is not None
    assert [v["code"] for v in liste["vagues"]] == list(canaux.VAGUES)
    assert [v["avec_urgence"] for v in liste["vagues"]] == [True, True, True, False]
    assert [v["code"] for v in liste["vagues"] if v["defaut"]] == [canaux.VAGUE_STANDARD]
    #  Ce que chaque vague du canal Urgence installe aujourd'hui ; Fixe n'en a pas.
    assert [(v["cible"] or {}).get("version") for v in liste["vagues"]] == [
        "2.172.0",
        "2.171.0",
        "2.171.0",
        None,
    ]
