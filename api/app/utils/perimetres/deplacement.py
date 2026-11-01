"""Déplacer un nœud dans l'arborescence — d'un rang, ou d'un niveau (01/11/2026).

Demandé à l'écran : *« on peut changer l'ordre avec les flèches du haut et du bas ;
ajouter la possibilité de monter ou descendre d'un niveau (flèches de gauche et de
droite) »*. Les quatre flèches d'un nœud posent la même question — où le ranger
parmi ses frères, et sous quel parent — et elle se répond ICI, en fonction pure sur
des lignes déjà lues :

| Flèche | Le nœud… |
|---|---|
| ↑ haut   | échange sa place avec le frère qui le précède |
| ↓ bas    | échange sa place avec le frère qui le suit |
| ← gauche | sort de son parent, et se range juste après lui |
| → droite | entre dans le frère qui le précède, en dernier de ses enfants |

C'est le geste d'un plan (un traitement de texte, un gestionnaire de fichiers) :
« droite » sans frère précédent n'a nulle part où aller, « gauche » à la racine
non plus.

🔴 **Le rang se renumérote dans la fratrie d'arrivée** (0, 1, 2…). Les flèches
écrivaient `ordre ± 1` : deux frères à `ordre` égal ne s'échangeaient pas — le tri
départage par le code, et le clic restait sans effet visible. Les lectures de
l'arbre (`GET /perimetres`, `dupliquable`) et le geste qui refuse lisent la même
fonction : l'écran ne grise une flèche que si le serveur la refuserait.
"""

from dataclasses import dataclass
from typing import Optional

from app.models.perimetre import Perimetre

from .branche import descendants, enfants_par_parent

SENS = ("haut", "bas", "gauche", "droite")


@dataclass(frozen=True)
class Deplacement:
    """Où le nœud arrive : son parent, et la fratrie d'arrivée dans l'ordre voulu."""

    parent_id: Optional[int]
    fratrie: list[Perimetre]


def _avec_batiment(noeuds: list[Perimetre]) -> bool:
    return any(n.batiment_id is not None for n in noeuds)


def _ancetres(parent_id: Optional[int], par_id: dict[int, Perimetre]) -> list[Perimetre]:
    """Le parent et tous ses ancêtres — bornés par `vus` (un cycle écrit à la main)."""
    sortie: list[Perimetre] = []
    vus: set[int] = set()
    courant = par_id.get(parent_id) if parent_id is not None else None
    while courant is not None and courant.id not in vus:
        vus.add(courant.id)
        sortie.append(courant)
        courant = par_id.get(courant.parent_id) if courant.parent_id is not None else None
    return sortie


def refus_deplacement(
    noeud: Perimetre, noeuds: list[Perimetre], sens: str, racine: Optional[str]
) -> Optional[str]:
    """Pourquoi ce déplacement n'a pas lieu — ou `None` s'il en a un.

    `racine` : le code du périmètre par défaut (`code_par_defaut`).
    """
    return _calculer(noeud, noeuds, sens, racine)[1]


def deplacement(
    noeud: Perimetre, noeuds: list[Perimetre], sens: str, racine: Optional[str]
) -> Optional[Deplacement]:
    """Le déplacement demandé, ou `None` s'il est refusé (`refus_deplacement` dit pourquoi)."""
    return _calculer(noeud, noeuds, sens, racine)[0]


def sens_admis(noeud: Perimetre, noeuds: list[Perimetre], racine: Optional[str]) -> list[str]:
    """Les flèches que le serveur accepterait pour ce nœud — ce que l'écran active."""
    return [s for s in SENS if _calculer(noeud, noeuds, s, racine)[0] is not None]


def _calculer(
    noeud: Perimetre, noeuds: list[Perimetre], sens: str, racine: Optional[str]
) -> tuple[Optional[Deplacement], Optional[str]]:
    if sens not in SENS:
        return None, f"Sens inconnu : {sens}."
    par_id = {n.id: n for n in noeuds}
    enfants = enfants_par_parent(noeuds)
    freres = [n for n in enfants.get(noeud.parent_id, []) if n.id != noeud.id]
    rang = [n.id for n in enfants.get(noeud.parent_id, [])].index(noeud.id)

    if sens in ("haut", "bas"):
        cible = rang - 1 if sens == "haut" else rang + 1
        if not 0 <= cible <= len(freres):
            return None, "Ce périmètre est déjà le premier." if sens == "haut" else (
                "Ce périmètre est déjà le dernier."
            )
        return Deplacement(noeud.parent_id, [*freres[:cible], noeud, *freres[cible:]]), None

    #  🔴 Changer de niveau la racine changerait le périmètre PAR DÉFAUT — celui
    #  que désigne tout contenu publié sans périmètre explicite (`code_par_defaut`).
    if racine is not None and noeud.code == racine:
        return None, "La racine de l'arborescence ne change pas de niveau."

    if sens == "gauche":
        parent = par_id.get(noeud.parent_id) if noeud.parent_id is not None else None
        if parent is None:
            return None, "Ce périmètre est déjà au premier niveau."
        nouveau_parent_id = parent.parent_id
        oncles = [n for n in enfants.get(nouveau_parent_id, []) if n.id != noeud.id]
        apres = [n.id for n in oncles].index(parent.id) + 1
        fratrie = [*oncles[:apres], noeud, *oncles[apres:]]
    else:
        if rang == 0:
            return None, "Aucun périmètre ne le précède : il n'a pas où descendre."
        precedent = enfants[noeud.parent_id][rang - 1]
        nouveau_parent_id = precedent.id
        fratrie = [*enfants.get(precedent.id, []), noeud]

    #  🔴 Un bâtiment ne se range pas dans un autre bâtiment : le lien au bâtiment
    #  réel décide QUI LIT (`batiments_cibles`, par remontée de l'arbre), et une
    #  branche à deux bâtiments empilés ferait lire à l'un ce qui vise l'autre.
    if _avec_batiment([noeud, *descendants(noeud, noeuds)]) and _avec_batiment(
        _ancetres(nouveau_parent_id, par_id)
    ):
        return None, "Un bâtiment ne se range pas dans un autre bâtiment."
    return Deplacement(nouveau_parent_id, fratrie), None
