"""Le rapport « Suivi des affaires » du Reporting CS (16/10/2026, maquette D2).

Trois points d'accès, tous réservés au conseil syndical et à l'administration —
le rapport est un outil du conseil, et la synthèse est un appel facturé :

| Route | Ce qu'elle rend |
|---|---|
| `GET /suivi-affaires` | le relevé : nombre, répartition, affaires — l'écran ne recalcule rien |
| `POST /suivi-affaires/synthese` | la synthèse de l'assistant ; n'enregistre rien |
| `POST /suivi-affaires/pdf` | le PDF, avec la synthèse affichée si l'écran l'envoie |

La règle d'entrée au rapport vit dans `utils/suivi_affaires/releve`.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.utils import horloge
from app.utils.config_site import config_site
from app.utils.limiter import LIMITE_APPEL_FACTURE, limiter
from app.utils.liens import nom_site
from app.utils.llm import ErreurLLM
from app.utils.logo import logo_televerse_png
from app.utils.suivi_affaires import synthese as assistant
from app.utils.suivi_affaires.format import (
    MAX_CARACTERES_POINT,
    MAX_CARACTERES_RESUME,
    MAX_POINTS,
)
from app.utils.suivi_affaires.pdf import generer_pdf
from app.utils.suivi_affaires.releve import releve

router = APIRouter(prefix="/suivi-affaires", tags=["suivi-affaires"])


class AffaireOuverteRead(BaseModel):
    id: int
    numero: str
    titre: str
    descriptif: str
    categorie: str
    libelle_categorie: str
    statut: str
    libelle_statut: str
    ouverte_le: date
    age_jours: int
    #: `ancienne` (> 90 j), `moyenne` (> 30 j), `recente` — les seuils restent au serveur.
    anciennete: str

    class Config:
        from_attributes = True


class CategorieRead(BaseModel):
    categorie: str
    libelle: str
    nombre: int

    class Config:
        from_attributes = True


class SuiviAffairesRead(BaseModel):
    jour: date
    total: int
    anciennes: int
    par_categorie: list[CategorieRead]
    affaires: list[AffaireOuverteRead]
    #: Le ✨ a-t-il un sens ? Décidé par le serveur, rien de la configuration ne sort.
    synthese_disponible: bool


class SyntheseRead(BaseModel):
    """Du TEXTE, jamais du HTML : l'écran l'affiche tel quel, le PDF l'échappe."""

    resume: str = Field(max_length=MAX_CARACTERES_RESUME)
    points: list[str] = Field(default_factory=list, max_length=MAX_POINTS)


class DemandePdf(BaseModel):
    #: La synthèse affichée à l'écran, à reprendre dans le PDF — ou rien.
    synthese: Optional[SyntheseRead] = None


@router.get("", response_model=SuiviAffairesRead, summary="Les affaires non closes (CS/Admin)")
def lire_suivi(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    r = releve(session, user)
    return SuiviAffairesRead(
        jour=r.jour,
        total=r.total,
        anciennes=r.anciennes,
        par_categorie=[CategorieRead.model_validate(c) for c in r.par_categorie],
        affaires=[AffaireOuverteRead.model_validate(a) for a in r.affaires],
        synthese_disponible=assistant.disponible(session),
    )


@router.post(
    "/synthese",
    response_model=SyntheseRead,
    summary="Synthèse des affaires en cours par l'assistant (CS/Admin)",
)
@limiter.limit(LIMITE_APPEL_FACTURE)
async def synthetiser(
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Rend une synthèse. N'enregistre rien — elle se relit, et se rejoue."""
    try:
        s = await assistant.rediger(session, releve(session, user), demandeur=user.id)
    except ErreurLLM as exc:
        raise HTTPException(400, str(exc))
    return SyntheseRead(resume=s.resume, points=s.points)


@router.post("/pdf", summary="Le rapport Suivi des affaires en PDF (CS/Admin)")
def exporter_pdf(
    body: DemandePdf,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    s = body.synthese
    synthese = (
        assistant.Synthese(
            resume=s.resume, points=[p[:MAX_CARACTERES_POINT] for p in s.points if p.strip()]
        )
        if s and s.resume.strip()
        else None
    )
    site = config_site(session)
    pdf = generer_pdf(
        releve(session, user),
        synthese,
        site_nom=nom_site(site.get("site_nom")),
        logo_png=logo_televerse_png(session),
    )
    nom = f"suivi-des-affaires-{horloge.aujourd_hui():%Y-%m-%d}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )
