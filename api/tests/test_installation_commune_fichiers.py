"""Les fichiers `/uploads/*` d'une installation commune — servis par l'API (#2053).

Arbitrage du 17/10/2026 (option B) : la racine est celle de la copropriété que
l'HÔTE désigne. L'essai pose, dans deux copropriétés, un fichier de MÊME clé et de
contenus différents :

- **cas zéro et témoin** : sous l'hôte de A, à une session de A, la clé rend le
  fichier de A ; sous celui de B, celui de B ;
- **étanchéité** : le jeton de A sous l'hôte de B est refusé ; aucune clé ne sort
  de la racine (`..`, chemin absolu, lien) ;
- **ce que le Caddyfile refuse** (`stockage.JAMAIS_SERVIS`) se refuse ici aussi, et
  le Caddyfile refuse bien chacun de ces dossiers — une seule liste ;
- **sans session** : 401 ; **installation propre** : 404, Caddy y garde le service ;
- l'en-tête `Cache-Control: private, no-store` est posé.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils import stockage as module_stockage
from app.utils.limiter import limiter
from tests.aides_caddy import blocs_handle, caddyfile
from tests.test_etancheite_coproprietes import HOTES, commune  # noqa: F401 — la fixture
from tests.test_etancheite_coproprietes import _sous

CLE = "photos/temoin.txt"


@pytest.fixture(scope="module")
def fichiers(commune):  # noqa: F811 — la fixture importée
    from app import contexte

    for nom in ("a", "b"):
        copro = contexte.par_identifiant(f"essai-{nom}")
        for cle, contenu in (
            (CLE, f"fichier de {nom}"),
            ("prive/pv.txt", "privé"),
            ("annonces-hall/a.pdf", "affiche"),
        ):
            chemin = copro.racine_fichiers / cle
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(contenu, encoding="utf-8")
    return commune


def _client():
    limiter.reset()
    return TestClient(app, raise_server_exceptions=False)


def test_chaque_hote_sert_le_fichier_de_SA_copropriete(fichiers):
    client = _client()
    for nom in ("a", "b"):
        jeton, _ = fichiers["temoins"][nom]
        reponse = _sous(client, f"/uploads/{CLE}", nom, jeton)
        assert reponse.status_code == 200, reponse.text
        assert reponse.text == f"fichier de {nom}"
        assert reponse.headers["cache-control"] == "private, no-store"


def test_le_jeton_de_A_n_ouvre_rien_chez_B(fichiers):
    jeton_a, _ = fichiers["temoins"]["a"]
    reponse = _sous(_client(), f"/uploads/{CLE}", "b", jeton_a)
    assert reponse.status_code == 401
    assert "fichier de" not in reponse.text


def test_sans_session_rien_n_est_servi(fichiers):
    assert _sous(_client(), f"/uploads/{CLE}", "a").status_code == 401


@pytest.mark.parametrize(
    "cle",
    ["prive/pv.txt", "annonces-hall/a.pdf", "../b/photos/temoin.txt", "%2e%2e/b/photos/temoin.txt"],
)
def test_ni_les_dossiers_jamais_servis_ni_une_sortie_de_la_racine(fichiers, cle):
    jeton, _ = fichiers["temoins"]["a"]
    reponse = _sous(_client(), f"/uploads/{cle}", "a", jeton)
    assert reponse.status_code == 404, cle
    assert "fichier de b" not in reponse.text and "privé" not in reponse.text


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="liens symboliques indisponibles")
def test_un_lien_vers_une_autre_racine_ne_sert_rien(fichiers, tmp_path):
    from app import contexte

    a = contexte.par_identifiant("essai-a").racine_fichiers
    b = contexte.par_identifiant("essai-b").racine_fichiers
    lien = a / "photos" / "vers-b.txt"
    try:
        os.symlink(b / CLE, lien)
    except OSError:
        pytest.skip("créer un lien demande un privilège sur ce poste")
    jeton, _ = fichiers["temoins"]["a"]
    try:
        assert _sous(_client(), "/uploads/photos/vers-b.txt", "a", jeton).status_code == 404
    finally:
        lien.unlink()


def test_une_installation_propre_laisse_le_service_a_caddy(fichiers, monkeypatch):
    """Témoin : la route existe, mais ne sert rien hors d'une installation commune —
    même à une session valide."""
    from app.auth.jwt import creer_jeton_acces
    from app.config import get_settings
    from app.models.core import RoleUtilisateur
    from tests.aides_base import compte

    monkeypatch.setattr(get_settings(), "coproprietes_fichier", "")
    from sqlmodel import Session, SQLModel

    from app.database import engine

    SQLModel.metadata.create_all(engine)  # la base de la copropriété de configuration
    with Session(engine) as session:
        admin = compte(session, prefixe="propre", role=RoleUtilisateur.admin, roles_json="admin")
        jeton = creer_jeton_acces(admin.id, admin.hashed_password)
    reponse = _client().get(
        f"/uploads/{CLE}", headers={"host": "testserver"}, cookies={"access_token": jeton}
    )
    assert reponse.status_code == 404


def test_le_caddyfile_refuse_chaque_dossier_jamais_servi():
    """Une liste : ce que l'API refuse est ce que Caddy refuse (`test_uploads_prives`)."""
    blocs = {chemin: corps for chemin, corps in blocs_handle(caddyfile())}
    for dossier in module_stockage.JAMAIS_SERVIS:
        corps = blocs.get(f"/uploads/{dossier}/*")
        assert corps is not None and "respond 404" in corps, dossier
    assert HOTES  # la fixture de l'installation commune réelle sert ici
