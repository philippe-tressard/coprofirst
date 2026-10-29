"""Les transcriptions des PV d'AG — Ma résidence › Règlement, pour l'administration (29/10/2026).

Un PV déposé dans la Fiche est transcrit par l'assistant — d'office par la tâche
quotidienne s'il est récent, par « Transcrire » sinon —, puis RELU et validé ici :
il devient alors un fichier des décisions d'AG, que les questions au règlement
lisent. Toutes les routes sont à l'administration, comme les fichiers que
l'assistant lit (`visibility.CATEGORIES_ADMIN_SEUL`).

La logique vit dans `utils/question_reglement/transcription` ; ce routeur la sert.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import contexte
from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import Document, Utilisateur
from app.models.reglement import TranscriptionPV
from app.utils import llm_limites
from app.utils.lecture import lire_objet
from app.utils.question_reglement import transcription as tr
from app.utils.recuperer import ou_404

#  Monté par `routers/reglement.py`, sous son préfixe `/reglement`.
router = APIRouter(prefix="/transcriptions")


class TranscriptionRead(BaseModel):
    id: int
    statut: str
    statut_libelle: str
    contenu: Optional[str] = None
    erreur: Optional[str] = None
    cree_le: datetime
    valide_le: Optional[datetime] = None

    class Config:
        from_attributes = True


class PvTranscrit(BaseModel):
    """Un PV de la Fiche, et sa dernière transcription."""

    pv_id: int
    titre: str
    date_ag: Optional[date] = None
    transcription: Optional[TranscriptionRead] = None


class EtatTranscriptions(BaseModel):
    #: L'usage « Transcription d'un PV » est-il prêt ? — sinon, pas de bouton.
    disponible: bool
    pvs: list[PvTranscrit]


class ValidationTranscription(BaseModel):
    contenu: str = Field(min_length=tr.MIN_CARACTERES, max_length=tr.MAX_CARACTERES)


def _lire(ligne: TranscriptionPV) -> TranscriptionRead:
    return lire_objet(TranscriptionRead, ligne, statut_libelle=tr.statut_libelle(ligne.statut))


@router.get("", response_model=EtatTranscriptions)
def lister(session: Session = Depends(get_session), _: Utilisateur = Depends(require_admin)):
    """Les PV de la Fiche, du plus récent au plus ancien, chacun avec sa transcription."""
    sortie = []
    for pv in tr.pvs(session):
        ligne = tr.derniere_transcription(session, pv.id)
        sortie.append(
            PvTranscrit(
                pv_id=pv.id,
                titre=pv.titre,
                date_ag=pv.date_ag,
                transcription=_lire(ligne) if ligne else None,
            )
        )
    return EtatTranscriptions(disponible=tr.disponible(session), pvs=sortie)


@router.post("/pv/{pv_id}", response_model=TranscriptionRead, status_code=202)
def transcrire(
    pv_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """« Transcrire » : ouvre la transcription et la remplit en tâche de fond.

    Refusée si une transcription de ce PV est en cours ou attend sa relecture : la
    relire, ou la rejeter, d'abord."""
    pv = ou_404(session, Document, pv_id, "Procès-verbal")
    cat = tr.categorie(session, tr.CODE_PV)
    if cat is None or pv.categorie_id != cat.id:
        raise HTTPException(400, "Ce document n'est pas un PV d'assemblée générale.")
    if not tr.disponible(session):
        raise HTTPException(
            400, "L'assistant n'est pas activé pour cette transcription (Admin › Assistant IA)."
        )
    derniere = tr.derniere_transcription(session, pv.id)
    if derniere is not None and derniere.statut in (tr.EN_COURS, tr.A_RELIRE):
        raise HTTPException(409, "Une transcription de ce PV est en cours ou attend sa relecture.")
    refus = llm_limites.refus_avant_envoi(session, tr.USAGE_TRANSCRIPTION_PV, user.id)
    if refus:
        raise HTTPException(429, refus[1])
    ligne = tr.ouvrir(session, pv, user.id)
    background_tasks.add_task(tr.en_tache_de_fond, contexte.courante(), ligne.id)
    return _lire(ligne)


@router.post("/{transcription_id}/valider", response_model=TranscriptionRead)
def valider(
    transcription_id: int,
    body: ValidationTranscription,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """Le texte RELU — corrigé ou non — entre dans les décisions que l'assistant lit."""
    ligne = ou_404(session, TranscriptionPV, transcription_id, "Transcription")
    return _lire(tr.valider(session, ligne, body.contenu, user))


@router.delete("/{transcription_id}", status_code=204)
def rejeter(
    transcription_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Rejette une transcription à relire ou en échec — le PV peut être retranscrit.

    Une transcription VALIDÉE ne se rejette pas ici : son fichier se retire des
    décisions d'AG, comme tout fichier que l'assistant lit."""
    ligne = ou_404(session, TranscriptionPV, transcription_id, "Transcription")
    if ligne.statut not in (tr.A_RELIRE, tr.ECHEC):
        raise HTTPException(409, "Seule une transcription à relire ou en échec se rejette.")
    session.delete(ligne)
    session.commit()
