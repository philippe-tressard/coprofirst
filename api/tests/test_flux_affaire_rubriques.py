"""Une affaire dépliée au fil : trois rubriques, chacune avec SES pièces (15/10/2026).

Signalé à l'écran sur TK-109008 : la carte d'une affaire résolue montrait le
texte de la DEMANDE et, dessous, les photos de la CLÔTURE — sans rien qui dise
d'où elles venaient. La carte de résolution n'envoyait pas le texte de clôture,
et le repli des pièces sur l'affaire mêlait les deux.

Arbitré parmi cinq maquettes (A) : « Dernière mise à jour » (texte, auteur, ses
pièces), « Synthèse » si l'affaire est close et la synthèse lisible, « Demande
initiale » (sa date, ses pièces). Et la synthèse validée ENRICHIT la carte sans
la dater : une affaire qui remonterait en tête deux jours après sa réparation se
lirait comme une nouvelle panne.
"""

from __future__ import annotations

import json
from datetime import timedelta

from sqlmodel import col, select

from app.models.core import RoleUtilisateur, Ticket, TicketEvolution
from app.models.synthese import BROUILLON, VALIDEE, SyntheseAffaire
from app.routers.flux import tickets as flux_tickets
from app.routers.flux.commun import ContexteFlux
from app.utils import horloge
from tests.aides_affaire import _compte, _creer, _suite, session  # noqa: F401 — fixture


def _carte(session, user, ticket_id: int):
    maintenant = horloge.maintenant()
    ctx = ContexteFlux(
        session=session, user=user, now=maintenant, since=maintenant - timedelta(days=14)
    )
    cartes = [c for c in flux_tickets.collecter(ctx) if c.meta.get("ticket_id") == ticket_id]
    return cartes[0] if cartes else None


def _affaire_resolue(session, cs) -> Ticket:
    """Une panne déposée avec une photo, puis close par une Suite qui porte la sienne."""
    ticket = session.get(Ticket, _creer(session, cs, categorie="panne").id)
    ticket.photos_urls = json.dumps(["/uploads/demande.jpg"])
    session.add(ticket)
    session.commit()
    _suite(
        session,
        cs,
        ticket.id,
        type="etat",
        nouveau_statut="résolu",
        contenu="<p>Gâche remplacée, portillon fonctionnel.</p>",
    )
    evol = session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket.id)
        .order_by(col(TicketEvolution.id).desc())
    ).first()
    evol.fichiers_urls = json.dumps(["/uploads/cloture.jpg", "/uploads/devis.pdf"])
    session.add(evol)
    session.commit()
    return ticket


def _synthese(session, ticket: Ticket, statut: str) -> None:
    session.add(
        SyntheseAffaire(ticket_id=ticket.id, statut=statut, synthese="<p>Motoréducteur bloqué.</p>")
    )
    session.commit()


def test_la_carte_de_resolution_porte_le_texte_de_cloture(session):  # noqa: F811
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    ticket = _affaire_resolue(session, cs)
    carte = _carte(session, cs, ticket.id)
    assert carte is not None and carte.type == "ticket_resolu", "cas zéro : la carte de résolution"
    assert carte.meta["evol_contenu"] == "Gâche remplacée, portillon fonctionnel."
    assert carte.meta["evol_auteur"], "la dernière mise à jour nomme qui l'a écrite"


def test_chaque_rubrique_porte_ses_propres_pieces(session):  # noqa: F811
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    carte = _carte(session, cs, _affaire_resolue(session, cs).id)
    assert carte.meta["evol_pieces"] == {
        "photos_urls": ["/uploads/cloture.jpg"],
        "fichiers_urls": ["/uploads/devis.pdf"],
    }
    assert carte.meta["demande"]["photos_urls"] == ["/uploads/demande.jpg"]
    assert carte.meta["demande"]["fichiers_urls"] == []
    assert carte.meta["demande"]["le"], "la demande dit sa date"


def test_une_suite_sans_piece_ne_prend_pas_celles_de_la_demande(session):  # noqa: F811
    """Le repli sur l'affaire reste pour la VIGNETTE pliée, jamais pour la rubrique."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    ticket = session.get(Ticket, _creer(session, cs, categorie="panne").id)
    ticket.photos_urls = json.dumps(["/uploads/demande.jpg"])
    session.add(ticket)
    session.commit()
    _suite(session, cs, ticket.id)
    carte = _carte(session, cs, ticket.id)
    assert carte.meta["evol_pieces"] == {"photos_urls": [], "fichiers_urls": []}
    assert carte.meta["photos_urls"] == ["/uploads/demande.jpg"], (
        "la vignette pliée garde son repli"
    )


def test_la_synthese_validee_rejoint_la_carte_sans_la_dater(session):  # noqa: F811
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    resident = _compte(session)
    ticket = _affaire_resolue(session, cs)
    avant = _carte(session, resident, ticket.id)
    assert avant is not None, "cas zéro : le résident lit la panne"
    assert "synthese" not in avant.meta

    _synthese(session, ticket, VALIDEE)
    apres = _carte(session, resident, ticket.id)
    assert apres.meta["synthese"] == {"texte": "Motoréducteur bloqué.", "validee": True}
    assert apres.date == avant.date, "la validation ne fait pas remonter la carte (15/10/2026)"


def test_un_brouillon_ne_se_lit_qu_au_conseil(session):  # noqa: F811
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    resident = _compte(session)
    ticket = _affaire_resolue(session, cs)
    _synthese(session, ticket, BROUILLON)
    assert _carte(session, cs, ticket.id).meta["synthese"]["validee"] is False
    assert "synthese" not in _carte(session, resident, ticket.id).meta


def test_une_affaire_rouverte_ne_montre_plus_sa_synthese(session):  # noqa: F811
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    ticket = _affaire_resolue(session, cs)
    _synthese(session, ticket, VALIDEE)
    _suite(session, cs, ticket.id, type="etat", nouveau_statut="ouvert")
    assert "synthese" not in _carte(session, cs, ticket.id).meta
