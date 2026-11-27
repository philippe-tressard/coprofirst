"""Un nom de la fiche d'accueil s'écrit en entier, sur UNE ligne (#3144, #3151).

## Pourquoi on mesure

Le conseil s'imprime en quatre colonnes étroites : en 14,5 px, un nom de vingt-trois
caractères passait à la ligne, et le document remis à l'arrivant montrait « Mme
Christine » sur une ligne et son nom sur la suivante. Le navigateur qui imprime ne
sait pas réduire un texte pour qu'il tienne : la taille se décide donc ICI, avant
d'écrire le document, en mesurant chaque nom dans la police que la fiche embarque
(Atkinson Hyperlegible gras, la même que le lecteur verra).

## La règle, arbitrée sur maquette puis sur la fiche servie

1. Une taille COMMUNE à TOUS les noms du document — le conseil ET le syndic —, la
   plus grande où chacun tient dans la place que sa carte lui laisse, **photo
   comprise** — au plus `PLAFOND`, jamais sous `PLANCHER` : des noms de tailles
   différentes se liraient comme une hiérarchie qui n'existe pas. Jusqu'à #3151,
   chaque rangée avait la sienne, et le syndic s'imprimait plus gros que le conseil.
2. Un nom s'écrit toujours EN ENTIER, prénom compris. Le prénom ne s'abrège plus à
   son initiale (« M. J.-C. EXEMPLE », de #3144 à #3151) : c'est la taille qui cède.
3. Un nom qui ne tient pas même au plancher est AUTORISÉ à passer à la ligne
   (`tient=False`) : couper un nom sur le papier, sans le dire, serait pire que deux
   lignes — c'est la faute de #3143.

Fonctions PURES : la place disponible vient de `fiche_arrivant_css.place_nom`, qui
la dérive des mêmes constantes que la feuille.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import NamedTuple

from app.utils.pdf_theme import fichier_police_lisible

logger = logging.getLogger(__name__)

#: La taille d'un nom quand la place ne manque pas, en px.
PLAFOND = 14.5
#: En dessous, un nom passe à la ligne plutôt que de réduire encore (9,4 pt) —
#: loin du plancher de lisibilité de #2776 (10,5 px).
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


def taille_commune(noms: list[tuple[str, float]]) -> float:
    """La taille, au dixième de px, où chacun des `(texte, place)` tient. PURE.

    `place` est celle du nom, photo déduite : c'est le nom le plus SERRÉ qui
    décide, pas le plus long.
    """
    if not noms:
        return PLAFOND
    ideale = min((place - _JEU_PX) / largeur(texte, 1.0) for texte, place in noms if texte)
    return max(PLANCHER, min(PLAFOND, int(ideale * 10) / 10))


def poser(genre: str, prenom: str, nom: str, taille: float, place: float) -> NomPose:
    """Le nom tel qu'il s'imprime à `taille` dans `place` px : toujours entier."""
    entier = nom_complet(genre, prenom, nom)
    return NomPose(entier, largeur(entier, taille) <= place - _JEU_PX)
