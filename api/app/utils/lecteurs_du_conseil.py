"""Les LECTEURS DU CONSEIL — le conseil syndical, l'administration et les comptes du
syndic —, et la vignette Public / Privé d'une affaire (#2082).

## Qui lit les points du conseil

Ceux à qui le fil annonce un compte rendu validé (arbitré le 17/10/2026, #2042),
et qui lisent les CR « CS et présents » dans la rubrique d'une affaire.

## La vignette (arbitrée le 20/10/2026)

> « Privé = CS & Syndic / Public = tout autre cas. »

Une affaire est **privée** quand AUCUN compte actif hors du conseil et du syndic
ne la lit — son auteur résident compris : s'il la lit, elle est publique. La
lecture se juge par `ticket_visible`, la règle de la fiche, compte par compte —
jamais une recopie de ses cas (confidentiel, destinataires, catégorie).
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.auth.deps import est_moderateur
from app.models.core import StatutUtilisateur, Utilisateur
from app.models.tickets import Ticket
from app.utils.valeurs import valeur
from app.utils.visibility import ticket_visible


def lit_les_points_conseil(user: Utilisateur) -> bool:
    """Le conseil (et l'administration) et les comptes du syndic."""
    return est_moderateur(user) or valeur(user.statut) == StatutUtilisateur.syndic.value


def privees(session: Session, tickets: list[Ticket]) -> set[int]:
    """Les affaires que seuls le conseil et le syndic lisent — les comptes lus UNE fois."""
    if not tickets:
        return set()
    autres = [
        u
        for u in session.exec(select(Utilisateur).where(Utilisateur.actif == True)).all()  # noqa: E712
        if not lit_les_points_conseil(u)
    ]
    return {t.id for t in tickets if not any(ticket_visible(t, u) for u in autres)}
