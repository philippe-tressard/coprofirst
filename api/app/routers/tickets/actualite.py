"""Une affaire de catégorie « Actualité » : ce qu'elle DIFFUSE, et ses deux invariants.

## Pourquoi un module (#1091, lot 4 — 23/09/2026)

L'actualité est devenue une catégorie d'affaire. Son écran, son vocabulaire de
diffusion et ses gabarits de courriel, eux, restent ceux de l'actualité : un
message WhatsApp qui se RESTREINT quand le public est ciblé, le courriel
`publication_syndic` au syndic et au CS, l'affiche de hall. Une affaire suivie
diffuse autrement (`courriels.py`) — le lecteur, le ton, le fil ne sont pas les
mêmes.

Ce module reprend la logique de `routers/publications/` (création, correction,
Suite), adaptée aux colonnes de l'affaire :

| Actualité (avant) | Affaire « Actualité » |
|---|---|
| `contenu` | `description` |
| `urgente` | `priorite == "haute"` |
| `confidentiel` (réservé au périmètre) | `reserve_perimetre` |
| `brouillon` (réservé au conseil) | Destinataires = « Conseil syndical » SEUL (#1096) |
| `Document.publication_id` | `Document.ticket_id` |
| `AnnonceHall.publication_id` | `AnnonceHall.ticket_id` |

⚠️ Il n'en existe qu'UNE écriture : le code des publications est retiré dans le
même lot.
"""

from __future__ import annotations

import json
import logging
from app.utils import horloge
from typing import Optional

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.models.annonce_hall import AnnonceHall
from app.models.core import Ticket, TicketEvolution, Utilisateur
from app.utils.recuperer import ou_rien
from app.models.documents import Document
from app.utils.config_site import config_site
from app.utils.dates_fr import datetime_longue_paris as _fmt_paris
from app.utils.fichiers import chemins_locaux
from app.utils.liens import adresse_du_site, lien_ticket, nom_site
from app.utils.noms import contexte_personne, nom_auteur
from app.utils.perimetres import a_portee_globale, batiments_cibles, parse_json_perimetres
from app.utils.photos import parse_photos, premiere_photo
from app.utils.stockage import stockage
from app.utils.visibility import hors_du_hall, reservee_au_conseil

from .suite_groupe import message_suite

logger = logging.getLogger("hostachy.actualite")


# ── L'invariant d'accès ─────────────────────────────────────────────────────
#  « Réservée au conseil » et « hors du hall » vivent dans `utils/visibility` :
#  les sources d'affiche les appellent aussi, et un utilitaire n'importe pas
#  un routeur.


def appliquer_acces(ticket: Ticket, session: Session) -> None:
    """Fait tenir, à chaque écriture, ce que l'Accès et la réserve promettent.

    1. 🔒 « Visible du seul périmètre » sur un périmètre GLOBAL ne retire la
       lecture à personne : le drapeau est retiré plutôt que conservé et menteur
       (règle de l'ancienne publication, #347).
    2. Un contenu qui se referme — réservé au conseil, ou au périmètre — ne reste
       pas punaisé dans un hall : ses affiches sont ARCHIVÉES (le PDF a été
       envoyé, il fait foi : archiver ≠ supprimer).
    """
    if ticket.reserve_perimetre:
        try:
            codes = json.loads(ticket.perimetre_cible or "[]")
        except (TypeError, ValueError):
            codes = None
        if isinstance(codes, list) and (not codes or a_portee_globale([str(c) for c in codes])):
            ticket.reserve_perimetre = False
    if not hors_du_hall(ticket):
        return
    for annonce in session.exec(
        select(AnnonceHall).where(
            AnnonceHall.ticket_id == ticket.id,
            AnnonceHall.archivee == False,  # noqa: E712
        )
    ).all():
        annonce.archivee = True
        session.add(annonce)


# ── Le contexte des gabarits `publication_*` ────────────────────────────────


def _historique(session: Session, ticket: Ticket, *, sauf_derniere: bool) -> list[dict]:
    """Les paroles du fil, pour l'encart « historique » des courriels.

    Écrit une fois : l'ancien module l'écrivait deux fois, pour le syndic et
    pour l'adresse externe.
    """
    evols = [
        e
        for e in session.exec(
            select(TicketEvolution)
            .where(TicketEvolution.ticket_id == ticket.id)
            .order_by(TicketEvolution.cree_le)
        ).all()
    ]
    if sauf_derniere and evols:
        evols = evols[:-1]
    lignes = []
    for e in evols:
        if not e.contenu:
            continue
        auteur = ou_rien(session, Utilisateur, e.auteur_id)
        lignes.append(
            {
                "auteur_nom": nom_auteur(auteur, e.auteur_qualite),
                "date": _fmt_paris(e.cree_le),
                "contenu": e.contenu,
            }
        )
    return lignes


