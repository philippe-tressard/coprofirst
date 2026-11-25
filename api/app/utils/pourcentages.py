"""La part d'un total en pour cent entier : une règle servie au site et aux apps (#3060).

Le pourcentage d'une option de sondage se calculait dans l'écran du site
(`ResultatsSondage.pct`, `Math.round`). Chaque app l'aurait recalculé, avec son
propre arrondi. Il se calcule ici, et les clients lisent le champ `part`.

**Arrondi au demi SUPÉRIEUR, en arithmétique entière** : c'est la règle de l'écran
(`Math.round`), gardée pour que les chiffres affichés ne bougent pas. 1 vote sur 8
fait 13 %. `round()` de Python arrondit au PAIR (`round(12.5) == 12`) : il en aurait
changé. Les parts s'arrondissent une à une, et leur somme peut faire 99 ou 101 %,
comme avant.

Les autres pourcentages servis passent par la même porte (#3104) : le taux de retour
des arrivants, le taux d'envoi d'un formulaire, le taux d'adoption, la part d'un
canal d'audience. `round(100 * …)` est refusé ailleurs
(🔒 `test_pourcentages_une_porte.py`).
"""

from __future__ import annotations


def part_en_pourcent(nombre: int, total: int, vide: int | None = 0) -> int | None:
    """`nombre` sur `total`, en pour cent arrondi à l'entier ; `vide` si le total est nul.

    `vide` : `0` pour une part (aucun vote, aucune vue) ; `None` pour un taux qui n'a
    pas de base — l'écran dit « — », pas « 0 % »."""
    if total <= 0:
        return vide
    return (200 * nombre + total) // (2 * total)
