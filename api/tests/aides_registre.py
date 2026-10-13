"""Le registre des installations ALLUMÉ pour un test — une seule mise en place (§4.11).

Partagée par les tests du registre (inscription, bail, sauvegarde) : la base
`plateforme` est posée par SA chaîne de migrations (`registre.migrer`), le
registre se croit la référence sous son nom dédié, et toute lecture de sa base —
par la route (`get_session_plateforme`) comme par la sauvegarde (`base.moteur`) —
tombe sur la base du test.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session

from app.config import get_settings
from app.main import app
from app.registre import base, migrer
from app.utils.limiter import limiter
from tests.aides_base import moteur_memoire

#: Le nom dédié du registre, dans les tests.
HOTE = "registre.example"


@contextmanager
def registre_allume(monkeypatch) -> Iterator:
    """Rend le moteur de la base `plateforme`, migrée ; tout est défait en sortie."""
    moteur = moteur_memoire(partage=True, schema=False)
    migrer.migrer(moteur)
    reglages = get_settings()
    monkeypatch.setattr(reglages, "plateforme_database_url", "postgresql+psycopg://essai")
    monkeypatch.setattr(reglages, "hote_registre", HOTE)
    monkeypatch.setattr(base, "est_reference", lambda: True)
    monkeypatch.setattr(base, "moteur", lambda: moteur)

    def _session():
        with Session(moteur) as s:
            yield s

    app.dependency_overrides[base.get_session_plateforme] = _session
    limiter.reset()
    try:
        yield moteur
    finally:
        app.dependency_overrides.pop(base.get_session_plateforme, None)
        limiter.reset()


@contextmanager
def installation_branchee(monkeypatch, dossier) -> Iterator:
    """Le registre allumé, sa clé des baux posée, et une RÉPLIQUE qui l'appelle.

    Les appels HTTP de l'installation (`inscription.client`) sont routés vers
    l'application de test, sous le nom dédié du registre : les deux côtés parlent
    pour de vrai, le bail est réellement signé puis vérifié. Rend le moteur de la
    base `plateforme`.
    """
    from fastapi.testclient import TestClient

    from app.inscription import client, cles
    from app.registre import signature
    from app.utils import installation

    ref_privee, ref_publique = signature.generer_paire()
    reglages = get_settings()
    monkeypatch.setattr(reglages, "cle_signature_baux", signature.en_base64(ref_privee))
    monkeypatch.setattr(reglages, "installation_dir", str(dossier / "installation"))
    monkeypatch.setattr(reglages, "registre_url", f"https://{HOTE}")
    monkeypatch.setattr(reglages, "installation_essai", False)
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "replique")
    monkeypatch.setattr(cles, "CLES_REFERENCE", {1: ref_publique})

    def poster(url, content, headers, timeout):
        chemin = url.removeprefix(f"https://{HOTE}")
        return TestClient(app).post(chemin, content=content, headers={**headers, "host": HOTE})

    monkeypatch.setattr(client.httpx, "post", poster)
    with registre_allume(monkeypatch) as moteur:
        yield moteur
