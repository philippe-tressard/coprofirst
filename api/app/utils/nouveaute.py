"""« Est-ce nouveau ? » — le badge NEW d'une carte (#2506).

La règle vivait dans le front seulement (`isNouveau`, `#lib/date.ts`) : l'app
iOS, qui ne lit que le contrat de l'API, ne montrait aucun badge. Elle se
calcule donc ici, et chaque élément d'une liste la porte en `nouveau: bool`
(`standards/09` §8, règle 1).

⚠️ La date est celle de CRÉATION, jamais celle de modification : une correction
ne dit rien au lecteur, elle ne doit donc rien changer à ce qu'il voit
(signalé le 01/09/2026, la règle du front).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.utils import horloge

#: Combien de temps un élément reste « nouveau ».
DUREE_NOUVEAUTE = timedelta(hours=48)


def est_nouveau(cree_le: Optional[datetime], maintenant: Optional[datetime] = None) -> bool:
    """Vrai si `cree_le` (UTC naïf, comme la base) date de moins de 48 h."""
    if cree_le is None:
        return False
    instant = maintenant if maintenant is not None else horloge.maintenant()
    return instant - cree_le < DUREE_NOUVEAUTE
