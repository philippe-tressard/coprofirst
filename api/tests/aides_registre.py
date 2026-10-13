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
