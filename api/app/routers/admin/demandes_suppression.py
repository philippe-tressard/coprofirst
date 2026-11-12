"""Admin — la file des demandes de suppression de compte (#2699).

Une personne demande l'effacement de son compte (`routers/auth_suppression.py`) ;
l'administration le traite par la purge de `DELETE /admin/utilisateurs/{id}`
(`suppression_compte.supprimer_compte`), inchangée. Réservé à l'ADMINISTRATEUR,
comme cette suppression : c'est une suppression définitive (CLAUDE.md, dépendances
d'auth). La file s'affiche dans l'onglet « À traiter » de `/admin`.

Les règles vivent dans `utils/demande_suppression`.
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session

from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.utils import demande_suppression as regles
from app.utils.demande_suppression import (
    DemandeSuppressionEnAttente,
    DemandeSuppressionTraitee,
)

router = APIRouter()


@router.get("/demandes-suppression", response_model=list[DemandeSuppressionEnAttente])
def lister_demandes_suppression(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Les demandes de suppression en cours, la plus ancienne d'abord."""
    return regles.file_d_attente(session)


@router.post("/demandes-suppression/{demande_id}/traiter", response_model=DemandeSuppressionTraitee)
def traiter_demande_suppression(
    demande_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Efface le compte qui l'a demandé (jamais en démonstration). 409 si elle n'est plus en cours."""
    return regles.traiter(session, demande_id, admin, background_tasks)
