"""Comment un envoi quitte l'installation — par le relais de la plateforme (#2493, #2494).

Spécification : `specs/architecture/notifications-push.md` §2 et §4.

| Installation | Chemin |
|---|---|
| la référence | `utils/push/relais.transmettre`, en processus — sans requête vers elle-même, et sans bail (§4) |
| une réplique | `inscription/client.demander_notification` : la demande signée, le bail joint, au relais de la référence |
| une installation d'essai | rien ne part : la référence n'est jamais appelée (règle 9) |

Le relais refuse tant que le secret de la plateforme manque (compte de service FCM,
clé `.p8` d'Apple) : le service `notifications_push` est coupé par défaut, et la cloche
ne perd rien (N9). Les tests remplacent `TRANSPORT` par un double : aucun appel réseau
n'y part.

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


class TransportDeLInstallation:
    """Le chemin de CETTE installation vers le relais — relu à chaque envoi."""

    def transmettre(self, envoi: Envoi) -> Resultat:
        #  Imports tardifs : le relais et le client du registre importent ce module.
        from app.utils import installation

        if installation.est_reference():
            from app.utils.push import relais

            return relais.transmettre(envoi)
        from app.inscription import client

        try:
            reponse = client.demander_notification(envoi)
        except client.RegistreInjoignable as exc:
            return Resultat("refuse", str(exc))
        return Resultat(reponse.statut, reponse.motif)


#: Le transport en service — lu à chaque envoi, jamais réassigné par le code.
TRANSPORT: Transport = TransportDeLInstallation()

__all__ = ["Resultat", "Statut", "TRANSPORT", "Transport", "TransportDeLInstallation"]
