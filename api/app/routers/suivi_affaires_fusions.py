"""Les FUSIONS d'affaires liées du Suivi des affaires (#2083) — au point comme
entre deux points.

| Route | Ce qu'elle fait |
|---|---|
| `POST /suivi-affaires/fusions/proposition` | le titre et la description proposés (assistant, sinon sans lui) — n'écrit rien |
| `POST /suivi-affaires/fusions/conciliation` | pour chaque affaire du groupe, la fusion est-elle possible — sinon l'écart et les options pour l'autoriser (`utils/fusion_conciliation`) — n'écrit rien |
| `POST /suivi-affaires/fusions` | la plus ancienne absorbe les autres (ou celle que la conciliation désigne), et prend le titre et la description relus |
| `POST /suivi-affaires/fusions/ecarter` | « Ne pas fusionner » : la paire ne se rassemble plus, ni ne se propose à la clôture |

Réservé au conseil syndical et à l'administration ; la proposition est un appel
facturé (limité). Les règles : `utils/fusion_en_cours` et `utils/fusion_en_cours_ia`.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.routers.tickets.fusion import CandidateFusion
from app.schemas_communs import ChoixConciliation
from app.utils import fusion_en_cours
from app.utils.fusion_affaires import candidates, conciliations_par_affaire, prevenir_auteurs
from app.utils.fusion_en_cours_ia import proposer_fusion
from app.utils.limiter import LIMITE_APPEL_FACTURE, limiter
from app.utils.llm import ErreurLLM

router = APIRouter(prefix="/suivi-affaires/fusions", tags=["suivi-affaires"])


class GroupeEntree(BaseModel):
    #: Les affaires liées du groupe — deux au moins.
    ids: list[int] = Field(min_length=2, max_length=20)


class FusionEntree(GroupeEntree):
    titre: str = Field(min_length=1, max_length=200)
    #: Le texte riche relu par le conseil — assaini à l'affichage, comme toute description.
    description: str = Field(default="", max_length=50_000)
    #: Qui absorbe, quand le conseil a concilié une fusion refusée en inversant les rôles.
    principale_id: int | None = None
    #: Les fusions refusées pour fuite de lecture que le conseil a conciliées.
    conciliations: list[ChoixConciliation] = []


class PropositionRead(BaseModel):
    titre: str
    description: str
    #: Rédigée par l'assistant — sinon composée sans lui.
    assiste_ia: bool

    class Config:
        from_attributes = True


class FusionRead(BaseModel):
    principale_id: int
    absorbees: list[int]


@router.post(
    "/proposition",
    response_model=PropositionRead,
    summary="Le titre et la description proposés pour une fusion (CS/Admin)",
)
@limiter.limit(LIMITE_APPEL_FACTURE)
async def proposition(
    request: Request,
    body: GroupeEntree,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    tickets = fusion_en_cours.affaires_du_groupe(session, body.ids)
    try:
        return PropositionRead.model_validate(
            await proposer_fusion(session, tickets, demandeur=user.id)
        )
    except ErreurLLM as exc:
        raise HTTPException(400, str(exc))


@router.post(
    "/conciliation",
    response_model=list[CandidateFusion],
    summary="Ce qui empêche de fusionner ce groupe, et les options pour l'autoriser (CS/Admin)",
)
def conciliation(
    body: GroupeEntree,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    principale, *autres = fusion_en_cours.affaires_du_groupe(session, body.ids)
    voulues = {t.id for t in autres}
    return [c for c in candidates(session, principale, user, inversion=True) if c["id"] in voulues]


@router.post("", response_model=FusionRead, summary="Fusionner des affaires liées (CS/Admin)")
def fusionner(
    body: FusionEntree,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    principale, absorbees = fusion_en_cours.fusionner(
        session,
        body.ids,
        user,
        body.titre,
        body.description,
        body.principale_id,
        conciliations_par_affaire(body.conciliations),
    )
    session.commit()
    #  L'auteur d'une absorbée l'apprend à la cloche — pas de courriel : son
    #  affaire n'est pas close, son suivi se poursuit ailleurs.
    prevenir_auteurs(session, background_tasks, absorbees, user, courriel=False, deja=set())
    session.commit()
    return FusionRead(principale_id=principale.id, absorbees=[a.id for a, _ in absorbees])


@router.post("/ecarter", status_code=204, summary="Ne pas fusionner des affaires liées (CS/Admin)")
def ecarter(
    body: GroupeEntree,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    fusion_en_cours.ecarter(session, body.ids, user)
    session.commit()
