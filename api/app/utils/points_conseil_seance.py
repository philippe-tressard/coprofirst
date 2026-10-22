"""Les affaires OUVERTES EN SÉANCE d'un point CS / Syndic (#2084).

## La demande (19/10/2026, reformulation validée le 20/10/2026)

> « Offrir la possibilité d'ajouter un point (qui n'est pas une affaire non
> close) en fin des affaires, avec possibilité d'ouvrir une affaire en séance ;
> et par défaut, à chaque nouveau point, une affaire sera préinitialisée avec
> les éléments de ce reporting, de catégorie Études & travaux, avec la date du
> point, pour permettre d'ajouter des points annexes CS & Syndic. »

## Arbitré le 20/10/2026

- L'affaire **« Points annexes CS & Syndic du <date> »** est créée **dès
  l'ouverture** d'un point du **Suivi affaires** seulement — une réunion, une
  affaire annexe : le point Entretiens repris à moins de deux heures est la même
  réunion. Catégorie Études & travaux — lue du conseil seul, par la règle de sa
  catégorie (`visibility/defauts_affaire`) —, préremplie du Quand, du Où et du
  Qui. Restée sans compte rendu à la validation, ou point abandonné : elle est
  **annulée** (`annuler_annexe_vide`), jamais supprimée — archiver ≠ supprimer.
- **Ouvrir une affaire en séance** : titre, catégorie, description ; elle rejoint
  la liste du point (`ajouter_affaire_initiale`) et paraît en fin de tableau —
  la plus récente.
"""

from __future__ import annotations

import html
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session

from app.models.core import STATUTS_TICKET_CLOS, Utilisateur
from app.models.points_conseil import MODE_AFFAIRES, PointConseil
from app.models.tickets import CategorieTicket, Ticket, TicketEvolution
from app.utils import horloge
from app.utils.categories_ticket import libelle_categorie
from app.utils.dates_fr import date_longue, datetime_longue
from app.utils.perimetres import perimetre_cible_json
from app.utils.points_conseil import (
    ajouter_affaire_initiale,
    cr_de,
    nom_present,
    presents_du_point,
)
from app.utils.points_conseil_ou import ou_du_point
from app.utils.suivi_affaires.repartition import ORDRE_SERIES
from app.utils.valeurs import valeur

#: Le titre de l'affaire annexe — la date du point s'y lit.
TITRE_ANNEXE = "Points annexes CS & Syndic du {date}"

#: Les catégories qu'une affaire ouverte en séance peut prendre : celles du
#: rapport — ni actualité, ni bogue. La liste est celle des séries de couleur.
CATEGORIES_SEANCE: tuple[str, ...] = ORDRE_SERIES


def creer_affaire(
    session: Session,
    point: PointConseil,
    user: Utilisateur,
    *,
    titre: str,
    categorie: str,
    description: str,
) -> Ticket:
    """Une affaire ouverte pendant le point, qui rejoint sa liste. Sans `commit`."""
    from app.routers.tickets.commun import generer_numero

    if categorie not in CATEGORIES_SEANCE:
        raise HTTPException(422, "Catégorie inconnue pour une affaire ouverte en séance")
    maintenant = horloge.maintenant()
    ticket = Ticket(
        numero=generer_numero(session),
        titre=titre.strip(),
        description=description,
        categorie=categorie,
        statut="ouvert",
        priorite="normale",
        auteur_id=user.id,
        perimetre_cible=perimetre_cible_json(),
        cree_le=maintenant,
        mis_a_jour_le=maintenant,
    )
    session.add(ticket)
    session.flush()
    ajouter_affaire_initiale(point, ticket)
    session.add(point)
    return ticket


def _description_annexe(session: Session, point: PointConseil) -> str:
    e = html.escape
    presents = ", ".join(nom_present(p) for p in presents_du_point(session, point.id))
    return (
        f"<p>Point CS / Syndic du {e(datetime_longue(point.debut))} — {e(ou_du_point(point))}.</p>"
        + (f"<p>Présents : {e(presents)}.</p>" if presents else "")
        + "<p>Les points abordés en dehors des affaires en cours se notent dans le "
        "compte rendu de cette affaire.</p>"
    )


def ouvrir_annexe(session: Session, point: PointConseil, user: Utilisateur) -> Optional[Ticket]:
    """L'affaire « Points annexes » d'un point du Suivi affaires — créée à
    l'ouverture, une seule. Sans `commit`."""
    if point.mode != MODE_AFFAIRES or point.affaire_annexe_id is not None:
        return None
    ticket = creer_affaire(
        session,
        point,
        user,
        titre=TITRE_ANNEXE.format(date=date_longue(point.debut)),
        categorie=CategorieTicket.etude_travaux.value,
        description=_description_annexe(session, point),
    )
    point.affaire_annexe_id = ticket.id
    session.add(point)
    return ticket


def annuler_annexe_vide(session: Session, point: PointConseil, par: Optional[Utilisateur]) -> bool:
    """L'affaire annexe restée sans compte rendu est annulée — à la validation
    comme à l'abandon du point. Rend vrai si elle l'a été. Sans `commit`."""
    from app.routers.tickets.suite_sections import appliquer_statut

    ticket = session.get(Ticket, point.affaire_annexe_id) if point.affaire_annexe_id else None
    if ticket is None or valeur(ticket.statut) in STATUTS_TICKET_CLOS:
        return False
    if point.id is not None and cr_de(session, point.id, ticket.id) is not None:
        return False
    maintenant = horloge.maintenant()
    evol = TicketEvolution(
        ticket_id=ticket.id,
        type="etat",
        contenu="Aucun point annexe n'a été noté pendant le point CS / Syndic.",
        ancien_statut=valeur(ticket.statut),
        nouveau_statut="annulé",
        auteur_id=par.id if par else point.auteur_id,
        cree_le=maintenant,
    )
    session.add(evol)
    #  Sans synthèse : une affaire vide n'a rien à raconter (21/10/2026).
    appliquer_statut(session, ticket, evol, "annulé", maintenant, synthese=False)
    return True


def categories_seance() -> list[tuple[str, str]]:
    """Les catégories proposées, avec leur libellé — la seule liste de l'écran."""
    return [(c, libelle_categorie(c)) for c in CATEGORIES_SEANCE]
