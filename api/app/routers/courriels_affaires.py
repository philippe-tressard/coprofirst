"""Les courriels reçus à l'adresse des affaires — ce que la relève en a fait.

Espace CS › Courriels. Une ligne par message traité (`utils/courriel_journal`),
les plus récents d'abord, dans la limite du paramètre du site.

## Qui lit quoi (05/10/2026)

Le conseil syndical et l'administration — c'est le conseil qui transfère les
messages, c'est lui qui doit voir qu'un transfert n'est pas entré. Mais l'adresse
d'un expéditeur est une donnée personnelle : **l'administrateur la lit en entier,
le conseil n'en lit que le nom**. Le journal était réservé à l'admin pour cette
raison ; ouvrir la lecture ne doit pas ouvrir l'adresse.

⚠️ Jamais le corps du message : le journal dit ce qui a été DÉCIDÉ, le texte vit
dans le fil de l'affaire ou dans la boîte de réception.

## Sauf un message À CLASSER (#2555)

Authentifié, d'un correspondant connu, il ne désigne aucune affaire : la ligne
porte son aperçu et des affaires suggérées, et trois gestes — le rattacher, en
créer une affaire, l'écarter (`utils/courriel_a_classer`). Le conseil classe :
c'est lui qui transfère, et qui écrit au fil de toute affaire.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import RoleUtilisateur, Ticket, Utilisateur
from app.models.courriel import CourrielAClasser
from app.utils import courriel_a_classer as a_classer
from app.utils.courriel_fil import repere_ecrit
from app.utils.recuperer import ou_404, present_ou_404
from app.utils.courriel_journal import (
    derniers_releves,
    nom_de_l_expediteur,
    nombre_affiche,
)

router = APIRouter(prefix="/courriels-affaires", tags=["courriels-affaires"])


class AffaireSuggeree(BaseModel):
    id: int
    numero: str
    titre: str


class AClasserRead(BaseModel):
    """Le message en attente d'une ligne du journal (#2555)."""

    id: int
    statut: str
    #: Le début du texte, sans citation — vide une fois classé.
    apercu: str = ""
    #: Les affaires ouvertes proches : une proposition, jamais un choix fait.
    suggestions: list[AffaireSuggeree] = []


class CourrielReleveRead(BaseModel):
    """Une ligne du journal des relèves — propre à cet écran, donc déclarée ici."""

    id: int
    releve_le: datetime
    envoye_le: datetime | None = None
    #: L'adresse en entier pour l'administrateur, le nom seul pour le conseil.
    expediteur: str
    objet: str
    decision: str
    motif: str
    ticket_id: int | None = None
    affaire: str | None = None
    a_classer: AClasserRead | None = None


class JournalCourriels(BaseModel):
    #: Le paramètre du site : combien de messages l'écran en montre au plus.
    limite: int
    messages: list[CourrielReleveRead]


@router.get("", response_model=JournalCourriels)
def courriels_affaires(
    user: Utilisateur = Depends(require_cs_or_admin),
    session: Session = Depends(get_session),
):
    """Ce que la relève a fait des derniers messages, et pourquoi (#1447).

    Les IGNORE y figurent — c'est eux qui étaient muets.
    """
    voit_l_adresse = user.has_role(RoleUtilisateur.admin)
    releves = derniers_releves(session)
    attente = a_classer.en_attente(session, [r.id for r in releves])
    messages = []
    for r in releves:
        ligne = CourrielReleveRead.model_validate(r, from_attributes=True)
        if not voit_l_adresse:
            ligne.expediteur = nom_de_l_expediteur(r.expediteur)
        if r.id in attente:
            ligne.a_classer = _a_classer_lu(session, attente[r.id])
        messages.append(ligne)
    return JournalCourriels(limite=nombre_affiche(session), messages=messages)


def _a_classer_lu(session: Session, item: CourrielAClasser) -> AClasserRead:
    if item.statut != a_classer.A_CLASSER:
        return AClasserRead(id=item.id, statut=item.statut)
    return AClasserRead(
        id=item.id,
        statut=item.statut,
        apercu=a_classer.apercu(item),
        suggestions=[
            AffaireSuggeree(id=t.id, numero=t.numero, titre=t.titre)
            for t in a_classer.suggestions(session, item)
        ],
    )


class Rattachement(BaseModel):
    #: Le numéro de l'affaire, tel qu'on l'écrit (« TK-570894 », « #TK-570894 »).
    numero: str


class Classement(BaseModel):
    """Ce que le geste a fait — le bilan, et l'affaire qui a reçu le message."""

    bilan: str
    ticket_id: int | None = None


def _classable(session: Session, item_id: int) -> CourrielAClasser:
    return ou_404(session, CourrielAClasser, item_id, "Message à classer")


def _geste(session: Session, faire) -> Classement:
    """Le geste, ou un 409 dont le motif est écrit pour l'écran."""
    try:
        bilan, ticket = faire()
    except a_classer.NonClassable as exc:
        raise HTTPException(409, str(exc).capitalize() + ".") from exc
    session.commit()
    return Classement(bilan=bilan, ticket_id=ticket.id if ticket else None)


@router.post("/a-classer/{item_id}/rattacher", response_model=Classement)
def rattacher(
    item_id: int,
    corps: Rattachement,
    user: Utilisateur = Depends(require_cs_or_admin),
    session: Session = Depends(get_session),
):
    """Verse le message au fil d'une affaire OUVERTE, comme un transfert du conseil."""
    item = _classable(session, item_id)
    numero = repere_ecrit(corps.numero)
    ticket = present_ou_404(
        numero
        and session.exec(select(Ticket).where(func.lower(Ticket.numero) == numero.lower())).first()
        or None,
        f"Aucune affaire « {corps.numero.strip()} ».",
    )
    return _geste(session, lambda: (a_classer.rattacher(session, item, ticket, user), ticket))


@router.post("/a-classer/{item_id}/creer", response_model=Classement)
def creer(
    item_id: int,
    user: Utilisateur = Depends(require_cs_or_admin),
    session: Session = Depends(get_session),
):
    """Une affaire neuve, décrite par le message — Étude & travaux, conseil seul."""
    item = _classable(session, item_id)

    def faire():
        ticket = a_classer.creer(session, item, user)
        return f"affaire #{ticket.numero} créée", ticket

    return _geste(session, faire)


@router.post("/a-classer/{item_id}/ecarter", response_model=Classement)
def ecarter(
    item_id: int,
    user: Utilisateur = Depends(require_cs_or_admin),
    session: Session = Depends(get_session),
):
    """Rien n'est écrit : le message n'appelait pas de suite."""
    item = _classable(session, item_id)

    def faire():
        a_classer.ecarter(session, item, user)
        return "message écarté", None

    return _geste(session, faire)
