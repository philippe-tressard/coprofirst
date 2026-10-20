"""L'ÉTAT À LA VALIDATION d'une affaire abordée en point CS / Syndic (#2082).

## La demande (19/10/2026, reformulation validée le 20/10/2026)

> « Lors de l'édition d'une affaire du CR : ajouter le changement d'état tel qu'il
> est et offrir la possibilité de changer l'état à la validation du CR (pas
> avant) : a minima Syndic, mais on peut dire clos ou annulé. »
>
> « Si une affaire a son suivi à AG, ne pas par défaut la mettre à Chez le
> syndic : seule une correction manuelle est autorisée. »

- La saisie du CR montre l'état actuel et propose `ETATS_A_LA_VALIDATION` ;
  `etat_par_defaut` dit lequel est coché d'office.
- Rien ne change avant la validation : l'état choisi s'écrit sur le CR
  (`etat_cible`), et `appliquer_etats` le pose à la validation — par une Suite
  d'état, le chemin de la fiche (`appliquer_statut`), jamais une écriture de
  `ticket.statut` à côté.
- Une affaire close ailleurs pendant le point n'est pas rouverte par le CR :
  rouvrir est une décision, qui se prend sur la fiche.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session

from app.models.core import STATUTS_TICKET_CLOS, Utilisateur
from app.models.points_conseil import CompteRenduAffaire, PointConseil
from app.models.tickets import StatutTicket, Ticket, TicketEvolution
from app.utils import horloge
from app.utils.dates_fr import date_longue
from app.utils.valeurs import valeur

#: Ce que la saisie propose, dans l'ordre du cycle — « a minima Chez le syndic ».
ETATS_A_LA_VALIDATION: tuple[str, ...] = (
    StatutTicket.en_cours.value,
    StatutTicket.en_ag.value,
    StatutTicket.chez_prestataire.value,
    StatutTicket.résolu.value,
    StatutTicket.annulé.value,
)


def etat_par_defaut(statut: str) -> str:
    """PURE. L'état coché d'office : l'actuel s'il est proposé — « À l'AG » reste
    à l'AG —, sinon « Chez le syndic » (une affaire Ouverte qu'on vient d'aborder)."""
    return statut if statut in ETATS_A_LA_VALIDATION else StatutTicket.en_cours.value


def exiger_etat_cible(etat: Optional[str]) -> Optional[str]:
    """L'état demandé, s'il est proposé — 422 sinon ; `None` : l'affaire ne change pas."""
    if etat is not None and etat not in ETATS_A_LA_VALIDATION:
        raise HTTPException(422, "État inconnu pour la validation du compte rendu")
    return etat


def changement_a_poser(ticket: Ticket, cr: CompteRenduAffaire) -> Optional[str]:
    """PURE. L'état que la validation pose — `None` s'il n'y a rien à faire.

    Rien pour une affaire absorbée (son suivi est terminé, #1704), déjà dans cet
    état, ou close ailleurs pendant le point : le CR ne rouvre pas.
    """
    cible, actuel = cr.etat_cible, valeur(ticket.statut)
    if not cible or cible == actuel or ticket.fusionnee_dans_id is not None:
        return None
    if actuel in STATUTS_TICKET_CLOS:
        return None
    return cible


def appliquer_etats(
    session: Session,
    point: PointConseil,
    abordees: list[tuple[Ticket, CompteRenduAffaire]],
    par: Optional[Utilisateur],
) -> int:
    """À la validation : chaque affaire abordée prend l'état décidé, par une Suite
    d'état signée de qui valide — de l'auteur du point, d'office. Rend leur nombre."""
    #  Import différé : la règle d'un changement d'état vit chez les routeurs
    #  des affaires, qui importent (de loin) ce module.
    from app.routers.tickets.suite_sections import appliquer_statut

    maintenant = horloge.maintenant()
    poses = 0
    for ticket, cr in abordees:
        cible = changement_a_poser(ticket, cr)
        if cible is None:
            continue
        evol = TicketEvolution(
            ticket_id=ticket.id,
            type="etat",
            contenu=f"Décidé au point CS / Syndic du {date_longue(point.debut)}.",
            ancien_statut=valeur(ticket.statut),
            nouveau_statut=cible,
            auteur_id=par.id if par else point.auteur_id,
            cree_le=maintenant,
        )
        session.add(evol)
        appliquer_statut(session, ticket, evol, cible, maintenant)
        poses += 1
    return poses
