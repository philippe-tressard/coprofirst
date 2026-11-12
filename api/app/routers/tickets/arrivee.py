"""**L'arrivée d'un ticket** : qui est prévenu, par quel canal, et une seule fois.

Extrait de `courriels.py` le 08/09/2026, quand la déduplication des envois (#850)
l'a porté de 454 à 510 lignes et que le garde-fou de modularité l'a refusé.

Le découpage n'est pas de commodité : ces trois fonctions forment **un** geste —
prévenir le conseil qu'un ticket vient d'être déposé — et il se décide sur deux
canaux dont les portées diffèrent volontairement :

===================  ==========================  ==============================
Canal                Destinataires               Pourquoi cette portée
===================  ==========================  ==============================
notification in-app  tout le conseil (+ admin)   une ligne dans une liste qu'on
                                                 parcourt ne dérange personne
courriel             CS du **périmètre**, moins  une boîte aux lettres, si — et
                     ceux déjà servis            deux fois, encore plus
===================  ==========================  ==============================

⚠️ Le reste de `courriels.py` compose et envoie des messages ; ceci **décide qui
les reçoit**. Les deux se lisaient ensemble par accident du découpage initial.
"""

from __future__ import annotations

from typing import Optional

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.models.core import StatutUtilisateur, Ticket, Utilisateur
from app.utils.destinataires import (
    batiments_du_perimetre,
    membres_cs_notifiables,
    membres_cs_ou_admin,
)
from app.utils.liens import lien_ticket
from app.utils.perimetres import parse_json_perimetres
from app.utils.noms import contexte_personne

from .commun import destinataires_syndic_cs

#  Le CONTEXTE du message reste dans `courriels` : composer et décider-qui sont
#  deux gestes, et c'est justement ce que ce découpage sépare.
from .courriels import _contexte_ticket
from app.utils.cloche import sonner


def _notifier_cs_creation(
    session: Session,
    ticket: Ticket,
    urgence: bool,
    auteur: Optional[Utilisateur] = None,
    background_tasks: Optional[BackgroundTasks] = None,
    deja_servies: Optional[set[str]] = None,
    par_courriel: bool = True,
) -> None:
    """Prévient le conseil syndical d’un nouveau ticket — in-app ET par courriel.

    🔴 `par_courriel=False` : l’auteur est du conseil et DIFFUSE lui-même — la case
    « Conseil syndical » de sa Diffusion décide du courriel (`ticket_syndic`), pas
    cette notification (03/10/2026, signalé à l’écran : *« si CS n’est pas
    sélectionné, il ne doit pas envoyer au CS »*). Un résident n’a pas cette case :
    pour lui le conseil est toujours prévenu. La cloche, elle, reste posée.

    🔴 **Le courriel manquait** (08/09/2026, vérification demandée à l’écran).
    Cette fonction ne posait qu’une `Notification`, et sa docstring le disait en
    toutes lettres. Un conseiller qui n’ouvre pas le site ne voyait donc jamais
    passer un signalement — au moment précis où quelqu’un attend une réaction.

    ⚠️ **Deux portées, et c’est voulu.** La notification in-app va à tout le CS ;
    le courriel au CS du **périmètre** du ticket. Ce qui est tolérable dans une
    liste qu’on parcourt ne l’est pas dans une boîte aux lettres — et
    `membres_cs_notifiables(session, batiments)` est la fonction prévue pour ça
    (tableau « Destinataires » de la skill `api-scaffold` §8).

    ⚠️ La préférence « e-mails de mon bâtiment / des autres » est appliquée par
    `send_email_group` via `batiments_concernes`, destinataire par destinataire.
    Elle n’est donc **pas** réécrite ici : c’est `utils/preferences_mail` qui
    tranche, et une seconde lecture ferait une seconde façon d’être en désaccord
    avec ce que le résident a demandé.
    """
    cs_members = membres_cs_ou_admin(session)
    if urgence:
        syndics = session.exec(
            select(Utilisateur).where(Utilisateur.statut == StatutUtilisateur.syndic)
        ).all()
        cs_ids = {m.id for m in cs_members}
        cs_members = list(cs_members) + [s for s in syndics if s.id not in cs_ids]

    for member in cs_members:
        sonner(
            session,
            batiments=batiments_du_perimetre(parse_json_perimetres(ticket.perimetre_cible)),
            destinataire_id=member.id,
            type="ticket_update",
            titre=f"Nouveau ticket : {ticket.titre}",
            corps=ticket.description[:200],
            lien=lien_ticket(ticket.id),
            urgente=urgence,
        )

    if background_tasks is None or auteur is None or not par_courriel:
        #  Sans tâche de fond, il n’y a pas d’envoi possible : le dire plutôt que
        #  de laisser croire que le courriel est parti.
        return
    _envoyer_email_cs_creation(
        session,
        ticket,
        auteur,
        urgence,
        background_tasks,
        deja_servies=deja_servies,
    )


