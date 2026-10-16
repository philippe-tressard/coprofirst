"""Router telemetry — le tableau de bord de l'administrateur.

La COLLECTE (`POST /telemetry/collect`, publique) vit dans `telemetry_collecte.py`
depuis le 28/09/2026 (#779) : écrire et lire sont deux notions, et ce fichier
dépassait 500 lignes. Les LECTURES — quatre portées et un filtre — vivent dans
`utils/telemetrie_tableau` depuis le 03/10/2026 : trois portées tenaient déjà
300 lignes ici, la quatrième et le filtre auraient repassé le plafond.
"""

from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.auth.deps import require_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.utils import horloge
from app.utils.telemetrie_calculs import _palmares
from app.utils.telemetrie_tableau import fiches_utilisateurs, tableau, top_utilisateurs

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/dashboard")
def dashboard(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
    scope: str = Query("jour", pattern="^(jour|mois|annee|total)$"),
    gestionnaire: str = Query("avec", pattern="^(avec|sans)$"),
):
    """Les statistiques agrégées du tableau de bord admin, par portée.

    scope=jour   → aujourd'hui (évènements bruts)
    scope=mois   → 30 jours (agrégat journalier)
    scope=annee  → 12 derniers mois (agrégat mensuel + mois en cours)
    scope=total  → 10 ans, par année
    gestionnaire=sans → sans les vues du gestionnaire du site, si le filtre est proposé
    """
    return tableau(session, scope, gestionnaire)


@router.get("/users-active")
def users_active(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Top utilisateurs actifs sur les 30 derniers jours."""
    #  Une DATE, comparée à `cree_le` — jamais le texte « AAAA-MM-JJ », que le
    #  serveur refuse de comparer à un horodatage (#1747).
    thirty_days_ago = datetime.combine(horloge.aujourd_hui() - timedelta(days=30), time.min)
    rows = top_utilisateurs(session, thirty_days_ago)
    fiches = fiches_utilisateurs(session, rows)
    return [{"user_id": r[0], **ligne} for r, ligne in zip(rows, _palmares(rows, fiches))]
