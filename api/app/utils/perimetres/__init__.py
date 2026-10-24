"""Périmètres — l'arbre en base et son rendu, source unique du produit.

Aucun code de périmètre n'est écrit dans le produit : l'arborescence vit dans la
table `perimetre`, elle s'édite depuis `/admin/patrimoine`, et **la vider ne casse
rien** — un périmètre vide vaut « concerne tout le monde ».

🔴 **La surface publique NE BOUGE PAS.** Une quinzaine de modules et de tests
écrivent `from app.utils.perimetres import …` ; un découpage qui casse ses
importateurs n'est pas un découpage, c'est un déménagement à leurs frais.
"""

from .arbre import (
    Noeud,
    a_portee_globale,
    arbre,
    batiments_cibles,
    couvre,
    code_par_defaut,
    est_perimetre_par_defaut,
    invalider_cache,
    parse_json_perimetres,
    parse_perimetres,
    perimetre_cible_json,
    perimetre_defaut_liste,
    perimetre_defaut_texte,
    perimetre_du_batiment,
    sous_l_une_des_branches,
)
from .libelles import (
    SEPARATEUR_ELEMENT,
    SEPARATEUR_GROUPE,
    perimetre_label,
    perimetre_label_json,
    perimetre_label_liste,
    perimetre_label_un,
)

__all__ = [
    "Noeud",
    "SEPARATEUR_ELEMENT",
    "SEPARATEUR_GROUPE",
    "a_portee_globale",
    "arbre",
    "batiments_cibles",
    "code_par_defaut",
    "couvre",
    "est_perimetre_par_defaut",
    "invalider_cache",
    "parse_json_perimetres",
    "parse_perimetres",
    "perimetre_cible_json",
    "perimetre_defaut_liste",
    "perimetre_defaut_texte",
    "perimetre_du_batiment",
    "perimetre_label",
    "perimetre_label_json",
    "perimetre_label_liste",
    "perimetre_label_un",
    "sous_l_une_des_branches",
]
