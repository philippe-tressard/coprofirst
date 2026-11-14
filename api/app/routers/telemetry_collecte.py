"""Télémétrie — la COLLECTE : ce que `sendBeacon` poste depuis chaque écran.

Extraite de `routers/telemetry.py` le 28/09/2026, au fil de l'eau (#779) : le
fichier faisait 511 lignes et portait deux notions — ÉCRIRE les événements
(public, anonymes compris) et LIRE le tableau de bord (administrateur). Même
préfixe `/telemetry` : l'URL publique ne bouge pas.

## Elle sait QUI — rétablie le 02/10/2026

La v2.92.0 (#1545) avait retiré `user_id` : le tableau de bord avait perdu ses
statistiques par utilisateur (actifs, palmarès…), sans l'accord de
l'utilisateur du produit. Elles sont rétablies (migration 0247), la politique
de confidentialité dit de nouveau « rattachées à votre compte », et le refus du
profil est honoré ICI comme dans le navigateur.

## La session se lit par `auth/deps.py`, jamais ici (#1595)

Avant #1595, cette route décodait le cookie elle-même — sans `actif` ni
l'empreinte du mot de passe : une session invalidée restait reconnue. Elle
prend `utilisateur_ou_anonyme`, la même chaîne que toute route authentifiée,
qui rend `None` au lieu d'un 401 pour un visiteur.

## Le volume est borné (#1597)

Route PUBLIQUE, déclarée comme telle dans `test_autorisation.py`. Elle écrit en
base : plafond par minute ET par jour (`LIMITE_COLLECTE_AUDIENCE`), lot borné en
nombre, champs bornés en taille — refusés en bloc (422), pas tronqués : le
client du site n'envoie rien de tel, une charge hors norme vient d'ailleurs.

## Le canal d'accès (14/11/2026)

Le lot dit d'où il vient — le site, l'app iPhone, plus tard l'app Android
(`canal`, `utils/canaux_audience`) ; chaque page vue le garde. Seules les pages
vues le portent : erreurs, durées et gestes restent comptés sans lui.

## Les erreurs, les durées d'affichage et les gestes passent par ici (#1631, #1632, #1633)

Même route, même plafond, même refus du profil — mais chacune dans sa table
(`TRAITEMENTS_A_PART`), sans identifiant de compte : dans `telemetry_event`,
le tableau de bord les compterait comme des pages vues.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import utilisateur_ou_anonyme
from app.database import get_session
from app.models.core import TelemetryEvent, Utilisateur
from app.utils import horloge
from app.utils.canaux_audience import CANAL_PAR_DEFAUT, Canal
from app.utils.erreurs_navigateur import ACTION_ERREUR, enregistrer_erreur
from app.utils.gestes_formulaire import (
    ACTION_ENVOI,
    ACTION_OUVERTURE,
    enregistrer_envoi,
    enregistrer_ouverture,
)
from app.utils.mesures_affichage import ACTION_MESURE, enregistrer_mesure
from app.utils.limiter import LIMITE_COLLECTE_AUDIENCE, limiter

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

#: Les actions qui ne sont PAS des pages vues, et qui les écrit — chacune sans
#: identifiant de compte, avec la même signature `(session, page, detail, instant)`.
TRAITEMENTS_A_PART = {
    ACTION_ERREUR: enregistrer_erreur,
    ACTION_MESURE: enregistrer_mesure,
    ACTION_OUVERTURE: enregistrer_ouverture,
    ACTION_ENVOI: enregistrer_envoi,
}

#: Le client vide sa file toutes les 30 secondes, et dès qu'elle atteint ce
#: nombre (`front/src/lib/telemetry.ts`, `EVENEMENTS_PAR_LOT`) : un lot plus
#: gros ne vient pas de lui. ⚠️ Les deux valeurs se tiennent à la main — le
#: front et l'API ne partagent aucun fichier (contextes de build séparés).
EVENEMENTS_PAR_LOT = 20


class EvenementAudience(BaseModel):
    page: str = Field(min_length=1, max_length=200)  # chemin, sans requête
    action: str = Field(default="view", max_length=20)
    detail: str | None = Field(default=None, max_length=100)


class LotAudience(BaseModel):
    events: list[EvenementAudience] = Field(max_length=EVENEMENTS_PAR_LOT)
    #: Le canal d'accès du client qui poste (`utils/canaux_audience`) : le site s'il
    #: ne le dit pas — c'est le cas du front, seul client avant le 14/11/2026.
    canal: Canal = CANAL_PAR_DEFAUT


@router.post("/collect", status_code=204)
@limiter.limit(LIMITE_COLLECTE_AUDIENCE)
def collect(
    body: LotAudience,
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur | None = Depends(utilisateur_ou_anonyme),
):
    """Endpoint de collecte appelé par `sendBeacon` — rattaché au compte s'il y en a un."""
    if user and user.opt_out_telemetrie:
        return  # RGPD art. 21 : le refus du profil vaut aussi côté serveur
    user_id = user.id if user else None
    now = horloge.maintenant()
    for ev in body.events:
        traitement = TRAITEMENTS_A_PART.get(ev.action)
        if traitement is not None:
            traitement(session, ev.page, ev.detail, now)
            continue
        session.add(
            TelemetryEvent(
                user_id=user_id,
                page=ev.page,
                action=ev.action,
                detail=ev.detail,
                canal=body.canal,
                cree_le=now,
            )
        )
    session.commit()
