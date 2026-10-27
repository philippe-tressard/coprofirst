"""Tickets — fil de suivi : changements d'état et commentaires du CS.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""

import json
from app.utils import horloge

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import (
    est_moderateur,
    get_current_user,
    peut_commenter,
    require_admin,
    require_cs_or_admin,
)
from app.database import get_session
from app.models.core import (
    STATUTS_TICKET_CLOS,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.schemas import TicketEvolutionCreate, TicketEvolutionRead, TicketEvolutionUpdate
from .actualite import diffuser_actualite
from app.utils.evolutions import TYPES_SAISIS, evolution_modifiable, supprimer_evolution
from app.utils.perimetre_fil import doit_propager
from app.utils.suivi_fil import statuts_avant
from app.utils.suivi_actualite import etat_de_la_suite, refuser_etat
from app.utils.valeurs import valeur
from app.utils.nature_affaire import est_actualite
from app.utils.fichiers import chemins_locaux
from app.utils.assiste_ia import marquer as marquer_assiste_ia
from app.utils.photos import photos_internes, photos_json
from app.utils.recuperer import ou_404
from app.utils.synthese_affaire.lecture import evolutions_lisibles
from app.utils.visibility import reservee_au_conseil, ticket_visible

from .commun import (
    STATUT_LABELS,
    evol_read,
)
from .suite_sections import (
    appliquer_sections_suite,
    appliquer_statut,
    corriger_suivi,
)
from .courriels import envoyer_email_externe, envoyer_email_syndic_cs
from .notifier_auteur import _notifier_auteur
from .suite_groupe import message_suite
from app.utils.liens import adresse_du_site
from app.utils.affaires_liees import ajouter_liens
from app.utils.fusion_affaires import (
    conciliations_par_affaire,
    fusionner,
    prevenir_auteurs,
    refuser_si_absorbee,
)

router = APIRouter()

#  `_STATUTS_ADMIS = ("ouvert", "en_cours", "résolu", "fermé")` vivait ici, et
#  refusait `annulé` depuis le tout premier commit — le jour où les écrans se
#  sont mis à le proposer, le même geste réussissait depuis la fiche du ticket
#  et échouait depuis la liste (#415). La liste ne revient pas : le type
#  `StatutTicket` porté par `TicketEvolutionCreate.nouveau_statut` valide, et il
#  est le seul à le faire.


@router.get("/{ticket_id}/evolutions", response_model=list[TicketEvolutionRead])
def get_evolutions(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = ou_404(session, Ticket, ticket_id, "Ticket")
    #  🔴 LE FIL SE LIT PAR QUI LIT L'AFFAIRE (29/09/2026), arbitré à l'écran
    #  après TK-124285 : des copropriétaires lisaient l'affaire de leur
    #  bâtiment et en voyaient les suites VIDES — la règle était celle de
    #  l'écriture (`peut_commenter`), et l'écran avalait le 403. Les droits
    #  appartiennent à l'affaire, jamais à une Suite : celle qui les change
    #  les change pour tout le fil, et le dit (`visibility/trace_droits.py`).
    #  C'est la règle des messages (`messages.py`), et celle de la recherche.
    if not ticket_visible(ticket, user):
        raise HTTPException(403, "Accès refusé")
    evols = session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket_id)
        .order_by(TicketEvolution.cree_le)
    ).all()
    #  La Suite d'une synthèse en brouillon ne se lit que du conseil (#1643).
    evols = evolutions_lisibles(session, ticket, evols, user)
    #  L'état d'avant chaque entrée : la pastille qui, en correction, ramène la
    #  Suite à un commentaire (`suivi_fil.py`) — calculé ici, une fois.
    avant = statuts_avant(evols, etat_de_la_suite(ticket))
    return [evol_read(e, session, avant.get(e.id)) for e in evols]


@router.patch("/{ticket_id}/evolutions/{evol_id}", response_model=TicketEvolutionRead)
def update_evolution(
    ticket_id: int,
    evol_id: int,
    body: TicketEvolutionUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    evol = evolution_modifiable(
        session,
        TicketEvolution,
        evol_id,
        champ_parent="ticket_id",
        parent_id=ticket_id,
        user=user,
    )
    if body.contenu is not None:
        evol.contenu = body.contenu
    if body.fichiers_urls is not None:
        evol.fichiers_urls = photos_json(body.fichiers_urls)
    marquer_assiste_ia(evol, body)
    ticket = ou_404(session, Ticket, ticket_id, "Ticket")
    refuser_si_absorbee(ticket)  # corriger la Suite de fusion la rouvrirait (#1704)
    if body.perimetre_cible is not None:
        #  🔴 CORRIGER, pas raturer. La règle et son pourquoi vivent dans
        #  `app/utils/perimetre_fil.py` — elle a son `--selftest`.
        evol.perimetre_cible = (
            json.dumps(body.perimetre_cible, ensure_ascii=False) if body.perimetre_cible else None
        )
        fil = session.exec(
            select(TicketEvolution)
            .where(TicketEvolution.ticket_id == ticket_id)
            .order_by(TicketEvolution.cree_le)
        ).all()
        #  ⚠️ L'entrée en base porte encore l'ancienne valeur dans `fil` : on la
        #  remplace par l'objet modifié, sinon on compare la correction à
        #  elle-même d'avant.
        fil = [evol if e.id == evol.id else e for e in fil]
        if doit_propager(evol, fil):
            ticket.perimetre_cible = evol.perimetre_cible
            session.add(ticket)
    #  🔄 Toutes les sections d'une Suite se corrigent (01/10/2026) — le Suivi
    #  d'abord : il corrige l'entrée, et l'affaire seulement si c'est sa dernière
    #  transition (`utils/suivi_fil.py`). Le reste, comme à l'ajout.
    if body.type is not None:
        corriger_suivi(session, ticket, evol, body, user)
    appliquer_sections_suite(session, ticket, evol, body, user)
    if body.affaires_liees:
        ajouter_liens(session, ticket, body.affaires_liees, user)
    session.add(evol)
    session.commit()
    session.refresh(evol)
    fil = session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket_id)
        .order_by(TicketEvolution.cree_le)
    ).all()
    return evol_read(evol, session, statuts_avant(fil, etat_de_la_suite(ticket)).get(evol.id))


@router.delete("/{ticket_id}/evolutions/{evol_id}", status_code=204)
def delete_evolution(
    ticket_id: int,
    evol_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """Retirer une entrée du fil — **administrateur seulement**.

    ## Pourquoi cette capacité existe (18/08/2026)

    Demandée à l'écran après le défaut des corrections auto-tracées : deux entrées
    « Correction : Description modifiée ; Périmètre modifié ; … » s'étaient
    inscrites sur un ticket alors qu'une seule catégorie avait changé. Elles ne
    décrivent rien qui ait eu lieu, et **rien ne permettait de les retirer** — pas
    même à l'administrateur : *« je ne peux le faire »*.

    Le fil est une mémoire ; une mémoire qui garde des faits inventés vaut moins
    qu'une mémoire trouée. La capacité manquait, et son absence obligeait à
    envisager une intervention en base — ce que la règle d'or du projet interdit
    tant que l'API tourne.

    ## Pourquoi `require_admin` et non `require_cs_or_admin`

    La correction d'une entrée (`PATCH`) est ouverte à son auteur : réécrire son
    propre commentaire est un geste ordinaire. **Effacer** ne l'est pas — cela fait
    disparaître une trace que d'autres ont pu lire et sur laquelle ils ont pu agir.
    C'est la même frontière que pour la suppression d'un ticket, et la même règle
    que « archiver n'est pas supprimer » : le geste irréversible reste à l'admin.

    ## Les transitions aussi — arbitrage corrigé le 18/08/2026

    Ce endpoint a d'abord refusé les entrées de type « etat », au motif qu'un
    mouvement de workflow est un fait de la vie du dossier et non un texte qu'on
    rature. **L'arbitrage était le mien, pas celui de l'utilisateur**, qui avait
    demandé « une suppression pour les historiques » sans distinction — et qui a
    constaté l'absence dès la première entrée d'état rencontrée.

    Ce qui le rend acceptable : supprimer l'entrée **ne change pas l'état du
    ticket**. `Ticket.statut` vit dans sa propre colonne ; le fil n'en est que le
    récit. Le coût est donc une perte de TRAÇABILITÉ — on ne saura plus quand le
    ticket est passé « En cours » —, pas une incohérence de données.

    ⚠️ C'est un coût réel, et c'est la raison pour laquelle le geste reste réservé
    à l'administrateur : le fil sert de preuve au conseil syndical face au syndic.
    Une transition effacée ne se retrouve pas.

    ⚠️ **Les RÉPONSES restent inaccessibles** (`type == "reponse"`) : elles
    appartiennent à leur auteur, souvent un résident, et un administrateur qui les
    effacerait supprimerait la parole de quelqu'un d'autre. Ce n'est pas la même
    chose que retirer une ligne que le système a écrite ou qu'on a écrite soi-même.
    """
    #  🔴 La décision a quitté ce fichier (#512) : les actualités et les
    #  événements ont désormais le même geste, et trois copies auraient divergé
    #  au premier ajustement de la liste des types. Ce qui reste ici est le
    #  contrôle d'accès — c'est au routeur de dire qui il laisse entrer.
    supprimer_evolution(
        session,
        TicketEvolution,
        evol_id,
        champ_parent="ticket_id",
        parent_id=ticket_id,
    )
    return None


def _parole_pour_le_groupe(ticket: Ticket, body: TicketEvolutionCreate) -> str:
    """Ce que la Suite dit — son texte, ou le changement d'état qu'elle porte.

    Le rappel de l'historique et le lien s'y ajoutent dans `message_suite`.
    """
    if body.contenu:
        return body.contenu
    if body.type == "etat":
        return (
            f"Ticket #{ticket.numero} — {ticket.titre} : statut → "
            f"{STATUT_LABELS.get(body.nouveau_statut or '', body.nouveau_statut or '')}"
        )
    return ""


@router.post("/{ticket_id}/evolutions", response_model=TicketEvolutionRead, status_code=201)
def add_evolution(
    ticket_id: int,
    body: TicketEvolutionCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    #  ⚠️ `get_current_user` et non `require_cs_or_admin` : le droit dépend du
    #  TICKET, qu'une dépendance FastAPI ne connaît pas encore. Il est vérifié
    #  deux lignes plus bas, et refuser ici serait refuser à l'auteur.
    user: Utilisateur = Depends(get_current_user),
):
    ticket = ou_404(session, Ticket, ticket_id, "Ticket")
    #  🔴 Commenter et faire avancer le suivi : l'auteur, le « saisi pour »,
    #  l'admin — et le conseil syndical, qui suit les dossiers (18/08/2026).
    #  Avant, l'AUTEUR de la demande ne pouvait pas commenter sa propre demande.
    if not peut_commenter(ticket, user):
        raise HTTPException(403, "Accès refusé")
    refuser_si_absorbee(ticket)  # son fil vit dans la principale (#1704)
    #  La liste vit dans `utils/evolutions` : créer, corriger et effacer
    #  posent la même question, et elle était écrite quatre fois (#779).
    if body.type not in TYPES_SAISIS:
        raise HTTPException(422, "Type invalide (commentaire ou etat)")
    if body.type == "etat" and not body.nouveau_statut:
        raise HTTPException(422, "nouveau_statut requis pour un changement d'état")
    if body.type == "etat":
        refuser_etat(ticket, body.nouveau_statut, est_cs=est_moderateur(user))

    ancien_statut = etat_de_la_suite(ticket) if body.type == "etat" else None
    evol = TicketEvolution(
        ticket_id=ticket_id,
        type=body.type,
        contenu=body.contenu,
        ancien_statut=ancien_statut,
        nouveau_statut=body.nouveau_statut if body.type == "etat" else None,
        auteur_id=user.id,
        cree_le=horloge.maintenant(),
        fichiers_urls=photos_json(body.fichiers_urls),
        perimetre_cible=(
            json.dumps(body.perimetre_cible, ensure_ascii=False) if body.perimetre_cible else None
        ),
        assiste_ia=body.assiste_ia,
    )
    session.add(evol)

    #  🔴 Le périmètre déclaré devient celui du TICKET (#497).
    #
    #  Un ticket se signale avec ce qu'on sait au moment où on le signale — donc
    #  souvent le périmètre le plus large, parce qu'on ignore d'où ça vient. Puis
    #  on cherche : « bâtiment 2 » devient « bât. 2, 3ᵉ étage, cage B ».
    #
    #  Le reporter ici plutôt que de le recalculer à la lecture rend justes, du
    #  même coup et SANS LES TOUCHER, toutes les vues qui lisent déjà
    #  `ticket.perimetre_cible` : les cartes, les listes, les e-mails, et le
    #  message WhatsApp envoyé quelques lignes plus bas. L'historique du
    #  resserrement, lui, reste sur chaque évolution.
    #
    #  ⚠️ `body.perimetre_cible` vide ou absent ne touche à RIEN : une évolution
    #  qui ne parle pas du périmètre ne l'élargit pas à la résidence entière.
    if body.perimetre_cible:
        ticket.perimetre_cible = json.dumps(body.perimetre_cible, ensure_ascii=False)
        ticket.mis_a_jour_le = horloge.maintenant()
        session.add(ticket)
    #  Mise en avant, Quand, Intervenant, Équipement, Destinataires, Accès : la
    #  correction d'une Suite les pose aussi, d'où un seul lieu (01/10/2026).
    appliquer_sections_suite(session, ticket, evol, body, user)

    if body.type == "etat":
        appliquer_statut(session, ticket, evol, body.nouveau_statut, horloge.maintenant())
    #  🔀 Une Suite qui CLÔT peut absorber des affaires liées (#1704).
    absorbees = []
    if body.fusionner and valeur(ticket.statut) in STATUTS_TICKET_CLOS and body.type == "etat":
        absorbees = fusionner(
            session,
            ticket,
            body.fusionner,
            user,
            evol,
            conciliations_par_affaire(body.conciliations),
        )

    if ticket.auteur_id != user.id and body.notifier:
        _notifier_auteur(
            session,
            background_tasks,
            ticket=ticket,
            user=user,
            body=body,
            ancien_statut=ancien_statut,
        )

    #  Une Suite AJOUTE des affaires liées, elle n'en retire aucune (#1342).
    if body.affaires_liees:
        ajouter_liens(session, ticket, body.affaires_liees, user)
    session.commit()
    session.refresh(evol)
    #  Leurs auteurs, une fois chacun — l'auteur de la principale l'est déjà.
    prevenu = ticket.auteur_id if ticket.auteur_id != user.id and body.notifier else None
    prevenir_auteurs(
        session, background_tasks, absorbees, user, courriel=body.notifier, deja={prevenu}
    )

    #  Une ACTUALITÉ diffuse sa Suite par son module (#1091) — une parole vide
    #  ne part nulle part, comme l'ancienne publication.
    if est_actualite(ticket) and est_moderateur(user):
        if body.contenu and body.contenu.strip():
            diffuser_actualite(
                session,
                ticket,
                user,
                background_tasks,
                whatsapp=bool(body.partager_whatsapp),
                syndic=bool(body.envoyer_syndic),
                cs=bool(body.envoyer_cs),
                auteur=bool(getattr(body, "envoyer_auteur", False)),
                externe=body.email_externe,
                commentaire=body.contenu,
                fichiers_urls=body.fichiers_urls,
            )
        return evol_read(evol, session)

    # ── Notifications WhatsApp / syndic / CS optionnelles ──────────────────
    #  🔴 Un ticket réservé au conseil ne part pas sur le groupe des résidents
    #  (05/09/2026) : la même règle qu'à la création, au troisième point d'envoi.
    #  Le syndic et le CS, eux, restent joignables — ce sont les destinataires
    #  légitimes d'un dossier fermé au voisinage.
    #
    #  🔴 Et le groupe est un MÉGAPHONE vers tous les résidents : réservé au
    #  conseil, comme à la création (`crud.py`). L'auteur d'une affaire ouvre une
    #  Suite sur la sienne — il ne publie pas au nom du site (#1164, 23/09/2026).
    est_cs = est_moderateur(user)
    partage_whatsapp = body.partager_whatsapp and est_cs and not reservee_au_conseil(ticket)
    if partage_whatsapp or body.envoyer_syndic or body.envoyer_cs:
        # Évolutions précédentes (hors celle qui vient d'être créée) — le même
        # historique alimente le message WhatsApp et le tableau de l'e-mail.
        evols_hist = session.exec(
            select(TicketEvolution)
            .where(
                TicketEvolution.ticket_id == ticket.id,
                TicketEvolution.id != evol.id,
            )
            .order_by(TicketEvolution.cree_le)
        ).all()

        #  `partage_whatsapp`, pas `body.partager_whatsapp` : c'est CE `if` qui
        #  décide de l'envoi, le précédent pouvant être franchi par le syndic
        #  ou le CS seuls.
        if partage_whatsapp:
            from app.utils.diffusion import config_diffusion

            from .groupe import diffuser_l_affaire

            wa_config = config_diffusion(session)
            if wa_config is not None:
                #  Le message de CETTE Suite, et le lien de la fiche pour le reste
                #  du fil — jamais le message initial (28/09/2026).
                suite = message_suite(
                    session,
                    ticket,
                    _parole_pour_le_groupe(ticket, body),
                    site_url=adresse_du_site(),
                    suite_enregistree=True,
                    fichiers_urls=body.fichiers_urls,
                )
                diffuser_l_affaire(
                    background_tasks,
                    wa_config,
                    ticket,
                    suite.titre,
                    suite.contenu,
                    urgente=suite.urgente,
                    image_url=suite.photo,
                    lien=suite.lien,
                )

        if body.envoyer_syndic or body.envoyer_cs or getattr(body, "envoyer_auteur", False):
            envoyer_email_syndic_cs(
                ticket,
                user,
                background_tasks,
                session,
                syndic=bool(body.envoyer_syndic),
                cs=bool(body.envoyer_cs),
                # `photos_internes` avant résolution : même filtre qu'à
                # l'enregistrement, pour ne pas joindre une URL que l'on vient
                # précisément de refuser de stocker.
                pieces_jointes=chemins_locaux(photos_internes(body.fichiers_urls)),
                commentaire=body.contenu,
                evolutions=evols_hist,
                auteur=bool(getattr(body, "envoyer_auteur", False)),
            )

    #  Email externe — CS/Admin uniquement, et ce commentaire le disait sans que
    #  le code le fasse : un résident écrivait, depuis l'adresse du site, à qui
    #  il voulait (#1164).
    if body.email_externe and body.email_externe.strip() and est_cs:
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

    return evol_read(evol, session)
