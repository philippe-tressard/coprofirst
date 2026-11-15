"""📊 Les affaires d'un prestataire, en chiffres — sur sa fiche (#1646).

Combien d’affaires closes il a eues parmi les intervenants désignés
(`utils/prestataires_affaire`, #2704), combien de temps elles sont restées « Chez le
prestataire » (jours ouvrés), leur durée totale, les relances au syndic — et
l'évolution d'un exercice comptable à l'autre.

## Arbitré par l'utilisateur (04/10/2026)

- **Le conseil syndical seul** (`require_cs_or_admin`), comme la notation de
  l'intervenant : c'est une donnée de négociation.
- **Toutes les affaires** où il est intervenu, celles du carnet comme les autres.

Le calcul n'est pas ici : `utils/synthese_affaire/agregats` mesure chaque
affaire comme sa synthèse la mesurerait, et le bilan du carnet emploie le même.

Un fichier à part, et non une route de plus dans `prestataires.py` : celui-ci
approche les 500 lignes (modularité, rang 1). Même préfixe — l'URL dit l'objet,
le fichier dit le sujet, comme `compteurs.py` et `prestataires_archivage.py`.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Prestataire, Utilisateur
from app.schemas_synthese import ExerciceLu, ResumeAffaires
from app.utils.recuperer import ou_404
from app.utils.prestataires_affaire import affaires_du_prestataire
from app.utils.synthese_affaire.agregats import bilan_prestataire
from app.utils.valeurs import valeur

router = APIRouter(prefix="/prestataires", tags=["prestataires"])


class AffaireExercice(BaseModel):
    """Une affaire close d'un exercice, listée sous lui (R3d)."""

    id: int
    titre: str
    cloture: Optional[str] = None
    issue: str


class ResumeExercice(ResumeAffaires, ExerciceLu):
    """Les moyennes d'un exercice comptable, et ses affaires (la plus récente d'abord)."""

    affaires: list[AffaireExercice] = []


class MetriquesPrestataire(BaseModel):
    """L'ensemble des affaires closes du prestataire, puis chaque exercice (le plus récent d'abord)."""

    prestataire_id: int
    ensemble: ResumeAffaires
    exercices: list[ResumeExercice]


@router.get("/{p_id}/metriques", response_model=MetriquesPrestataire)
def lire_metriques_prestataire(
    p_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les métriques des affaires closes où ce prestataire était l'intervenant désigné."""
    ou_404(session, Prestataire, p_id, "Prestataire")
    return bilan_prestataire(session, p_id)


class AffaireANoter(BaseModel):
    """Une affaire où le prestataire est intervenant — ce qu'on peut noter avec lui."""

    id: int
    titre: str
    statut: str


@router.get("/{p_id}/affaires", response_model=list[AffaireANoter], deprecated=True)
def lire_affaires_du_prestataire(
    p_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """ANNONCÉE AU RETRAIT (v3.100.0) : remplacée par `GET /prestataires/affaires-a-noter`.

    Les affaires où ce prestataire est intervenant désigné, la plus récente d'abord —
    le choix proposé quand le conseil syndical note le couple prestataire / affaire."""
    ou_404(session, Prestataire, p_id, "Prestataire")
    return [
        AffaireANoter(id=t.id, titre=t.titre, statut=valeur(t.statut))
        for t in affaires_du_prestataire(session, p_id)
    ]
