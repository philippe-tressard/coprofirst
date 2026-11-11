"""« Cette affaire est-elle close ? » — la règle servie aux deux clients (#2511).

Close = résolue ou annulée (`STATUTS_TICKET_CLOS`) : elle quitte le suivi. Le site
la calculait dans son front (`estTicketClos`) sur l'affaire, la ligne du fil et
les affaires liées ; l'app iOS ne lit que le contrat (`standards/09` §8, règle 1).
Chaque réponse qui porte un état d'affaire la sert donc en `close`, calculée ici :
`TicketRead` (`schemas_affaire_servie`), `AffaireLieeLue`, la ligne du fil
(`flux/commun.CHAMPS_PASTILLES`). Le référentiel la sert par état
(`GET /tickets/referentiels`, `statuts[].clos`).

« Comment se dit cet état ? » (`libelle_etat`) vit ici aussi depuis #2633 : le
front l'appliquait encore (`statutTicketLabel`) aux états du fil, des Suites, des
affaires liées et des comptes rendus, servis en codes. Chaque réponse les sert
désormais en clair, par cette fonction.
"""

from __future__ import annotations

from app.models.tickets import STATUTS_TICKET_CLOS
from app.utils.valeurs import valeur


#: Libellé lisible de chaque état — e-mails, notifications, fil d'évolutions.
#:
#: Les quatre premières clés sont les états du workflow (`StatutTicket`) ;
#: `fermé` n'en est plus un depuis le 17/08/2026 (#415, migration 0149) mais
#: reste **affichable** : le fil de tickets anciens raconte « Ouvert → Fermé »,
#: et une ligne d'histoire ne se réécrit pas. Sans ce libellé, ces évolutions
#: afficheraient la valeur brute.
#:
#: Un couvercle vérifie que ce dictionnaire couvre l'énumération et rien de
#: fantaisiste : `api/tests/test_statuts_tickets.py`.
STATUT_LABELS = {
    "ouvert": "Ouvert",
    "en_ag": "À l’AG",
    "en_cours": "Chez le syndic",
    "chez_prestataire": "Chez le prestataire",
    "résolu": "Résolu",
    "annulé": "Annulé",
    "fermé": "Fermé",  # historique seulement — cf. STATUTS_TICKET_HISTORIQUES
    "publie": "Publiée",  # sans cycle — une actualité (#1091)
}


def libelle_etat(statut) -> str:
    """« Chez le syndic » — la valeur brute si elle est inconnue (l'état d'une idée,
    d'une annonce), jamais effacée ; vide s'il manque."""
    brut = str(valeur(statut) or "")
    return STATUT_LABELS.get(brut, brut)


def affaire_close(statut) -> bool:
    """Vrai si l'état (énumération ou chaîne) clôt l'affaire ; faux s'il manque."""
    return bool(statut) and valeur(statut) in STATUTS_TICKET_CLOS


__all__ = ["STATUT_LABELS", "affaire_close", "libelle_etat"]
