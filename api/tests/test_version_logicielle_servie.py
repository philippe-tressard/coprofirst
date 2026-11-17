"""La release qu'une installation sert se lit dans `GET /config` (#2833).

Avant le 17/11/2026, aucune route publique ne disait QUELLE release une installation
sert : `version_contrat` seulement, que plusieurs releases partagent. Une app ne
pouvait donc pas juger « cette installation sert au moins vX.Y.Z » (une table publiée
dans une release précise).

La chaîne :
- l'image de l'API porte la release (`VERSION_IMAGE`), lue dans `front/package.json`
  par la CI (`images.yml`, sortie `version`) et par le build de secours d'un nœud
  (`lib-parite.exporter_git_hash`) — la source même du pied de page (P3) ;
- `installation.version_logicielle()` la lit, après la version promue d'une réplique
  (`COPROFIRST_VERSION`) et avant le commit — c'est aussi ce que le registre reçoit ;
- `config_publique` la publie (`version_logicielle`).

Le post-check (P3b) confronte en production `GET /api/config` au pied de page.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import get_settings
from app.utils import config_publique, installation

RACINE = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "promue, image, commit, attendue",
    [
        ("3.112.0", "3.113.0", "a6fc7249", "3.112.0"),  # réplique : la version promue
        ("", "3.113.0", "a6fc7249", "3.113.0"),  # référence : la release de l'image
        ("", "", "a6fc7249", "a6fc7249"),  # image sans release (build local) : le commit
        ("", "", "dev", "inconnue"),
    ],
)
def test_la_version_logicielle_suit_sa_chaine(monkeypatch, promue, image, commit, attendue):
    reglages = get_settings()
    monkeypatch.setattr(reglages, "coprofirst_version", promue)
    monkeypatch.setattr(reglages, "version_image", image)
    monkeypatch.setattr(reglages, "git_hash", commit)
    assert installation.version_logicielle() == attendue


def test_get_config_publie_la_version_logicielle(monkeypatch):
    monkeypatch.setattr(get_settings(), "coprofirst_version", "")
    monkeypatch.setattr(get_settings(), "version_image", "3.113.0")
    cles = config_publique.cles_calculees({})
    assert cles["version_logicielle"] == "3.113.0" == installation.version_logicielle()


def _lire(chemin: str) -> str:
    return (RACINE / chemin).read_text(encoding="utf-8")


def test_l_image_de_l_api_porte_la_release_de_package_json():
    """Les trois chemins qui bâtissent l'image de l'API lui passent la release."""
    #  La CI : la sortie `version` du job qui la lit dans front/package.json.
    images = _lire(".github/workflows/images.yml")
    assert "version=$(node -p \"require('./front/package.json').version\")" in images
    assert re.search(r"VERSION_IMAGE=\$\{\{\s*needs\.version\.outputs\.version\s*\}\}", images)
    #  Le Dockerfile la reçoit et la pose dans l'environnement de l'API.
    dockerfile = _lire("api/Dockerfile")
    assert re.search(r"^ARG VERSION_IMAGE=\s*$", dockerfile, re.M)
    assert re.search(r"^ENV VERSION_IMAGE=\$VERSION_IMAGE\s*$", dockerfile, re.M)
    #  Le build de secours d'un nœud : docker-compose la transmet, la porte l'exporte.
    compose = _lire("docker-compose.yml")
    construction_api = compose.split("\n  api:", 1)[1].split("container_name: hostachy_api", 1)[0]
    assert "VERSION_IMAGE: ${VERSION_IMAGE:-}" in construction_api
    parite = _lire("scripts/lib/lib-parite.sh")
    porte = parite.split("exporter_git_hash() {", 1)[1].split("\n}", 1)[0]
    assert "VERSION_IMAGE" in porte and "front/package.json" in porte
