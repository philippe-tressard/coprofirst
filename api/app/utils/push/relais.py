"""La TRANSMISSION du relais de la plateforme — chez la référence seule (#2494, #2789).

Spécification : `specs/architecture/notifications-push.md` §4 et §11. Une seule
fonction, `transmettre`, employée par les deux chemins du relais :

| Qui demande | Par où |
|---|---|
| une réplique | `POST /plateforme/notifications` (`registre/relais.py`), après ses gardes |
| la référence pour elle-même | en processus (`transport.TransportDeLInstallation`), sans bail (§4) |

## Les secrets, et leur absence

Posés dans le `.env` des deux nœuds de la référence par
`scripts/exploitation/poser-secret-push.sh`, jamais à la main :

| Plateforme | Réglages | Transport |
|---|---|---|
| `fcm` (Android) | `FCM_COMPTE_SERVICE` : le compte de service Google, JSON en base64 | `fcm.TransportFcm` |
| `apns` (iPhone) | `APNS_CLE` : la clé `.p8` d'Apple, en base64 ; `APNS_ID_CLE` : son identifiant | `apns.TransportApns` |

Absent ou illisible → `refuse`, et rien ne part. Le relais ne garde rien d'un envoi :
il transmet et oublie (N8). Chaque transport, lui, garde son jeton d'accès (une heure
au plus) — un état de PROCESSUS, qui ne porte aucune donnée de copropriété
(`DU_PROCESSUS` de `test_etat_module_par_copropriete.py`).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import Callable, Optional

from app.config import get_settings
from app.utils.push.apns import TransportApns
from app.utils.push.envoi import Envoi
from app.utils.push.fcm import TransportFcm
from app.utils.push.transport import Resultat, Transport

SANS_COMPTE_FCM = "le relais n'a pas de compte de service FCM (réglage FCM_COMPTE_SERVICE)"
SANS_CLE_APNS = "le relais n'a pas de clé APNs (réglages APNS_CLE et APNS_ID_CLE)"

#: Le transport de chaque plateforme, sous l'empreinte de ses réglages : des réglages
#: changés (l'API recréée) en construisent un autre ; les mêmes gardent leur jeton.
_transports: dict[str, tuple[str, Transport]] = {}


def _decoder(valeur: str) -> Optional[bytes]:
    if not valeur:
        return None
    try:
        return base64.b64decode(valeur, validate=True)
    except (ValueError, binascii.Error):
        return None


def compte_service_fcm(valeur: str) -> Optional[dict]:
    """PURE. Le compte de service que porte le réglage, ou None : vide ou illisible."""
    octets = _decoder(valeur)
    try:
        compte = json.loads(octets) if octets else None
    except ValueError:
        return None
    return compte if isinstance(compte, dict) else None


def cle_apns(valeur: str) -> Optional[str]:
    """PURE. La clé `.p8` (PEM) que porte le réglage, ou None : vide ou illisible."""
    octets = _decoder(valeur)
    try:
        pem = octets.decode("ascii") if octets else ""
    except UnicodeDecodeError:
        return None
    return pem if "PRIVATE KEY" in pem else None


def _fcm() -> Optional[Transport]:
    compte = compte_service_fcm(get_settings().fcm_compte_service)
    return TransportFcm(compte) if compte else None


def _apns() -> Optional[Transport]:
    reglages = get_settings()
    pem = cle_apns(reglages.apns_cle)
    return TransportApns(pem, reglages.apns_id_cle) if pem else None


#: Par plateforme : les réglages qui la décident, la fabrique du transport, le refus.
PLATEFORMES: dict[str, tuple[Callable[[], str], Callable[[], Optional[Transport]], str]] = {
    "fcm": (lambda: get_settings().fcm_compte_service, _fcm, SANS_COMPTE_FCM),
    "apns": (
        lambda: get_settings().apns_cle + "|" + get_settings().apns_id_cle,
        _apns,
        SANS_CLE_APNS,
    ),
}


def _transport(plateforme: str) -> Optional[Transport]:
    reglages, fabrique, _ = PLATEFORMES[plateforme]
    empreinte = hashlib.sha256(reglages().encode()).hexdigest()
    connu = _transports.get(plateforme)
    if connu and connu[0] == empreinte:
        return connu[1]
    try:
        transport = fabrique()
    except ValueError:
        transport = None
    if transport is None:
        return None
    _transports[plateforme] = (empreinte, transport)
    return transport


def transmettre(envoi: Envoi) -> Resultat:
    """Transmet `envoi` au service de sa plateforme — jamais ne lève pour un secret absent."""
    transport = _transport(envoi.plateforme)
    if transport is None:
        return Resultat("refuse", PLATEFORMES[envoi.plateforme][2])
    return transport.transmettre(envoi)


__all__ = [
    "PLATEFORMES",
    "SANS_CLE_APNS",
    "SANS_COMPTE_FCM",
    "cle_apns",
    "compte_service_fcm",
    "transmettre",
]
