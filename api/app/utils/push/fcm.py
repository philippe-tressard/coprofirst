"""Le transport vers Firebase Cloud Messaging HTTP v1 — l'avertissement d'un téléphone Android (#2789).

Spécification : `specs/architecture/notifications-push.md` §4 et §5. Comme la clé `.p8`
d'Apple (N1), le **compte de service** du projet Firebase de CoproFirst n'est détenu que
par la RÉFÉRENCE — jamais une installation, jamais le dépôt. Ce transport est celui que
le relais de la plateforme (#2494) emploiera pour un appareil `fcm` ; tant qu'il n'est pas
branché, `transport.TRANSPORT` reste `RelaisNonBranche` et rien ne part.

## Le geste

1. Un jeton d'accès OAuth 2.0 : une assertion JWT signée RS256 par la clé privée du
   compte de service (`iss`, `scope` de FCM, `aud` = `token_uri`, une heure), échangée à
   `token_uri` ; gardé jusqu'à une minute avant son échéance.
2. `POST https://fcm.googleapis.com/v1/projects/<projet>/messages:send`, corps composé
   par `envoi.charge_fcm` — et par elle seule.

## Ce que Google répond (§4)

- 200 → `envoye` ;
- `UNREGISTERED`, ou `INVALID_ARGUMENT` sur le jeton → `jeton_perime` : l'installation
  retire l'appareil ;
- tout autre refus, ou une panne réseau → `refuse`, avec un motif qui ne répète rien de
  la requête (ni jeton, ni abonnement : N8).

🔒 `tests/test_push_fcm.py` — aucun appel réseau : le client HTTP est un double.
"""

from __future__ import annotations

import time
from typing import Optional

import httpx
import jwt

from app.utils.push.envoi import Envoi, charge_fcm
from app.utils.push.transport import Resultat

PORTEE = "https://www.googleapis.com/auth/firebase.messaging"
URL_ENVOI = "https://fcm.googleapis.com/v1/projects/{projet}/messages:send"
#: Les erreurs FCM qui disent un jeton à oublier — l'appareil n'est plus inscrit.
ERREURS_JETON_PERIME = frozenset({"UNREGISTERED", "INVALID_ARGUMENT"})
#: Les champs du compte de service que ce transport lit — rien d'autre.
CHAMPS_COMPTE = ("project_id", "client_email", "private_key", "token_uri")


class TransportFcm:
    """Transmet un `Envoi` de plateforme `fcm` à FCM HTTP v1, au nom du compte de service."""

    def __init__(self, compte_service: dict, http: Optional[httpx.Client] = None):
        manquants = [c for c in CHAMPS_COMPTE if not compte_service.get(c)]
        if manquants:
            raise ValueError(f"compte de service incomplet : {', '.join(manquants)}")
        self._compte = {c: compte_service[c] for c in CHAMPS_COMPTE}
        self._http = http or httpx.Client(timeout=10)
        self._acces: Optional[str] = None
        self._expire_a = 0.0

    def _jeton_acces(self) -> str:
        maintenant = time.time()
        if self._acces and maintenant < self._expire_a - 60:
            return self._acces
        assertion = jwt.encode(
            {
                "iss": self._compte["client_email"],
                "scope": PORTEE,
                "aud": self._compte["token_uri"],
                "iat": int(maintenant),
                "exp": int(maintenant) + 3600,
            },
            self._compte["private_key"],
            algorithm="RS256",
        )
        reponse = self._http.post(
            self._compte["token_uri"],
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        reponse.raise_for_status()
        corps = reponse.json()
        self._acces = corps["access_token"]
        self._expire_a = maintenant + int(corps.get("expires_in", 3600))
        return self._acces

    def transmettre(self, envoi: Envoi) -> Resultat:
        if envoi.plateforme != "fcm":
            return Resultat("refuse", "envoi d'une autre plateforme que FCM")
        try:
            reponse = self._http.post(
                URL_ENVOI.format(projet=self._compte["project_id"]),
                json=charge_fcm(envoi),
                headers={"Authorization": f"Bearer {self._jeton_acces()}"},
            )
        except httpx.HTTPError as exc:
            return Resultat("refuse", f"FCM injoignable ({type(exc).__name__})")
        if reponse.status_code == 200:
            return Resultat("envoye")
        code = erreur_fcm(reponse)
        if code in ERREURS_JETON_PERIME:
            return Resultat("jeton_perime", f"FCM : {code}")
        return Resultat("refuse", f"FCM : HTTP {reponse.status_code} {code or ''}".strip())


def erreur_fcm(reponse: httpx.Response) -> Optional[str]:
    """PURE. Le code d'erreur FCM (`UNREGISTERED`…) d'une réponse, ou son statut général."""
    try:
        erreur = reponse.json().get("error", {})
    except ValueError:
        return None
    for detail in erreur.get("details", []):
        if detail.get("errorCode"):
            return detail["errorCode"]
    return erreur.get("status")


__all__ = ["ERREURS_JETON_PERIME", "TransportFcm", "erreur_fcm"]
