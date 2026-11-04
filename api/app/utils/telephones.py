"""Les numéros d'un champ téléphone — découpés une fois, au serveur (#2505).

Un champ téléphone porte parfois plusieurs numéros séparés par des virgules
(« 01 23 45 67 89, 06 12 34 56 78 »). Le site les découpait dans le front
(`telephonesDe`, `#lib/utils`) ; l'app iOS, qui ne recopie aucune règle du
front, n'avait que la chaîne brute. Le serveur sert donc la liste
(`telephones`) : chaque client en fait un lien d'appel par numéro.

Dédoublonnée et sans vide, comme le front : un numéro saisi deux fois ne
s'affiche qu'une fois, et la liste sert de clé de rendu sans collision.
"""

from __future__ import annotations

from typing import Optional


def telephones_de(champ: Optional[str]) -> list[str]:
    """« 01 23, 06 45, 01 23, » → `["01 23", "06 45"]` — l'ordre de saisie, sans doublon."""
    vus: dict[str, None] = {}
    for brut in (champ or "").split(","):
        numero = brut.strip()
        if numero:
            vus.setdefault(numero, None)
    return list(vus)
