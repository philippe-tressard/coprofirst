"""Le transport vers APNs, le service de notifications d'Apple — l'avertissement d'un iPhone (#2494).

Spécification : `specs/architecture/notifications-push.md` §4 et §5. La **clé `.p8`** du
compte Apple Developer de CoproFirst n'est détenue que par la RÉFÉRENCE (N1) — jamais
une installation, jamais le dépôt : elle se pose dans le `.env` des deux nœuds par
`scripts/exploitation/poser-secret-push.sh`. Sans elle, le relais refuse un appareil
`apns` et rien ne part (`utils/push/relais`).

## Le geste

1. Un jeton d'authentification : un JWT **ES256** signé par la clé `.p8`, `iss` =
   l'identifiant d'équipe, `kid` = l'identifiant de la clé. Apple le refuse au-delà
   d'une heure et en limite le renouvellement : il se garde `RENOUVELLEMENT`, entre les
   20 et 60 minutes qu'Apple exige.
2. `POST /3/device/<jeton>` en **HTTP/2** (`httpx[http2]`) vers `api.push.apple.com`, ou
   `api.sandbox.push.apple.com` pour un appareil de développement. Le corps est
   `envoi.charge_apns`, les en-têtes `envoi.entetes_apns` — et eux seuls (N4).

## Ce qu'Apple répond (§4)

- 200 → `envoye`, avec l'`apns-id` qu'Apple rend (journalisable, N8) ;
- 410 `Unregistered`, ou 400 `BadDeviceToken` → `jeton_perime` : l'installation retire
  l'appareil ;
- tout autre refus, ou une panne réseau → `refuse`, avec un motif qui ne répète rien
  de la requête (ni jeton, ni abonnement : N8).

🔒 `tests/test_push_apns.py` — aucun appel réseau : le client HTTP est un double.
"""

from __future__ import annotations

import time
from typing import Optional

import httpx
import jwt

from app.utils.push.envoi import Envoi, charge_apns, entetes_apns
from app.utils.push.transport import Resultat

#: L'équipe Apple Developer de CoproFirst et son application (spec §1) — publiques.
EQUIPE = "GUX8KASNTG"
SUJET = "fr.coprofirst.app"
HOTES = {
    "production": "https://api.push.apple.com",
    "developpement": "https://api.sandbox.push.apple.com",
}
#: Un jeton d'authentification se garde ce temps : Apple exige entre 20 et 60 minutes.
RENOUVELLEMENT = 50 * 60
#: Les refus d'Apple qui disent un jeton à oublier — l'appareil n'est plus inscrit.
RAISONS_JETON_PERIME = frozenset({"Unregistered", "BadDeviceToken"})


class TransportApns:
    """Transmet un `Envoi` de plateforme `apns` à APNs, au nom de la clé `.p8`."""

    def __init__(self, cle_pem: str, id_cle: str, http: Optional[httpx.Client] = None):
        if not cle_pem or not id_cle:
            raise ValueError("clé APNs incomplète : la clé et son identifiant sont requis")
        self._cle = cle_pem
        self._id_cle = id_cle
        #  HTTP/2 : APNs n'accepte que lui (`httpx[http2]`, h2 sous licence MIT).
        self._http = http or httpx.Client(http2=True, timeout=10)
        self._jeton: Optional[str] = None
        self._signe_a = 0.0

    def _jeton_auth(self) -> str:
        maintenant = time.time()
        if self._jeton and maintenant - self._signe_a < RENOUVELLEMENT:
            return self._jeton
        self._jeton = jwt.encode(
            {"iss": EQUIPE, "iat": int(maintenant)},
            self._cle,
            algorithm="ES256",
            headers={"kid": self._id_cle},
        )
        self._signe_a = maintenant
        return self._jeton

    def transmettre(self, envoi: Envoi) -> Resultat:
        if envoi.plateforme != "apns":
            return Resultat("refuse", "envoi d'une autre plateforme qu'APNs")
        entetes = {
            **entetes_apns(envoi),
            "apns-topic": SUJET,
            #  10 : remis aussitôt ; 5 : au gré de l'économie d'énergie du téléphone.
            "apns-priority": "10" if envoi.niveau == "urgent" else "5",
            "authorization": f"bearer {self._jeton_auth()}",
        }
        url = f"{HOTES[envoi.environnement]}/3/device/{envoi.jeton}"
        try:
            reponse = self._http.post(url, json=charge_apns(envoi), headers=entetes)
        except httpx.HTTPError as exc:
            return Resultat("refuse", f"APNs injoignable ({type(exc).__name__})")
        if reponse.status_code == 200:
            return Resultat("envoye", apns_id=reponse.headers.get("apns-id"))
        raison = raison_apns(reponse)
        if reponse.status_code == 410 or raison in RAISONS_JETON_PERIME:
            return Resultat("jeton_perime", f"APNs : {raison or reponse.status_code}")
        return Resultat("refuse", f"APNs : HTTP {reponse.status_code} {raison or ''}".strip())


def raison_apns(reponse: httpx.Response) -> Optional[str]:
    """PURE. La raison qu'Apple donne d'un refus (`BadDeviceToken`…), ou None."""
    try:
        return reponse.json().get("reason")
    except ValueError:
        return None


__all__ = ["EQUIPE", "RAISONS_JETON_PERIME", "SUJET", "TransportApns", "raison_apns"]
