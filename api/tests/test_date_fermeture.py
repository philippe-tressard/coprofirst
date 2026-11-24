"""Une affaire se date de sa FERMETURE, jamais d'une correction (16/11/2026, #2804).

Signalé à l'écran : au carnet d'entretien, une affaire close paraissait à la date
où le conseil l'avait corrigée (rangée sous un équipement), pas à celle où elle
avait été fermée. Le formulaire de correction renvoie toujours l'état de
l'affaire, et la route réécrivait `ferme_le` dès que cet état était clos.

Trois faits gardés ici, lus en base après l'appel (`standards/04` §14) :
- corriger une affaire close ne déplace pas sa date de fermeture ; la fermer, si ;
- une intervention d'Entretien se date au carnet de sa fermeture, au jour de Paris ;
- la migration 0339 rend à une affaire close la date relue dans son fil.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime

import sqlalchemy as sa
from fastapi import BackgroundTasks
from sqlmodel import Session

from app.database import engine
from app.models.core import Ticket, TicketEvolution, Utilisateur
from app.routers.tickets.mise_a_jour import update_ticket
from app.schemas import TicketUpdate
from app.utils.carnet_entretien import construire_carnet
from tests import aides_migrations
from tests.aides_base import moteur_de_test
from tests.aides_purge import purger_ligne
from tests.aides_fil import cs  # noqa: F401 — fixture importée par son nom (#2950)

FERMEE_LE = datetime(2026, 9, 20, 23, 30)  # UTC : le 21 septembre à Paris
JOUR_DE_FERMETURE = date(2026, 9, 21)


def _affaire(session: Session, auteur: Utilisateur, **champs) -> Ticket:
    ticket = Ticket(
        numero=f"T-{uuid.uuid4().hex[:6]}",
        titre="Ascenseur bloqué",
        description="<p>Réparée.</p>",
        auteur_id=auteur.id,
        perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
        **champs,
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def _purger(session: Session, ticket_id: int) -> None:
    session.expire_all()
    for evol in session.get(Ticket, ticket_id).evolutions:
        session.delete(evol)
    purger_ligne(session, Ticket, ticket_id)
    session.commit()


def test_corriger_une_affaire_close_garde_sa_date_de_fermeture(cs):
    """Le formulaire renvoie « Résolu » avec la correction : la date ne bouge pas."""
    with Session(engine) as session:
        ticket = _affaire(session, cs, categorie="sinistre", statut="résolu", ferme_le=FERMEE_LE)
        try:
            update_ticket(
                ticket.id,
                TicketUpdate(statut="résolu", priorite="haute"),
                BackgroundTasks(),
                session,
                cs,
            )
            session.expire_all()
            relu = session.get(Ticket, ticket.id)
            assert relu.priorite == "haute", "la correction doit avoir eu lieu"
            assert relu.ferme_le == FERMEE_LE
        finally:
            _purger(session, ticket.id)


def test_fermer_une_affaire_par_correction_la_date(cs):
    """Le cas inverse : sans lui, le test ci-dessus passerait sur une route muette."""
    with Session(engine) as session:
        ticket = _affaire(session, cs, categorie="sinistre", statut="ouvert")
        try:
            update_ticket(ticket.id, TicketUpdate(statut="résolu"), BackgroundTasks(), session, cs)
            session.expire_all()
            assert session.get(Ticket, ticket.id).ferme_le is not None
        finally:
            _purger(session, ticket.id)


def test_une_intervention_se_date_au_carnet_de_sa_fermeture(cs):
    """Le jour prévu (`debut`) n'est pas la date du carnet ; la fermeture l'est, à Paris."""
    with Session(engine) as session:
        ticket = _affaire(
            session,
            cs,
            categorie="entretien",
            statut="résolu",
            debut=datetime(2026, 9, 1, 8, 0),
            ferme_le=FERMEE_LE,
        )
        try:
            lignes = [
                e
                for e in construire_carnet(session, lecteur=cs)
                if e["lien"].endswith(f"/{ticket.id}")
            ]
            assert [e["date"] for e in lignes] == [JOUR_DE_FERMETURE.isoformat()]
        finally:
            _purger(session, ticket.id)


# ── La migration 0339 ────────────────────────────────────────────────────────


def _dates(moteur) -> dict[str, datetime | None]:
    with moteur.connect() as conn:
        lignes = conn.execute(sa.text("SELECT numero, ferme_le FROM ticket")).all()
    return dict(lignes)


def test_la_migration_rend_la_date_relue_dans_le_fil():
    moteur = moteur_de_test()
    fermee = datetime(2026, 9, 20, 10, 0)
    corrigee = datetime(2026, 11, 10, 9, 0)  # la date fausse : celle d'une correction
    refermee = datetime(2026, 10, 5, 14, 0)
    with Session(moteur) as s:
        tickets = {
            #  Fermée par une transition, puis corrigée : la date revient à la transition.
            "TK-TRANSITION": Ticket(statut="résolu", ferme_le=corrigee),
            #  Rouverte puis refermée par correction : la plus récente fermeture fait foi.
            "TK-REFERMEE": Ticket(statut="résolu", ferme_le=corrigee),
            #  Aucune trace au fil : rien à relire, rien ne change.
            "TK-SANS-TRACE": Ticket(statut="résolu", ferme_le=corrigee),
            #  Rouverte depuis : sa date n'est pas celle d'une affaire close.
            "TK-ROUVERTE": Ticket(statut="ouvert", ferme_le=corrigee),
        }
        for numero, t in tickets.items():
            t.numero, t.titre, t.description, t.categorie = numero, "t", "d", "sinistre"
            s.add(t)
        s.commit()
        ids = {numero: t.id for numero, t in tickets.items()}

        def etat(numero, quand, nouveau="résolu"):
            s.add(
                TicketEvolution(
                    ticket_id=ids[numero],
                    type="etat",
                    ancien_statut="en_cours",
                    nouveau_statut=nouveau,
                    cree_le=quand,
                )
            )

        def correction(numero, quand, texte):
            s.add(
                TicketEvolution(
                    ticket_id=ids[numero], type="commentaire", contenu=texte, cree_le=quand
                )
            )

        etat("TK-TRANSITION", fermee)
        etat("TK-REFERMEE", fermee)
        correction("TK-REFERMEE", datetime(2026, 10, 1), "Correction : État : Résolu → Ouvert")
        correction("TK-REFERMEE", refermee, "Correction : État : Ouvert → Résolu")
        etat("TK-ROUVERTE", fermee)
        s.commit()

    migration = aides_migrations.charger_migration("0339")
    attendu = {
        "TK-TRANSITION": fermee,
        "TK-REFERMEE": refermee,
        "TK-SANS-TRACE": corrigee,
        "TK-ROUVERTE": corrigee,
    }
    aides_migrations.jouer_pas(moteur, migration.upgrade)
    assert _dates(moteur) == attendu
    aides_migrations.jouer_pas(moteur, migration.upgrade)  # rejouée : rien de plus
    assert _dates(moteur) == attendu
    moteur.dispose()
