"""Les transferts de courriel versés dans une affaire — et les gestes qui les défont (#1482).

Un fil transféré à l'adresse des affaires y entre en autant de Suites que de
messages (`utils/courriel_transfert`). Versé au mauvais endroit, il s'annule, se
réaffecte ou devient une affaire neuve d'un geste : la règle et son pourquoi
sont dans `utils/versement_transfert`, qui ne sont qu'appelés ici.

Versé au BON endroit, il se valide : il quitte la liste (13/10/2026).

Qui : celui qui a transféré, et l'administrateur — `auth/appartenance` :
`peut_defaire_le_versement` le dit, `exiger_auteur_du_versement` en fait un 403.
La liste ne rend que les transferts que le lecteur peut défaire, et elle le
demande au même prédicat que le geste (#1551).
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.appartenance import (
    exiger_auteur_du_versement,
    exiger_objet_autorise,
    peut_defaire_le_versement,
)
from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Ticket, Utilisateur
from app.utils import versement_transfert as versements
from app.utils.noms import nom_auteur
from app.utils.recuperer import ou_404
from app.utils.visibility import ticket_visible

router = APIRouter()


class TransfertLu(BaseModel):
    """Un transfert versé, tel que l'affaire le montre à qui peut le défaire."""

    id: int
    cree_le: datetime
    transfere_par_nom: str
    suites: int
    affaire_creee: bool
    #: Pourquoi il ne se défait plus — absent s'il se défait.
    bloque: Optional[str] = None
    #: Réaffecter ou détacher : celui qui a transféré doit aussi modérer.
    peut_deplacer: bool


class Deplacement(BaseModel):
    """Vers une affaire existante — ou, sans `ticket_id`, vers une affaire neuve."""

    ticket_id: Optional[int] = None


class AffaireVisee(BaseModel):
    """L'affaire où le transfert est désormais — l'écran y conduit."""

    ticket_id: int
    numero: str


def _visee(ticket: Ticket) -> AffaireVisee:
    return AffaireVisee(ticket_id=ticket.id, numero=ticket.numero)


@router.get("/{ticket_id}/transferts", response_model=list[TransfertLu])
def lister_transferts(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    rendus = []
    for v in versements.a_proposer(session, ticket_id):
        #  La liste et le geste posent la même question (#1551).
        if not peut_defaire_le_versement(v, user, deplacer=False):
            continue
        auteur = session.get(Utilisateur, v.transfere_par_id)
        rendus.append(
            TransfertLu(
                id=v.id,
                cree_le=v.cree_le,
                transfere_par_nom=nom_auteur(auteur),
                suites=len(versements.suites_du(session, v)),
                affaire_creee=v.affaire_creee,
                bloque=versements.motif_bloquant(session, v),
                peut_deplacer=peut_defaire_le_versement(v, user, deplacer=True),
            )
        )
    return rendus


@router.post("/{ticket_id}/transferts/{transfert_id}/annuler", response_model=AffaireVisee)
def annuler_transfert(
    ticket_id: int,
    transfert_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    v = exiger_auteur_du_versement(session, ticket_id, transfert_id, user, deplacer=False)
    ticket = versements.annuler(session, v)
    session.commit()
    return _visee(ticket)


@router.post("/{ticket_id}/transferts/{transfert_id}/valider", response_model=AffaireVisee)
def valider_transfert(
    ticket_id: int,
    transfert_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    #  Le droit d'annuler : confirmer est le geste de celui qui a transféré.
    v = exiger_auteur_du_versement(session, ticket_id, transfert_id, user, deplacer=False)
    ticket = versements.valider(session, v, user)
    session.commit()
    return _visee(ticket)


@router.post("/{ticket_id}/transferts/{transfert_id}/deplacer", response_model=AffaireVisee)
def deplacer_transfert(
    ticket_id: int,
    transfert_id: int,
    body: Deplacement,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    v = exiger_auteur_du_versement(session, ticket_id, transfert_id, user, deplacer=True)
    if body.ticket_id is None:
        ticket = versements.detacher(session, v, user)
    else:
        #  On ne verse que dans une affaire qu'on lit : la même question.
        cible = ou_404(session, Ticket, body.ticket_id, "Ticket")
        if not ticket_visible(cible, user):
            raise HTTPException(403, "Accès refusé")
        ticket = versements.reaffecter(session, v, cible, user)
    session.commit()
    return _visee(ticket)
