"""Les appareils de la personne connectée — enregistrer, retirer (#2493).

Spécification : `specs/architecture/notifications-push.md` §6.2. Appelé par
l'application iOS seule : à la connexion (`POST`), à la déconnexion (`DELETE`).
La PWA n'enregistre pas d'appareil — aucun client TypeScript ; le client Swift se
génère du contrat publié (#2456).

Les règles — changement de main, retraits, purge — vivent dans `utils/push/appareils`.
Aucune réponse ne répète le jeton : un 204, sans corps.
"""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.appareils import Appareil
from app.models.core import Utilisateur
from app.utils.limiter import LIMITE_PREFERENCE, limiter
from app.utils.push.appareils import enregistrer
from app.utils.push.envoi import MOTIF_ABONNEMENT, MOTIF_JETON, Environnement
from app.utils.recuperer import present_ou_404

router = APIRouter(prefix="/appareils", tags=["appareils"])


class AppareilEnregistre(BaseModel):
    """Ce que l'application envoie — rien d'autre n'est admis."""

    model_config = ConfigDict(extra="forbid")

    jeton: str = Field(pattern=MOTIF_JETON)
    environnement: Environnement
    abonnement: str = Field(pattern=MOTIF_ABONNEMENT)


@router.post("", status_code=204, response_class=Response)
@limiter.limit(LIMITE_PREFERENCE)
def enregistrer_appareil(
    request: Request,
    body: AppareilEnregistre,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Enregistre (ou rafraîchit) l'appareil de la personne connectée."""
    enregistrer(session, user.id, **body.model_dump())
    session.commit()
    return Response(status_code=204)


@router.delete("/{abonnement}", status_code=204, response_class=Response)
@limiter.limit(LIMITE_PREFERENCE)
def retirer_appareil(
    request: Request,
    abonnement: str,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Retire l'appareil de la personne — l'abonnement d'un autre compte rend 404."""
    appareil = present_ou_404(
        session.exec(
            select(Appareil).where(
                Appareil.abonnement == abonnement, Appareil.utilisateur_id == user.id
            )
        ).first(),
        "Appareil introuvable",
    )
    session.delete(appareil)
    session.commit()
    return Response(status_code=204)
