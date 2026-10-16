"""Le rapport « Suivi des affaires » du Reporting CS (16/10/2026, maquette D2).

Trois points d'accès, tous réservés au conseil syndical et à l'administration —
le rapport est un outil du conseil, et le résumé est un appel facturé :

| Route | Ce qu'elle rend |
|---|---|
| `GET /suivi-affaires` | le relevé : nombre, répartition, affaires — l'écran ne recalcule rien |
| `POST /suivi-affaires/resumes` | fait rédiger le résumé de chaque affaire, et le garde sur elle (#2035) |
| `POST /suivi-affaires/pdf` | le PDF du relevé |

La règle d'entrée au rapport vit dans `utils/suivi_affaires/releve` : celle de
la relance du syndic, que l'écran porte en second mode depuis #2035.

🔴 `POST /suivi-affaires/synthese` — la synthèse d'ENSEMBLE de #2034 — a été
retirée le 16/10/2026 (#2035) : ce qui sert est l'état de chaque affaire.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
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
from app.utils.suivi_affaires import resumes as assistant
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
    #: Les codes du périmètre, pour le badge (qui tait celui par défaut).
    perimetre_cible: list[str]
    #: Depuis la dernière avancée — le repère de la relance du syndic (#2035).
    jours_sans_avancee: int
    #: Au-delà du délai de relance : cochée d'office en mode « Relancer le syndic ».
    a_relancer: bool
    #: Les jours des relances déjà envoyées, la plus ancienne en tête.
    relances: list[date]
    #: Ce qui s'affiche sous le titre : le résumé de l'assistant, sinon le descriptif.
    apercu: str
    apercu_ia: bool

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
    #: Le délai de relance réglé, en jours — le pli « moins de N jours » le cite.
    delai_jours: int
    #: Le ✨ a-t-il un sens ? Décidé par le serveur, rien de la configuration ne sort.
    resumes_disponibles: bool


class ResumesRedigesRead(BaseModel):
    #: Le nombre d'affaires dont le résumé vient d'être écrit.
    rediges: int


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
        delai_jours=r.delai_jours,
        resumes_disponibles=assistant.disponible(session),
    )


@router.post(
    "/resumes",
    response_model=ResumesRedigesRead,
    summary="Résumé de chaque affaire en cours par l'assistant (CS/Admin)",
)
@limiter.limit(LIMITE_APPEL_FACTURE)
async def resumer(
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Fait rédiger le résumé de chaque affaire du relevé et le garde sur elle ;
    l'écran les relit par `GET /suivi-affaires`."""
    r = releve(session, user)
    try:
        par_affaire = await assistant.rediger(session, r, demandeur=user.id)
    except ErreurLLM as exc:
        raise HTTPException(400, str(exc))
    return ResumesRedigesRead(rediges=assistant.enregistrer_resumes(session, r, par_affaire))


@router.post("/pdf", summary="Le rapport Suivi des affaires en PDF (CS/Admin)")
def exporter_pdf(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    site = config_site(session)
    pdf = generer_pdf(
        releve(session, user),
        site_nom=nom_site(site.get("site_nom")),
        logo_png=logo_televerse_png(session),
    )
    nom = f"suivi-des-affaires-{horloge.aujourd_hui():%Y-%m-%d}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )
