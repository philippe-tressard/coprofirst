"""Ce qui part de l'installation vers le relais, et ce que le relais envoie à Apple (#2493).

Spécification : `specs/architecture/notifications-push.md` §3 (N4, N5) et §5.

## Un schéma FERMÉ

`Envoi` refuse tout champ inconnu : la minimisation se contrôle par le contrat,
pas par la bonne foi (N5). Il ne porte que l'appareil (jeton, environnement),
l'abonnement opaque, le NIVEAU — `urgent` pour les seuls avis urgents, décision
du 03/11/2026 —, l'horodatage et un nonce. Ni titre, ni type, ni nom, ni
identifiant d'utilisateur ou de notification : 🔒 `test_push_porte.py`.

## La charge FCM (#2789)

`charge_fcm` est son pendant pour Android : Firebase Cloud Messaging HTTP v1, le même
texte fixe, l'abonnement, la priorité haute pour un avis urgent seulement.

## La charge APNs

`charge_apns` est la seule écriture de ce qui part chez Apple — le relais la
composera par elle quand son transport APNs sera branché (#2494), jamais l'installation (N4). Un texte générique fixe,
l'abonnement, le niveau *time-sensitive* pour un avis urgent, et **aucune
pastille** (décision du 03/11/2026 : l'application la calcule à l'ouverture).
"""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Literal

import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.utils import horloge

#: Un jeton APNs : 32 octets en hexadécimal aujourd'hui ; Apple se réserve de l'allonger.
MOTIF_JETON = r"^[0-9a-fA-F]{64,200}$"
#: Un jeton d'enregistrement FCM (#2789) : base64 URL et « : », ~150 à 250 caractères ;
#: Google n'en garantit pas la longueur, la borne haute est large.
MOTIF_JETON_FCM = r"^[A-Za-z0-9_:-]{100,1024}$"
#: Le motif du jeton, par plateforme — une table, lue par l'envoi ET par la route.
MOTIFS_JETON = {"apns": MOTIF_JETON, "fcm": MOTIF_JETON_FCM}
#: L'abonnement tiré par l'application : aléatoire, sans signification hors du téléphone.
MOTIF_ABONNEMENT = r"^[A-Za-z0-9_-]{16,64}$"

Environnement = Literal["production", "developpement"]
Plateforme = Literal["apns", "fcm"]
Niveau = Literal["normal", "urgent"]

#: Le texte de la bannière — fixe, en français, jamais un réglage d'une installation (§5).
TITRE = "CoproFirst"
CORPS = "Vous avez une nouvelle notification."


def jeton_conforme(plateforme: str, jeton: str) -> bool:
    """PURE. Le jeton a-t-il la forme de celui de sa plateforme ?"""
    motif = MOTIFS_JETON.get(plateforme)
    return bool(motif and re.fullmatch(motif, jeton or ""))


class JetonDePlateforme(BaseModel):
    """Un jeton et sa plateforme, jugés ensemble — la base de l'envoi ET de la route
    `POST /appareils` (#2789) : le motif du jeton dépend de la plateforme."""

    #: `apns` par défaut : l'app iOS publiée avant #2789 ne l'envoie pas.
    plateforme: Plateforme = "apns"
    jeton: str = Field(max_length=1024)

    @model_validator(mode="after")
    def _jeton_de_sa_plateforme(self):
        if not jeton_conforme(self.plateforme, self.jeton):
            raise ValueError(f"jeton non conforme au motif de {self.plateforme}")
        return self


class Envoi(JetonDePlateforme):
    """La demande d'avertir UN appareil — rien de plus ne sort de l'installation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    environnement: Environnement
    abonnement: str = Field(pattern=MOTIF_ABONNEMENT)
    niveau: Niveau
    emis_le: datetime
    nonce: str


def envoi_pour(appareil, *, urgent: bool) -> Envoi:
    """L'envoi qui avertit `appareil` — horodaté et à usage unique (§4, point 5)."""
    return Envoi(
        plateforme=appareil.plateforme,
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


def charge_fcm(envoi: Envoi) -> dict:
    """PURE. Le message envoyé à FCM HTTP v1 (#2789) : le même texte fixe et le même
    abonnement qu'APNs (§5), la bannière regroupée par abonnement, la priorité haute pour
    un avis urgent seulement. Ni résidence, ni titre, ni type, ni nombre."""
    return {
        "message": {
            "token": envoi.jeton,
            "notification": {"title": TITRE, "body": CORPS},
            "data": {"a": envoi.abonnement},
            "android": {
                "collapse_key": envoi.abonnement,
                "priority": "high" if envoi.niveau == "urgent" else "normal",
            },
        }
    }


def entetes_apns(envoi: Envoi) -> dict[str, str]:
    """PURE. Les en-têtes APNs propres à l'envoi : une bannière par abonnement (§5)."""
    return {"apns-push-type": "alert", "apns-collapse-id": envoi.abonnement}


__all__ = [
    "CORPS",
    "Envoi",
    "JetonDePlateforme",
    "MOTIF_ABONNEMENT",
    "MOTIF_JETON",
    "MOTIF_JETON_FCM",
    "MOTIFS_JETON",
    "TITRE",
    "charge_apns",
    "charge_fcm",
    "jeton_conforme",
    "entetes_apns",
    "envoi_pour",
]
