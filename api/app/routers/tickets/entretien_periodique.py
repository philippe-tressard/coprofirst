"""Tickets — l'entretien périodique de l'exercice : chaque visite, et si elle a eu lieu.

Espace CS › Reporting › Suivi des affaires : le bilan des visites en tête du mode
« Suivi entretiens périodiques » (#2043, `BilanVisites`) — arbitré le 10/10/2026. Ces
visites ont quitté la relance syndic, qui n'a pas à presser le syndic pour un
passage de prestataire sous contrat ; elles se suivent ici, une ligne par
passage prévu dans l'année civile en cours.

La règle (« qu'est-ce qu'un entretien périodique ? ») et l'état d'une visite
vivent dans `utils/entretien_periodique` — calculés au serveur, jamais par
l'écran.
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Ticket, Utilisateur
from app.models.prestataires import ContratEntretien, Prestataire
from app.utils import horloge
from app.utils.affaire_absorbee import pas_absorbee
from app.utils.entretien_periodique import condition_periodique, etat_visite, jour_de_reference
from app.utils.lecture import lire_objet

router = APIRouter()


class VisitePeriodique(BaseModel):
    """Une visite de l'exercice, telle que la vue la liste."""

    id: int
    numero: str
    titre: str
    statut: str
    debut: Optional[datetime] = None
    ferme_le: Optional[datetime] = None
    #  Dérivés : le nom de l'intervenant, le contrat, l'état au jour de la lecture.
    prestataire_nom: Optional[str] = None
    contrat_libelle: Optional[str] = None
    etat: str

    class Config:
        from_attributes = True


class EntretienPeriodiqueResponse(BaseModel):
    exercice: int
    visites: list[VisitePeriodique]


def _noms(session: Session, modele, ids: set[int], champ: str) -> dict[int, str]:
    """`id → libellé` pour les identifiants cités, en une requête."""
    if not ids:
        return {}
    lignes = session.exec(select(modele).where(col(modele.id).in_(ids))).all()
    return {o.id: getattr(o, champ) for o in lignes}


@router.get("/entretiens-periodiques", response_model=EntretienPeriodiqueResponse)
def lister_entretiens_periodiques(
    session: Session = Depends(get_session),
    _user: Utilisateur = Depends(require_cs_or_admin),
):
    """Les visites périodiques de l'année civile en cours, dans l'ordre des dates.

    Une affaire 📦 archivée ou absorbée par une fusion ne compte plus : le
    conseil l'a rangée, elle ne dit plus rien d'une visite à faire.
    """
    aujourd_hui: date = horloge.aujourd_hui()
    exercice = aujourd_hui.year
    candidates = session.exec(
        select(Ticket).where(condition_periodique(), ~col(Ticket.archive_manuel), pas_absorbee())
    ).all()
    visites = sorted(
        (t for t in candidates if jour_de_reference(t).year == exercice),
        key=lambda t: (jour_de_reference(t), t.numero),
    )
    prestataires = _noms(
        session, Prestataire, {t.prestataire_id for t in visites if t.prestataire_id}, "nom"
    )
    contrats = _noms(
        session, ContratEntretien, {t.contrat_id for t in visites if t.contrat_id}, "libelle"
    )
    return EntretienPeriodiqueResponse(
        exercice=exercice,
        visites=[
            lire_objet(
                VisitePeriodique,
                t,
                prestataire_nom=prestataires.get(t.prestataire_id),
                contrat_libelle=contrats.get(t.contrat_id),
                etat=etat_visite(t, aujourd_hui),
            )
            for t in visites
        ],
    )
