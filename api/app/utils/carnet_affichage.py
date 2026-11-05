"""Ce que l'écran du carnet d'entretien montre, rangé au serveur (#2505).

`utils/carnet_entretien` construit les FAITS du carnet. Ce module dit comment on
les MONTRE — trois règles que le site calculait dans le front et que l'app iOS,
qui ne recopie aucune règle du front, ne pouvait pas montrer :

1. **le filtre par année** (24/09/2026). Le décret n° 2001-477 (art. 4) date les
   travaux par leur « année de réalisation » et ne prévoit ni durée de
   conservation ni archivage : le carnet est CUMULATIF. D'où l'année civile,
   « Toutes » par défaut, et les **contrats** présents quelle que soit l'année —
   le décret veut ceux EN VIGUEUR (art. 3 et 4) : un contrat signé en 2019 vaut
   en 2026. Ce que vivait `#lib/carnet.ts`, tenu par `lint:carnet-annee` ;
2. **les années proposées** : celles des faits datés, sans les contrats, de la
   plus récente à la plus ancienne ;
3. **le regroupement par équipement** : chaque groupe garde l'ordre des entrées
   (du fait le plus récent au plus ancien), et les groupes se rangent par leur
   entrée la plus RÉCENTE — ce qui a bougé se lit en premier, l'équipement dont
   plus rien ne bouge tombe en bas, où il se remarque.
"""

from __future__ import annotations

from typing import Optional

from app.utils.equipements import libelle_dans

#: Le titre du groupe des entrées qu'aucun équipement ne range.
SANS_EQUIPEMENT = "Sans équipement rattaché"


def annees_du_carnet(entrees: list[dict]) -> list[str]:
    """Les années des faits datés, de la plus récente à la plus ancienne."""
    annees = {e["date"][:4] for e in entrees if e["origine"] != "contrat"}
    return sorted(annees, reverse=True)


def entrees_de_l_annee(entrees: list[dict], annee: Optional[str]) -> list[dict]:
    """Les entrées d'une année — `None` ou `""` : toutes. Les contrats restent."""
    return [
        e for e in entrees if not annee or e["origine"] == "contrat" or e["date"].startswith(annee)
    ]


def groupes_par_equipement(entrees: list[dict], libelles: dict[str, str]) -> list[dict]:
    """Les entrées rangées sous leur équipement, le groupe le plus récent d'abord.

    `entrees` arrive du fait le plus récent au plus ancien (`construire_carnet`) :
    la première entrée d'un groupe en est donc la plus récente. `libelles` est la
    table des équipements (`utils/equipements.libelles`), lue une fois.
    """
    par: dict[str, list[dict]] = {}
    for entree in entrees:
        par.setdefault(entree["equipement"] or "", []).append(entree)
    groupes = [
        {
            "equipement": code or None,
            "equipement_libelle": libelle_dans(libelles, code) if code else SANS_EQUIPEMENT,
            "entrees": liste,
        }
        for code, liste in par.items()
    ]
    #  Tri STABLE : à date égale, l'ordre d'apparition — celui du front.
    return sorted(groupes, key=lambda g: g["entrees"][0]["date"], reverse=True)
