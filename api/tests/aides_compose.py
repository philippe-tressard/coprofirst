"""Les services de `docker-compose.yml`, lus une fois pour les tests d'images (#1872).

Deux natures de service, et deux chemins pour leurs correctifs :

- un service **construit** (`build:`) tient son système de son Dockerfile — ses
  images de base se lisent dans les `FROM` ;
- un service **tiré** (`image:` sans `build:`, aujourd'hui PostgreSQL) tourne sur
  l'image publiée elle-même.

Les Dockerfile se lisent par `instructions_dockerfile` et `etape_finale` : deux
contrôles d'images (npm retiré, paquets du système à jour) jugent l'étape finale.

`services_construits` vivait dans `test_images_publiees.py` ; le contrôle de
suivi des images (`test_images_compose_suivies.py`) en a besoin aussi, et un
fichier de tests ne s'importe pas d'un autre.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[2]
COMPOSE = RACINE / "docker-compose.yml"


def lire_yaml(chemin: Path) -> dict:
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))


def declencheurs(flux: dict) -> dict:
    """Les déclencheurs (`on:`) d'un workflow lu par `lire_yaml`.

    PyYAML lit la clé `on` comme le booléen True (YAML 1.1). Recopiée dans trois
    tests de workflows avant #2571.
    """
    return flux.get("on") or flux.get(True) or {}


def services_construits() -> dict[str, tuple[str, str]]:
    """Chaque service qui se CONSTRUIT : nom → (contexte, Dockerfile relatif à la racine)."""
    construits = {}
    for nom, service in lire_yaml(COMPOSE)["services"].items():
        build = service.get("build")
        if build:
            contexte = build["context"].removeprefix("./") or "."
            fichier = build.get("dockerfile", "Dockerfile")
            construits[nom] = (contexte, fichier if contexte == "." else f"{contexte}/{fichier}")
    return construits


def images_tirees() -> dict[str, str]:
    """Chaque service qui tourne sur une image PUBLIÉE (`image:` sans `build:`) : nom → image."""
    return {
        nom: service["image"]
        for nom, service in lire_yaml(COMPOSE)["services"].items()
        if service.get("image") and not service.get("build")
    }


def instructions_dockerfile(source: str) -> list[tuple[str, str]]:
    """Les instructions d'un Dockerfile, continuations jointes et commentaires ôtés."""
    lignes, courante = [], ""
    for brute in source.replace("\r\n", "\n").split("\n"):
        if brute.lstrip().startswith("#"):
            continue
        if brute.rstrip().endswith("\\"):
            courante += brute.rstrip()[:-1] + " "
            continue
        courante += brute
        if courante.strip():
            lignes.append(courante.strip())
        courante = ""
    return [
        (m.group(1).upper(), m.group(2)) for m in (re.match(r"(\S+)\s*(.*)", x) for x in lignes)
    ]


def etape_finale(source: str) -> list[tuple[str, str]]:
    """Les instructions de la DERNIÈRE étape (`FROM` compris) : celle qui tourne."""
    instructions = instructions_dockerfile(source)
    debuts = [i for i, (mot, _) in enumerate(instructions) if mot == "FROM"]
    return instructions[debuts[-1] :] if debuts else []
