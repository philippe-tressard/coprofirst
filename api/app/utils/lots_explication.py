"""La phrase qui explique ce qu'un lot emporte — écrite une fois, côté serveur (#2215).

« Cette place (SS 2) est desservie par Bât. 3 › Ascenseur et Bât. 3 › Escaliers.
Elle contribue aux charges Générales pour 8/10 000 et Ascenseur A pour 34/10 000. »

Un résident du bâtiment 1 qui paie l'ascenseur du bâtiment 3 doit pouvoir le lire
sans ouvrir le règlement (spec `lots-et-perimetres.md` §9). L'écran la rend telle
quelle : un gabarit recomposé dans une page divergerait de celui-ci au premier
accord oublié. L'application EXPLIQUE la charge ; elle ne la calcule pas.
"""

from __future__ import annotations

from typing import Optional

from app.models.copropriete import NatureLot
from app.utils.etages import etage_label
from app.utils.montants import montant_fr

#: Le sujet de la phrase et son accord : (« Cette place », féminin ?).
_SUJETS: dict[Optional[NatureLot], tuple[str, bool]] = {
    NatureLot.logement: ("Ce logement", False),
    NatureLot.commerce: ("Ce commerce", False),
    NatureLot.cave: ("Cette cave", True),
    NatureLot.parking: ("Cette place", True),
    NatureLot.divers: ("Ce lot", False),
    None: ("Ce lot", False),
}


def _liste(elements: list[str]) -> str:
    """« A », « A et B », « A, B et C »."""
    if len(elements) <= 1:
        return "".join(elements)
    return ", ".join(elements[:-1]) + " et " + elements[-1]


def phrase(
    nature: Optional[NatureLot],
    etage: Optional[int],
    desservi_par: list[str],
    quotes: Optional[list[tuple[str, int, int]]],
) -> Optional[str]:
    """La phrase, ou `None` s'il n'y a rien à expliquer — fonction PURE.

    `desservi_par` : les libellés des nœuds de circulation ; `quotes` : les
    `(libellé, numérateur, dénominateur)` que le lecteur a le droit de voir, `None`
    sinon (la phrase s'arrête alors à la desserte).
    """
    sujet, feminin = _SUJETS.get(nature, _SUJETS[None])
    if nature in (NatureLot.cave, NatureLot.parking) and etage is not None:
        sujet = f"{sujet} ({etage_label(etage)})"
    morceaux = []
    if desservi_par:
        accord = "desservie" if feminin else "desservi"
        morceaux.append(f"{sujet} est {accord} par {_liste(desservi_par)}.")
    if quotes:
        pronom = ("Elle" if feminin else "Il") if morceaux else sujet
        parts = [
            f"{libelle} pour {montant_fr(n, '')}/{montant_fr(d, '')}" for libelle, n, d in quotes
        ]
        morceaux.append(f"{pronom} contribue aux charges {_liste(parts)}.")
    return " ".join(morceaux) or None
