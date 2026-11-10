"""Le NIVEAU d'un périmètre — et le plafond que l'arborescence ne dépasse pas.

Demandé le 10/11/2026 : *« interdire de niveau 4 ou plus »*, et dans une affaire
*« autoriser un niveau 3 similaire au niveau précédent »*. L'exemple donné :

| Niveau | Nœud |
|---|---|
| 1 | Bâtiment 1 |
| 2 | Logement |
| 3 | Terrasses Balcons |

🔴 **Le niveau n'est pas la profondeur.** « Bâtiments » est une racine qui ne se
cible pas — un REGROUPEMENT — et il ne compte pas : « Bâtiment 1 », son enfant, est
au niveau 1 comme « Parking », racine sélectionnable. C'est la définition du premier
niveau du sélecteur (`perimetresNiveau1`, `#lib/perimetres/arbre`) et de la
qualification des libellés (`libelles._est_groupe_racine`) : ce qui fait une pastille
de tête à la saisie est au niveau 1 ici.

Les gestes d'administration qui POSENT un nœud — création, modification du parent ou
de `selectionnable`, flèche « descendre d'un niveau », copie sous d'autres parents —
demandent tous `refus_niveau` avant d'écrire, et la lecture de l'arbre sert
`niveau` et `niveaux_libres` pour que l'écran grise ce que le serveur refuserait.
Un nœud déjà trop profond (écrit avant la règle) n'est ni supprimé ni bloquant :
aucun geste ne peut en créer un de PLUS (`nouveaux_trop_profonds`).
"""

from typing import Optional

from app.models.perimetre import Perimetre

from .branche import descendants

#: Le niveau le plus profond qu'un périmètre peut occuper.
NIVEAU_MAX = 3


def _est_regroupement(n: Perimetre) -> bool:
    """Une racine qui ne se cible pas (« Bâtiments ») : elle ne compte pas de niveau."""
    return n.parent_id is None and not n.selectionnable


def niveau(noeud: Perimetre, par_id: dict[int, Perimetre]) -> int:
    """Le niveau d'un nœud : 1 pour une tête de rangée, 0 pour un regroupement.

    Borné par `vus` : un cycle écrit à la main ne doit pas suspendre la requête.
    """
    chaine: list[Perimetre] = []
    vus: set[int] = set()
    courant: Optional[Perimetre] = noeud
    while courant is not None and courant.id not in vus:
        vus.add(courant.id)
        chaine.append(courant)
        courant = par_id.get(courant.parent_id) if courant.parent_id is not None else None
    return sum(1 for n in chaine if not _est_regroupement(n))


def hauteur(noeud: Perimetre, noeuds: list[Perimetre]) -> int:
    """Combien de niveaux la branche de `noeud` compte SOUS lui (0 pour une feuille)."""
    #  `descendants` rend les parents avant leurs enfants : la profondeur du
    #  parent est toujours connue quand on lit celle de l'enfant.
    profondeurs = {noeud.id: 0}
    for n in descendants(noeud, noeuds):
        profondeurs[n.id] = profondeurs.get(n.parent_id, 0) + 1
    return max(profondeurs.values())


def niveaux_libres(noeud: Perimetre, par_id: dict[int, Perimetre]) -> int:
    """Combien de niveaux ce nœud peut encore porter sous lui — 0 : plus aucun enfant."""
    return max(0, NIVEAU_MAX - niveau(noeud, par_id))


def niveau_d_arrivee(
    selectionnable: bool, parent_id: Optional[int], par_id: dict[int, Perimetre]
) -> int:
    """Le niveau qu'aurait un nœud posé sous `parent_id`."""
    if parent_id is None:
        return 1 if selectionnable else 0
    parent = par_id.get(parent_id)
    return (niveau(parent, par_id) if parent is not None else 0) + 1


def refus_niveau(
    noeud: Optional[Perimetre],
    selectionnable: bool,
    parent_id: Optional[int],
    noeuds: list[Perimetre],
) -> Optional[str]:
    """Pourquoi poser ce nœud (et sa branche) sous `parent_id` dépasserait le plafond.

    `noeud` : le nœud déplacé ou copié — `None` pour une création, qui n'a pas de
    branche. Rend `None` quand le geste reste dans les niveaux permis.
    """
    par_id = {n.id: n for n in noeuds}
    arrivee = niveau_d_arrivee(selectionnable, parent_id, par_id)
    plus_profond = arrivee + (hauteur(noeud, noeuds) if noeud is not None else 0)
    if plus_profond <= NIVEAU_MAX:
        return None
    return (
        f"L'arborescence s'arrête au niveau {NIVEAU_MAX} : ce geste poserait un "
        f"périmètre au niveau {plus_profond}."
    )


def trop_profonds(noeuds: list[Perimetre]) -> set[int]:
    """Les identifiants des nœuds au-delà du plafond."""
    par_id = {n.id: n for n in noeuds}
    return {n.id for n in noeuds if niveau(n, par_id) > NIVEAU_MAX}


def nouveaux_trop_profonds(avant: set[int], noeuds: list[Perimetre]) -> Optional[str]:
    """Le refus d'une écriture qui ferait passer un nœud de PLUS au-delà du plafond.

    `avant` : `trop_profonds` lu avant l'écriture. Un nœud écrit avant la règle ne
    bloque pas une modification sans rapport — seul l'écart compte.
    """
    if trop_profonds(noeuds) - avant:
        return (
            f"L'arborescence s'arrête au niveau {NIVEAU_MAX} : cette modification "
            "ferait descendre un périmètre au-delà."
        )
    return None
