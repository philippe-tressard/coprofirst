"""Un constat sur des données : son code, sa gravité, son message, les lots qu'il cite.

La forme commune des constats du patrimoine — ceux de l'état descriptif avant son
application (`utils/etat_descriptif`, #2213) et ceux de l'onglet Lots de
l'administration (#2216) —, écrite une fois : deux écrans les rendent par le même
composant (`ConstatsLots.svelte`).

Les gravités, du plus fort au plus faible. `INCONNU` dit qu'un contrôle n'a pas pu
se calculer : il bloque comme un `BLOQUANT`, il ne vaut jamais OK (`standards/04`).
"""

from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel

BLOQUANT = "bloquant"
INCONNU = "inconnu"
AVERTISSEMENT = "avertissement"
INFORMATION = "information"


class Constat(BaseModel):
    code: str
    gravite: str
    message: str
    lots: list[str] = []


def constat(code: str, gravite: str, message: str, lots: Iterable[str] = ()) -> Constat:
    return Constat(code=code, gravite=gravite, message=message, lots=list(lots))


def applicable(constats: list[Constat]) -> bool:
    """Un seul bloquant ou un seul inconnu, et rien ne s'applique."""
    return not any(c.gravite in (BLOQUANT, INCONNU) for c in constats)
