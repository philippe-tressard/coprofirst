"""Les DÉCISIONS de l'opérateur sur une installation inscrite (R4 #1880, spec §4.11).

Valider, suspendre, rétablir, résilier — et accorder des services. Chacune change ce
que le bail portera à son prochain renouvellement : la référence ne pousse jamais
(règle 5), l'installation le tire chaque nuit, ou à la demande de son administrateur.

## Les règles

1. **Une décision s'inscrit au journal** (qui, quand, quoi, pourquoi) — c'est le seul
   endroit où le registre change d'état autrement que par l'installation elle-même.
   Un geste sans motif est refusé : le journal dit POURQUOI, pas seulement quoi.
2. **Les transitions sont déclarées** (`TRANSITIONS`) : on ne valide qu'une inscription
   en attente, on ne rétablit qu'une installation suspendue. Résilier est définitif —
   l'installation retombe en mode limité, l'effacement de ses données revient à son
   exploitant (§4.11).
3. **La référence ne se décide pas** : elle figure dans son registre (règle 7), active,
   canal `main`, et aucun geste ne la touche.
4. **Les services accordés** sont ceux de `utils/services.SERVICES_AUTORISABLES`, et
   eux seuls — la même liste que l'installation lit.
5. **Supprimer ne s'offre qu'à une installation résiliée**, une fois (`supprimable`) :
   ce que le geste efface, et ce qu'il garde jusqu'à l'échéance des conditions,
   vit dans `registre/conservation.py`.
"""

from __future__ import annotations

import json

from sqlmodel import Session

from app.registre.modeles import (
    IDENTIFIANT_REFERENCE,
    DecisionRegistre,
    EtatInscription,
    Installation,
)
from app.utils import horloge
from app.utils.services import SERVICES_AUTORISABLES

#: L'auteur d'un geste fait par le registre lui-même, et non par l'opérateur.
SYSTEME = "système"

#: geste → (états de départ admis, état d'arrivée)
TRANSITIONS: dict[str, tuple[frozenset[EtatInscription], EtatInscription]] = {
    "valider": (frozenset({EtatInscription.en_attente}), EtatInscription.active),
    "suspendre": (frozenset({EtatInscription.active}), EtatInscription.suspendue),
    "retablir": (frozenset({EtatInscription.suspendue}), EtatInscription.active),
    "resilier": (
        frozenset({EtatInscription.en_attente, EtatInscription.active, EtatInscription.suspendue}),
        EtatInscription.resiliee,
    ),
}

#: Le geste qui accorde ou retire des services — il ne change pas l'état.
GESTE_SERVICES = "services"

#: Le geste qui retire une installation résiliée de la liste (`registre/conservation`)
#: — il ne change pas l'état non plus : elle reste résiliée.
GESTE_SUPPRIMER = "supprimer"


class DecisionRefusee(ValueError):
    """Le geste ne s'applique pas : le message dit pourquoi, en clair."""


def auteur_de(utilisateur_id: int | None) -> str:
    """L'auteur d'un geste au journal : un IDENTIFIANT, jamais un nom (données personnelles)."""
    return f"opérateur #{utilisateur_id}" if utilisateur_id else SYSTEME


def consigner(
    session: Session, inst: Installation, geste: str, motif: str = "", auteur: str = SYSTEME
) -> DecisionRegistre:
    """Inscrit une décision au journal de l'installation — la seule écriture du journal."""
    ligne = DecisionRegistre(installation_id=inst.id, geste=geste, motif=motif, auteur=auteur)
    session.add(ligne)
    return ligne


def services_de(inst: Installation) -> list[str]:
    """Les services accordés à `inst`, dans l'ordre du registre — illisible, aucun."""
    try:
        lus = json.loads(inst.services_autorises or "[]")
    except ValueError:
        return []
    return [code for code in SERVICES_AUTORISABLES if code in lus]


def exiger_motif(motif: str) -> str:
    motif = (motif or "").strip()
    if not motif:
        raise DecisionRefusee("Un motif est requis : le journal dit pourquoi.")
    return motif


def decidable(inst: Installation) -> bool:
    """L'opérateur peut-il décider de cette installation ? Pas de la référence (règle 3)."""
    return inst.identifiant != IDENTIFIANT_REFERENCE


def supprimable(inst: Installation) -> bool:
    """L'opérateur peut-il la supprimer ? Résiliée, pas la référence, pas déjà supprimée."""
    return decidable(inst) and inst.etat == EtatInscription.resiliee and inst.effacee_le is None


def gestes_possibles(inst: Installation) -> list[str]:
    """Les gestes qui s'appliquent à `inst` aujourd'hui — l'écran les lit."""
    if not decidable(inst):
        return []
    gestes = [geste for geste, (depart, _) in TRANSITIONS.items() if inst.etat in depart]
    return gestes + [GESTE_SUPPRIMER] if supprimable(inst) else gestes


def _exiger_pas_la_reference(inst: Installation) -> None:
    if not decidable(inst):
        raise DecisionRefusee("La référence ne se décide pas : elle reste active, canal main.")


def decider(
    session: Session, inst: Installation, geste: str, motif: str, auteur: str
) -> DecisionRegistre:
    """Applique un geste de `TRANSITIONS` à `inst`, et l'inscrit au journal."""
    if geste not in TRANSITIONS:
        raise DecisionRefusee(f"Geste inconnu : {geste}")
    _exiger_pas_la_reference(inst)
    motif = exiger_motif(motif)
    depart, arrivee = TRANSITIONS[geste]
    if inst.etat not in depart:
        raise DecisionRefusee(
            f"« {geste} » ne s'applique pas à une installation {inst.etat.value}."
        )
    inst.etat = arrivee
    inst.mis_a_jour_le = horloge.maintenant()
    session.add(inst)
    return consigner(session, inst, geste, motif, auteur)


def accorder_services(
    session: Session, inst: Installation, services: list[str], motif: str, auteur: str
) -> DecisionRegistre:
    """Fixe les services accordés à `inst` — ceux du registre seulement — et l'inscrit."""
    _exiger_pas_la_reference(inst)
    motif = exiger_motif(motif)
    inconnus = sorted(set(services) - set(SERVICES_AUTORISABLES))
    if inconnus:
        raise DecisionRefusee(f"Service(s) que la référence n'accorde pas : {', '.join(inconnus)}")
    accordes = [code for code in SERVICES_AUTORISABLES if code in services]
    inst.services_autorises = json.dumps(accordes)
    inst.mis_a_jour_le = horloge.maintenant()
    session.add(inst)
    texte = ", ".join(accordes) or "aucun"
    return consigner(session, inst, GESTE_SERVICES, f"{motif} — services : {texte}", auteur)
