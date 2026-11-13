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

Corriger une Suite ANCIENNE ne doit pas défaire un état RÉCENT : une transition
qui la SUIT dans le fil garde la main, et l'affaire ne bouge pas.

## La dernière transition part de l'état réel (#2715, 13/11/2026)

La règle exigeait aussi que l'affaire soit encore dans l'état que la Suite lui
avait donné. Or un état se pose hors du fil — le crayon du titre écrit une
« Correction : État … » sans transition, la création en lot naît « Chez le
prestataire » sans Suite. Corriger la dernière Suite en « Résolu » laissait alors
l'affaire « Chez le prestataire », sans un mot (TK-E00066). Arbitré : quand la
Suite corrigée est la dernière transition et qu'elle DONNE un état, l'affaire le
prend, quel que soit l'état réel. Ramenée à un commentaire, elle ne fait pas
revenir l'affaire à l'état ancien du fil — ce serait écraser le plus récent.

Ce qui n'est pas répercuté se DIT : la route sert `affaire_suivie` (False) et
l'écran propose d'appliquer l'état (`suite_sections.corriger_suivi`).

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
    *,
    devient_transition: bool,
) -> bool:
    """L'affaire doit-elle suivre la correction du Suivi de cette entrée ?

    Jamais si une transition la SUIT dans le fil. Sinon, oui si l'affaire est
    encore dans l'état que l'entrée lui donnait AVANT d'être corrigée
    (`resultat_avant`) — ou si l'entrée corrigée DONNE un état
    (`devient_transition`) : l'état réel, posé hors du fil, cède alors (#2715).

    ⚠️ Cas zéro : entrée sans identifiant ou absente du fil → `False`. La valeur
    sûre est celle qui n'écrit pas.
    """
    if entree_id is None or entree_id not in [e.id for e in fil]:
        return False
    if suivie_d_une_transition(entree_id, fil):
        return False
    return statut_affaire == resultat_avant or devient_transition


def suivie_d_une_transition(entree_id: Optional[int], fil: Sequence[Any]) -> bool:
    """Une transition SUIT-elle cette entrée dans le fil ? Absente : non."""
    ids = [e.id for e in fil]
    if entree_id not in ids:
        return False
    return any(getattr(e, "type", None) == "etat" for e in fil[ids.index(entree_id) + 1 :])


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
    assert doit_propager_statut(4, "résolu", fil, "résolu", devient_transition=True)
    assert not doit_propager_statut(2, "en_cours", fil, "résolu", devient_transition=True)
    #  5. Un commentaire après la dernière transition propage aussi (il en devient une).
    assert doit_propager_statut(3, "en_cours", [c1, t2, c3], "en_cours", devient_transition=True)
    #  6. L'état réel, posé hors du fil (crayon du titre, lot), cède à la dernière
    #     transition (#2715)…
    assert doit_propager_statut(4, "résolu", fil, "chez_prestataire", devient_transition=True)
    #     …mais la ramener à un commentaire ne fait pas revenir l'état ancien du fil.
    assert not doit_propager_statut(4, "résolu", fil, "fermé", devient_transition=False)
    #     Dans l'état qu'elle donnait, la ramener à un commentaire propage, comme avant.
    assert doit_propager_statut(4, "résolu", fil, "résolu", devient_transition=False)
    #  7. Cas zéro.
    assert not doit_propager_statut(None, "résolu", fil, "résolu", devient_transition=True)
    assert not doit_propager_statut(9, "résolu", fil, "résolu", devient_transition=True)
    assert suivie_d_une_transition(3, fil) and not suivie_d_une_transition(4, fil)
    assert resultat(t4, "en_cours") == "résolu" and resultat(c3, "en_cours") == "en_cours"
    print("OK suivi_fil : 17 cas verifies.")


if __name__ == "__main__":
    _selftest()
