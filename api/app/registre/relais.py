"""Le RELAIS des notifications push — `POST /plateforme/notifications` (#2494, #2789).

Spécification : `specs/architecture/notifications-push.md` §4. Une route PUBLIQUE de la
référence, sous le nom dédié du registre : une réplique lui demande d'avertir UN
appareil ; le relais juge sur pièces, compose lui-même la charge et la transmet
(`utils/push/relais.transmettre`). Ses gardes, dans l'ordre — les communes APPELÉES
dans `registre/gardes`, jamais recopiées (#2953) :

1. **Servie seulement ici** : `routeur.servi_ici` — ailleurs, 404.
2. **Taille et débit** : `gardes.lire_contrat` (taille, contrat, version),
   `LIMITE_RELAIS_PUSH` par adresse, et
   `PLAFOND_PAR_MINUTE` par installation — une installation bavarde ne prive pas les
   autres.
3. **Le bail se croit** : `inscription/constat.constater`, la règle de l'installation
   elle-même (clés par époque, clés révoquées, empreinte de la clé, échéance, état) —
   puis l'état `active` et le service `notifications_push` dans le bail.
4. **Signée** par la clé dont le bail porte l'empreinte, sur les octets REÇUS :
   `gardes.exiger_signature`.
5. **Fraîche et unique** : `emis_le` à moins de `FENETRE` de l'horloge du relais, et
   un nonce jamais vu dans cette fenêtre — un envoi rejoué n'avertit pas deux fois.

Le refus dit quelle garde a manqué, jamais ce qu'il a lu. Le journal porte
l'identifiant de l'installation, la plateforme et le statut — jamais le jeton (N8).
🔒 `tests/test_push_relais.py`.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from app.inscription import cles, constat
from app.inscription.depot import EtatLocal
from app.registre.contrat import DemandeNotification, ReponseNotification
from app.registre.gardes import exiger_signature, lire_contrat
from app.registre.routeur import servi_ici
from app.utils import horloge
from app.utils.limiter import LIMITE_RELAIS_PUSH, limiter
from app.utils.push import relais
from app.utils.services import SERVICE_PUSH

logger = logging.getLogger("hostachy.registre")

router = APIRouter(prefix="/plateforme", tags=["plateforme"])

#: L'âge maximal d'un envoi, et la durée pendant laquelle son nonce reste connu (§4, 5).
FENETRE = timedelta(minutes=5)

#: Les envois d'UNE installation en une minute — une alerte à toute une résidence tient
#: dessous (un envoi par appareil) ; au-delà, 429 pour elle seule.
PLAFOND_PAR_MINUTE = 600

#: Les nonces vus dans la fenêtre, et l'instant de leur passage. État de PROCESSUS
#: de la plateforme, sans donnée de copropriété (`DU_PROCESSUS`, §4 point 5).
_nonces: dict[str, datetime] = {}
#: Les instants des derniers envois, par installation (garde 2).
_envois: dict[str, deque] = {}


def _bail_admis(demande: DemandeNotification, maintenant: datetime) -> None:
    """Garde 3 : le bail se croit, l'installation est active et le service accordé."""
    verdict = constat.constater(
        EtatLocal(identifiant=demande.identifiant, bail=demande.bail.model_dump(mode="json")),
        maintenant=maintenant,
        cle_installation=demande.cle_publique,
        reference=False,
        essai=False,
        cles=cles.CLES_REFERENCE,
        revoquees=cles.REVOQUEES,
    )
    if verdict.etat != constat.ACTIVE:
        raise HTTPException(403, f"Bail non admis : {verdict.raison}.")
    if SERVICE_PUSH not in (verdict.services or frozenset()):
        raise HTTPException(403, "Le bail n'accorde pas les notifications sur téléphone.")


def _sous_le_plafond(identifiant: str, maintenant: datetime) -> None:
    """Garde 2, par installation : `PLAFOND_PAR_MINUTE` envois glissants."""
    passes = _envois.setdefault(identifiant, deque())
    while passes and maintenant - passes[0] > timedelta(minutes=1):
        passes.popleft()
    if len(passes) >= PLAFOND_PAR_MINUTE:
        raise HTTPException(429, "Trop d'envois de cette installation : réessayer plus tard.")
    passes.append(maintenant)


def _frais_et_unique(demande: DemandeNotification, maintenant: datetime) -> None:
    """Garde 5 : l'envoi date de moins de `FENETRE`, et son nonce n'a jamais servi."""
    for nonce, vu_le in list(_nonces.items()):
        if maintenant - vu_le > FENETRE:
            _nonces.pop(nonce, None)
    if abs(maintenant - demande.envoi.emis_le) > FENETRE:
        raise HTTPException(400, "Envoi hors de la fenêtre de fraîcheur.")
    if demande.envoi.nonce in _nonces:
        raise HTTPException(409, "Envoi déjà reçu.")
    _nonces[demande.envoi.nonce] = maintenant


@router.post(
    "/notifications", response_model=ReponseNotification, dependencies=[Depends(servi_ici)]
)
@limiter.limit(LIMITE_RELAIS_PUSH)
async def relayer(request: Request):
    """Avertit UN appareil d'une installation au bail cru — la charge est composée ici."""
    corps = await request.body()
    demande = lire_contrat(corps, DemandeNotification)
    maintenant = horloge.maintenant()
    _bail_admis(demande, maintenant)
    exiger_signature(demande.cle_publique, corps, request)
    _sous_le_plafond(demande.identifiant, maintenant)
    _frais_et_unique(demande, maintenant)
    resultat = relais.transmettre(demande.envoi)
    logger.info(
        "relais push : %s, %s, %s", demande.identifiant, demande.envoi.plateforme, resultat.statut
    )
    return ReponseNotification(statut=resultat.statut, motif=resultat.motif)
