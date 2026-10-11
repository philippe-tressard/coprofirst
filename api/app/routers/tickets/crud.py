"""Tickets — cycle de vie : lister, créer, lire, modifier, supprimer.

Extrait de `tickets.py` le 08/08/2026. Voir `__init__.py` pour la règle de découpage.
"""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select
from app.utils.affaires_liees import poser_liens, supprimer_liens_de
from app.utils.intervenant import appliquer_intervenant
from app.utils.nature_affaire import (
    categorie_reservee,
    est_actualite,
    est_bug,
    perimetre_bug,
    statut_pour,
)
from app.utils.perimetres import perimetre_cible_json
from .actualite import appliquer_acces, diffuser_actualite
from app.utils.quand import exiger_description
from app.utils.suivi_actualite import normaliser_suivi, poser_etat_saisi

from app.auth.appartenance import exiger_objet_autorise
from app.auth.deps import (
    exiger_non_externe,
    get_current_user,
    est_moderateur,
    require_admin,
)
from app.database import get_session
from app.models.core import (
    Ticket,
    Utilisateur,
)
from app.schemas import TicketCreate, TicketRead
from app.utils.fichiers import chemins_locaux
from app.utils.suppression_liee import (
    flush_si_necessaire,
    supprimer_documents_de,
    supprimer_lignes_liees,
)
from app.utils.photos import parse_photos, photos_json
from app.utils.courriel_entrant import nouveau_jeton
from app.utils.visibility import reservee_au_conseil, ticket_visible

from app.utils.kanban_tickets import suivi_par_defaut
from .commun import (
    appliquer_options,
    generer_numero,
    ticket_read,
    trier_par_activite,
    pieces_du_ticket,
)
from .lecture_groupee import lecture_groupee
from .arrivee import _notifier_cs_creation, adresses_deja_servies
from .courriels import (
    _alerter_bug,
    _partager_sur_le_groupe,
    envoyer_email_externe,
    envoyer_email_syndic_cs,
)
from app.utils.categories_ticket import ticket_urgent
from app.utils.recuperer import ou_404

