"""Les montres de la personne connectée — émettre, renouveler, lister, retirer (#2771).

Appelé par le TÉLÉPHONE connecté (iPhone, Android), jamais par la montre : ces routes
prennent la session par cookie (`get_current_user`), qu'un jeton de montre n'ouvre pas.
La montre ne lit que la cloche (`GET /notifications`) : sa portée est une ligne de la table
commune des jetons d'appareil (`auth/jetons_appareil.PORTEES`, #2770).

Les règles — portée, échéance, révocation — vivent dans `auth/jetons_montre`. Le jeton
brut n'est rendu qu'à l'émission et au renouvellement ; la liste ne le répète jamais.
Aucun client TypeScript : la PWA n'a pas de montre ; les apps génèrent leur client du
contrat publié (#2456).
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.auth.jetons_appareil import renouveler
from app.auth.jetons_montre import emettre, suivre_le_compte
from app.database import get_session
from app.models.core import Utilisateur
from app.models.jetons import JetonMontre
from app.utils import horloge
from app.utils.journal_securite import journaliser_securite
from app.utils.limiter import LIMITE_PREFERENCE, limiter
from app.utils.recuperer import present_ou_404

router = APIRouter(prefix="/montres", tags=["montres"])


class MontreDemandee(BaseModel):
    """Ce que le téléphone envoie — rien d'autre n'est admis."""

    model_config = ConfigDict(extra="forbid")

    plateforme: Literal["watchos", "wearos"]


class MontreLue(BaseModel):
    """Une montre de la personne, sans son jeton."""

    id: int
    plateforme: str
    cree_le: datetime
    expire_le: datetime
    vu_le: datetime | None


class MontreEmise(MontreLue):
    """Une montre et son jeton brut — rendu UNE fois, à transmettre à la montre."""

    jeton: str


def _ma_montre(session: Session, montre_id: int, user: Utilisateur) -> JetonMontre:
    """La montre `montre_id` de `user` ; celle d'un autre compte rend 404."""
    return present_ou_404(
        session.exec(
            select(JetonMontre).where(
                JetonMontre.id == montre_id, JetonMontre.utilisateur_id == user.id
            )
        ).first(),
        "Montre introuvable",
    )


def _emise(jeton: JetonMontre, brut: str) -> MontreEmise:
    return MontreEmise(
        **MontreLue.model_validate(jeton, from_attributes=True).model_dump(), jeton=brut
    )


@router.post("", response_model=MontreEmise, status_code=201)
@limiter.limit(LIMITE_PREFERENCE)
def emettre_montre(
    request: Request,
    body: MontreDemandee,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Émet le jeton d'une montre de la personne connectée : lecture de la cloche seule."""
    jeton, brut = emettre(session, user, body.plateforme, horloge.maintenant())
    session.commit()
    session.refresh(jeton)
    journaliser_securite(
        "montre_reliee", acteur_id=user.id, cible_id=user.id, detail=f"montre {jeton.id}"
    )
    return _emise(jeton, brut)


@router.post("/{montre_id}/renouveler", response_model=MontreEmise)
@limiter.limit(LIMITE_PREFERENCE)
def renouveler_montre(
    request: Request,
    montre_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Remplace le jeton d'une montre de la personne et repousse son échéance."""
    jeton = _ma_montre(session, montre_id, user)
    suivre_le_compte(jeton, user)
    brut = renouveler(session, "montre", jeton, horloge.maintenant())
    session.commit()
    session.refresh(jeton)
    return _emise(jeton, brut)


@router.get("", response_model=list[MontreLue])
@limiter.limit(LIMITE_PREFERENCE)
def lister_montres(
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Les montres reliées au compte, pour les voir et les retirer — jamais leur jeton."""
    return session.exec(
        select(JetonMontre)
        .where(JetonMontre.utilisateur_id == user.id)
        .order_by(JetonMontre.cree_le.desc())
    ).all()


@router.delete("/{montre_id}", status_code=204, response_class=Response)
@limiter.limit(LIMITE_PREFERENCE)
def retirer_montre(
    request: Request,
    montre_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Retire une montre de la personne : son jeton cesse aussitôt de servir."""
    session.delete(_ma_montre(session, montre_id, user))
    session.commit()
    journaliser_securite(
        "montre_retiree", acteur_id=user.id, cible_id=user.id, detail=f"montre {montre_id}"
    )
    return Response(status_code=204)
