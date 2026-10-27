"""Les affaires liées qu'on peut ABSORBER en clôturant celle-ci (#1704).

La boîte de clôture les demande avant d'envoyer la Suite ou la correction qui
clôt : chacune avec son verdict. Une affaire lue par moins de monde que celle
qu'on clôt est montrée avec sa raison ET son plan de conciliation : l'écart, et
ce que chaque option ferait lire à qui (`utils/fusion_conciliation`). Le geste
lui-même passe par les champs `fusionner` et `conciliations` des deux chemins
de clôture (`utils/fusion_affaires`).

Le schéma de réponse vit ici : un seul routeur s'en sert.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Ticket, Utilisateur
from app.schemas import AffaireLieeLue
from app.utils.fusion_affaires import candidates
from app.utils.recuperer import ou_404
from app.utils.visibility import ticket_visible

router = APIRouter()


class PersonneConcernee(BaseModel):
    id: int
    nom: str


class EcartFusion(BaseModel):
    """Une section d'accès qui diffère entre les deux affaires."""

    champ: str
    libelle: str
    principale: str
    absorbee: str


class ResultatConciliation(BaseModel):
    perimetre: str
    destinataires: str
    acces: str


class OptionConciliation(BaseModel):
    """Une façon d'autoriser la fusion, avec ce qu'elle fait lire."""

    code: str
    libelle: str
    disponible: bool
    pourquoi: Optional[str] = None
    #: Les personnes qui liront ce qu'elles ne lisaient pas — à confirmer par leur nom.
    exposes: list[PersonneConcernee] = []
    #: Combien perdent l'accès à un fil qu'elles lisaient.
    perdants: int = 0
    resultat: Optional[ResultatConciliation] = None
    consentement: bool = False


class Conciliation(BaseModel):
    ecarts: list[EcartFusion]
    options: list[OptionConciliation]


class CandidateFusion(AffaireLieeLue):
    """Une affaire liée proposée à la fusion — la forme d'une affaire nommée
    (date de création comprise, #2173) —, et ce qui l'en empêche le cas échéant
    (avec le plan pour l'autoriser quand c'est une fuite de lecture)."""

    fusionnable: bool
    motif: Optional[str] = None
    conciliation: Optional[Conciliation] = None


@router.get("/{ticket_id}/fusion", response_model=list[CandidateFusion])
def candidates_a_la_fusion(
    ticket_id: int,
    inversion: bool = False,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """`inversion` : l'appelant laisse choisir qui absorbe (la correction, le Suivi) —
    pas la clôture, où l'affaire qu'on clôt absorbe (#1704)."""
    ticket = ou_404(session, Ticket, ticket_id, "Ticket")
    if not ticket_visible(ticket, user):
        raise HTTPException(403, "Accès refusé")
    return candidates(session, ticket, user, inversion=inversion)