def adresses_deja_servies(
    session: Session, ticket: Ticket, *, categorie: str | None = None
) -> set[str]:
    """Les adresses qu’un autre courriel du MÊME ticket va déjà servir.

    🔴 Consigne du 08/09/2026 : *« éviter le doublon quand la notification
    comprend les destinataires qui sont inclus dans la diffusion du ticket »*.

    Trois courriels peuvent partir pour une seule création — `ticket_syndic`,
    `ticket_bug_admin`, `ticket_nouveau_cs` — décidés à trois endroits qui ne se
    connaissent pas. Le récit complet, et la raison pour laquelle c’est
    `ticket_nouveau_cs` qui cède, vivent dans `utils/envois_uniques` : les écrire
    ici aussi en ferait une seconde version à tenir d’accord.
    """
    from app.utils.envois_uniques import adresses

    servies: set[str] = set()

    if ticket.destinataire_syndic or ticket.destinataire_cs:
        servies |= adresses(
            destinataires_syndic_cs(
                session,
                syndic=ticket.destinataire_syndic,
                cs=ticket.destinataire_cs,
            )
        )

    #  ⚠️ Le gestionnaire du site n’est PAS toujours dans `membres_cs_notifiables`
    #  (il faut qu’il ait une ligne `MembreCS`), et son adresse de notification
    #  peut être une adresse de configuration plutôt que celle d’un compte. Le
    #  recouvrement est donc CONDITIONNEL — mais quand il a lieu, il coûte deux
    #  courriels, et le retirer ne coûte rien.
    if (categorie or ticket.categorie) == "bug":
        from app.auth.adresse_compte import normaliser_adresse
        from app.utils.email import get_site_manager_notification_email

        adresse_admin, _ = get_site_manager_notification_email(session)
        if adresse_admin:
            servies.add(normaliser_adresse(adresse_admin))

    return servies


def _envoyer_email_cs_creation(
    session: Session,
    ticket: Ticket,
    auteur: Utilisateur,
    urgence: bool,
    background_tasks: BackgroundTasks,
    deja_servies: set[str] | None = None,
) -> list[str]:
    """Le courriel `ticket_nouveau_cs`, au CS du périmètre. Rend les adresses visées.

    Rendre la liste plutôt que rien : c’est ce qui permet à un test de constater
    QUI est visé, et non seulement qu’un envoi a été programmé.

    `deja_servies` porte les adresses qu’un courriel plus disant va déjà servir
    pour le même ticket — voir `adresses_deja_servies`.
    """
    from app.utils.email import send_email_group
    from app.utils.envois_uniques import sans_les_deja_servies

    batiments = batiments_du_perimetre(parse_json_perimetres(ticket.perimetre_cible))
    destinataires = membres_cs_notifiables(session, batiments)
    if deja_servies:
        destinataires = sans_les_deja_servies(destinataires, deja_servies)
    #  Une liste vide est un résultat NORMAL : tout le monde a déjà été servi par
    #  un message plus complet. Ne rien envoyer, plutôt qu’envoyer à personne —
    #  ce qui laisserait une trace sans destinataire dans `historique_email`.
    if not destinataires:
        return []

    background_tasks.add_task(
        send_email_group,
        code="ticket_nouveau_cs",
        to_recipients=destinataires,
        context={
            "ticket": _contexte_ticket(ticket),
            "auteur": contexte_personne(auteur),
            "urgent": urgence,
        },
        session=session,
        #  🔴 C’est CE paramètre qui fait respecter « e-mails de mon bâtiment »
        #  ou « des autres » — sans lui, la préférence ne s’applique pas.
        batiments_concernes=batiments,
    )
    return [email for _, email in destinataires]
