"""L'adresse du site, posée pour un test (#2058).

L'adresse ne se lit plus en base (`site_url`) : elle est celle du contexte —
l'`ORIGIN` d'une installation propre (`liens.adresse_du_site`). Un test qui veut
des liens en `https://5hostachy.fr/…` pose donc l'`ORIGIN`, le temps du test.
"""

from __future__ import annotations

from app.config import get_settings


def poser_adresse_du_site(monkeypatch, adresse: str) -> None:
    """L'adresse publique de la copropriété de configuration, le temps du test."""
    monkeypatch.setattr(get_settings(), "origin", adresse)
