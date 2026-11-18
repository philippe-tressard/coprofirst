"""Les droits RGPD d'un compte sur SA télémétrie — accès, effacement, opposition.

## Pourquoi ce module (#835, 08/09/2026)

Extrait d'`auth.py` quand le garde-fou de modularité a refusé de le laisser
grossir (601 → 621 lignes). Le refus disait vrai : ces trois routes ne parlent
pas d'authentification. Elles répondent aux articles 15, 17, 20 et 21 du RGPD sur
une donnée que le site collecte — c'est un sujet à part entière, et il vivait au
milieu de la connexion, du rafraîchissement de jeton et de la vérification
d'adresse.

⚠️ Le préfixe reste `/auth` : ces routes sont publiées sous `/auth/me/telemetrie`
depuis toujours, et un client les appelle. Déplacer le code ne déplace pas
l'adresse — c'est le seul point sur lequel une extraction peut casser en silence.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import PresenceMensuelle, TelemetryEvent, Utilisateur
from app.models.telemetrie import DerniereVisite
from app.utils import telemetrie_compte
from app.utils.limiter import LIMITE_DONNEES_PERSONNELLES, LIMITE_PREFERENCE, limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me/telemetrie")
@limiter.limit(LIMITE_DONNEES_PERSONNELLES)
def export_telemetrie(
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Exporter ses données de télémétrie (RGPD art. 15 + 20 — droit d'accès et portabilité)."""
    events = session.exec(
        select(TelemetryEvent)
        .where(TelemetryEvent.user_id == user.id)
        .order_by(TelemetryEvent.cree_le.desc())  # type: ignore
    ).all()
    #  Et les mois où le compte est venu (0254) : le seul fait gardé au-delà des
    #  30 jours d'évènements, exporté avec eux — on rend TOUT ce qu'on tient.
    presences = session.exec(
        select(PresenceMensuelle.mois)
        .where(PresenceMensuelle.user_id == user.id)
        .order_by(PresenceMensuelle.mois.desc())  # type: ignore
    ).all()
    #  Et le jour de la dernière visite (#1629), gardé 12 mois.
    visite = session.get(DerniereVisite, user.id)
    return {
        "evenements": [
            {
                "page": ev.page,
                "action": ev.action,
                "detail": ev.detail,
                "canal": ev.canal,  # site, app Apple… (14/11/2026)
                "appareil": ev.appareil,  # téléphone, tablette… ; None = non précisé (#2774)
                "date": ev.cree_le.isoformat() if ev.cree_le else None,
            }
            for ev in events
        ],
        "mois_de_presence": list(presences),
        "jour_de_derniere_visite": visite.jour if visite else None,
    }


@router.delete("/me/telemetrie", status_code=204)
@limiter.limit(LIMITE_DONNEES_PERSONNELLES)
def effacer_telemetrie(
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Effacer ses données de télémétrie (RGPD art. 17 — droit à l'effacement).

    Évènements, présence mensuelle (0254) et jour de la dernière visite (#1629) :
    « l'effacement porte sur le tout », écrit une fois dans `utils/telemetrie_compte`.
    """
    telemetrie_compte.effacer_telemetrie(session, user.id)
    session.commit()


class OptOutTelemetrieBody(BaseModel):
    opt_out_telemetrie: bool


@router.patch("/me/opt-out-telemetrie", status_code=204)
@limiter.limit(LIMITE_PREFERENCE)
def toggle_opt_out_telemetrie(
    request: Request,
    body: OptOutTelemetrieBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Activer/désactiver la collecte de télémétrie (RGPD art. 21 — droit d'opposition)."""
    user.opt_out_telemetrie = body.opt_out_telemetrie
    session.add(user)
    if body.opt_out_telemetrie:
        telemetrie_compte.oublier_derniere_visite(session, user.id)
    session.commit()
