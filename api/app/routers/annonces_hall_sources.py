"""Annonces de hall — ce qu'une affiche peut REPRENDRE du fil.

Extrait de `routers/annonces_hall.py` le 28/09/2026, au fil de l'eau (#779) : le
fichier faisait 523 lignes. Lister les éléments reprenables et pré-remplir une
affiche depuis l'un d'eux est une notion à part — la lecture du fil — qui ne
partage rien avec la création, l'envoi ou l'historique des affiches. Même
découpage que l'aperçu (`annonces_hall_apercu`) : un routeur sans préfixe,
inclus par celui des annonces AVANT ses routes à paramètre.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.routers.annonces_hall_schemas import PrefillAffiche, SourceReprenable
from app.utils.recuperer import connu_ou_404, present_ou_404

router = APIRouter()


@router.get(
    "/sources",
    response_model=list[SourceReprenable],
    summary="Ce qu'on peut reprendre au hall (CS/Admin)",
)
def sources_reprenables(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les éléments du fil qu'une affiche peut reprendre — trois familles.

    Signalé à l'écran le 10/09/2026 : « je ne vois pas la présélection de toutes
    les publications, tickets etc. publiés dans le fil ». Le sélecteur ne
    proposait que des `Publication` ; le fil, lui, agrège aussi les tickets et
    les événements. La règle et les exclusions vivent dans `utils/sources_affiche`.
    """
    from app.utils.sources_affiche import sources_disponibles

    return [
        {
            "cle": s.cle(),
            "type": s.type,
            "famille": s.famille,
            "id": s.id,
            "titre": s.titre,
            "date": s.date,
            "epingle": s.epingle,
        }
        for s in sources_disponibles(session)
    ]


@router.get(
    "/depuis/{type_source}/{id_source}",
    response_model=PrefillAffiche,
    summary="Pré-remplissage depuis un élément du fil (CS/Admin)",
)
def prefill_depuis_element(
    type_source: str,
    id_source: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Pré-remplit l'affiche depuis une affaire (actualités comprises) ou un événement.

    ⚠️ Un élément confidentiel, archivé ou brouillon rend **404**, sans dire
    lequel des deux motifs s'applique : distinguer « inexistant » de « existant
    mais fermé » renseignerait sur un contenu qu'on protège.
    """
    from app.utils.sources_affiche import FAMILLES, prefill_source

    connu_ou_404(FAMILLES, type_source, "Type d'élément inconnu")
    return present_ou_404(
        prefill_source(session, type_source, id_source), "Élément introuvable ou non reprenable"
    )
