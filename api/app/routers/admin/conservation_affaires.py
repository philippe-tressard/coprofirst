"""Admin — le CONSTAT de la conservation des affaires (#2014, lot L1).

Ce qui partira, et quand : par exercice et par type, le nombre d'affaires et le
poids de leurs pièces jointes (`utils/conservation_affaires.constat`). En lecture
seule : rien n'est archivé ni retiré tant que le lot L2 n'est pas livré et que
l'administrateur n'a pas coché la case qui l'applique.

Réservé à l'ADMINISTRATEUR de la copropriété : ce sont les données de la
résidence, que l'opérateur de la plateforme ne lit pas (#1750).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.utils import conservation_affaires as ca
from app.utils.lecture import lire_objet
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


class ConstatConservation(BaseModel):
    #: le mois où commence l'exercice — `None` : l'année civile (fiche copropriété)
    mois_debut_exercice: Optional[int] = None
    #: L1 : toujours faux — le constat ne retire rien
    application_active: bool = False
    echeances: list[EcheanceLue]


@router.get("/conservation-affaires", response_model=ConstatConservation)
def lire_constat(session: Session = Depends(get_session), _: Utilisateur = Depends(require_admin)):
    return ConstatConservation(
        mois_debut_exercice=mois_debut_exercice(session),
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
    )
