"""La part d'un total en pour cent entier : une règle servie au site et aux apps (#3060).

Le pourcentage d'une option de sondage se calculait dans l'écran du site
(`ResultatsSondage.pct`, `Math.round`). Chaque app l'aurait recalculé, avec son
propre arrondi. Il se calcule ici, et les clients lisent le champ `part`.

**Arrondi au demi SUPÉRIEUR, en arithmétique entière** : c'est la règle de l'écran
(`Math.round`), gardée pour que les chiffres affichés ne bougent pas. 1 vote sur 8
fait 13 %. `round()` de Python arrondit au PAIR (`round(12.5) == 12`) : il en aurait
changé. Les parts s'arrondissent une à une, et leur somme peut faire 99 ou 101 %,
comme avant.
"""

from __future__ import annotations


def part_en_pourcent(nombre: int, total: int) -> int:
    """`nombre` sur `total`, en pour cent arrondi à l'entier ; 0 si le total est nul."""
    if total <= 0:
        return 0
    return (200 * nombre + total) // (2 * total)