#  Seul sous-router à porter le préfixe : ses deux routes de collection ont un
#  chemin VIDE (`GET /tickets`, `POST /tickets`), et FastAPI refuse un chemin
#  vide sur un router sans préfixe. Les trois autres sous-modules déclarent des
#  chemins nus et reçoivent le préfixe au montage (cf. `__init__.py`).
router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketRead])
def list_tickets(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    #  🔴 UNE SEULE RÈGLE DE VISIBILITÉ, ET ELLE EST EN PYTHON (#710, 02/09/2026).
    #
    #  Ce filtre existait aussi en SQL — `auteur_id == moi OR saisi_pour == moi` —
    #  et disait donc la même chose que `ticket_visible` dans un autre langage.
    #  Tant que la règle tenait en deux colonnes, les deux écritures pouvaient
    #  rester d'accord par chance. Le périmètre y met fin : il demande l'arbre des
    #  périmètres, l'héritage de la portée globale et les lots de l'utilisateur,
    #  qu'aucun `where` ne sait exprimer sans re-dériver la règle une troisième
    #  fois.
    #
    #  Alors la liste passe par la MÊME fonction que la fiche. C'est le motif que
    #  `flux/sante.py` emploie déjà, et pour la même raison : « la liste ramenait
    #  ce que le détail refusait » est un défaut qu'on ne voit jamais depuis la
    #  liste — on ne remarque pas ce qui manque.
    #
    #  ⚠️ Coût assumé : tous les tickets sont chargés puis filtrés. À l'échelle
    #  d'une copropriété c'est quelques centaines de lignes ; le jour où ça ne
    #  l'est plus, la réponse est la pagination, jamais une seconde règle.
    tickets = session.exec(select(Ticket)).all()

    #  Le tri suit l'ACTIVITÉ, pas la date de dépôt (05/09/2026) : la règle et sa
    #  raison vivent dans `commun.py`, avec les autres décisions partagées.
    tickets = trier_par_activite(session, tickets)
    #  Ce qui se lit autour de chaque affaire, lu UNE fois pour la liste (#1838) :
    #  le compte de requêtes ne croît plus avec le nombre d'affaires. Les liens
    #  restent filtrés par ce lecteur — un lien ne révèle rien (#1342).
    groupe = lecture_groupee(session, tickets)
    return [
        ticket_read(ticket, session, user, groupe=groupe)
        for ticket in tickets
        if ticket_visible(ticket, user)
    ]


@router.post("", response_model=TicketRead, status_code=201)
def create_ticket(
    body: TicketCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    exiger_non_externe(user, "créer de tickets")

    #  Les champs « de commandement » engagent autre chose que leur auteur : à
    #  qui la demande est adressée (syndic, conseil syndical), pour qui elle est
    #  saisie, et où elle en est dans son workflow. Un résident ne les fixe pas —
    #  sinon il adresse un ticket au syndic sans passer par le CS, ou dépose un
    #  signalement déjà « Résolu », donc hors du suivi, sans que personne l'ait
    #  regardé. Ils sont donc neutralisés hors CS/admin.
    #
    #  Le contrôle est ici, côté serveur : ce que l'interface masque n'est qu'un
    #  confort (socle 03 §1). Le prédicat, lui, vit dans `auth/deps` — il
    #  s'appelait `peut_commander` jusqu'au 20/09/2026, un nom qui décrivait CE
    #  geste-ci et que les vingt-cinq autres points d'usage n'ont donc jamais
    #  reconnu comme le leur (#1028).
    est_cs = est_moderateur(user)
    #  Une actualité est publiée par le conseil (#1091) — refusée, pas neutralisée :
    #  la retomber en « panne » publierait sous une autre catégorie que celle choisie.
    if categorie_reservee(body.categorie) and not est_cs:
        raise HTTPException(403, "Cette catégorie est réservée au conseil syndical")
    #  Même règle que pour une actualité, et au même endroit (#1092).
    exiger_description(body.description, debut=body.debut)
    bug = est_bug(body.categorie)
    ticket = Ticket(
        numero=generer_numero(session),
        #  L'adresse de réponse est fixée à la CRÉATION (#703) : la poser plus
        #  tard obligerait à savoir quels tickets en ont déjà une, et un ticket
        #  sans jeton part avec un courriel sans `Reply-To` — la réponse du
        #  syndic retomberait alors dans la boîte muette d'avant.
        jeton_courriel=nouveau_jeton(),
        titre=body.titre,
        description=body.description,
        #  🔴 « Quand » se PLANIFIE par le conseil syndical, et par lui seul
        #  (arbitré le 23/09/2026) : ce qu'un résident enverrait est ignoré,
        #  comme l'intervenant — l'écran ne lui ouvre pas la section.
        debut=body.debut if est_cs else None,
        fin=body.fin if est_cs else None,
        categorie=body.categorie,
        auteur_id=user.id,
        lot_id=body.lot_id,
        batiment_id=body.batiment_id,
        perimetre_cible=perimetre_bug() if bug else perimetre_cible_json(body.perimetre_cible),
        #  Posée juste en dessous par `appliquer_options`, depuis la case
        #  « Urgent » — plus jamais déduite de la catégorie (`CategorieTicket`).
        priorite="normale",
        #  Le workflow est saisissable dès la création, mais en LISTE BLANCHE et
        #  réservé au CS : un résident qui déposerait un ticket déjà « résolu »
        #  le sortirait du suivi. Une valeur inconnue retombe sur « ouvert »
        #  plutôt que d'être refusée — le ticket doit exister même si le client
        #  envoie n'importe quoi (socle 03 §2, liste blanche ancrée).
        #  La liste blanche vit dans `statut_pour`, avec la règle de l'actualité
        #  (sans cycle, toujours `publie`) : une seule écriture des deux (#1091).
        statut=statut_pour(body.categorie, body.statut, est_cs=est_cs),
        public_cible=json.dumps(body.public_cible) if est_cs and body.public_cible else None,
        reserve_perimetre=bool(body.reserve_perimetre) and est_cs,
        destinataire_syndic=body.destinataire_syndic if est_cs and not bug else False,
        destinataire_cs=body.destinataire_cs if est_cs and not bug else False,
        saisi_pour_user_id=body.saisi_pour_user_id if est_cs else None,
        saisi_pour_nom=body.saisi_pour_nom if est_cs else None,
        saisi_pour_email=body.saisi_pour_email if est_cs else None,
        # `photos_internes` écarte toute URL qui n'a pas été produite par notre
        # endpoint d'upload : sans ce filtre, un client pourrait faire pointer une
        # pièce jointe vers un site tiers, servi ensuite à chaque lecteur.
        photos_urls=photos_json(body.photos_urls),
        fichiers_urls=photos_json(body.fichiers_urls),
        #  « Rédigé avec l'assistant IA » — le geste est réservé au CS, mais la
        #  marque se lit telle quelle : un résident ne peut pas l'obtenir, le
        #  serveur refusant l'appel qui la justifie (`routers/assistant`).
        assiste_ia=body.assiste_ia,
    )
    session.add(ticket)
    session.flush()
    #  Ses affaires liées (#1342) : l'identifiant existe depuis le `flush`.
    if body.affaires_liees:
        poser_liens(session, ticket, body.affaires_liees, user)
    #  🔴 LES OPTIONS DE PUBLICATION — une écriture, trois chemins (05/09/2026).
    #  `appliquer_options` porte la table et le contrôle de droit ; ce routeur
    #  ne réécrit ni l'une ni l'autre (`commun.OPTIONS_TICKET`).
    #  🔴 Le défaut de CATÉGORIE d'abord, `appliquer_options` peut le
    #  contredire ensuite : poser le défaut APRÈS effacerait un décochage.
    #  (Le droit est dans `OPTIONS_RESERVEES_AU_CS`, pas réécrit ici.)
    ticket.suivi_kanban = suivi_par_defaut(body.categorie)
    if not bug:  # un bogue n'a pas de mise en avant (#1191)
        appliquer_options(ticket, body, est_cs=est_cs)
    normaliser_suivi(ticket)  # la case ne vaut que pour une actualité
    poser_etat_saisi(ticket, body.suivi_actualite, est_cs=est_cs)  # Résolu dès l'ouverture
    appliquer_intervenant(ticket, body, session, est_cs=est_cs)

    #  🔴 UNE ACTUALITÉ DIFFUSE COMME UNE ACTUALITÉ (#1091, lot 4) : son module
    #  porte le message restreint, le gabarit `publication_syndic`, l'affiche, et
    #  la réserve « Conseil syndical seul » (#1096). `est_cs` est redondant avec
    #  le refus plus haut — il est écrit ICI pour que la garde se lise au point
    #  d'envoi (`test_canaux_notification`).
    if est_actualite(ticket) and est_cs:
        appliquer_acces(ticket, session)
        session.commit()
        session.refresh(ticket)
        diffuser_actualite(
            session,
            ticket,
            user,
            background_tasks,
            whatsapp=bool(body.partager_whatsapp),
            syndic=ticket.destinataire_syndic,
            cs=ticket.destinataire_cs,
            auteur=bool(getattr(body, "envoyer_auteur", False)),
            externe=body.email_externe,
            affiche=bool(body.annonce_hall),
        )
        return ticket_read(ticket, session, user)

    #  ⚠️ APRÈS `appliquer_options` : c'est elle qui pose `priorite`.
    #
    #  🔴 `deja_servies` — consigne du 08/09/2026 : *« éviter le doublon quand la
    #  notification comprend les destinataires qui sont inclus dans la diffusion
    #  du ticket »*. Trois courriels peuvent partir pour ce même ticket, et un
    #  conseiller du bâtiment visé était dans deux listes.
    #
    #  ⚠️ L'ORDRE compte : les adresses sont calculées AVANT la notification,
    #  parce que c'est elle qui cède. Elle ne porte que le titre et l'auteur,
    #  quand les deux autres portent les pièces jointes, l'adresse de réponse ou
    #  le nom du bogue. Le destinataire reçoit donc PLUS, pas moins — c'est ce
    #  qui rend la déduplication acceptable (`courriels.adresses_deja_servies`).
    #  Une actualité, c'est le conseil qui la publie : lui annoncer « nouvelle
    #  affaire » lui renverrait sa propre information (#1091, « jamais deux fois »).
    #  Un BOGUE ne prévient que le gestionnaire du site (#1191) : `_alerter_bug`.
    if not est_actualite(ticket) and not bug:
        _notifier_cs_creation(
            session,
            ticket,
            urgence=ticket_urgent(ticket),
            auteur=user,
            background_tasks=background_tasks,
            deja_servies=adresses_deja_servies(session, ticket, categorie=body.categorie),
            #  Le conseil diffuse par SA Diffusion : sans la case « Conseil syndical »,
            #  aucun courriel ne part vers lui. Un résident n'a pas cette case.
            par_courriel=not est_cs,
        )

    if bug:
        _alerter_bug(session, ticket, user, background_tasks)

    #  🔴 CE QUI EST RÉSERVÉ AU CONSEIL NE PART PAS SUR LE GROUPE (05/09/2026),
    #  demandé à l'écran : *« si "Visibilité du ticket au seul conseil syndical"
    #  est sélectionné, la diffusion WhatsApp est interdite »*.
    #
    #  L'actualité tenait déjà la règle (`not pub.brouillon` à chaque canal) ; le
    #  ticket, non — un ticket fermé au voisinage pouvait partir en entier sur le
    #  groupe des résidents. La garde est ici plutôt que dans l'écran : une case
    #  masquée ne protège rien, le champ peut être posté directement.
    #  Réservée : cochée, ou fermée par sa catégorie sans choix du conseil (#1436).
    if body.partager_whatsapp and est_cs and not reservee_au_conseil(ticket) and not bug:
        _partager_sur_le_groupe(session, ticket, background_tasks)

    if (
        ticket.destinataire_syndic
        or ticket.destinataire_cs
        or getattr(body, "envoyer_auteur", False)
    ):
        envoyer_email_syndic_cs(
            ticket,
            user,
            background_tasks,
            session,
            syndic=ticket.destinataire_syndic,
            cs=ticket.destinataire_cs,
            # Mêmes règles de résolution que partout ailleurs : URL interne →
            # chemin local, hors de /app/uploads on ignore.
            pieces_jointes=chemins_locaux(pieces_du_ticket(ticket)),
            auteur=bool(getattr(body, "envoyer_auteur", False)),
        )

    session.commit()
    session.refresh(ticket)

    # Email externe si adresse fournie (CS/Admin uniquement)
    email_ext = (body.email_externe or "").strip()
    if email_ext and est_cs and not bug:
        envoyer_email_externe(
            ticket,
            user,
            email_ext,
            background_tasks,
            session,
            is_commentaire=False,
            fichiers_urls=parse_photos(ticket.fichiers_urls),
        )

    return ticket_read(ticket, session, user)


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = exiger_objet_autorise(session, Ticket, ticket_id, "Ticket", user, ticket_visible)
    return ticket_read(ticket, session, user)


@router.delete("/{ticket_id}", status_code=204)
def delete_ticket(
    ticket_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    ticket = ou_404(session, Ticket, ticket_id, "Ticket")
    #  Tout ce qui n'existe que par ce ticket part avec lui. Les DOCUMENTS
    #  manquaient (#546) : un document joint n'a plus d'objet sans son porteur.
    #  Le `flush()` ordonne les DELETE — pourquoi : `utils/suppression_liee.py`.
    enfants = supprimer_lignes_liees(session, ticket.evolutions, ticket.messages)
    supprimer_liens_de(session, ticket_id)  # ses affaires liées (#1342)
    docs = supprimer_documents_de(session, "ticket_id", ticket_id)
    flush_si_necessaire(session, enfants, docs)
    session.delete(ticket)
    session.commit()
