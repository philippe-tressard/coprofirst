"""Les affaires liées qu'on peut ABSORBER en clôturant celle-ci (#1704).

La boîte de clôture les demande avant d'envoyer la Suite ou la correction qui
clôt : chacune avec son verdict — une affaire lue par moins de monde que celle
qu'on clôt est montrée, désactivée, avec sa raison. Le geste lui-même passe par
le champ `fusionner` des deux chemins de clôture (`utils/fusion_affaires`).

Le schéma de réponse vit ici : un seul routeur s'en sert.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Ticket, Utilisateur
from app.schemas import AffaireLieeLue
from app.utils.fusion_affaires import candidates
from app.utils.recuperer import ou_404
from app.utils.visibility import ticket_visible

router = APIRouter()


class CandidateFusion(AffaireLieeLue):
    """Une affaire liée proposée à la fusion — la forme d'une affaire nommée
    (date de création comprise, #2173) —, et ce qui l'en empêche le cas échéant."""

    fusionnable: bool
    motif: Optional[str] = None


@router.get("/{ticket_id}/fusion", response_model=list[CandidateFusion])
def candidates_a_la_fusion(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    ticket = ou_404(session, Ticket, ticket_id, "Ticket")
    if not ticket_visible(ticket, user):
        raise HTTPException(403, "Accès refusé")
    return candidates(session, ticket, user)
