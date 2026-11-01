"""Une BRANCHE de l'arborescence — un nœud et tout ce qui vit sous lui.

Trois gestes d'administration la manipulent d'un bloc : la **duplication**
(« Bâtiment 1 » et ses espaces deviennent « Bâtiment 5 » et les mêmes espaces), la
**copie sous d'autres parents** (« Local vélos » posé d'un geste sous trois
bâtiments, même nom, mêmes caractéristiques) et la **suppression en cascade** (un
nœud et ses descendants, après confirmation).
Les règles vivent ici, en fonctions pures sur des lignes déjà lues, pour que la
lecture de l'arbre (`dupliquable`, `nb_descendants`) et le geste qui refuse
posent la MÊME question — jamais une copie de la règle dans la liste.
"""

from typing import Optional

from app.models.perimetre import Perimetre


def enfants_par_parent(noeuds: list[Perimetre]) -> dict[Optional[int], list[Perimetre]]:
    """Les enfants de chaque nœud, dans l'ordre d'affichage (`ordre`, puis `code`).

    Lu par la lecture de l'arbre ET par la branche : deux tris divergents sont
    un tri de trop.
    """
    enfants: dict[Optional[int], list[Perimetre]] = {}
    for n in noeuds:
        enfants.setdefault(n.parent_id, []).append(n)
    for liste in enfants.values():
        liste.sort(key=lambda n: (n.ordre, n.code))
    return enfants


def descendants(noeud: Perimetre, noeuds: list[Perimetre]) -> list[Perimetre]:
    """Tous les descendants de `noeud`, parents avant enfants (parcours en largeur).

    Borné par `vus` : un cycle en base — écrit à la main — ne doit pas suspendre
    la requête (`standards/04`).
    """
    enfants = enfants_par_parent(noeuds)

    sortie: list[Perimetre] = []
    vus: set[int] = {noeud.id}
    a_visiter = [noeud.id]
    while a_visiter:
        courant = a_visiter.pop(0)
        for enfant in enfants.get(courant, []):
            if enfant.id in vus:
                continue
            vus.add(enfant.id)
            sortie.append(enfant)
            a_visiter.append(enfant.id)
    return sortie


def refus_duplication(branche: list[Perimetre]) -> Optional[str]:
    """Pourquoi ce nœud ne se duplique pas — ou `None` s'il le peut.

    `branche` : les DESCENDANTS du nœud (sans lui).

    🔴 Un descendant rattaché à un bâtiment réel refuse la duplication. C'est ce
    lien qui décide QUI LIT un contenu ciblé (`batiments_cibles`) : recopié, il
    ferait lire aux résidents d'un bâtiment ce qui est publié pour un autre. Le
    nœud dupliqué, lui, reçoit son bâtiment de l'administrateur — un seul choix,
    dans la boîte ; plusieurs bâtiments d'un coup n'en auraient aucun de juste.
    """
    if not branche:
        return "Ce périmètre n'a pas de sous-périmètre à dupliquer."
    if any(n.batiment_id is not None for n in branche):
        return (
            "Cette branche contient des bâtiments : dupliquez-les un par un, chacun "
            "reçoit alors son propre bâtiment."
        )
    return None


def refus_copie(noeud: Perimetre, branche: list[Perimetre]) -> Optional[str]:
    """Pourquoi ce nœud ne se copie pas sous d'autres parents — ou `None` s'il le peut.

    `branche` : les DESCENDANTS du nœud (sans lui). La copie garde le libellé et
    toutes les caractéristiques : c'est « le local vélos » posé dans trois
    bâtiments d'un geste (01/11/2026). Une feuille se copie donc aussi.

    🔴 Rien de rattaché à un bâtiment réel : la copie le recopierait tel quel, et
    ferait lire aux résidents d'un bâtiment ce qui est publié pour un autre — la
    règle de `refus_duplication`. Sous son nouveau parent, la copie hérite du
    bâtiment de celui-ci par remontée de l'arbre, ce qui est le but.
    """
    if noeud.batiment_id is not None or any(n.batiment_id is not None for n in branche):
        return (
            "Ce périmètre est (ou contient) un bâtiment : il ne se copie pas sous "
            "d'autres périmètres. Dupliquez le bâtiment, il reçoit alors le sien."
        )
    return None


def code_copie(code_parent_source: str, code_parent_copie: str, code: str) -> str:
    """Le code d'un descendant dans la copie, dérivé de celui de son parent.

    `bat:1/hall` sous `bat:1` devient `batiments/batiment-5/hall` sous
    `batiments/batiment-5`. Un code qui ne prolonge pas celui de son parent —
    créé à la main — garde son dernier segment sous le nouveau parent.
    """
    prefixe = f"{code_parent_source}/"
    suffixe = code[len(prefixe) :] if code.startswith(prefixe) else code.rsplit("/", 1)[-1]
    return f"{code_parent_copie}/{suffixe}"


def codes_de_la_copie(
    noeud: Perimetre, branche: list[Perimetre], code_copie_racine: str
) -> dict[int, str]:
    """Le code de chaque nœud de la copie, par identifiant du nœud SOURCE.

    `branche` est rangée parents avant enfants (`descendants`) : le code d'un
    parent est donc toujours connu quand on dérive celui de ses enfants.
    """
    sources = {noeud.id: noeud, **{n.id: n for n in branche}}
    codes = {noeud.id: code_copie_racine}
    for n in branche:
        parent = sources[n.parent_id]
        codes[n.id] = code_copie(parent.code, codes[parent.id], n.code)
    return codes


#: Ce que la copie reprend de chaque nœud source, tel quel. Le code, le parent,
#: l'ordre de la tête, le libellé et la description de la tête, et le bâtiment
#: se décident à part — voir `routers/patrimoine.dupliquer_perimetre`.
CHAMPS_RECOPIES = (
    "libelle",
    "libelle_court",
    "description",
    "icone",
    "portee_globale",
    "selectionnable",
    "privatif",
    "hors_copropriete",
    "ordre",
    "actif",
)
