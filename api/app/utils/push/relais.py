"""La TRANSMISSION du relais de la plateforme — chez la référence seule (#2494, #2789).

Spécification : `specs/architecture/notifications-push.md` §4 et §11. Une seule
fonction, `transmettre`, employée par les deux chemins du relais :

| Qui demande | Par où |
|---|---|
| une réplique | `POST /plateforme/notifications` (`registre/relais.py`), après ses gardes |
| la référence pour elle-même | en processus (`transport.TransportDeLInstallation`), sans bail (§4) |

## Les secrets, et leur absence

- **FCM** : le compte de service du projet Firebase de CoproFirst, réglage
  `FCM_COMPTE_SERVICE` (le fichier JSON de Google en base64, sur une ligne), posé dans
  le `.env` des deux nœuds de la référence par `scripts/exploitation/poser-compte-fcm.sh`.
  Absent ou illisible → `refuse`, et rien ne part.
- **APNs** : la clé `.p8` n'existe pas encore (#2494) ; un appareil `apns` est refusé
  avec ce motif, jusqu'au lot qui branchera son transport.

Le relais ne garde rien d'un envoi : il transmet et oublie (N8). Le transport FCM, lui,
garde son jeton d'accès OAuth d'une heure — un état de PROCESSUS, qui ne porte aucune
donnée de copropriété (`DU_PROCESSUS` de `test_etat_module_par_copropriete.py`).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import Optional

from app.config import get_settings
from app.utils.push.envoi import Envoi
from app.utils.push.fcm import TransportFcm
from app.utils.push.transport import Resultat

SANS_COMPTE_FCM = "le relais n'a pas de compte de service FCM (réglage FCM_COMPTE_SERVICE)"
SANS_CLE_APNS = "le transport APNs n'est pas branché : la clé .p8 manque (#2494)"

#: Le transport FCM du compte en service, sous l'empreinte de son réglage : un réglage
#: changé (l'API recréée) en construit un autre ; le même garde son jeton d'accès.
_fcm: dict[str, TransportFcm] = {}


def compte_service_fcm(valeur: str) -> Optional[dict]:
    """PURE. Le compte de service que porte le réglage, ou None : vide ou illisible."""
    if not valeur:
        return None
    try:
        compte = json.loads(base64.b64decode(valeur, validate=True))
    except (ValueError, binascii.Error):
        return None
    return compte if isinstance(compte, dict) else None


def _transport_fcm() -> Optional[TransportFcm]:
    valeur = get_settings().fcm_compte_service
    cle = hashlib.sha256(valeur.encode()).hexdigest()
    if cle not in _fcm:
        compte = compte_service_fcm(valeur)
        if compte is None:
            return None
        try:
            transport = TransportFcm(compte)
        except ValueError:
            return None
        _fcm.clear()
        _fcm[cle] = transport
    return _fcm[cle]


def transmettre(envoi: Envoi) -> Resultat:
    """Transmet `envoi` au service de sa plateforme — jamais ne lève pour un secret absent."""
    if envoi.plateforme == "fcm":
        transport = _transport_fcm()
        return transport.transmettre(envoi) if transport else Resultat("refuse", SANS_COMPTE_FCM)
    return Resultat("refuse", SANS_CLE_APNS)


__all__ = ["SANS_CLE_APNS", "SANS_COMPTE_FCM", "compte_service_fcm", "transmettre"]
