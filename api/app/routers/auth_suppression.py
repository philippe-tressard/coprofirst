"""Router auth/suppression — demander la suppression de SON compte (#2699).

L'app iOS doit permettre de lancer la suppression du compte (règle 5.1.1 v de
l'App Store) ; le site offre le même geste depuis Mon profil. Les règles —
mot de passe, une demande à la fois, traitement par l'administration, démo
jamais effacée — vivent dans `utils/demande_suppression`, partagé avec la file
de l'administration (`routers/admin/demandes_suppression.py`).

Même préfixe `/auth`, monté à part dans `main.py`, comme `auth_profil` et
`auth_telemetrie` : il ne parle pas d'authentification.
"""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Utilisateur
from app.utils import demande_suppression as regles
from app.utils.demande_suppression import DemandeSuppressionRead, EtatDemandeSuppression
from app.utils.limiter import LIMITE_LECTURE_AUTHENTIFIEE, LIMITE_SECRET_EPROUVE, limiter

router = APIRouter(prefix="/auth", tags=["auth"])


class DemandeSuppressionCreate(BaseModel):
    mot_de_passe: str = Field(min_length=1)
    motif: Optional[str] = Field(default=None, max_length=1000)


@router.get("/demande-suppression", response_model=EtatDemandeSuppression)
@limiter.limit(LIMITE_LECTURE_AUTHENTIFIEE)
def ma_demande_suppression(
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Ma demande en cours (`demande` vide s'il n'y en a pas), le délai annoncé et ce qui sera effacé."""
    return regles.etat(session, user)


@router.post("/demande-suppression", status_code=201, response_model=DemandeSuppressionRead)
#  Un mot de passe y est éprouvé : la limite des secrets, pas celle des préférences.
@limiter.limit(LIMITE_SECRET_EPROUVE)
def demander_suppression(
    request: Request,
    body: DemandeSuppressionCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Demande la suppression de mon compte. 400 : mot de passe faux ; 409 : une demande est déjà en cours."""
    demande = regles.deposer_demande(session, user, body.mot_de_passe, body.motif, background_tasks)
    return regles.lire(demande)


@router.delete("/demande-suppression", status_code=204)
@limiter.limit(LIMITE_LECTURE_AUTHENTIFIEE)
def retirer_demande_suppression(
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Je retire ma demande, tant qu'elle n'a pas été traitée. 404 s'il n'y en a pas."""
    regles.retirer(session, user)
    return Response(status_code=204)
