"""« Cette affaire est-elle close ? » — la règle servie aux deux clients (#2511).

Close = résolue ou annulée (`STATUTS_TICKET_CLOS`) : elle quitte le suivi. Le site
la calculait dans son front (`estTicketClos`) sur l'affaire, la ligne du fil et
les affaires liées ; l'app iOS ne lit que le contrat (`standards/09` §8, règle 1).
Chaque réponse qui porte un état d'affaire la sert donc en `close`, calculée ici :
`TicketRead` (`schemas_affaire_servie`), `AffaireLieeLue`, la ligne du fil
(`flux/commun.CHAMPS_PASTILLES`). Le référentiel la sert par état
(`GET /tickets/referentiels`, `statuts[].clos`).
"""

from __future__ import annotations

from app.models.tickets import STATUTS_TICKET_CLOS
from app.utils.valeurs import valeur


def affaire_close(statut) -> bool:
    """Vrai si l'état (énumération ou chaîne) clôt l'affaire ; faux s'il manque."""
    return bool(statut) and valeur(statut) in STATUTS_TICKET_CLOS


__all__ = ["affaire_close"]
