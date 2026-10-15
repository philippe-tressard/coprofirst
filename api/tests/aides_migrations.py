"""Charger une migration Alembic comme un module, écrit une fois (#1495).

Les migrations ne sont pas un paquet importable (`alembic/versions/` n'a pas de
`__init__.py`, et leurs noms commencent par un chiffre) : un test qui veut lire
leurs constantes passe par `importlib`. Ces quatre lignes étaient recopiées dans
chaque fichier qui en avait besoin.
"""

from __future__ import annotations

import importlib.util
import pathlib
from types import ModuleType

VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"


def chemin_migration(motif: str) -> pathlib.Path:
    """Le fichier de migration qui correspond à `motif` (`"0194_*.py"`, `"0243"`…), ou lève."""
    if not motif.endswith(".py"):
        motif = f"{motif}*.py"
    trouves = sorted(VERSIONS.glob(motif))
    assert len(trouves) == 1, f"`{motif}` désigne {len(trouves)} migration(s), il en faut une."
    return trouves[0]


def charger_migration(motif: str) -> ModuleType:
    """La migration désignée par `motif`, chargée comme un module."""
    chemin = chemin_migration(motif)
    spec = importlib.util.spec_from_file_location(f"migration_{chemin.stem}", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
