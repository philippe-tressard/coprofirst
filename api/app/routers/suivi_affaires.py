"""Le rapport « Suivi des affaires » du Reporting CS (16/10/2026, maquette D2).

Trois points d'accès, tous réservés au conseil syndical et à l'administration —
le rapport est un outil du conseil, et le résumé est un appel facturé :

| Route | Ce qu'elle rend |
|---|---|
| `GET /suivi-affaires?mode=&point=` | le relevé du mode (`affaires`, `entretien` — #2043) : nombre, répartitions, affaires ; avec `point`, les affaires du point en cours y restent jusqu'à sa validation (#2082) |
| `POST /suivi-affaires/resumes` | fait rédiger le résumé de chaque affaire, et le garde sur elle (#2035) |
| `POST /suivi-affaires/pdf?mode=` | le PDF du relevé du mode |

La règle d'entrée au rapport vit dans `utils/suivi_affaires/releve` : celle de
la relance du syndic, que l'écran porte en second mode depuis #2035.

🔴 `POST /suivi-affaires/synthese` — la synthèse d'ENSEMBLE de #2034 — a été
retirée le 16/10/2026 (#2035) : ce qui sert est l'état de chaque affaire.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.utils import horloge
from app.utils.config_site import config_site
from app.utils.lecture import lire_objet
from app.utils.limiter import LIMITE_APPEL_FACTURE, limiter
from app.utils.liens import nom_site
from app.utils.llm import ErreurLLM
from app.utils.logo import logo_televerse_png
from app.utils.suivi_affaires import resumes as assistant
from app.utils.suivi_affaires.pdf import generer_pdf
from app.utils.suivi_affaires.releve import MODE_AFFAIRES, MODE_ENTRETIEN, releve
from app.utils.points_conseil import point_courant, releve_du_point
from app.utils.points_conseil_etats import etat_par_defaut

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
    #: Les bâtiments visés (#2043) ; l'état de la visite, en mode `entretien`.
    batiments: list[int]
    etat_visite: Optional[str] = None
    #: Nouvelle, ou une entrée au fil depuis le dernier résumé (#2044), et pourquoi.
    a_evolue: bool
    motif_evolution: Optional[str] = None
    #: « Qui la lit » (#2089) : les champs que lit la pastille de la page Affaires.
    confidentiel: bool = False
    public_cible: list[str] = []
    reserve_perimetre: bool = False
    #: L'état coché d'office à la saisie de son CR — « À l'AG » reste à l'AG (#2082).
    etat_par_defaut: str = ""
    #: Le groupe des affaires liées rassemblées (#2083) — `None` pour une affaire seule.
    groupe: Optional[int] = None
    #: L'historique de fusion, cité au point : « TK-12 — Titre » des absorbées.
    fusionnees: list[str] = []

    class Config:
        from_attributes = True


class TrancheRead(BaseModel):
    cle: str
    libelle: str
    nombre: int
    #: La teinte de la tranche (`repartition.teinter`) — l'écran la peint, sans la choisir.
    teinte: str = ""

    class Config:
        from_attributes = True


class BarreRead(BaseModel):
    """Une barre d'une répartition, découpée selon l'autre (#2043)."""

    cle: str
    libelle: str
    nombre: int
    tranches: list[TrancheRead]

    class Config:
        from_attributes = True


class SuiviAffairesRead(BaseModel):
    jour: date
    total: int
    anciennes: int
    #: Les affaires fusionnées dans celles du relevé — le troisième chiffre.
    fusionnees: int = 0
    #: Par catégorie (tranches par bâtiment) et par bâtiment (tranches par catégorie).
    par_categorie: list[BarreRead]
    par_batiment: list[BarreRead]
    mode: str
    affaires: list[AffaireOuverteRead]
    #: Le délai de relance réglé, en jours — le pli « moins de N jours » le cite.
    delai_jours: int
    #: Le ✨ a-t-il un sens ? Décidé par le serveur, rien de la configuration ne sort.
    resumes_disponibles: bool

    class Config:
        from_attributes = True


class ResumesRedigesRead(BaseModel):
    #: Le nombre d'affaires dont le résumé vient d'être écrit.
    rediges: int


def _mode(mode: str) -> str:
    if mode not in (MODE_AFFAIRES, MODE_ENTRETIEN):
        raise HTTPException(422, "Mode du rapport inconnu")
    return mode


@router.get("", response_model=SuiviAffairesRead, summary="Les affaires non closes (CS/Admin)")
def lire_suivi(
    mode: str = MODE_AFFAIRES,
    point: bool = False,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    #  Le tableau d'un point en cours ou en relecture garde SES affaires, même
    #  closes ailleurs entre-temps (#2082) ; la relance, elle, lit sans `point`.
    mode = _mode(mode)
    courant = point_courant(session, mode) if point else None
    r = releve_du_point(session, courant, user) if courant else releve(session, user, mode)
    #  Lu sur le relevé (jour, total, anciennes, mode, délai) ; ne se nomme que
    #  ce qui se calcule ici (`lire_objet`, #1563).
    return lire_objet(
        SuiviAffairesRead,
        r,
        par_categorie=[BarreRead.model_validate(c) for c in r.par_categorie],
        par_batiment=[BarreRead.model_validate(c) for c in r.par_batiment],
        affaires=[
            lire_objet(AffaireOuverteRead, a, etat_par_defaut=etat_par_defaut(a.statut))
            for a in r.affaires
        ],
        #  Pas de résumé en mode entretien : une visite se dit par son état (#2043).
        resumes_disponibles=r.mode == MODE_AFFAIRES and assistant.disponible(session),
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
    #  Seules les affaires nouvelles ou qui ont évolué depuis leur dernier
    #  résumé (#2044) : les autres gardent le leur, et l'appel coûte moins.
    tout = releve(session, user)
    r = replace(tout, affaires=[a for a in tout.affaires if a.a_evolue])
    try:
        par_affaire = await assistant.rediger(session, r, demandeur=user.id)
    except ErreurLLM as exc:
        raise HTTPException(400, str(exc))
    return ResumesRedigesRead(rediges=assistant.enregistrer_resumes(session, r, par_affaire))


@router.post("/pdf", summary="Le rapport Suivi des affaires en PDF (CS/Admin)")
def exporter_pdf(
    mode: str = MODE_AFFAIRES,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    site = config_site(session)
    pdf = generer_pdf(
        releve(session, user, _mode(mode)),
        site_nom=nom_site(site.get("site_nom")),
        logo_png=logo_televerse_png(session),
    )
    nom = f"suivi-des-affaires-{horloge.aujourd_hui():%Y-%m-%d}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )
