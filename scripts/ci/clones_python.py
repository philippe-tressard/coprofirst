#!/usr/bin/env python3
"""Clones de code dans l'API Python — un PLAFOND décroissant, mesuré par jscpd (#1564).

## Pourquoi

Aucune mesure de duplication Python n'existait en CI : l'audit du 02/10/2026 a
compté 29 clones à la main (`npx jscpd`), dont sept duplications réelles, et rien
n'empêchait d'en écrire de nouvelles. Ce contrôle est le garde-fou
(`standards/05` §2) : il échoue dès qu'un clone s'AJOUTE, et aussi quand l'un
DISPARAÎT sans que le plafond baisse — sinon la marge libérée servirait à en
réintroduire un autre.

## Ce qui reste (6 au 02/10/2026) — des jumeaux légitimes, pas de la dette

Rien de ce qui reste n'est une règle écrite deux fois : ce sont des **déclarations**
que le langage force à répéter — le bloc d'imports d'un routeur voisin
(`admin/annuaire` ↔ `admin/profils`, `admin/arrivants` ↔ `admin/comptes`,
`calendrier` ↔ `publications`), l'en-tête d'un module jumeau
(`import_telecommandes` ↔ `import_vigiks`) et
deux signatures de fonctions qui doivent rester identiques
(`utils/whatsapp.py`, `utils/llm_fournisseurs.py`). Les factoriser ferait une
indirection de plus pour rien (`standards/02` §4 quater).

## Ce que mesure l'outil — et ce qu'il ne mesure pas

`jscpd app --min-tokens 50 --format python` : les clones EXACTS d'au moins 50
tokens. Il ne voit pas une logique réécrite avec d'autres noms — c'est ce que la
relecture et les contrôles « une notion, une source » (`test_*_source_unique.py`)
tiennent. La version de l'outil est épinglée : le compte dépend d'elle.

Usage : python scripts/ci/clones_python.py
    0 = le compte égale le plafond
    1 = plus de clones que le plafond (en ajouter un), ou moins (baisser le plafond)
    2 = INCONNU (npx absent, jscpd injoignable, rapport illisible)
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

#: 🔴 Ce nombre ne monte JAMAIS. Il descend quand un clone disparaît.
#: Carte des plafonds décroissants : #1571.
PLAFOND_CLONES = 6

#: ÉPINGLÉ : le compte change d'une version à l'autre de l'outil. Monter la
#: version = un lot dédié, qui relit le plafond.
JSCPD = "jscpd@5.4.0"

RACINE = pathlib.Path(__file__).resolve().parents[2]


def verdict(compte: int | None, plafond: int = PLAFOND_CLONES) -> tuple[int, str]:
    """Le code de sortie et le message, sans rien lire ni lancer (testable seul)."""
    if compte is None:
        return 2, "INCONNU : le nombre de clones n'a pas pu être mesuré."
    if compte > plafond:
        return 1, (
            f"{compte} clones pour un plafond de {plafond} : une duplication a été AJOUTÉE. "
            "Factoriser (`standards/02`), jamais relever le plafond."
        )
    if compte < plafond:
        return 1, (
            f"{compte} clones pour un plafond de {plafond} : baisser PLAFOND_CLONES à {compte} "
            "dans `scripts/ci/clones_python.py` — la marge libérée servirait à en écrire un autre."
        )
    return 0, f"OK : {compte} clones, égal au plafond."


def mesurer(cible: str = "app", dans: pathlib.Path = RACINE / "api") -> int | None:
    """Lance jscpd sur `cible` (par défaut `api/app`) et rend le nombre de clones, ou `None`."""
    npx = shutil.which("npx")
    if npx is None:
        return None
    with tempfile.TemporaryDirectory() as sortie:
        commande = [
            npx, "--yes", JSCPD, cible, "--min-tokens", "50", "--format", "python",
            "--reporters", "json", "--output", sortie, "--silent",
        ]  # fmt: skip
        try:
            subprocess.run(commande, cwd=dans, check=True, capture_output=True, timeout=600)
            rapport = json.loads((pathlib.Path(sortie) / "jscpd-report.json").read_text("utf-8"))
            return int(rapport["statistics"]["total"]["clones"])
        except (OSError, subprocess.SubprocessError, KeyError, ValueError):
            return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    code, message = verdict(mesurer())
    print(message)
    sys.exit(code)
