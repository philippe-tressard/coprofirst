"""Un pourcentage servi s'arrondit par UNE porte : `utils/pourcentages` (#3104).

POURQUOI (24/11/2026) — #3060 a posé `part_en_pourcent` (demi au SUPÉRIEUR, en
arithmétique entière) pour la part d'un sondage. Quatre autres pourcentages de
l'API s'écrivaient à la main par `round(100 * x / y)`, qui arrondit au PAIR
(`round(12.5) == 12`) : le taux de retour des arrivants, le taux d'envoi d'un
formulaire, le taux d'adoption et la part d'un canal d'audience. Deux règles pour
une même notion, et un écran qui disait 12 % là où un autre aurait dit 13 %.

CE QUE CE TEST TIENT :

- `part_en_pourcent` rend sa valeur VIDE quand le total est nul — `0` par défaut,
  `None` pour un taux qui n'a pas de base (les trois `taux` la gardent) ;
- aucun `round(100 * …)` dans `api/app` hors de `utils/pourcentages.py`, sauf les
  exceptions DÉCLARÉES ci-dessous ; une exception qui cesse de servir échoue.
"""

from __future__ import annotations

import re
import subprocess

from app.utils.pourcentages import part_en_pourcent
from tests.aides_compose import RACINE

#: Un pourcentage arrondi à la main.
ARRONDI_A_LA_MAIN = re.compile(r"round\(\s*100\s*\*")

#: La seule porte.
PORTE = "api/app/utils/pourcentages.py"

#: Les exceptions, chacune avec sa raison : ce ne sont pas des pourcentages servis.
EXCEPTIONS = {
    "api/app/utils/suivi_affaires/pdf_barres.py": (
        "largeurs CSS d'un graphique en barres, à deux décimales — une géométrie, "
        "jamais un chiffre lu (#3104)"
    ),
}


def test_la_valeur_vide_se_choisit():
    assert part_en_pourcent(0, 0) == 0
    assert part_en_pourcent(0, 0, vide=None) is None
    assert part_en_pourcent(1, 8, vide=None) == 13, "le demi monte, même avec une valeur vide"


def _occurrences() -> dict[str, list[str]]:
    fichiers = subprocess.run(
        ["git", "ls-files", "--", "api/app/*.py"],
        cwd=RACINE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert len(fichiers) > 300, "la portée n'est pas lue en entier"  # cas zéro
    trouves: dict[str, list[str]] = {}
    for rel in fichiers:
        for numero, ligne in enumerate((RACINE / rel).read_text("utf-8").splitlines(), 1):
            if ARRONDI_A_LA_MAIN.search(ligne) and not ligne.lstrip().startswith("#"):
                trouves.setdefault(rel, []).append(f"{numero}: {ligne.strip()}")
    return trouves


def test_aucun_pourcentage_arrondi_a_la_main():
    trouves = _occurrences()
    fautes = {f: occ for f, occ in trouves.items() if f != PORTE and f not in EXCEPTIONS}
    assert not fautes, (
        "pourcentage arrondi par round() (au PAIR) — passer par "
        f"utils/pourcentages.part_en_pourcent : {fautes}"
    )
    inutiles = sorted(set(EXCEPTIONS) - set(trouves))
    assert not inutiles, f"exceptions qui ne servent plus, à retirer : {inutiles}"


def test_le_controle_voit_un_arrondi_a_la_main():
    """Témoin (`standards/04` §2) : les formes du 24/11 sont vues, la porte non."""
    for fautif in (
        '"taux": round(100 * revenus / connus) if connus else None,',
        "return round(100 * part / total) if total else 0",
        "round( 100*x/y)",
    ):
        assert ARRONDI_A_LA_MAIN.search(fautif), fautif
    for juste in ("part_en_pourcent(revenus, connus, vide=None)", "round(SEUIL * 100)"):
        assert not ARRONDI_A_LA_MAIN.search(juste), juste
