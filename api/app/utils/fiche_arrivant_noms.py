"""Un nom de la fiche d'accueil tient sur UNE ligne (#3144).

## Pourquoi on mesure

Le conseil s'imprime en quatre colonnes étroites : en 14,5 px, un nom de vingt-trois
caractères passait à la ligne, et le document remis à l'arrivant montrait « Mme
Christine » sur une ligne et son nom sur la suivante. Le navigateur qui imprime ne
sait pas réduire un texte pour qu'il tienne : la taille se décide donc ICI, avant
d'écrire le document, en mesurant chaque nom dans la police que la fiche embarque
(Atkinson Hyperlegible gras, la même que le lecteur verra).

## La règle, arbitrée sur maquette

1. Une taille COMMUNE à tous les noms d'un bloc, la plus grande où le plus long
   tient — au plus `PLAFOND`, jamais sous `PLANCHER` : des noms de tailles
   différentes côte à côte se liraient comme une hiérarchie qui n'existe pas.
2. Un nom qui ne tient toujours pas à cette taille — la photo du gestionnaire du
   site lui prend de la place — passe le prénom à son initiale : « M. J.-C. EXEMPLE ».
3. Un nom qui ne tient même pas abrégé est rendu tel quel et AUTORISÉ à passer à la
   ligne (`tient=False`) : couper un nom sur le papier, sans le dire, serait pire
   que deux lignes — c'est la faute de #3143.

Fonctions PURES : la place disponible vient de `fiche_arrivant_css.place_nom`, qui
la dérive des mêmes constantes que la feuille.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import NamedTuple

from app.utils.pdf_theme import fichier_police_lisible

logger = logging.getLogger(__name__)

#: La taille d'un nom quand la place ne manque pas, en px.
PLAFOND = 14.5
#: En dessous, on abrège le prénom plutôt que de réduire encore (9,4 pt).
PLANCHER = 12.5
#: L'approche des noms (`letter-spacing` de `.membre-nom`), en em.
APPROCHE_EM = -0.01
#: Ce que mesure un glyphe absent de la police, en em : large, pour ne jamais
#: promettre une place qu'il ne tiendra pas.
_GLYPHE_INCONNU_EM = 0.7
#: La marge d'arrondi entre la mesure et le rendu du navigateur, en px.
_JEU_PX = 1.0


class NomPose(NamedTuple):
    texte: str  #: en clair : l'appelant l'échappe
    tient: bool  #: False : le nom passe à la ligne plutôt que d'être coupé


@lru_cache(maxsize=1)
def _metriques() -> tuple[dict[int, str], dict[str, tuple[int, int]], int] | None:
    """(cmap, chasses, unités par em) du gras — None si la police est illisible.

    Mémorisé, y compris l'absence : le fichier fait partie de l'image, il ne
    reviendra pas sans un redéploiement (à la différence de `police_lisible_css`,
    qui sert le document et ne doit pas figer un échec passager).
    """
    try:
        from fontTools.ttLib import TTFont

        police = TTFont(fichier_police_lisible(700), lazy=True)
        return police.getBestCmap(), dict(police["hmtx"].metrics), police["head"].unitsPerEm
    except Exception as exc:  # noqa: BLE001 — une mesure manquante ne coûte pas la fiche
        logger.error("Police de mesure illisible (%s) — noms estimés", exc)
        return None


def largeur(texte: str, taille: float) -> float:
    """La largeur de `texte` en gras à `taille` px, approche comprise. PURE."""
    m = _metriques()
    if m is None:
        em = len(texte) * _GLYPHE_INCONNU_EM
    else:
        cmap, chasses, upm = m
        em = sum(
            chasses[cmap[ord(c)]][0] / upm if ord(c) in cmap else _GLYPHE_INCONNU_EM for c in texte
        )
    return (em + len(texte) * APPROCHE_EM) * taille


def nom_complet(genre: str, prenom: str, nom: str) -> str:
    """« M. Jean EXEMPLE » — en clair."""
    return " ".join(p for p in (genre.strip(), prenom.strip(), nom.strip().upper()) if p)


def initiales(prenom: str) -> str:
    """« Jean-Claude » → « J.-C. », « Marie Anne » → « M. A. ». PURE."""
    return re.sub(r"(\w)\w*\.?", r"\1.", prenom.strip())


def taille_commune(noms: list[tuple[str, float]]) -> float:
    """La taille, au dixième de px, où le plus long des `(texte, place)` tient. PURE."""
    if not noms:
        return PLAFOND
    ideale = min((place - _JEU_PX) / largeur(texte, 1.0) for texte, place in noms if texte)
    return max(PLANCHER, min(PLAFOND, int(ideale * 10) / 10))


def poser(genre: str, prenom: str, nom: str, taille: float, place: float) -> NomPose:
    """Le nom tel qu'il s'imprime à `taille` dans `place` px : entier, ou prénom abrégé."""
    entier = nom_complet(genre, prenom, nom)
    if largeur(entier, taille) <= place - _JEU_PX:
        return NomPose(entier, True)
    abrege = nom_complet(genre, initiales(prenom), nom)
    return NomPose(abrege, largeur(abrege, taille) <= place - _JEU_PX)
