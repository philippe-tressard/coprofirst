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


#: La chaîne de la base `plateforme` (registre des installations), à part de celle d'une copropriété.
VERSIONS_PLATEFORME = VERSIONS.parent.parent / "alembic_plateforme" / "versions"

#: Les DEUX chaînes de migrations (#2948) : celle d'une copropriété et celle de la
#: base `plateforme`. Un contrôle qui ne lit que la première laisse la seconde
#: hors de toute garde — ce qu'il était jusqu'au 23/11/2026.
CHAINES = {"copropriete": VERSIONS, "plateforme": VERSIONS_PLATEFORME}


def sources_des_chaines() -> dict[str, str]:
    """`<chaîne>/<fichier>` → source, pour chaque migration des deux chaînes.

    Cas zéro PAR chaîne : un dossier qui a bougé fait échouer, au lieu de rendre
    une chaîne vide qu'aucun relevé ne verrait."""
    sources = {}
    for nom, dossier in CHAINES.items():
        fichiers = sorted(dossier.glob("*.py"))
        assert fichiers, f"la chaîne `{nom}` ({dossier}) ne rend aucune migration"
        sources |= {f"{nom}/{f.name}": f.read_text(encoding="utf-8") for f in fichiers}
    return sources


def chemin_migration(motif: str, dossier: pathlib.Path | None = None) -> pathlib.Path:
    """Le fichier de migration qui correspond à `motif` (`"0194_*.py"`, `"0243"`…), ou lève.

    `dossier` : la chaîne ; par défaut celle d'une copropriété, lue À L'APPEL (un test
    peut remplacer `VERSIONS`)."""
    if not motif.endswith(".py"):
        motif = f"{motif}*.py"
    trouves = sorted((dossier or VERSIONS).glob(motif))
    assert len(trouves) == 1, f"`{motif}` désigne {len(trouves)} migration(s), il en faut une."
    return trouves[0]


def charger_migration(motif: str, dossier: pathlib.Path | None = None) -> ModuleType:
    """La migration désignée par `motif`, chargée comme un module."""
    chemin = chemin_migration(motif, dossier)
    spec = importlib.util.spec_from_file_location(f"migration_{chemin.stem}", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
