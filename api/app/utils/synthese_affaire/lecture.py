"""Qui lit une synthèse, et sous quelle forme (#1643).

## La règle, arbitrée le 03/10/2026

| État | Qui la lit |
|---|---|
| `brouillon` | le conseil syndical et l'administration (`est_moderateur`), avec un bandeau |
| `validee` | qui lit l'affaire — `ticket_visible`, la règle de la liste, de la fiche et du carnet |
| `a_produire`, `annulee` | personne : la première n'a pas encore de Suite, la seconde a été remplacée |

🔴 La règle vaut pour la **Suite porteuse** comme pour la synthèse : le fil
(`GET /tickets/{id}/evolutions`) retire une entrée `synthese` que le lecteur ne
peut pas lire. Une Suite n'a aucune colonne de visibilité — c'est ici, et
seulement ici, qu'elle en reçoit une.

La Suite ne porte d'ailleurs **aucun texte** (`contenu` vide) : il vit dans
`synthese_affaire`. Le courriel au syndic, la recherche et le fil d'activité,
qui lisent les Suites, n'ont donc rien à divulguer d'un brouillon.
"""

from __future__ import annotations

import json
from typing import Iterable, Optional

from sqlmodel import Session, col, select

from app.auth.deps import est_moderateur
from app.models.core import Ticket, TicketEvolution, Utilisateur
from app.models.synthese import BROUILLON, VALIDEE, SyntheseAffaire
from app.schemas_synthese import SyntheseLue
from app.utils.lecture import lire_objet
from app.utils.noms import nom_affiche
from app.utils.synthese_affaire.recidive import CLE as RECIDIVE
from app.utils.visibility import ticket_visible

#: Le type de la Suite porteuse — ni `commentaire` ni `etat` (`models/evolution.py`).
TYPE_SYNTHESE = "synthese"
#: Ce qui s'affiche : un brouillon ou une synthèse validée.
STATUTS_AFFICHES = (BROUILLON, VALIDEE)


def lisible(synthese: SyntheseAffaire, ticket: Ticket, user: Utilisateur) -> bool:
    """Ce lecteur peut-il lire cette synthèse ? — la règle de l'en-tête."""
    if synthese.statut == VALIDEE:
        return ticket_visible(ticket, user)
    if synthese.statut == BROUILLON:
        return est_moderateur(user) and ticket_visible(ticket, user)
    return False


def synthese_courante(session: Session, ticket_id: int) -> Optional[SyntheseAffaire]:
    """La synthèse affichée de l'affaire — la plus récente, brouillon ou validée."""
    return syntheses_courantes(session, [ticket_id]).get(ticket_id)


def syntheses_courantes(session: Session, ticket_ids: Iterable[int]) -> dict[int, SyntheseAffaire]:
    """La synthèse affichée de chacune de ces affaires, lue en UNE requête.

    Le fil d'activité la demande pour toutes ses affaires closes à la fois
    (15/10/2026) : une lecture par carte reviendrait au coût que #1838 a retiré.
    """
    ids = list(ticket_ids)
    if not ids:
        return {}
    courantes: dict[int, SyntheseAffaire] = {}
    for synthese in session.exec(
        select(SyntheseAffaire)
        .where(
            col(SyntheseAffaire.ticket_id).in_(ids),
            col(SyntheseAffaire.statut).in_(STATUTS_AFFICHES),
        )
        .order_by(col(SyntheseAffaire.cree_le).desc())
    ).all():
        courantes.setdefault(synthese.ticket_id, synthese)
    return courantes


def evolutions_lisibles(
    session: Session, ticket: Ticket, evolutions: Iterable[TicketEvolution], user: Utilisateur
) -> list[TicketEvolution]:
    """Le fil, sans les Suites de synthèse que ce lecteur ne peut pas lire."""
    evolutions = list(evolutions)
    ids = [e.id for e in evolutions if e.type == TYPE_SYNTHESE]
    if not ids:
        return evolutions
    par_evolution = {
        s.evolution_id: s
        for s in session.exec(
            select(SyntheseAffaire).where(col(SyntheseAffaire.evolution_id).in_(ids))
        ).all()
    }
    return [
        e
        for e in evolutions
        if e.type != TYPE_SYNTHESE
        or (e.id in par_evolution and lisible(par_evolution[e.id], ticket, user))
    ]


def metriques(synthese: SyntheseAffaire, *, conseil: bool = False) -> Optional[dict]:
    """Les métriques figées, relues — `None` si la colonne est vide ou illisible.

    🔴 La récidive d'un équipement (#1647) nomme d'AUTRES affaires : le conseil la
    lit, les copropriétaires — qui lisent la synthèse validée — non. Elle est
    retirée ICI, la seule porte de lecture, et le retrait est le comportement par
    défaut : un appelant qui oublie `conseil=True` ne divulgue rien.
    """
    try:
        lues = json.loads(synthese.metriques_json) if synthese.metriques_json else None
    except ValueError:
        return None
    if isinstance(lues, dict) and not conseil:
        lues.pop(RECIDIVE, None)
    return lues


def synthese_lue(
    session: Session, synthese: SyntheseAffaire, *, conseil: bool = False
) -> SyntheseLue:
    """La synthèse telle que l'écran et le carnet la lisent — une seule composition.

    `conseil` : le lecteur est un modérateur (`est_moderateur`) — il reçoit aussi
    la récidive d'équipement. Le carnet ne le passe jamais."""
    valideur = (
        session.get(Utilisateur, synthese.validee_par_id) if synthese.validee_par_id else None
    )
    return lire_objet(
        SyntheseLue,
        synthese,
        metriques=metriques(synthese, conseil=conseil),
        validee_par_nom=nom_affiche(valideur.prenom, valideur.nom) if valideur else None,
    )


def syntheses_validees(session: Session, ticket_ids: Iterable[int]) -> dict[int, SyntheseAffaire]:
    """La synthèse validée de chaque affaire — pour le carnet, en une requête."""
    ids = list(ticket_ids)
    if not ids:
        return {}
    lignes = session.exec(
        select(SyntheseAffaire)
        .where(col(SyntheseAffaire.ticket_id).in_(ids), SyntheseAffaire.statut == VALIDEE)
        .order_by(col(SyntheseAffaire.cree_le))
    ).all()
    return {s.ticket_id: s for s in lignes}


__all__ = [
    "STATUTS_AFFICHES",
    "TYPE_SYNTHESE",
    "evolutions_lisibles",
    "lisible",
    "metriques",
    "synthese_courante",
    "synthese_lue",
    "syntheses_validees",
]
