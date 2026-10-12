"""Router diagnostics réglementaires — types + rapports avec upload."""

import logging
from datetime import datetime, date as dateclass
from app.utils import horloge
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import DiagnosticRapport, DiagnosticType, Utilisateur
from app.utils.annexes import retirer_fichier_principal, supprimer_annexes
from app.utils.fichiers import enregistrer_televersement
from app.utils.stockage import stockage
from app.utils.lecture import lire_objet
from app.utils.recuperer import fichier_ou_404, ou_404

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


# ── Schémas ────────────────────────────────────────────────────────────────


class RapportRead(BaseModel):
    id: int
    diagnostic_type_id: int
    titre: str
    date_rapport: Optional[dateclass] = None
    fichier_nom: str
    taille_octets: Optional[int] = None
    mime_type: str
    synthese: Optional[str] = None
    publie_le: datetime

    class Config:
        from_attributes = True


class DiagnosticTypeRead(BaseModel):
    id: int
    code: str
    nom: str
    texte_legislatif: str
    frequence: Optional[str] = None
    ordre: int
    non_applicable: bool = False
    rapports: list[RapportRead] = []

    class Config:
        from_attributes = True


class DiagnosticTypeNonApplicableUpdate(BaseModel):
    non_applicable: bool


class RapportUpdate(BaseModel):
    titre: Optional[str] = None
    date_rapport: Optional[str] = None  # ISO date string ou null
    synthese: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/types", response_model=list[DiagnosticTypeRead])
def list_types(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    types = session.exec(
        select(DiagnosticType)
        .where(DiagnosticType.actif == True)  # noqa: E712
        .order_by(DiagnosticType.ordre)
    ).all()
    return [_type_lu(session, t) for t in types]


def _type_lu(session: Session, t: DiagnosticType) -> DiagnosticTypeRead:
    """Un type de diagnostic et ses rapports, le plus récent d'abord.

    🔴 Écrit DEUX FOIS, colonne par colonne — la liste et la bascule « non
    applicable » — jusqu'au 02/10/2026 (#1563).
    """
    rapports = session.exec(
        select(DiagnosticRapport)
        .where(DiagnosticRapport.diagnostic_type_id == t.id)
        .order_by(
            DiagnosticRapport.date_rapport.desc().nullslast(), DiagnosticRapport.publie_le.desc()
        )
    ).all()
    return lire_objet(
        DiagnosticTypeRead, t, rapports=[RapportRead.model_validate(r) for r in rapports]
    )


@router.patch("/types/{type_id}/non-applicable", response_model=DiagnosticTypeRead)
def toggle_non_applicable(
    type_id: int,
    body: DiagnosticTypeNonApplicableUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    diag_type = ou_404(session, DiagnosticType, type_id, "Type de diagnostic")
    diag_type.non_applicable = body.non_applicable
    session.add(diag_type)
    session.commit()
    session.refresh(diag_type)
    return _type_lu(session, diag_type)


@router.post("/types/{type_id}/rapports", response_model=RapportRead, status_code=201)
async def upload_rapport(
    type_id: int,
    titre: str = Form(...),
    date_rapport: str | None = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    ou_404(session, DiagnosticType, type_id, "Type de diagnostic")

    # Dans le dossier PRIVÉ (`enregistrer_televersement`) et non à la racine du
    # volume : un rapport de diagnostic (DPE, amiante, plomb) se télécharge par un
    # endpoint authentifié ; posé à la racine, il serait aussi servi en statique
    # par Caddy, sans aucun contrôle.
    raw_name = file.filename or "rapport"
    #  Les 16 premiers octets suffisent à toutes les signatures connues ;
    #  🔴 Validation ET écriture en un seul geste (#825) : lire seize octets,
    #  rembobiner, vérifier la signature, journaliser, refuser, nommer, copier.
    #  Ces neuf lignes étaient recopiées dans trois routeurs — une copie qui
    #  oublie le `seek(0)` écrit un fichier tronqué sans que rien ne le dise.
    cle = enregistrer_televersement(file, raw_name, user)
    st = stockage()

    parsed_date = None
    if date_rapport:
        try:
            parsed_date = dateclass.fromisoformat(date_rapport)
        except ValueError:
            pass

    rapport = DiagnosticRapport(
        diagnostic_type_id=type_id,
        titre=titre,
        date_rapport=parsed_date,
        # `raw_name` vaut déjà `file.filename or "rapport"` : un seul repli, en
        # amont, plutôt que deux expressions à garder d'accord.
        fichier_nom=raw_name,
        **st.colonnes(cle),
        taille_octets=st.chemin(cle).stat().st_size,
        mime_type=file.content_type or "application/octet-stream",
        publie_par_id=user.id,
        publie_le=horloge.maintenant(),
    )
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    return rapport


@router.patch("/rapports/{rapport_id}", response_model=RapportRead)
def update_rapport(
    rapport_id: int,
    body: RapportUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    rapport = ou_404(session, DiagnosticRapport, rapport_id, "Rapport")
    if body.titre is not None:
        rapport.titre = body.titre
    if body.date_rapport is not None:
        try:
            rapport.date_rapport = (
                dateclass.fromisoformat(body.date_rapport) if body.date_rapport else None
            )
        except ValueError:
            pass
    elif body.date_rapport == "":
        rapport.date_rapport = None
    if "synthese" in body.model_fields_set:
        rapport.synthese = body.synthese or None
    session.add(rapport)
    session.commit()
    session.refresh(rapport)
    return rapport


@router.delete("/rapports/{rapport_id}/fichier", response_model=RapportRead)
def retirer_fichier_rapport(
    rapport_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Retire le fichier du rapport : sa première annexe prend sa place — le geste
    du document (`utils/annexes`)."""
    rapport = ou_404(session, DiagnosticRapport, rapport_id, "Rapport")
    retirer_fichier_principal(session, rapport, "diagnostic")
    return rapport


@router.delete("/rapports/{rapport_id}", status_code=204)
def delete_rapport(
    rapport_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    rapport = ou_404(session, DiagnosticRapport, rapport_id, "Rapport")
    #  Le rapport emporte ses annexes (migration 0278, `utils/annexes`).
    supprimer_annexes(session, "diagnostic", rapport_id)
    # Supprime le fichier physique
    stockage().supprimer_de(rapport)
    session.delete(rapport)
    session.commit()


@router.get("/rapports/{rapport_id}/télécharger")
def download_rapport(
    rapport_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    rapport = ou_404(session, DiagnosticRapport, rapport_id, "Rapport")
    return FileResponse(
        fichier_ou_404(stockage().fichier_de(rapport)),
        filename=rapport.fichier_nom,
        media_type=rapport.mime_type,
    )
