"""Les LECTEURS DU CONSEIL — le conseil syndical, l'administration et les comptes du
syndic (#2082).

## Qui lit les points du conseil

Ceux à qui le fil annonce un compte rendu validé (arbitré le 17/10/2026, #2042),
et qui lisent les CR « CS et présents » dans la rubrique d'une affaire.

La vignette Public / Privé qui vivait ici a été retirée le 20/10/2026 (#2089) :
« qui la lit » se dit par la pastille de la page Affaires (`utils/lecture_affaire`).
"""

from __future__ import annotations

from app.auth.deps import est_moderateur
from app.models.core import StatutUtilisateur, Utilisateur
from app.utils.valeurs import valeur


def lit_les_points_conseil(user: Utilisateur) -> bool:
    """Le conseil (et l'administration) et les comptes du syndic."""
    return est_moderateur(user) or valeur(user.statut) == StatutUtilisateur.syndic.value
