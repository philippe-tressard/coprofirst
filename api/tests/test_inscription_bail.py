"""L'inscription et le bail, de bout en bout : une installation face au registre (R2 #1878).

Les deux côtés tournent dans ce processus : la référence (`registre/routeur.py`,
base `plateforme` migrée) et l'installation (`app/inscription/`), dont les appels
HTTP sont routés vers l'application de test sous le nom dédié du registre. Le bail
est réellement signé par une clé des baux, et réellement vérifié par l'installation.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.config import get_settings
from app.inscription import client, cles, depot
from app.inscription.depot import Contact
from app.models.core import RoleUtilisateur
from app.models.roles import ROLE_OPERATEUR
from app.registre import signature
from app.registre.modeles import DecisionRegistre, EtatInscription
from app.utils import installation
from tests.aides_http import base_http, client_http
from tests.aides_registre import installation_branchee, modifier_inscrite

CONTACT = Contact(prenom="Alix", nom="Durand", courriel="alix@example.org")


@pytest.fixture
def registre(monkeypatch, tmp_path):
    """La référence (registre allumé, clé des baux posée) et une RÉPLIQUE qui l'appelle."""
    with installation_branchee(monkeypatch, tmp_path) as moteur:
        yield moteur


def test_inscrite_en_attente_puis_validee_puis_suspendue(registre):
    client.inscrire(CONTACT)
    verdict = client.constat_courant()
    assert (verdict.etat, verdict.identifiant) == ("limitee", "CF-000001")
    assert "attente" in verdict.raison

    modifier_inscrite(registre, etat=EtatInscription.active)
    client.renouveler()
    verdict = client.constat_courant()
    assert (verdict.etat, verdict.canal, verdict.epoque) == ("active", "urgence", 1)

    modifier_inscrite(registre, etat=EtatInscription.suspendue)
    client.renouveler()
    assert client.constat_courant().etat == "suspendue"


def test_la_cle_reste_la_meme_et_l_identifiant_aussi(registre):
    client.inscrire(CONTACT)
    cle = client.cle_publique()
    client.inscrire(CONTACT.model_copy(update={"telephone": "0102030405"}))
    assert client.cle_publique() == cle
    assert depot.lire().identifiant == "CF-000001"
    assert (depot.dossier() / depot.CLE).exists()


def test_deux_cles_sous_un_identifiant_sont_un_clone_signale(registre):
    client.inscrire(CONTACT)
    (depot.dossier() / depot.CLE).unlink()  # une autre machine, même état copié
    with pytest.raises(client.RegistreInjoignable, match="409"):
        client.renouveler()
    with Session(registre) as s:
        gestes = s.exec(select(DecisionRegistre.geste)).all()
    assert "clone_signale" in gestes


def test_un_bail_demande_pour_une_installation_inconnue_rend_404(registre):
    client.inscrire(CONTACT)
    modifier_inscrite(registre, identifiant="CF-000999")
    with pytest.raises(client.RegistreInjoignable, match="404 Installation inconnue du registre"):
        client.renouveler()


def test_sans_cle_des_baux_la_reference_ne_delivre_rien_et_c_est_dit(registre, monkeypatch):
    monkeypatch.setattr(get_settings(), "cle_signature_baux", "")
    client.inscrire(CONTACT)  # inscrite ; le bail est refusé, l'erreur rangée
    etat = depot.lire()
    assert etat.identifiant == "CF-000001" and "503" in (etat.derniere_erreur or "")
    assert client.constat_courant().etat == "limitee"


def test_un_bail_signe_par_une_autre_cle_n_est_pas_range(registre, monkeypatch):
    monkeypatch.setattr(cles, "CLES_REFERENCE", {1: signature.generer_paire()[1]})
    client.inscrire(CONTACT)
    etat = depot.lire()
    assert etat.bail is None and "signature" in (etat.derniere_erreur or "")


def test_la_reference_et_l_essai_n_appellent_jamais(registre, monkeypatch):
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "reference")
    with pytest.raises(client.RegistreInjoignable):
        client.inscrire(CONTACT)
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "replique")
    monkeypatch.setattr(get_settings(), "installation_essai", True)
    monkeypatch.setattr(get_settings(), "origin", "http://localhost")
    with pytest.raises(client.RegistreInjoignable):
        client.inscrire(CONTACT)
    assert not depot.cle_existe()


def test_l_essai_n_est_pas_cru_hors_d_un_hote_local(monkeypatch):
    monkeypatch.setattr(get_settings(), "installation_essai", True)
    monkeypatch.setattr(get_settings(), "origin", "https://residence.example")
    monkeypatch.setattr(get_settings(), "database_url", "postgresql+psycopg://x@y/z")
    assert not client.essai_admis()


# ── L'écran de l'opérateur ──────────────────────────────────────────────────


@pytest.fixture
def http_operateur(registre):
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}")
        yield http, moteur


@pytest.mark.parametrize(
    "role",
    [None, RoleUtilisateur.résident, RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin],
)
def test_les_routes_sont_reservees_a_l_operateur(registre, role):
    with base_http() as moteur:
        http, _ = client_http(moteur, role)
        assert http.get("/admin/installation/inscription").status_code in (401, 403)
        assert http.post("/admin/installation/bail").status_code in (401, 403)


def test_l_operateur_s_inscrit_depuis_l_administration(http_operateur):
    http, _ = http_operateur
    avant = http.get("/admin/installation/inscription").json()
    assert avant["etat"] == "limitee" and avant["peut_s_inscrire"]
    conditions = http.get("/admin/installation/conditions").json()
    corps = {
        "prenom": "Alix",
        "nom": "Durand",
        "courriel": "alix@example.org",
        "conditions_acceptees": conditions["version"],
        "accepte": True,
    }
    r = http.post("/admin/installation/inscription", json=corps)
    assert r.status_code == 200, r.text
    assert r.json()["identifiant"] == "CF-000001"
    refus = http.post("/admin/installation/inscription", json={**corps, "accepte": False})
    assert refus.status_code == 400
    perime = http.post(
        "/admin/installation/inscription",
        json={**corps, "conditions_acceptees": conditions["version"] + 1},
    )
    assert perime.status_code == 409
