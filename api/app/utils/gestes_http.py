"""Reconnaître un GESTE HTTP — `(méthode, chemin de route)` — dans une requête concrète.

Deux gardes à l'entrée des requêtes déclarent leurs gestes par le chemin de la
ROUTE (`/admin/utilisateurs/{user_id}`) et les reconnaissent sur le chemin
CONCRET (`/admin/utilisateurs/12`) : le mode démo (`utils/demo`, gestes FERMÉS) et
la suspension de l'installation (`inscription/suspension`, gestes laissés
OUVERTS). La lecture vivait dans `utils/demo` ; la seconde garde l'aurait
recopiée — elle est ici, une fois (R6 #1882).
"""

from __future__ import annotations

import re
from collections.abc import Iterable


def motif_de_route(chemin: str) -> re.Pattern[str]:
    """`/a/{id}/b` → l'expression qui reconnaît un chemin concret de cette route."""
    morceaux = re.split(r"(\{[^}]+\})", chemin)
    corps = "".join(
        (".+" if m.endswith(":path}") else "[^/]+") if m.startswith("{") else re.escape(m)
        for m in morceaux
    )
    return re.compile(f"^{corps}$")


def geste_concret(methode: str, chemin: str) -> tuple[str, str]:
    """La forme sous laquelle un geste se compare : `HEAD` vaut `GET`, sans `/` final."""
    return ("GET" if methode == "HEAD" else methode), (chemin.rstrip("/") or "/")


def indexer(gestes: Iterable[tuple[str, str]]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Les gestes déclarés, prêts à reconnaître un chemin concret."""
    return tuple((methode, motif_de_route(chemin)) for methode, chemin in gestes)


def reconnu(index: tuple[tuple[str, re.Pattern[str]], ...], methode: str, chemin: str) -> bool:
    """PURE : ce geste concret est-il l'un de ceux de l'index ?"""
    methode, chemin = geste_concret(methode, chemin)
    return any(m == methode and motif.match(chemin) for m, motif in index)
