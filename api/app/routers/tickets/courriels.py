"""Tickets — les e-mails que produit un ticket.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de
découpage.

Rassemble ce qui **compose et envoie** un message, pour que les routes ne
portent plus que la décision de l'envoyer. C'est aussi ce qui a permis de
supprimer le troisième exemplaire de la liste des destinataires : les deux
appelants (création d'un ticket, ajout d'une évolution) construisaient le même
e-mail `ticket_syndic` avec deux blocs de code distincts.
"""

from app.utils import horloge
from typing import Optional

from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.models.core import (
    MessageTicket,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.utils.photos import parse_photos
from app.utils.categories_ticket import libelle_categorie, ticket_urgent
from app.utils.copie_auteur import destinataires_et_copie
from app.utils.perimetres import perimetre_label_json
from app.utils.dates_fr import date_courte, datetime_longue_paris as fmt_paris
from app.utils.fichiers import chemins_locaux

from .commun import (
    config_site,
    contexte_site,
    destinataires_syndic_cs,
)
from .historique_courriel import (
    affaires_liees_du_courriel,
    contexte_affaires_liees,
    lignes_historique,
)
from app.utils.noms import contexte_personne, nom_auteur
from app.utils.recuperer import ou_rien
from app.utils.liens import adresse_du_site, nom_site


def _contexte_ticket(ticket) -> dict:
    """Le bloc `ticket` attendu par tous les modèles — une seule description."""
    return {
        "id": ticket.id,
        "numero": ticket.numero,
        "titre": ticket.titre,
        "description": ticket.description or "",
        #  🔴 LE LIBELLÉ, pas l'énumération. Le courriel du syndic affichait
        #  « CategorieTicket.panne » : `CategorieTicket` est une `(str, Enum)`, et
        #  depuis Python 3.11 son `__str__` rend le nom qualifié. Le destinataire
        #  lisait un identifiant de code Python. Signalé à l'écran le 31/08/2026.
        "categorie": libelle_categorie(ticket.categorie),
        #  🔴 LE PÉRIMÈTRE, absent jusqu'au 31/08/2026 — et c'est celui des deux
        #  ajouts qui compte le plus :
        #
        #  > « il manque le périmètre, il faut l'ajouter car cette information est
        #  > capitale pour le syndic ou le CS pour identifier le périmètre du
        #  > problème »
        #
        #  Un syndic qui reçoit « ferme-porte explosif » sans savoir de quel
        #  bâtiment ni de quelle cage d'escalier doit rappeler pour le demander.
        #  L'écran l'affiche depuis toujours ; le courriel, jamais.
        "perimetre": perimetre_label_json(getattr(ticket, "perimetre_cible", None)),
    }


def envoyer_email_syndic_cs(
    ticket,
    user: Utilisateur,
    background_tasks: BackgroundTasks,
    session: Session,
    *,
    syndic: bool,
    cs: bool,
    pieces_jointes: list[str],
    commentaire: Optional[str] = None,
    evolutions: Optional[list[TicketEvolution]] = None,
    auteur: bool = False,
):
    """E-mail `ticket_syndic`, à la création comme à l'ajout d'une évolution.

    Les deux appelants écrivaient ce bloc séparément. La conséquence était déjà
    visible : la clé `fichiers`, que le modèle interroge derrière un `{% if %}`,
    n'était fournie que d'un côté — Jinja évalue un indéfini à faux sans rien
    signaler, et les photos partaient en pièce jointe sans être annoncées.
    Elle est calculée ici sur ce qui est **réellement attaché**, pas sur
    l'intention.
    """
    destinataires, auteur_bcc, seule = destinataires_et_copie(
        session,
        ticket,
        destinataires_syndic_cs(session, syndic=syndic, cs=cs),
        demandee=auteur,
    )
    #  Cochée SEULE, la copie a son gabarit (03/10/2026).
    code = "ticket_copie_auteur" if seule else "ticket_syndic"
    if not destinataires:
        return

    from app.utils.email import send_email_group

    ctx = contexte_ticket_syndic(
        ticket,
        user,
        session,
        pieces_jointes=pieces_jointes,
        commentaire=commentaire,
        evolutions=evolutions,
    )

    #  🔴 LA COPIE VA AU PROPRIÉTAIRE DU TICKET, pas à qui écrit — et le
    #  propriétaire est le « Saisi pour » quand il existe (12/09/2026).
    #
    #  La règle, ses trois états successifs du 31/08/2026 et la déduplication
    #  vivent dans `app/utils/copie_auteur.py` — elle sert aussi les publications
    #  et le calendrier, où elle avait trois comportements différents.
    #  🔴 L'ADRESSE DE RÉPONSE (#703). C'est le SEUL courriel du site auquel on
    #  attend une réponse écrite : le syndic répond, et sa réponse doit rejoindre
    #  le fil du ticket au lieu de dormir dans une boîte que personne n'ouvre.
    #
    #  Le jeton part avec l'envoi, jamais l'identifiant du ticket : il sera
    #  recopié dans tous les carnets d'adresses de la chaîne, et un identifiant
    #  en clair donnerait le moyen d'écrire sur n'importe quel ticket en devinant
    #  `tickets+42@`. Voir `utils/courriel_entrant.py`.
    background_tasks.add_task(
        send_email_group,
        code=code,
        to_recipients=destinataires,
        context=ctx,
        session=session,
        bcc=auteur_bcc,
        attachments=pieces_jointes or None,
        jeton_reponse=getattr(ticket, "jeton_courriel", None),
    )


def contexte_ticket_syndic(
    ticket,
    user: Utilisateur,
    session: Session,
    *,
    pieces_jointes: list[str],
    commentaire: Optional[str] = None,
    evolutions: Optional[list[TicketEvolution]] = None,
) -> dict:
    """Le contexte du modèle `ticket_syndic` — **écrit une seule fois**.

    ## Pourquoi il est sorti de l'envoi (#498, 19/08/2026)

    L'aperçu avant diffusion doit montrer **ce qui partira**, pas une
    reconstitution : un contexte rebâti de son côté deviendrait faux à la
    première évolution du gabarit, et personne ne s'en apercevrait — puisque
    c'est justement l'aperçu qu'on regarderait pour le vérifier
    (`standards/04` §14).

    L'envoi et l'aperçu appellent donc cette fonction, et
    `api/tests/test_apercu_diffusion.py` échoue si l'un des deux s'en écarte.

    ⚠️ Elle accepte un ticket **non persisté** — c'est tout l'intérêt : l'aperçu
    est demandé avant que l'objet existe. Les champs attribués à la création
    (`id`, `numero`) valent alors `None`, et c'est à l'écran de le dire plutôt
    que d'inventer un numéro.
    """
    cfg = config_site(session)

    messages_ctx = []
    #  Les affaires liées prolongent l'historique : le lien s'y trace, et chacune
    #  s'ajoute dessous avec le sien (`historique_courriel`).
    liees = affaires_liees_du_courriel(session, ticket)
    historique = lignes_historique(ticket, evolutions or [], liees)
    for ev in evolutions or []:
        if ev.contenu:
            auteur_e = ou_rien(session, Utilisateur, ev.auteur_id)
            messages_ctx.append(
                {
                    "auteur_nom": nom_auteur(auteur_e, ev.auteur_qualite),
                    "date": fmt_paris(ev.cree_le),
                    "contenu": ev.contenu,
                    #  🔴 Le périmètre de CETTE entrée, demandé le 31/08/2026 :
                    #  *« il faut signaler l'auteur et le périmètre de chaque
                    #  commentaire »*. Une entrée peut préciser le périmètre — « on a
                    #  trouvé d'où vient la fuite » — et c'est justement ce qu'un
                    #  syndic cherche dans un fil.
                    #
                    #  ⚠️ VIDE quand l'entrée n'en parle pas, et le gabarit n'affiche
                    #  alors rien. Reprendre celui du ticket ferait croire que chaque
                    #  commentaire l'a redit — donc l'a confirmé — alors qu'il ne
                    #  faisait que ne rien préciser. C'est la même règle que le
                    #  serveur applique déjà à l'écriture : « laissé vide, le
                    #  périmètre du ticket ne bouge pas » (#497).
                    "perimetre": perimetre_label_json(getattr(ev, "perimetre_cible", None)),
                }
            )

    ctx = {
        "ticket": _contexte_ticket(ticket),
        "auteur": contexte_personne(user),
        **contexte_site(cfg),
        "is_commentaire": bool(commentaire and commentaire.strip()),
        "commentaire": commentaire or "",
        "date_commentaire": fmt_paris(horloge.maintenant()),
        #  Le périmètre que le COMMENTAIRE en cours précise, s'il en précise
        #  un. Vide sinon, et le gabarit n'affiche alors rien : reprendre celui
        #  du ticket ferait croire que ce commentaire l'a redit, donc confirmé.
        #
        #  ⚠️ Il vient des évolutions et non du ticket : à la CRÉATION il n'y a
        #  pas de commentaire, et la clé vaut alors la chaîne vide — présente,
        #  comme toutes les autres, parce qu'une clé absente est très exactement
        #  la panne « X is undefined » que ce dépôt a vue trois fois.
        "commentaire_perimetre": (
            perimetre_label_json(getattr(evolutions[-1], "perimetre_cible", None))
            if evolutions
            else ""
        ),
        "date_creation": date_courte(ticket.cree_le),
        #  🔴 Du PLUS RÉCENT au plus ancien (#529, signalé à l'écran : « le
        #  dernier message n'est pas inclus en premier »).
        #
        #  L'historique est construit en ordre chronologique — c'est le bon ordre
        #  pour une frise. Mais le bloc « messages » d'un e-mail se lit comme un
        #  fil de discussion : on veut d'abord ce à quoi on répond, pas l'échange
        #  d'il y a trois semaines. Le destinataire de ce mail est le SYNDIC, qui
        #  reçoit une reprise de sa propre réponse : la remonter en tête est
        #  exactement ce qu'il cherche.
        #
        #  ⚠️ `historique` garde l'ordre chronologique : c'est une frise, et une
        #  frise à l'envers ne se lit pas. Deux blocs, deux ordres, deux raisons.
        "messages": list(reversed(messages_ctx)),
        "historique": historique,
        "affaires_liees": contexte_affaires_liees(session, liees),
        "fichiers": bool(pieces_jointes),
    }
    return ctx


def envoyer_email_externe(
    ticket,
    user: Utilisateur,
    email_externe: str,
    background_tasks: BackgroundTasks,
    session: Session,
    *,
    is_commentaire: bool = True,
    nouveau_message: Optional[str] = None,
    fichiers_urls: Optional[list[str]] = None,
):
    """Envoie un e-mail vers une adresse externe avec l'historique du ticket."""
    from app.utils.email import send_email

    cfg = config_site(session)

    # Messages publics du ticket (historique)
    messages = session.exec(
        select(MessageTicket)
        .where(MessageTicket.ticket_id == ticket.id, MessageTicket.interne == False)  # noqa: E712
        .order_by(MessageTicket.cree_le)
    ).all()
    # Exclure le dernier si c'est le message courant
    msgs_for_history = messages[:-1] if (is_commentaire and messages) else messages
    msgs_ctx = []
    for m in msgs_for_history:
        auteur_m = ou_rien(session, Utilisateur, m.auteur_id)
        msgs_ctx.append(
            {
                "auteur_nom": nom_auteur(auteur_m, m.auteur_qualite),
                "date": fmt_paris(m.cree_le),
                "contenu": m.contenu,
            }
        )

    attachments = chemins_locaux(fichiers_urls or [])

    ctx = {
        "ticket": _contexte_ticket(ticket),
        "auteur": contexte_personne(user),
        "date_ticket": fmt_paris(ticket.cree_le),
        "date_commentaire": fmt_paris(horloge.maintenant()),
        **contexte_site(cfg),
        "app": {"url": adresse_du_site()},
        "is_commentaire": is_commentaire,
        "commentaire": nouveau_message or "",
        "messages": msgs_ctx,
        "fichiers": bool(attachments),
    }

    background_tasks.add_task(
        send_email,
        code="ticket_externe",
        to=email_externe,
        context=ctx,
        attachments=attachments or None,
    )


#  ── Déplacés depuis `crud.py` le 30/08/2026 (#546) ──────────────────────
#  Le contrôle de modularité a refusé une ligne de plus dans `crud.py`, et il
#  désignait un problème de PLACEMENT : ces deux fonctions COMPOSENT ET
#  ENVOIENT un message, ce que l'en-tête de ce fichier-ci décrit comme sa
#  raison d'être — « pour que les routes ne portent plus que la décision de
#  l'envoyer ». Elles étaient restées dans le CRUD par l'accident du
#  découpage initial, pas par choix.


def _alerter_bug(
    session: Session, ticket: Ticket, user: Utilisateur, background_tasks: BackgroundTasks
) -> None:
    """Un ticket « bug » prévient le gestionnaire du site : c'est du ressort admin.

    Lui SEUL (#1191, 24/09/2026) : sa cloche sonne toujours — le bogue est sa
    tâche —, le courriel suit le réglage `notify_ticket_bug_email`.
    """
    from app.utils.cloche import sonner_systeme
    from app.utils.destinataires import site_manager_user_id
    from app.utils.liens import lien_ticket

    gestionnaire = site_manager_user_id(session)
    if gestionnaire is not None:
        sonner_systeme(
            session,
            "bug",
            destinataire_id=gestionnaire,
            type="ticket_update",
            titre=f"Bogue signalé : {ticket.titre}",
            corps=ticket.description[:200],
            lien=lien_ticket(ticket.id),
        )
    cfg = config_site(session, "notify_ticket_bug_email", "site_email", "site_manager_user_id")
    if cfg.get("notify_ticket_bug_email") != "1":
        return

    from app.utils.email import get_site_manager_notification_email, send_email

    target_email, site_cfg = get_site_manager_notification_email(session)
    if not target_email:
        return
    background_tasks.add_task(
        send_email,
        code="ticket_bug_admin",
        to=target_email,
        context={
            "ticket": {
                "id": ticket.id,
                "numero": ticket.numero,
                "titre": ticket.titre,
                "description": ticket.description,
                "categorie": ticket.categorie,
            },
            "auteur": contexte_personne(user, email=user.email),
            "residence": {"nom": nom_site(site_cfg.get("site_nom"), cfg.get("site_nom"))},
            "app": {"url": adresse_du_site()},
        },
    )


def _partager_sur_le_groupe(
    session: Session, ticket: Ticket, background_tasks: BackgroundTasks
) -> None:
    """Publie le ticket sur le groupe WhatsApp, première photo comprise.

    L'autorisation est vérifiée par l'appelant : le groupe diffuse à tous les
    résidents, il n'est pas ouvert à l'auteur d'un ticket quelconque.
    """
    from app.utils.fichiers import est_image
    from app.utils.diffusion import config_diffusion

    from .groupe import diffuser_l_affaire

    wa_config = config_diffusion(session)
    if wa_config is None:
        return
    #  La première photo accompagne le message, comme l'image d'une actualité :
    #  sur une fuite ou une dégradation, c'est elle qui porte l'information. Les
    #  documents joints ne partent pas — le bridge n'envoie qu'une image.
    premiere_photo = next((u for u in parse_photos(ticket.photos_urls) if est_image(u)), None)
    diffuser_l_affaire(
        background_tasks,
        wa_config,
        ticket,
        f"🎫 {ticket.titre}",
        ticket.description,
        urgente=ticket_urgent(ticket),
        image_url=premiere_photo,
    )


#  🔴 DÉPLACÉE DEPUIS `crud.py` le 05/09/2026, au fil de l'eau : le garde-fou de
#  modularité a refusé que ce fichier-là grossisse pour recevoir les options de
#  publication. Sa place est ici, et pas seulement pour la taille — c'est un
#  EFFET de la création (« qui est prévenu ? »), du même registre exact que
#  `_alerter_bug` et `_partager_sur_le_groupe` juste en dessous. `crud.py` garde
#  la décision, ce module porte ce qui part.
