"""Lire une table PLATE du front — `NOM … = { cle: 'valeur', … }` — depuis Python.

## Pourquoi ce module (24/11/2026, #2947)

Les garde-fous qui confrontent une table du front à la liste de l'API lisaient
chacun la table à leur façon (`test_icones_evolution.py` avait la sienne). Trois
confrontations de plus allaient en écrire trois de plus : la lecture vit ici.

⚠️ La borne est la ligne qui COMMENCE par `}`, pas la première accolade fermante :
les valeurs du front portent des échappements `\\u{1F4AC}`, et un `\\{(.*?)\\}` non
gourmand s'arrêtait au milieu de la première (attrapé en exécutant le test, le
19/08/2026). Elle couvre `};` comme `} as const satisfies …;`.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.aides_routes_front import decoder_js

FRONT_LIB = Path(__file__).resolve().parents[2] / "front" / "src" / "lib"

_ENTREE = re.compile(r"^\s*'?([\w]+)'?\s*:\s*'([^']*)'", re.M)


def table_plate(fichier: str, nom: str) -> dict[str, str]:
    """La table `nom` de `front/src/lib/<fichier>`, clés et valeurs chaînes.

    Lève si la table est introuvable ou vide : un garde-fou qui ne trouve pas sa
    table ne surveille rien, et INCONNU vaut échec (`standards/04` §1).
    """
    source = (FRONT_LIB / fichier).read_text(encoding="utf-8")
    bloc = re.search(rf"\b{re.escape(nom)}\b[^=\n]*=\s*\{{(.*?)^\}}", source, re.S | re.M)
    assert bloc, f"`{nom}` est introuvable dans {fichier} : le contrôle ne surveille plus rien."
    table = {cle: decoder_js(valeur) for cle, valeur in _ENTREE.findall(bloc.group(1))}
    assert table, f"`{nom}` ({fichier}) se lit vide : sa forme a changé."
    return table
