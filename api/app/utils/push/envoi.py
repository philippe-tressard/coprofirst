"""Ce qui part de l'installation vers le relais, et ce que le relais envoie à Apple (#2493).

Spécification : `specs/architecture/notifications-push.md` §3 (N4, N5) et §5.

## Un schéma FERMÉ

`Envoi` refuse tout champ inconnu : la minimisation se contrôle par le contrat,
pas par la bonne foi (N5). Il ne porte que l'appareil (jeton, environnement),
l'abonnement opaque, le NIVEAU — `urgent` pour les seuls avis urgents, décision
du 03/11/2026 —, l'horodatage et un nonce. Ni titre, ni type, ni nom, ni
identifiant d'utilisateur ou de notification : 🔒 `test_push_porte.py`.

## La charge APNs

`charge_apns` est la seule écriture de ce qui part chez Apple — le relais (P1,
#2494) la composera par elle, jamais l'installation (N4). Un texte générique fixe,
l'abonnement, le niveau *time-sensitive* pour un avis urgent, et **aucune
pastille** (décision du 03/11/2026 : l'application la calcule à l'ouverture).
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.utils import horloge

#: Un jeton APNs : 32 octets en hexadécimal aujourd'hui ; Apple se réserve de l'allonger.
MOTIF_JETON = r"^[0-9a-fA-F]{64,200}$"
#: L'abonnement tiré par l'application : aléatoire, sans signification hors du téléphone.
MOTIF_ABONNEMENT = r"^[A-Za-z0-9_-]{16,64}$"

Environnement = Literal["production", "developpement"]
Niveau = Literal["normal", "urgent"]

#: Le texte de la bannière — fixe, en français, jamais un réglage d'une installation (§5).
TITRE = "CoproFirst"
CORPS = "Vous avez une nouvelle notification."


class Envoi(BaseModel):
    """La demande d'avertir UN appareil — rien de plus ne sort de l'installation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jeton: str = Field(pattern=MOTIF_JETON)
    environnement: Environnement
    abonnement: str = Field(pattern=MOTIF_ABONNEMENT)
    niveau: Niveau
    emis_le: datetime
    nonce: str


def envoi_pour(appareil, *, urgent: bool) -> Envoi:
    """L'envoi qui avertit `appareil` — horodaté et à usage unique (§4, point 5)."""
    return Envoi(
        jeton=appareil.jeton,
        environnement=appareil.environnement,
        abonnement=appareil.abonnement,
        niveau="urgent" if urgent else "normal",
        emis_le=horloge.maintenant(),
        nonce=secrets.token_urlsafe(16),
    )


def charge_apns(envoi: Envoi) -> dict:
    """PURE. Le corps envoyé à APNs : texte fixe, abonnement, niveau — aucune pastille."""
    aps: dict = {"alert": {"title": TITRE, "body": CORPS}, "sound": "default"}
    if envoi.niveau == "urgent":
        #  Traverse le mode Concentration : réservé aux avis urgents (décision du 03/11/2026).
        aps["interruption-level"] = "time-sensitive"
    return {"aps": aps, "a": envoi.abonnement}


def entetes_apns(envoi: Envoi) -> dict[str, str]:
    """PURE. Les en-têtes APNs propres à l'envoi : une bannière par abonnement (§5)."""
    return {"apns-push-type": "alert", "apns-collapse-id": envoi.abonnement}


__all__ = [
    "CORPS",
    "Envoi",
    "MOTIF_ABONNEMENT",
    "MOTIF_JETON",
    "TITRE",
    "charge_apns",
    "entetes_apns",
    "envoi_pour",
]