def _pieces(session: Session, ticket: Ticket, fichiers_urls: Optional[list[str]]) -> list[str]:
    """Photos, pièces jointes et documents de la bibliothèque rattachés à l'affaire."""
    chemins = chemins_locaux(parse_photos(ticket.photos_urls))
    chemins += chemins_locaux(parse_photos(ticket.fichiers_urls))
    if ticket.id is not None:
        for doc in session.exec(select(Document).where(Document.ticket_id == ticket.id)).all():
            if (fichier := stockage().fichier_de(doc)) is not None:
                chemins.append(str(fichier))
    if fichiers_urls:
        chemins += chemins_locaux(fichiers_urls)
    return chemins


def contexte_actualite(
    ticket: Ticket,
    user: Utilisateur,
    session: Session,
    *,
    commentaire: Optional[str] = None,
    fichiers_urls: Optional[list[str]] = None,
    pieces_de_l_affaire: bool = True,
) -> tuple[dict, list[str]]:
    """Le contexte des gabarits `publication_syndic` / `publication_externe`, et les pièces.

    Rendus ENSEMBLE : le drapeau `fichiers` du gabarit se calcule sur la liste —
    les séparer annoncerait des pièces qui ne partent pas (10/08/2026). L'aperçu
    de diffusion appelle la même fonction : il ne peut pas diverger de l'envoi.
    """
    cfg = config_site(session)
    est_commentaire = commentaire is not None
    pieces_jointes = (
        _pieces(session, ticket, fichiers_urls)
        if pieces_de_l_affaire
        else chemins_locaux(fichiers_urls or [])
    )
    ctx = {
        "publication": {
            "id": ticket.id,
            "titre": ticket.titre,
            "contenu": ticket.description or "",
            "lien": lien_ticket(ticket.id) if ticket.id is not None else "/tickets",
        },
        "auteur": contexte_personne(user),
        "residence": {"nom": nom_site(cfg.get("site_nom"))},
        "app": {"url": adresse_du_site()},
        "is_commentaire": est_commentaire,
        "commentaire": commentaire or "",
        "date_commentaire": _fmt_paris(horloge.maintenant()),
        "date_publication": _fmt_paris(ticket.cree_le),
        "evolutions": _historique(session, ticket, sauf_derniere=est_commentaire)
        if ticket.id
        else [],
        "fichiers": bool(pieces_jointes),
    }
    return ctx, pieces_jointes


# ── La diffusion ────────────────────────────────────────────────────────────


def _partager_sur_le_groupe(
    session: Session,
    ticket: Ticket,
    background_tasks: BackgroundTasks,
    *,
    commentaire: Optional[str] = None,
    fichiers_urls: Optional[list[str]] = None,
) -> None:
    from app.utils.diffusion import config_diffusion

    from .groupe import diffuser_l_affaire

    config = config_diffusion(session)
    if config is None:
        return
    #  L'adresse du site lue dans la configuration du CANAL, comme le partage
    #  d'une affaire suivie (`courriels._partager_sur_le_groupe`).
    site = adresse_du_site()
    lien = site + lien_ticket(ticket.id)
    titre, contenu, photo = (
        ticket.titre,
        ticket.description or "",
        premiere_photo(ticket.photos_urls),
    )
    if commentaire is not None:
        #  Une Suite part seule : le fil qui la précède se lit dans l'application.
        #  Le rappel et le lien viennent de `message_suite` : le canal place le
        #  lien après le texte — l'écrire aussi dans le texte le doublait.
        suite = message_suite(
            session,
            ticket,
            commentaire,
            site_url=site,
            suite_enregistree=True,
            fichiers_urls=fichiers_urls,
        )
        titre, contenu, photo, lien = suite.titre, suite.contenu, suite.photo, suite.lien
    diffuser_l_affaire(
        background_tasks,
        config,
        ticket,
        titre,
        contenu,
        urgente=ticket.priorite == "haute",
        image_url=photo,
        lien=lien,
    )


