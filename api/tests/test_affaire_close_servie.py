"""« Cette affaire est close » est SERVIE, jamais recalculée par un client (#2511).

Le site la calculait (`estTicketClos`, `#lib/tickets`) sur l'affaire, la ligne
du fil et les affaires liées ; l'app iOS ne lit que le contrat. La règle vit dans
`utils/etat_affaire.affaire_close`, et chaque réponse qui porte un état d'affaire
la sert en `close` : `TicketRead`, `AffaireLieeLue` (liées, `/tickets/choix`,
candidates d'une fusion), la ligne de pastilles du fil.
"""

from __future__ import annotations

from datetime import datetime

from app.models.core import StatutTicket, Ticket
from app.models.tickets import STATUTS_TICKET_CLOS
from app.routers.flux.commun import pastilles_affaire
from app.schemas_communs import AffaireLieeLue
from app.utils.affaires_liees import _lue
from app.utils.etat_affaire import affaire_close


def test_la_regle_suit_la_liste_des_etats_clos():
    for statut in StatutTicket:
        assert affaire_close(statut) is (statut.value in STATUTS_TICKET_CLOS)
        assert affaire_close(statut.value) is (statut.value in STATUTS_TICKET_CLOS)
    assert affaire_close(None) is False
    assert affaire_close("") is False


def _liee(statut: str) -> AffaireLieeLue:
    """Par le seul producteur : liées, `/tickets/choix`, candidates d'une fusion."""
    ticket = Ticket(id=1, numero="TK-1", titre="t", description="d", auteur_id=1, statut=statut)
    ticket.cree_le = datetime(2026, 11, 5)
    return AffaireLieeLue(**_lue(ticket))


def test_une_affaire_liee_sert_close():
    assert _liee("résolu").model_dump()["close"] is True
    assert _liee("annulé").model_dump()["close"] is True
    assert _liee("en_cours").model_dump()["close"] is False


def test_la_ligne_du_fil_sert_close():
    ouverte = Ticket(id=1, numero="TK-1", titre="t", description="d", auteur_id=1)
    close = Ticket(id=2, numero="TK-2", titre="t", description="d", auteur_id=1, statut="résolu")
    assert pastilles_affaire(ouverte)["close"] is False
    assert pastilles_affaire(close)["close"] is True
