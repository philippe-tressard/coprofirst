"""Les jetons de couleur du thème clair de `socle.css`, lus UNE fois (#2174, S2).

Le front désigne désormais ses teintes par un jeton (`var(--fil-rouge)`) : un test
qui mesure une couleur — le contraste d'une pastille, l'accord de l'écran et du
papier — doit la RÉSOUDRE, pas lire un littéral. Deux tests recopiaient chacun
sa lecture du fichier ; une seule vit ici.
"""

from __future__ import annotations

import pathlib
import re

SOCLE = pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "styles" / "socle.css"

_DECLARATION = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
_VAR = re.compile(r"^var\((--[\w-]+)\)$")


def jetons_du_theme_clair() -> dict[str, str]:
    """Nom → valeur brute, dans le premier bloc `:root` : le thème clair."""
    texte = SOCLE.read_text(encoding="utf-8")
    bloc = texte[texte.index(":root") :].split("\n}", 1)[0]
    jetons = {nom: valeur.strip() for nom, valeur in _DECLARATION.findall(bloc)}
    #  Cas zéro (`standards/04` §2) : un motif cassé rendrait un dictionnaire vide.
    assert len(jetons) >= 60, f"{len(jetons)} jeton(s) lu(s) dans socle.css — lecteur cassé"
    return jetons


def resoudre(valeur: str, jetons: dict[str, str] | None = None) -> str:
    """`var(--a)` → la valeur de `--a`, de renvoi en renvoi ; un littéral reste tel quel."""
    jetons = jetons if jetons is not None else jetons_du_theme_clair()
    vus: set[str] = set()
    while (m := _VAR.match(valeur.strip())) is not None:
        nom = m.group(1)
        assert nom in jetons, f"le jeton {nom} n'est défini nulle part dans socle.css"
        assert nom not in vus, f"renvoi circulaire autour de {nom}"
        vus.add(nom)
        valeur = jetons[nom]
    return valeur.strip()