def _ecrire_au_syndic_et_au_cs(
    session: Session,
    ticket: Ticket,
    user: Utilisateur,
    background_tasks: BackgroundTasks,
    *,
    syndic: bool,
    cs: bool,
    auteur: bool,
    commentaire: Optional[str],
    fichiers_urls: Optional[list[str]],
) -> None:
    from app.utils.copie_auteur import destinataires_et_copie
    from app.utils.destinataires import destinataires_syndic_cs
    from app.utils.email import send_email_group

    destinataires, bcc, seule = destinataires_et_copie(
        session,
        ticket,
        destinataires_syndic_cs(session, syndic=syndic, cs=cs),
        demandee=auteur,
    )
    #  Cochée SEULE, la copie a son gabarit (03/10/2026).
    code = "publication_copie_auteur" if seule else "publication_syndic"
    if not destinataires:
        return
    ctx, pieces = contexte_actualite(
        ticket,
        user,
        session,
        commentaire=commentaire,
        fichiers_urls=fichiers_urls,
    )
    background_tasks.add_task(
        send_email_group,
        code=code,
        to_recipients=destinataires,
        context=ctx,
        session=session,
        bcc=bcc,
        attachments=pieces or None,
        #  La préférence « mes bâtiments » se décide sur ce que l'actualité vise.
        batiments_concernes=batiments_cibles(parse_json_perimetres(ticket.perimetre_cible)),
    )


def _ecrire_au_dehors(
    session: Session,
    ticket: Ticket,
    user: Utilisateur,
    background_tasks: BackgroundTasks,
    adresse: str,
    *,
    commentaire: Optional[str],
    fichiers_urls: Optional[list[str]],
) -> None:
    from app.utils.email import send_email

    ctx, pieces = contexte_actualite(
        ticket,
        user,
        session,
        commentaire=commentaire,
        fichiers_urls=fichiers_urls,
        pieces_de_l_affaire=False,
    )
    ctx["is_commentaire"] = commentaire is not None
    background_tasks.add_task(
        send_email,
        code="publication_externe",
        to=adresse,
        context=ctx,
        bcc=[user.email] if user.email and user.email.lower() != adresse.lower() else None,
        attachments=pieces or None,
    )


def generer_affiche(
    session: Session,
    ticket: Ticket,
    user: Utilisateur,
    background_tasks: BackgroundTasks,
) -> None:
    """L'affiche de hall d'une actualité — une seule, et jamais pour un contenu refermé.

    Un hall n'a aucun contrôle d'accès derrière lui : réservée au conseil ou au
    périmètre, l'actualité n'y va pas. L'échec de la génération ne fait jamais
    échouer l'actualité : il est journalisé.
    """
    from app.routers.annonces_hall import creer_annonce_hall, images_de

    if hors_du_hall(ticket):
        logger.warning("Affiche de hall refusée : l'actualité %s est réservée", ticket.id)
        return
    if session.exec(select(AnnonceHall).where(AnnonceHall.ticket_id == ticket.id)).first():
        return
    try:
        creer_annonce_hall(
            session=session,
            user=user,
            background_tasks=background_tasks,
            titre=ticket.titre,
            message=ticket.description or "",
            perimetre_cible=parse_json_perimetres(ticket.perimetre_cible),
            images=images_de(ticket, session),
            ticket_id=ticket.id,
        )
    except Exception as exc:  # noqa: BLE001 — l'affiche ne bloque pas l'actualité
        logger.error("Affiche de hall non générée pour l'actualité %s : %s", ticket.id, exc)


def diffuser_actualite(
    session: Session,
    ticket: Ticket,
    user: Utilisateur,
    background_tasks: BackgroundTasks,
    *,
    whatsapp: bool = False,
    syndic: bool = False,
    cs: bool = False,
    auteur: bool = False,
    externe: Optional[str] = None,
    affiche: bool = False,
    commentaire: Optional[str] = None,
    fichiers_urls: Optional[list[str]] = None,
) -> None:
    """Fait partir ce que l'auteur a coché — rien du tout si l'actualité est réservée.

    Les droits sont ceux de l'APPELANT (une actualité ne se publie et ne se
    diffuse que par le conseil) : ce module ne les redécide pas.
    """
    if reservee_au_conseil(ticket):
        return
    if whatsapp:
        _partager_sur_le_groupe(
            session,
            ticket,
            background_tasks,
            commentaire=commentaire,
            fichiers_urls=fichiers_urls,
        )
    if syndic or cs or auteur:
        _ecrire_au_syndic_et_au_cs(
            session,
            ticket,
            user,
            background_tasks,
            syndic=syndic,
            cs=cs,
            auteur=auteur,
            commentaire=commentaire,
            fichiers_urls=fichiers_urls,
        )
    if externe and externe.strip():
        _ecrire_au_dehors(
            session,
            ticket,
            user,
            background_tasks,
            externe.strip(),
            commentaire=commentaire,
            fichiers_urls=fichiers_urls,
        )
    if affiche and commentaire is None:
        generer_affiche(session, ticket, user, background_tasks)


__all__ = [
    "appliquer_acces",
    "contexte_actualite",
    "diffuser_actualite",
    "generer_affiche",
]
