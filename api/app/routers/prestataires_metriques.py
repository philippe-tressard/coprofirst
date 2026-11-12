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

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Prestataire, Utilisateur
from app.schemas_synthese import ExerciceLu, ResumeAffaires
from app.utils.recuperer import ou_404
from app.utils.synthese_affaire.agregats import bilan_prestataire

router = APIRouter(prefix="/prestataires", tags=["prestataires"])


class ResumeExercice(ResumeAffaires, ExerciceLu):
    """Les moyennes d'un exercice comptable."""


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
