"""Admin — la CONSERVATION des affaires (#2014).

- `GET /admin/conservation-affaires` : le CONSTAT (lot L1) — ce qui partira, et
  quand, par exercice et par type (`utils/conservation_affaires.constat`) —, l'état
  de la case qui l'applique (lot L2, `SERVICE_CONSERVATION`, cochée dans
  Admin › Services et nulle part ailleurs) et les archives produites, copiées sur
  le PC ou en attente (lot L3).
- `GET /admin/conservation-affaires/archives/{id}/fichier` : le téléchargement
  d'une archive tant que le serveur la garde.

Réservé à l'ADMINISTRATEUR de la copropriété : ce sont les données de la
résidence, que l'opérateur de la plateforme ne lit pas (#1750).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.auth.deps import require_admin
from app.database import get_session
from app.models.conservation import ArchiveAffaires
from app.models.core import Utilisateur
from app.utils import conservation_affaires as ca
from app.utils.conservation_application import application_active
from app.utils.conservation_copie import DELAI_RETRAIT_JOURS
from app.utils.conservation_politique import politique_annonce
from app.utils.lecture import lire_objet
from app.utils.recuperer import fichier_ou_404, ou_404
from app.utils.stockage import stockage
from app.utils.synthese_affaire.rassemblement import mois_debut_exercice

router = APIRouter()


class EcheanceLue(BaseModel):
    type: str
    libelle: str
    #: en exercices complets après celui de la clôture
    exercices: int
    fondement: str
    exercice_cloture: str
    dernier_exercice_garde: str
    echoit_le: date
    affaires: int
    fichiers: int
    octets: int
    absents: int


class ArchiveLue(BaseModel):
    id: int
    nom: str
    exercice: str
    type: str
    libelle: str
    affaires: int
    fichiers: int
    octets: int
    cree_le: datetime
    #: `None` : le poste ne l'a pas encore copiée
    copiee_le: Optional[datetime] = None
    #: `None` : le serveur la garde encore — téléchargeable
    retiree_le: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConstatConservation(BaseModel):
    #: le mois où commence l'exercice — `None` : l'année civile (fiche copropriété)
    mois_debut_exercice: Optional[int] = None
    #: la case d'Admin › Services : cochée, les affaires échues sont traitées la nuit
    application_active: bool = False
    #: la politique de confidentialité servie porte la phrase de conservation (mesuré
    #: sur le texte) : case cochée sans elle, l'écran le dit
    politique_annonce: bool = False
    #: le serveur retire sa copie d'une archive ce nombre de jours après sa copie
    delai_retrait_jours: int = DELAI_RETRAIT_JOURS
    echeances: list[EcheanceLue]
    archives: list[ArchiveLue] = []


def _libelle(code: str) -> str:
    return next((t.libelle for t in ca.TYPES if t.code == code), code)


@router.get("/conservation-affaires", response_model=ConstatConservation)
def lire_constat(session: Session = Depends(get_session), _: Utilisateur = Depends(require_admin)):
    archives = session.exec(
        select(ArchiveAffaires).order_by(col(ArchiveAffaires.cree_le).desc())
    ).all()
    return ConstatConservation(
        mois_debut_exercice=mois_debut_exercice(session),
        application_active=application_active(session),
        politique_annonce=politique_annonce(session),
        echeances=[
            lire_objet(
                EcheanceLue,
                e,
                type=e.type.code,
                libelle=e.type.libelle,
                exercices=e.type.exercices,
                fondement=e.type.fondement,
            )
            for e in ca.constat(session)
        ],
        archives=[lire_objet(ArchiveLue, a, libelle=_libelle(a.type)) for a in archives],
    )


@router.get("/conservation-affaires/archives/{archive_id}/fichier")
def telecharger_archive(
    archive_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    archive = ou_404(session, ArchiveAffaires, archive_id, "Archive")
    return FileResponse(
        fichier_ou_404(stockage().chemin(archive.cle), "Archive retirée du serveur"),
        filename=archive.nom,
        media_type="application/zip",
    )
