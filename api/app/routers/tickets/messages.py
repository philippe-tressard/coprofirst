"""Tickets — messagerie publique et notes internes.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""

from app.utils import horloge

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import est_moderateur, get_current_user, lit_les_notes_internes
from app.database import get_session
from app.models.core import (
    MessageTicket,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.routers.tickets.messages_schemas import MessageCreate, MessageRead
from app.utils.liens import lien_ticket
from app.utils.photos import photos_json
from app.utils.visibility import ticket_visible

from .commun import config_site, contexte_site
from .courriels import envoyer_email_externe
from app.utils.destinataires import membres_cs_ou_admin
from app.utils.html_sur import html_riche
from app.utils.noms import contexte_personne
from app.utils.recuperer import ou_rien
from app.utils.cloche import sonner
from app.utils.fusion_affaires import refuser_si_absorbee

router = APIRouter()


@router.get("/{ticket_id}/messages", response_model=list[MessageRead])
def get_messages(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    stmt = select(MessageTicket).where(MessageTicket.ticket_id == ticket_id)
    # Messages internes réservés CS/admin
    if not lit_les_notes_internes(user):
        stmt = stmt.where(MessageTicket.interne == False)  # noqa: E712
    return session.exec(stmt.order_by(MessageTicket.cree_le)).all()


def _prevenir(
    session: Session,
    background_tasks: BackgroundTasks,
    *,
    destinataire_id: int,
    email: str,
    ticket: Ticket,
    user: Utilisateur,
    contenu: str,
    cfg: dict,
    titre_notif: str,
    lien: str,
) -> None:
    """Un e-mail et une notification in-app pour un destinataire.

    Les deux branches (le CS répond à l'auteur / un résident écrit au CS)
    faisaient exactement cela, écrit deux fois.

    ⚠️ Le `context=` est construit ICI, en dictionnaire littéral, et non reçu en
    paramètre. Première version : il était passé tout fait, et l'envoi est sorti
    du champ de `test_email_contexte_appel` — le garde-fou né de la troisième
    récidive de « X is undefined » ne voyait plus ce modèle du tout. Une
    factorisation qui aveugle un contrôle n'est pas une factorisation réussie
    (`standards/02-factorisation.md` §3).
    """
    from app.utils.email import send_email

    background_tasks.add_task(
        send_email,
        code="ticket_nouveau_message",
        to=email,
        context={
            "ticket": {"id": ticket.id, "numero": ticket.numero, "titre": ticket.titre},
            "message": {"contenu": html_riche(contenu[:300])},
            "auteur_action": contexte_personne(user),
            **contexte_site(cfg),
        },
        destinataire_id=destinataire_id,
    )
    sonner(
        session,
        destinataire_id=destinataire_id,
        type="ticket_update",
        titre=titre_notif,
        corps=contenu[:200],
        lien=lien,
    )


@router.post("/{ticket_id}/messages", response_model=MessageRead, status_code=201)
def add_message(
    ticket_id: int,
    body: MessageCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    #  🔴 La même garde que le `GET` ci-dessus : sans elle, n'importe quel compte
    #  écrivait sur une affaire qu'il ne peut pas lire — une affaire réservée au
    #  conseil comprise — et alertait le CS en son nom (#1164, 23/09/2026).
    ticket = exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    refuser_si_absorbee(ticket)  # la discussion vit dans la principale (#1704)
    est_cs = est_moderateur(user)
    if body.interne and not est_cs:
        raise HTTPException(403, "Messages internes réservés au CS")

    msg = MessageTicket(
        ticket_id=ticket_id,
        auteur_id=user.id,
        contenu=body.contenu,
        interne=body.interne,
        fichiers_urls=photos_json(body.fichiers_urls),
    )
    #  Auto-log évolution "réponse".
    #
    #  🔴 Elle porte le TEXTE et les pièces du message public (05/10/2026). Elle
    #  naissait vide : la fiche montre le message dans son fil de bulles, mais la
    #  carte de LISTE ne rend que l'Historique — une réponse de résident y
    #  apparaissait comme un en-tête sans corps, alors que le courriel envoyé au
    #  conseil, lui, la citait. Un message interne reste réduit à son mot : le
    #  texte d'une note ne s'écrit pas dans un fil que d'autres lisent.
    session.add(
        TicketEvolution(
            ticket_id=ticket_id,
            type="reponse",
            contenu="Message interne" if body.interne else body.contenu,
            auteur_id=user.id,
            cree_le=horloge.maintenant(),
            assiste_ia=body.assiste_ia,
            fichiers_urls="[]" if body.interne else photos_json(body.fichiers_urls),
        )
    )
    ticket.mis_a_jour_le = horloge.maintenant()
    session.add(msg)
    session.add(ticket)
    #  L'id du message est nécessaire AVANT le commit : les notifications
    #  ci-dessous ancrent leur lien dessus (`#msg-42`), pour déposer le lecteur
    #  sur la réponse qui a déclenché l'alerte et non en haut de page.
    session.flush()

    if not body.interne:
        cfg = config_site(session)
        lien = lien_ticket(ticket.id, msg.id)
        commun = dict(
            ticket=ticket,
            user=user,
            contenu=body.contenu,
            cfg=cfg,
            lien=lien,
        )

        if est_cs:
            # CS/Admin répond → notifier l'auteur du ticket
            if ticket.auteur_id != user.id:
                auteur = ou_rien(session, Utilisateur, ticket.auteur_id)
                if auteur and auteur.email:
                    _prevenir(
                        session,
                        background_tasks,
                        destinataire_id=ticket.auteur_id,
                        email=auteur.email,
                        titre_notif=f"Nouvelle réponse sur le ticket #{ticket.numero}",
                        **commun,
                    )
        else:
            # Résident répond → notifier les CS/Admin
            #  ⚠️ `email IS NOT NULL` a disparu ici, et c'était un défaut :
            #  une notification IN-APP n'a pas besoin d'adresse. La condition
            #  venait d'un copier-coller depuis un envoi de courriel, et privait
            #  d'alerte à l'écran un membre du CS sans adresse enregistrée.
            cs_members = membres_cs_ou_admin(session)
            for member in cs_members:
                if member.id != user.id:
                    _prevenir(
                        session,
                        background_tasks,
                        destinataire_id=member.id,
                        email=member.email,
                        titre_notif=f"Nouveau message sur le ticket #{ticket.numero}",
                        **commun,
                    )

    session.commit()
    session.refresh(msg)

    # Email externe (CS/Admin uniquement, après commit pour avoir l'id)
    #  🔴 `est_cs` : quiconque VOIT l'affaire peut lui écrire un message, et une
    #  affaire ordinaire est visible de tout son périmètre. Sans cette garde,
    #  n'importe quel résident faisait partir un courriel vers une adresse de son
    #  choix, depuis celle du site (#1164, 23/09/2026).
    if body.email_externe and body.email_externe.strip() and not body.interne and est_cs:
        envoyer_email_externe(
            ticket,
            user,
            body.email_externe.strip(),
            background_tasks,
            session,
            is_commentaire=True,
            nouveau_message=body.contenu,
            fichiers_urls=body.fichiers_urls,
        )

    return msg
