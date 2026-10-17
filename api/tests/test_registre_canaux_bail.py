"""Le canal, la vague et l'épinglage, de l'opérateur à la mise à jour nocturne (R5 #1881).

Les deux côtés parlent pour de vrai (`aides_registre.installation_branchee`) :
l'opérateur règle la distribution à la référence, la réplique renouvelle son bail —
réellement signé, puis vérifié —, et `POST /admin/maintenance/bail`, que lit
`deploiement/standard/mise-a-jour.sh`, rend la version à installer.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import get_settings
from app.inscription import client
from app.inscription.depot import Contact
from app.main import app
from app.models.core import RoleUtilisateur
from app.models.roles import ROLE_OPERATEUR
from app.registre import canaux, migrer
from app.registre.modeles import CanalDistribution, DecisionRegistre
from app.utils import horloge
from tests.aides_http import base_http, client_http
from tests.aides_registre import installation_branchee

CONTACT = Contact(prenom="Alix", nom="Durand", courriel="alix@example.org")
REPLIQUE = "CF-000002"
CLE = "cle-de-test-du-bail"


@pytest.fixture
def operateur(monkeypatch, tmp_path):
    """La référence, une réplique inscrite en 2.170.0, `replica` lu en 2.172.0."""
    monkeypatch.setattr(get_settings(), "coprofirst_version", "2.170.0")
    monkeypatch.setattr(get_settings(), "maintenance_key", CLE)
    with installation_branchee(monkeypatch, tmp_path) as registre, base_http() as moteur:
        with Session(registre) as s:
            migrer.inscrire_reference(s)
            canaux.relire_replica(s, "2.172.0", horloge.maintenant())
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
        json={"canal": "replica", "vague": 1, "motif": "essai", **corps},
    )


def test_sans_cle_le_bail_ne_se_lit_pas(operateur):
    assert TestClient(app).post("/admin/maintenance/bail").status_code in (401, 403)


def test_en_attente_aucune_version_a_installer(operateur):
    """D18 : pas de mise à jour automatique sans inscription validée."""
    lu = _bail_pour_la_maj()
    assert lu["etat"] == "limitee" and lu["version_cible"] is None


def test_validee_elle_recoit_la_version_de_replica(operateur):
    http, _ = operateur
    r = http.post(
        f"/admin/installations/{REPLIQUE}/decisions", json={"geste": "valider", "motif": "ok"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["version_cible"] == "2.172.0"
    lu = _bail_pour_la_maj()
    assert lu == {**lu, "etat": "active", "canal": "replica", "version_cible": "2.172.0"}


def test_l_operateur_epingle_puis_ordonne_le_retour(operateur):
    http, _ = operateur
    http.post(
        f"/admin/installations/{REPLIQUE}/decisions", json={"geste": "valider", "motif": "ok"}
    )
    r = _distribuer(http, vague=0, version_epinglee="2.169.0", motif="régression du 2.170")
    assert r.status_code == 200, r.text
    fiche = r.json()
    assert (fiche["vague"], fiche["version_epinglee"], fiche["version_cible"]) == (
        0,
        "2.169.0",
        "2.169.0",
    )
    assert fiche["decisions"][0]["geste"] == canaux.GESTE_DISTRIBUTION
    assert "épinglée en 2.169.0" in fiche["decisions"][0]["motif"]
    #  Le bail signé porte l'ordre ; le script le lit comme un retour.
    assert _bail_pour_la_maj()["version_cible"] == "2.169.0"
    #  Libérée : elle rejoint son canal.
    assert _distribuer(http, version_epinglee="").json()["version_epinglee"] is None
    assert _bail_pour_la_maj()["version_cible"] == "2.172.0"


@pytest.mark.parametrize(
    "corps, raison",
    [
        ({"canal": "main"}, "référence seule"),
        ({"canal": "special-inconnu"}, "Canal inconnu"),
        ({"vague": 7}, "Vague inconnue"),
        ({"version_epinglee": "5aa41dad"}, "X.Y.Z"),
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
        json={"canal": "replica", "vague": 1, "motif": "essai"},
    )
    assert r.status_code == 409


def test_un_canal_special_porte_sa_version_et_s_inscrit_au_journal(operateur):
    http, registre = operateur
    http.post(
        f"/admin/installations/{REPLIQUE}/decisions", json={"geste": "valider", "motif": "ok"}
    )
    r = http.put(
        "/admin/canaux-distribution/special-pilote",
        json={"version": "2.171.0", "motif": "client A"},
    )
    assert r.status_code == 200, r.text
    assert [c["nom"] for c in r.json()] == ["replica", "special-pilote"]
    assert r.json()[0]["modifiable"] is False and r.json()[1]["modifiable"] is True

    assert _distribuer(http, canal="special-pilote", vague=0).json()["version_cible"] == "2.171.0"
    r = http.put(
        "/admin/canaux-distribution/special-pilote", json={"version": "2.172.0", "motif": "suite"}
    )
    assert r.status_code == 200
    assert _bail_pour_la_maj()["version_cible"] == "2.172.0"
    with Session(registre) as s:
        gestes = s.exec(
            select(DecisionRegistre.motif).where(
                DecisionRegistre.geste == canaux.GESTE_CANAL_AVANCE
            )
        ).all()
        assert gestes == ["suite — special-pilote en 2.172.0"]
        assert s.exec(select(CanalDistribution).where(CanalDistribution.nom == "replica")).one()


@pytest.mark.parametrize(
    "nom, version", [("replica", "2.173.0"), ("Spécial", "2.1.0"), ("special-a", "v2")]
)
def test_un_canal_special_fautif_est_refuse(operateur, nom, version):
    http, _ = operateur
    r = http.put(f"/admin/canaux-distribution/{nom}", json={"version": version, "motif": "x"})
    assert r.status_code == 409


def test_la_liste_montre_les_canaux_et_les_vagues(operateur):
    http, _ = operateur
    liste = http.get("/admin/installations").json()
    assert [c["nom"] for c in liste["canaux"]] == ["replica"]
    assert liste["canaux"][0]["version"] == "2.172.0"
    assert [v["code"] for v in liste["vagues"]] == list(canaux.VAGUES)
