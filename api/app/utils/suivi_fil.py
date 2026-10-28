"""Corriger le Suivi qu'une Suite a enregistré, sans raturer le fil.

## La demande (01/10/2026, à l'écran)

> *« l'édition d'une suite doit permettre de modifier toutes les sections
> éditables et surtout le suivi »*

Arbitré le même jour : **corriger l'entrée**. La Suite garde sa date et son
auteur ; son état est corrigé — un commentaire peut devenir une transition, et
revenir à l'état d'avant la ramène à un commentaire.

## 🔴 Ce que cela renverse, et pourquoi c'est tenable

« Une correction n'est jamais une transition » (#431, #433) protégeait le fil
d'une étape que l'affaire n'a jamais franchie : corriger un TEXTE ne doit pas
rejouer la transition qu'il porte. Cette règle tient toujours pour le `PATCH`
d'une AFFAIRE (`test_correction_pas_transition.py`). Ce qui change ici est
l'objet corrigé : la Suite elle-même. Corriger « → En cours » en « → Résolu »,
c'est réécrire l'étape à la date où elle a été saisie — pas en ajouter une.

## ⚠️ La subtilité, la même que pour le périmètre (`perimetre_fil.py`)

Corriger une Suite ANCIENNE ne doit pas défaire un état RÉCENT. L'affaire suit
la correction seulement si cette Suite est la dernière transition du fil, ET si
l'affaire est encore dans l'état que la Suite lui avait donné — un état posé
depuis par l'édition de l'affaire (« Correction : État … ») n'est pas une
transition du fil, et ne doit pas être écrasé en silence.

Les trois règles sont pures, et se vérifient par `--selftest`.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence


def statuts_avant(fil: Sequence[Any], statut_affaire: str) -> dict[int, str]:
    """L'état en vigueur JUSTE AVANT chaque entrée du fil, par identifiant.

    `fil` est dans l'ordre chronologique. Avant la première transition, l'état
    est celui qu'elle quittait ; un fil sans transition n'a jamais changé
    d'état, donc c'est celui de l'affaire. Une transition dit elle-même d'où
    elle part (`ancien_statut`) : c'est un fait enregistré, il prime.

    ⚠️ C'est ce que l'écran montre comme « l'état d'avant » : la pastille qui,
    choisie, ramène la Suite à un commentaire. Le serveur le calcule une fois et
    le livre (`TicketEvolutionRead.statut_avant`) — l'écran n'en a pas de copie.
    """
    transitions = [e for e in fil if getattr(e, "type", None) == "etat"]
    courant = (
        getattr(transitions[0], "ancien_statut", None) or statut_affaire
        if transitions
        else statut_affaire
    )
    avant: dict[int, str] = {}
    for e in fil:
        if getattr(e, "type", None) == "etat":
            courant = getattr(e, "ancien_statut", None) or courant
        avant[e.id] = courant
        if getattr(e, "type", None) == "etat" and getattr(e, "nouveau_statut", None):
            courant = e.nouveau_statut
    return avant


def suivi_corrige(
    statut_avant: str, type_demande: str, statut_demande: Optional[str]
) -> tuple[str, Optional[str], Optional[str]]:
    """Ce que la Suite devient : `(type, ancien_statut, nouveau_statut)`.

    Le geste se DÉDUIT, comme à la saisie (`typeDeLEntree`, `#lib/evolutions`) :
    choisir l'état d'avant, c'est ne rien faire avancer — la Suite est alors un
    commentaire.
    """
    if type_demande == "etat" and statut_demande and statut_demande != statut_avant:
        return "etat", statut_avant, statut_demande
    return "commentaire", None, None


def resultat(entree: Any, statut_avant: str) -> str:
    """L'état dans lequel cette entrée laisse l'affaire."""
    if getattr(entree, "type", None) == "etat" and getattr(entree, "nouveau_statut", None):
        return entree.nouveau_statut
    return statut_avant


def doit_propager_statut(
    entree_id: Optional[int],
    resultat_avant: str,
    fil: Sequence[Any],
    statut_affaire: str,
) -> bool:
    """L'affaire doit-elle suivre la correction du Suivi de cette entrée ?

    Oui si aucune transition ne la SUIT dans le fil, et si l'affaire est encore
    dans l'état que l'entrée lui donnait AVANT d'être corrigée (`resultat_avant`).

    ⚠️ Cas zéro : entrée sans identifiant ou absente du fil → `False`. La valeur
    sûre est celle qui n'écrit pas.
    """
    if entree_id is None:
        return False
    ids = [e.id for e in fil]
    if entree_id not in ids:
        return False
    suivantes = fil[ids.index(entree_id) + 1 :]
    if any(getattr(e, "type", None) == "etat" for e in suivantes):
        return False
    return statut_affaire == resultat_avant


def _selftest() -> None:
    class E:
        def __init__(self, id, type, ancien=None, nouveau=None):
            self.id, self.type = id, type
            self.ancien_statut, self.nouveau_statut = ancien, nouveau

    c1 = E(1, "commentaire")
    t2 = E(2, "etat", "ouvert", "en_cours")
    c3 = E(3, "commentaire")
    t4 = E(4, "etat", "en_cours", "résolu")
    fil = [c1, t2, c3, t4]
    #  1. L'état d'avant : la première transition dit d'où elle part.
    assert statuts_avant(fil, "résolu") == {1: "ouvert", 2: "ouvert", 3: "en_cours", 4: "en_cours"}
    #  2. Un fil sans transition n'a jamais changé d'état.
    assert statuts_avant([c1, c3], "en_cours") == {1: "en_cours", 3: "en_cours"}
    #  3. Choisir l'état d'avant ramène à un commentaire ; un autre en fait une transition.
    assert suivi_corrige("ouvert", "etat", "ouvert") == ("commentaire", None, None)
    assert suivi_corrige("ouvert", "etat", "résolu") == ("etat", "ouvert", "résolu")
    assert suivi_corrige("ouvert", "commentaire", "résolu") == ("commentaire", None, None)
    #  4. La dernière transition propage ; une ancienne ne défait pas la récente.
    assert doit_propager_statut(4, "résolu", fil, "résolu")
    assert not doit_propager_statut(2, "en_cours", fil, "résolu")
    #  5. Un commentaire après la dernière transition propage aussi (il en devient une).
    assert doit_propager_statut(3, "en_cours", [c1, t2, c3], "en_cours")
    #  6. L'affaire a changé d'état depuis, hors fil : on ne l'écrase pas.
    assert not doit_propager_statut(4, "résolu", fil, "fermé")
    #  7. Cas zéro.
    assert not doit_propager_statut(None, "résolu", fil, "résolu")
    assert not doit_propager_statut(9, "résolu", fil, "résolu")
    assert resultat(t4, "en_cours") == "résolu" and resultat(c3, "en_cours") == "en_cours"
    print("OK suivi_fil : 13 cas verifies.")


if __name__ == "__main__":
    _selftest()
