"""Le libellé d'un bâtiment — « Bât. A ».

## Pourquoi ce module (09/09/2026)

`f"Bât. {batiment.numero}"` était écrit **onze fois**, dans huit fichiers qui ne
se connaissent pas : les accès d'administration (×2), les profils (×2),
l'inscription (×2), les lots, l'import de lots (×2), les tickets, les réponses de
la communauté, et le bailleur — où la fonction qui le portait était elle-même
écrite **deux fois dans le même fichier**. Chacun portait son propre repli :
« — », `None`, ou « Sans bâtiment ».

Rien n'était encore faux : les onze écrivaient la même chose. C'est exactement ce
qui rend la duplication d'un libellé difficile à voir — elle ne se manifeste qu'au
premier changement, et alors sur les écrans qu'on a oubliés. Le projet l'a déjà
vécu trois fois : sur l'étage (treize écritures, un rez-de-chaussée invisible),
sur les rôles (« Conseil syndical » en trois formes, dont deux dans la même boîte
aux lettres) et sur le périmètre.

## 🔴 La divergence qui EXISTE, et qu'il ne faut pas « corriger » ici

L'arbre des périmètres nomme ses nœuds « Bât. **{id}** » (`seed/patrimoine.py`),
là où ces huit-ci écrivent « Bât. **{numero}** ». Or `Batiment.numero` est une
**chaîne** — « A », « B », « C » — et `id` un entier. Le même bâtiment s'affiche
donc « Bât. 1 » dans un badge de périmètre et « Bât. A » dans l'annuaire.

Ce n'est **pas** un oubli : `seed/patrimoine.py` le dit et le laisse en l'état —
*« "Bât. A" serait plus juste — mais ce serait un changement, et il appartient à »*
l'utilisateur. Rassembler les onze copies ici ne tranche pas cette question ; elle
rend seulement l'écart visible en **un** endroit au lieu de onze, pour le jour où
il se tranchera.

⚠️ Ne pas « unifier » les deux en passant : ce serait modifier ce qu'affichent les
badges de périmètre de toute la copropriété, sans que personne l'ait demandé.
"""

from __future__ import annotations

from typing import Optional
from app.utils.valeurs import valeur


def libelle_batiment(batiment) -> str:
    """« Bât. A » — ou une chaîne VIDE quand il n'y a pas de bâtiment.

    ⚠️ Vide, jamais « — » ni « Sans bâtiment » : c'est l'appelant qui décide de ce
    qu'il affiche à la place, et les onze sites d'origine en avaient trois avis
    différents. Même règle que `etage_label`, pour la même raison — un repli
    imposé ici s'imposerait à des écrans qui n'ont pas la même place ni le même
    lecteur.

    Accepte aussi bien un `Batiment` qu'un objet qui porte un `numero` (une ligne
    d'import, un dictionnaire converti) : c'est le `numero` qui fait le libellé,
    pas le type.
    """
    numero = getattr(batiment, "numero", None) if batiment is not None else None
    if numero is None or str(numero).strip() == "":
        return ""
    #  La forme, écrite une fois : un point après « Bât », une espace ordinaire
    #  et non insécable — c'est ce qu'employaient les onze copies, et en changer
    #  serait un changement d'affichage, pas une factorisation.
    #  La lettre de l'acte entre parenthèses, quand elle est saisie et diffère du
    #  numéro (« Bât. 1 (D) ») : c'est ce qui relie l'écran au règlement, et elle
    #  ne s'écrit qu'ici (#2212).
    lettre = str(getattr(batiment, "lettre_rcp", None) or "").strip()
    if lettre and lettre != str(numero).strip():
        return f"Bât. {numero} ({lettre})"
    return f"Bât. {numero}"


def libelle_batiment_ou(batiment, defaut: Optional[str]) -> Optional[str]:
    """Le libellé, ou `defaut` s'il n'y a pas de bâtiment.

    Écrit ici parce que les appelants faisaient tous ce `or`, avec trois valeurs
    de repli — le motif est commun, la valeur ne l'est pas.
    """
    return libelle_batiment(batiment) or defaut


__all__ = ["libelle_batiment", "libelle_batiment_ou"]


def libelle_lot(lot) -> Optional[str]:
    """« Appartement 314 » — le lot, tel qu'un humain le lit.

    ## Pourquoi cette fonction (12/09/2026)

    La même notion était écrite **quatre fois**, et celle qui n'avait pas de
    garde était la fautive :

        acces/resident.py   f"{lot.type} {lot.numero}"          ← « TypeLot.appartement 314 »
        admin/acces.py ×2   `.value` sous une garde `hasattr(…)`, sinon `str(…)`
        bailleur/acces.py   idem

    🔴 `f"{enum}"` rend `TypeLot.appartement`, pas `appartement` : la
    représentation Python de l'énumération a fui jusqu'à l'écran du conseil
    syndical, dans la colonne « Lot » de tous les badges de la copropriété.
    Signalé à l'écran, capture à l'appui.

    ⚠️ Les trois autres écritures étaient correctes — elles portaient toutes le
    `hasattr(lot.type, "value")` défensif que la quatrième avait oublié. C'est
    la forme la plus discrète de la duplication : trois copies justes rendent la
    quatrième invisible, puisque *« ça marche ailleurs »*.

    ⚠️ Ce tableau dit où la notion « libellé du lot » était écrite, pas que la
    garde `hasattr(…)` avait disparu : elle a survécu trois fois dans
    `admin/acces.py` (l'audit des rattachements) jusqu'au 02/10/2026, coupée
    sur deux lignes par `ruff format` et donc invisible au relevé ligne à
    ligne de `test_valeur_source_unique` (#1536). C'est `valeur()` désormais.

    ⚠️ La majuscule initiale est posée ICI : l'enum stocke `appartement` en
    minuscules, et trois écrans l'affichaient tel quel.
    """
    if not lot:
        return None
    #  `.value` quand c'est un enum, la chaîne sinon — une base migrée peut
    #  rendre l'un ou l'autre selon le chemin de lecture.
    type_lot = str(valeur(lot.type) or "")
    return f"{type_lot.capitalize()} {lot.numero}".strip()
