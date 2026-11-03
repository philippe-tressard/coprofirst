"""Comment un envoi quitte l'installation — une interface, que le relais remplira (#2493).

Le relais de la plateforme (lot P1, #2494) attend la clé `.p8` du compte Apple
Developer. D'ici là, `TRANSPORT` ne transmet rien et le dit : le service
`notifications_push` est coupé par défaut, et la cloche ne perd rien (N9). Les
tests remplacent `TRANSPORT` par un double : aucun appel réseau n'y part.

Ce que le relais répond (§4) : `envoye`, `jeton_perime` (l'installation retire
l'appareil) ou `refuse`, avec un motif en clair qui ne répète rien de la requête.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Protocol

from app.utils.push.envoi import Envoi

Statut = Literal["envoye", "jeton_perime", "refuse"]


@dataclass(frozen=True)
class Resultat:
    statut: Statut
    motif: str = ""
    #  L'identifiant qu'Apple rend pour un envoi accepté — journalisable (N8).
    apns_id: Optional[str] = None


class Transport(Protocol):
    def transmettre(self, envoi: Envoi) -> Resultat: ...


class RelaisNonBranche:
    """Le transport tant que le relais (P1) n'existe pas : il refuse, sans rien envoyer."""

    def transmettre(self, envoi: Envoi) -> Resultat:
        return Resultat("refuse", "le relais de la plateforme n'est pas encore branché (#2494)")


#: Le transport en service — lu à chaque envoi, jamais réassigné par le code.
TRANSPORT: Transport = RelaisNonBranche()

__all__ = ["RelaisNonBranche", "Resultat", "Statut", "TRANSPORT", "Transport"]
