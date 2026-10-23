"""Prévenir l'AUTEUR d'une affaire qu'une Suite y a été ajoutée — courriel et cloche.

Sorti de `evolutions.py` le 26/09/2026 (#1342) : le routeur dépassait 500
lignes, et la section « Affaires liées » devait s'y ajouter. Prévenir l'auteur
est une notion à part — ce qu'on lui écrit, et quand — que le routeur appelle.
"""

from __future__ import annotations

from fastapi import BackgroundTasks
from sqlmodel import Session

from app.models.core import Ticket, Utilisateur
from app.schemas import TicketEvolutionCreate
from app.utils.cloche import sonner
from app.utils.html_sur import html_riche
from app.utils.liens import lien_ticket
from app.utils.noms import contexte_personne
from app.utils.recuperer import ou_rien

from .commun import STATUT_LABELS, config_site, contexte_site


def _notifier_auteur(
    session: Session,
    background_tasks: BackgroundTasks,
    *,
    ticket: Ticket,
    user: Utilisateur,
    body: TicketEvolutionCreate,
    ancien_statut: str | None,
) -> None:
    """E-mail et notification in-app à l'auteur du ticket, s'il n'agit pas lui-même."""
    from app.utils.email import send_email

    cfg = config_site(session)
    auteur = ou_rien(session, Utilisateur, ticket.auteur_id)
    base_ticket = {"id": ticket.id, "numero": ticket.numero, "titre": ticket.titre}

    if auteur and auteur.email:
        if body.type == "etat":
            background_tasks.add_task(
                send_email,
                code="ticket_statut_change",
                to=auteur.email,
                context={
                    "ticket": {
                        **base_ticket,
                        "statut": STATUT_LABELS.get(body.nouveau_statut, body.nouveau_statut),
                        "ancien_statut": STATUT_LABELS.get(ancien_statut or "", "Aucun"),
                    },
                    "destinataire": {"prenom": auteur.prenom, "nom": auteur.nom},
                    "auteur_action": contexte_personne(user),
                    **contexte_site(cfg),
                },
                destinataire_id=ticket.auteur_id,
            )
        elif body.type == "commentaire" and body.contenu:
            background_tasks.add_task(
                send_email,
                code="ticket_nouveau_message",
                to=auteur.email,
                context={
                    "ticket": base_ticket,
                    "message": {"contenu": html_riche(body.contenu[:300])},
                    "auteur_action": contexte_personne(user),
                    **contexte_site(cfg),
                },
                destinataire_id=ticket.auteur_id,
            )

    titre_notif = (
        f"Ticket #{ticket.numero} — statut : "
        f"{STATUT_LABELS.get(body.nouveau_statut, body.nouveau_statut)}"
        if body.type == "etat"
        else f"Nouveau commentaire sur le ticket #{ticket.numero}"
    )
    sonner(
        session,
        destinataire_id=ticket.auteur_id,
        type="ticket_update",
        titre=titre_notif,
        corps=(body.contenu or "")[:200],
        lien=lien_ticket(ticket.id),
    )
