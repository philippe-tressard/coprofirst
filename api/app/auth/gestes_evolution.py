"""Les gestes d'une entrée du fil (l'Historique) que l'écran OFFRE — servis avec elle (#2646).

## Pourquoi ce module

L'app iOS ne parle qu'au contrat de l'API. Pour offrir « Modifier la suite » ou
« Supprimer » sur une entrée de l'Historique, elle devrait recomposer la règle du
site (`RubriqueHistorique.peutCorriger` : droit sur l'affaire, type saisi, puis
auteur / « saisi pour » / admin) : une seconde copie, dans un autre dépôt, qui
divergerait au premier arbitrage (`standards/09` §8, règle 1). Le serveur sert donc,
sur chaque `TicketEvolutionRead`, ce que CE lecteur peut faire de CETTE entrée, et
le site lit les mêmes champs.

## La règle de ce module : jamais plus large que la route

Comme `gestes_affaire` : chaque prédicat dit ce que la route du geste ACCEPTE, en
appelant les prédicats et les listes qu'elle appelle (`auth/deps`,
`utils/evolutions`) — jamais une copie. 🔒 `test_gestes_evolution_servis.py` joue
chaque geste par sa route, pour chaque rôle et chaque type d'entrée, et confronte la
réponse au champ servi.
"""

from __future__ import annotations

from typing import Any

from app.auth.deps import est_moderateur, peut_editer
from app.models.core import RoleUtilisateur, Utilisateur
from app.utils.evolutions import TYPES_EFFACABLES, TYPES_SAISIS


def peut_corriger_evolution(evol: Any, ticket: Any, user: Utilisateur) -> bool:
    """✏️ `PATCH /tickets/{id}/evolutions/{evol_id}`.

    La route exige le conseil ou l'administration (`require_cs_or_admin`), refuse
    l'affaire absorbée (sa Suite vit dans la principale, #1704), puis demande à
    `evolution_modifiable` un type saisi (`TYPES_SAISIS`) et `peut_editer` — l'auteur,
    le « saisi pour », ou l'admin. Une entrée « Correction : … » tracée par le serveur
    ne se corrige pas.
    """
    return (
        est_moderateur(user)
        and getattr(ticket, "fusionnee_dans_id", None) is None
        and getattr(evol, "type", None) in TYPES_SAISIS
        and peut_editer(evol, user)
    )


def peut_supprimer_evolution(evol: Any, user: Utilisateur) -> bool:
    """🗑️ `DELETE /tickets/{id}/evolutions/{evol_id}` : l'administrateur, sur un type effaçable.

    Les réponses restent hors d'atteinte : elles appartiennent à leur auteur
    (`utils/evolutions`, arbitrage du 18/08/2026).
    """
    return user.has_role(RoleUtilisateur.admin) and getattr(evol, "type", None) in TYPES_EFFACABLES


def gestes_evolution_servis(
    evol: Any, ticket: Any | None, lecteur: Utilisateur | None
) -> dict[str, bool]:
    """Les champs `peut_*` de `TicketEvolutionRead` — tous FERMÉS sans lecteur ni affaire."""
    if lecteur is None or ticket is None:
        return {"peut_modifier": False, "peut_supprimer": False}
    return {
        "peut_modifier": peut_corriger_evolution(evol, ticket, lecteur),
        "peut_supprimer": peut_supprimer_evolution(evol, lecteur),
    }


__all__ = ["gestes_evolution_servis", "peut_corriger_evolution", "peut_supprimer_evolution"]
