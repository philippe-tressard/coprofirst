"""L'entretien PÉRIODIQUE — quelle affaire en est une, et où en est sa visite.

## La règle (arbitrée par l'utilisateur le 10/10/2026)

Une affaire **Entretien** est périodique quand elle porte un **contrat**
(`contrat_id` : le rythme est celui du contrat, #1445) **ou** une **récurrence**
propre (`frequence_type`). Ce sont les visites que pose « ⚙️ Init.
prestataires », une par passage prévu, et celles qu'un conseiller règle à la main.
Un Entretien ouvert sans l'un ni l'autre — une vérification ponctuelle demandée
au syndic — n'en est pas une.

Deux lecteurs, et c'est pourquoi la règle est écrite ICI :

- la **relance syndic** les écarte (`utils/relance_syndic`) : le passage d'un
  prestataire sous contrat ne se relance pas auprès du syndic, il se constate ;
- la vue **Entretien périodique** du reporting les montre, avec l'état de
  chaque visite (`etat_visite`).

## L'état d'une visite — calculé, jamais saisi

| État | Quand |
|---|---|
| `realisee` | l'affaire est résolue |
| `annulee` | l'affaire est annulée |
| `a_planifier` | ni l'un ni l'autre, et aucune date prévue (`debut`) |
| `non_realisee` | la date prévue est PASSÉE — la veille au plus tard |
| `a_venir` | la date prévue est aujourd'hui ou plus tard |

Le jour est celui de Paris (`horloge.jour_civil`) : une visite du 15 n'est pas
« non réalisée » à 1 h du matin le 15, heure d'été.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, or_
from sqlmodel import col

from app.models.tickets import CategorieTicket, StatutTicket, Ticket
from app.utils import horloge
from app.utils.valeurs import valeur

#: Les états d'une visite, dans l'ordre où l'écran les compte.
ETATS_VISITE: tuple[str, ...] = (
    "non_realisee",
    "a_venir",
    "a_planifier",
    "realisee",
    "annulee",
)


def condition_periodique():
    """La condition SQL « cette affaire est un entretien périodique »."""
    return and_(
        col(Ticket.categorie) == CategorieTicket.entretien.value,
        or_(col(Ticket.contrat_id).is_not(None), col(Ticket.frequence_type).is_not(None)),
    )


def jour_de_reference(ticket: Any) -> date:
    """Le jour qui range une visite dans un exercice : prévue, sinon close, sinon créée."""
    instant: date | datetime = ticket.debut or ticket.ferme_le or ticket.cree_le
    return horloge.jour_civil(instant)


def etat_visite(ticket: Any, aujourd_hui: date) -> str:
    """L'état d'une visite périodique au jour donné — voir la table en tête."""
    statut = valeur(ticket.statut)
    if statut == StatutTicket.résolu.value:
        return "realisee"
    if statut == StatutTicket.annulé.value:
        return "annulee"
    if ticket.debut is None:
        return "a_planifier"
    return "non_realisee" if horloge.jour_civil(ticket.debut) < aujourd_hui else "a_venir"


def conditions_entretien_en_cours() -> tuple:
    """Les conditions SQL « entretien périodique non clos » — le relevé du mode
    « Suivi entretiens périodiques » (#2043) : la règle de la relance, l'entretien
    périodique gardé au lieu d'être écarté."""
    from app.models.core import STATUTS_TICKET_ACTIFS
    from app.utils.affaire_absorbee import pas_absorbee

    return (
        col(Ticket.statut).in_(STATUTS_TICKET_ACTIFS),
        ~col(Ticket.archive_manuel),
        pas_absorbee(),
        condition_periodique(),
    )


__all__ = [
    "ETATS_VISITE",
    "condition_periodique",
    "conditions_entretien_en_cours",
    "etat_visite",
    "jour_de_reference",
]
