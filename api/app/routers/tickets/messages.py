"""Tickets — messagerie publique et notes internes.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""

from app.utils import horloge

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import est_auteur, est_moderateur, get_current_user, lit_les_notes_internes
from app.database import get_session
from app.models.core import (
    MessageTicket,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.routers.tickets.messages_schemas import MessageCreate, MessageRead, MessageUpdate
from app.utils.liens import lien_ticket
from app.utils.photos import photos_json
from app.utils.visibility import ticket_visible

from .commun import config_site, contexte_site
from .courriels import envoyer_email_externe
from app.utils.destinataires import membres_cs_ou_admin
from app.utils.html_sur import html_riche
from app.utils.lecture import lire_objet
from app.utils.noms import contexte_personne, nom_auteur
from app.utils.etat_affaire import affaire_close
from app.utils.recuperer import ou_404, ou_rien
from app.utils.cloche import sonner
from app.utils.fusion_affaires import refuser_si_absorbee

router = APIRouter()


def message_lu(m: MessageTicket, session: Session, lecteur: Utilisateur) -> MessageRead:
    """Un message tel que `lecteur` le lit dans le fil : le nom de son auteur, et si
    c'est le sien (#2680).

    Le nom est SERVI (#2633) : l'écran ne le compose pas. `nom_auteur` dit la
    qualité d'un auteur détaché par la conservation (#2014), « Ancien résident »
    quand le compte n'existe plus — la règle de l'Historique (`commun.evol_read`).
    """
    auteur = ou_rien(session, Utilisateur, m.auteur_id)
    return lire_objet(
        MessageRead,
        m,
        auteur_nom=nom_auteur(auteur, m.auteur_qualite),
        est_auteur=est_auteur(m, lecteur),
    )


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
    return [
        message_lu(m, session, user) for m in session.exec(stmt.order_by(MessageTicket.cree_le))
    ]


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
    miroir = TicketEvolution(
        ticket_id=ticket_id,
        type="reponse",
        contenu="Message interne" if body.interne else body.contenu,
        auteur_id=user.id,
        cree_le=horloge.maintenant(),
        assiste_ia=body.assiste_ia,
        fichiers_urls="[]" if body.interne else photos_json(body.fichiers_urls),
    )
    session.add(miroir)
    ticket.mis_a_jour_le = horloge.maintenant()
    session.add(msg)
    session.add(ticket)
    #  L'id du message est nécessaire AVANT le commit : les notifications
    #  ci-dessous ancrent leur lien dessus (`#msg-42`), pour déposer le lecteur
    #  sur la réponse qui a déclenché l'alerte et non en haut de page.
    session.flush()
    msg.evolution_id = miroir.id  # #2722 : la correction ou le retrait du message la suit

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

    return message_lu(msg, session, user)


def _message_de_l_auteur(
    session: Session, ticket_id: int, msg_id: int, user: Utilisateur
) -> tuple[Ticket, MessageTicket]:
    """Le message, si CE lecteur peut le corriger ou le retirer (#2722).

    La règle arbitrée le 14/11/2026 : **son auteur**, **tant que l'affaire n'est
    pas close**. Ni le conseil ni l'admin n'écrivent à la place de quelqu'un — le
    retrait d'un propos d'autrui reste une affaire de modération, qui n'est pas
    ouverte ici. Un auteur détaché (compte supprimé) n'est personne (`est_auteur`).
    """
    ticket = exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    refuser_si_absorbee(ticket)
    msg = ou_404(session, MessageTicket, msg_id, "Message", sous={"ticket_id": ticket_id})
    if not est_auteur(msg, user):
        raise HTTPException(403, "Seul l'auteur d'un message peut le modifier ou le supprimer")
    if affaire_close(ticket.statut):
        raise HTTPException(409, "Cette affaire est close : sa discussion ne se modifie plus")
    return ticket, msg


@router.patch("/{ticket_id}/messages/{msg_id}", response_model=MessageRead)
def update_message(
    ticket_id: int,
    msg_id: int,
    body: MessageUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket, msg = _message_de_l_auteur(session, ticket_id, msg_id, user)
    msg.contenu = body.contenu
    if body.fichiers_urls is not None:
        msg.fichiers_urls = photos_json(body.fichiers_urls)
    miroir = session.get(TicketEvolution, msg.evolution_id) if msg.evolution_id else None
    #  Une note interne n'a jamais écrit son texte dans l'Historique : elle n'y
    #  réécrit rien non plus (même règle qu'à l'envoi).
    if miroir and not msg.interne:
        miroir.contenu = body.contenu
        if body.fichiers_urls is not None:
            miroir.fichiers_urls = photos_json(body.fichiers_urls)
        session.add(miroir)
    ticket.mis_a_jour_le = horloge.maintenant()
    session.add(msg)
    session.add(ticket)
    session.commit()
    session.refresh(msg)
    return message_lu(msg, session, user)


@router.delete("/{ticket_id}/messages/{msg_id}", status_code=204)
def delete_message(
    ticket_id: int,
    msg_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _, msg = _message_de_l_auteur(session, ticket_id, msg_id, user)
    miroir_id = msg.evolution_id
    #  Le message référence son miroir : il part le premier.
    session.delete(msg)
    session.flush()
    miroir = session.get(TicketEvolution, miroir_id) if miroir_id else None
    if miroir:
        session.delete(miroir)
    session.commit()
