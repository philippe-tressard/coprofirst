"""Router règles & recommandations de la résidence."""

from app.utils import horloge
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import RegleResidence, Utilisateur
from app.utils.annexes import supprimer_annexes
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/regles-residence", tags=["règles-résidence"])


class RegleCreate(BaseModel):
    titre: str
    contenu: str = ""


class RegleUpdate(BaseModel):
    titre: Optional[str] = None
    contenu: Optional[str] = None
    ordre: Optional[int] = None


class RegleResidenceLue(BaseModel):
    """Une règle de la résidence — typée au contrat le 04/11/2026 (#2505).

    Elle était rendue en `list[dict]` : l'app iOS la décodait d'après le front.
    Les champs sont ceux que la route rendait déjà, sans un de plus.
    """

    id: int
    titre: str
    #: Le texte de la règle, tel que le conseil l'a rédigé.
    contenu: str
    ordre: int
    cree_par_id: Optional[int] = None
    cree_le: Optional[datetime] = None
    modifie_le: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[RegleResidenceLue])
def list_regles(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    return session.exec(
        select(RegleResidence).order_by(RegleResidence.ordre, RegleResidence.id)
    ).all()


@router.post("", status_code=201)
def create_regle(
    body: RegleCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    regle = RegleResidence(
        titre=body.titre,
        contenu=body.contenu,
        cree_par_id=user.id,
        cree_le=horloge.maintenant(),
    )
    session.add(regle)
    session.commit()
    session.refresh(regle)
    return {"id": regle.id, "titre": regle.titre, "contenu": regle.contenu, "ordre": regle.ordre}


@router.patch("/{regle_id}")
def update_regle(
    regle_id: int,
    body: RegleUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    regle = ou_404(session, RegleResidence, regle_id, "Règle")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(regle, k, v)
    regle.modifie_le = horloge.maintenant()
    session.add(regle)
    session.commit()
    session.refresh(regle)
    return {"id": regle.id, "titre": regle.titre, "contenu": regle.contenu, "ordre": regle.ordre}


@router.delete("/{regle_id}", status_code=204)
def delete_regle(
    regle_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    regle = ou_404(session, RegleResidence, regle_id, "Règle")
    #  La règle emporte ses pièces jointes (migration 0276, `utils/annexes`).
    supprimer_annexes(session, "regle", regle_id)
    session.delete(regle)
    session.commit()
