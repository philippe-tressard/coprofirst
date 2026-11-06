"""La prochaine visite d'un contrat, recalculée quand un Entretien récurrent se clôt.

## D'où ça vient (#1092, lot 5, 23/09/2026)

Le calendrier le faisait quand une maintenance récurrente passait « Terminé »
(`routers/calendrier.py`, `_update_contrat_prochaine_visite`). Les événements
sont devenus des affaires Entretien : la règle suit l'affaire, et elle est
écrite ICI, une fois, pour les deux chemins qui résolvent une affaire — la
Suite d'état (`evolutions.py`) et la correction (`mise_a_jour.py`).

## La règle (révisée le 28/09/2026, #1445)

- une affaire **Entretien** résolue, **sous contrat** (`contrat_id`) ;
- CE contrat, s'il est toujours en cours et toujours celui de l'intervenant ;
- sa `prochaine_visite` part de la date de l'intervention (`debut`, à défaut
  aujourd'hui), selon la fréquence du CONTRAT.

🔴 Le contrat était DEVINÉ jusque-là : son libellé cherché dans le titre de
l'affaire (« Otis — Ascenseur »), à défaut le seul contrat actif du
prestataire. Une affaire ne disait pas si l'intervention était sous contrat —
un dépannage hors contrat d'Otis avançait la visite d'entretien. Elle le dit
désormais, et la règle le lit.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from app.utils import horloge
from typing import Optional

from sqlmodel import Session

from app.models.prestataires import ContratEntretien
from app.models.tickets import CategorieTicket, StatutTicket
from app.utils.echeance_contrat import ajouter_mois
from app.utils.valeurs import valeur


def date_prochaine_visite(contrat: ContratEntretien, depuis: date) -> Optional[date]:
    """La visite suivante, d'après la fréquence du contrat — `None` s'il n'en a pas."""
    ft, fv = contrat.frequence_type, contrat.frequence_valeur
    if not ft or not fv:
        return None
    if ft == "semaines":
        return depuis + timedelta(weeks=fv)
    if ft == "mois":
        return ajouter_mois(depuis, fv)
    if ft == "fois_par_an":
        return ajouter_mois(depuis, max(1, 12 // fv))
    if ft == "ans":
        return ajouter_mois(depuis, 12 * fv)
    return None


def apres_cloture(ticket, session: Session) -> None:
    """Avance la prochaine visite du contrat quand un Entretien récurrent est résolu."""
    if valeur(ticket.categorie) != CategorieTicket.entretien.value:
        return
    if valeur(ticket.statut) != StatutTicket.résolu.value:
        return
    if not ticket.contrat_id:
        return  # hors contrat : aucune visite de contrat n'a eu lieu
    retenu = session.get(ContratEntretien, ticket.contrat_id)
    if retenu is None or not retenu.actif or retenu.prestataire_id != ticket.prestataire_id:
        return
    depuis = (
        ticket.debut.date()
        if isinstance(ticket.debut, datetime)
        else (ticket.debut or horloge.aujourd_hui())
    )
    suivante = date_prochaine_visite(retenu, depuis)
    if suivante:
        retenu.prochaine_visite = suivante
        session.add(retenu)


__all__ = ["apres_cloture", "date_prochaine_visite"]
