"""La nature d'un lot — la seule lecture de `Lot.nature` (#2212).

`nature` (l'état descriptif du règlement) précise `type` (appartement, cave,
parking) : c'est le premier temps d'une expansion, et un lot qui n'est pas encore
passé par l'import de l'état descriptif n'en a pas. Cette fonction répond pour lui,
en la déduisant de `type` — exactement ce que la migration 0312 a posé sur les lots
existants. Lire `lot.nature` en direct ferait diverger les deux le jour où l'un est
vide.
"""

from __future__ import annotations

from app.models.copropriete import NatureLot
from app.utils.valeurs import valeur

#: `type` → `nature`, pour un lot que l'état descriptif n'a pas encore désigné.
_NATURE_DU_TYPE = {
    "appartement": NatureLot.logement,
    "cave": NatureLot.cave,
    "parking": NatureLot.parking,
}

#: Les ANNEXES : un lot qu'on rejoint par une circulation, sans y vivre. Il ne fait
#: entrer aucun bâtiment dans « mes bâtiments » — le hall, le toit et les actualités
#: d'un bâtiment ne concernent pas qui y range sa voiture (spec §5 et §6).
NATURES_ANNEXES = frozenset({NatureLot.cave, NatureLot.parking})


def nature_du_lot(lot) -> NatureLot | None:
    """La nature déclarée, sinon celle que son type désigne ; `None` si rien ne la dit."""
    declaree = valeur(getattr(lot, "nature", None))
    if declaree:
        return NatureLot(declaree)
    return _NATURE_DU_TYPE.get(str(valeur(getattr(lot, "type", None)) or ""))


def est_annexe(lot) -> bool:
    """Une cave ou une place : desservie par une circulation, jamais un lieu de vie."""
    return nature_du_lot(lot) in NATURES_ANNEXES
