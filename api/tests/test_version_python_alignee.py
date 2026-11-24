"""Tout ce qui juge l'API la juge sous la version de Python de l'image (#2951).

L'image tourne en `python:3.12-slim` (`api/Dockerfile`). Le 23/11/2026, le job
« Lint Python (Ruff) » — celui qui lance `pip-audit` par `sys.executable`, donc
résout l'arbre des dépendances SOUS SA version — était en 3.11, comme la veille
de sécurité et la mesure des plafonds ; et Ruff, sans `target-version`, jugeait
le code pour 3.10. Un audit des dépendances fait pour une autre version que
celle qui tourne ne dit rien de ce qui tourne.

Ce test tient : chaque `python-version` des workflows, et la cible de Ruff
(`api/ruff.toml`), valent la version du `FROM python:` de l'image.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOCKERFILE = RACINE / "api" / "Dockerfile"
WORKFLOWS = RACINE / ".github" / "workflows"
RUFF = RACINE / "api" / "ruff.toml"

_FROM = re.compile(r"^FROM\s+python:(\d+\.\d+)", re.M)
_SETUP = re.compile(r"""python-version:\s*["']?(\d+\.\d+)["']?""")
_CIBLE = re.compile(r"""^target-version\s*=\s*["']py(\d)(\d+)["']""", re.M)


def version_de_l_image(texte: str) -> set[str]:
    return set(_FROM.findall(texte))


def ecarts(image: str, lues: dict[str, list[str]]) -> dict[str, list[str]]:
    """Fichier → versions qui ne sont pas celle de l'image. PURE."""
    return {
        f: [v for v in vs if v != image] for f, vs in lues.items() if any(v != image for v in vs)
    }


def _lues() -> dict[str, list[str]]:
    lues = {
        p.relative_to(RACINE).as_posix(): _SETUP.findall(p.read_text(encoding="utf-8"))
        for p in sorted(WORKFLOWS.glob("*.yml"))
    }
    lues = {f: vs for f, vs in lues.items() if vs}
    cible = _CIBLE.search(RUFF.read_text(encoding="utf-8"))
    lues["api/ruff.toml"] = [f"{cible.group(1)}.{cible.group(2)}"] if cible else ["absente"]
    return lues


def test_l_image_a_une_seule_version():
    versions = version_de_l_image(DOCKERFILE.read_text(encoding="utf-8"))
    assert len(versions) == 1, f"`FROM python:` de l'image : {versions or 'aucun'}"


def test_tout_ce_qui_juge_l_api_est_a_la_version_de_l_image():
    (image,) = version_de_l_image(DOCKERFILE.read_text(encoding="utf-8"))
    trouves = ecarts(image, _lues())
    assert not trouves, (
        f"L'image est en Python {image} ; ceux-ci jugent l'API sous une autre version : "
        f"{trouves}. Les aligner (un audit des dépendances résout l'arbre sous SA version)."
    )


def test_cas_zero_les_workflows_et_la_cible_sont_lus():
    lues = _lues()
    assert len([f for f in lues if f.startswith(".github/")]) >= 3, lues
    assert lues["api/ruff.toml"] != ["absente"], "`target-version` absente de api/ruff.toml"


def test_temoin_un_ecart_est_releve():
    assert ecarts("3.12", {"a.yml": ["3.12", "3.11"], "b.yml": ["3.12"]}) == {"a.yml": ["3.11"]}
    assert version_de_l_image("FROM python:3.12-slim AS base\nFROM python:3.12-slim") == {"3.12"}
    assert _SETUP.findall('python-version: "3.11" # commentaire') == ["3.11"]
