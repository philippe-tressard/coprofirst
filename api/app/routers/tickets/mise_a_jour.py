"""La CORRECTION d'un ticket — `PATCH /tickets/{id}`.

## Pourquoi ce module (#833, 08/09/2026)

Extrait de `crud.py` quand le garde-fou de modularité a refusé de le laisser
grossir. Le refus désignait juste : `crud.py` portait les cinq verbes d'un
ticket, et celui-ci pesait à lui seul **238 lignes** — plus que les quatre
autres réunis.

⚠️ Il rejoint `correction.py`, qui porte déjà `_appliquer_contenu` et
`_appliquer_relations` : la correction avait donc **sa moitié basse** dans un
module et **son point d'entrée** dans un autre. C'est ce que l'extraction répare,
et pas seulement une taille de fichier.

⚠️ Le préfixe reste `/tickets`, et `tickets/__init__.py` monte ce routeur
**après** `crud` : les chemins littéraux avant le motif `/{ticket_id}`, comme le
dit la docstring du paquet.
"""

from app.utils.affaires_liees import poser_liens
from app.utils.fusion_affaires import (
    conciliations_par_affaire,
    fusionner,
    prevenir_auteurs,
    refuser_si_absorbee,
)
from app.utils import horloge

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session

from app.auth.deps import est_moderateur, get_current_user, peut_commenter, peut_editer
from app.database import get_session
from app.models.core import (
    STATUTS_TICKET_CLOS,
    RoleUtilisateur,
    StatutTicket,
    Ticket,
    TicketEvolution,
    Utilisateur,
)
from app.schemas import TicketRead, TicketUpdate
from app.models.tickets import STATUTS_TICKET_SANS_CYCLE
from app.utils.suivi_actualite import normaliser_suivi, poser_etat_saisi
from app.utils.intervenant import appliquer_intervenant
from app.utils.prochaine_visite import apres_cloture
from app.utils.synthese_affaire.file import inscrire_si_eligible
from app.utils.nature_affaire import (
    ACTUALITE,
    categorie_reservee,
    change_de_nature,
    est_actualite,
    est_bug,
    perimetre_bug,
    statut_pour,
)
from app.utils.valeurs import valeur
from app.utils.fichiers import chemins_locaux
from app.utils.liens import lien_ticket
from app.utils.recuperer import ou_404
from app.utils.visibility import reservee_au_conseil

from .actualite import appliquer_acces, diffuser_actualite

from .commun import (
    appliquer_options,
    STATUT_LABELS,
    ticket_read,
    pieces_du_ticket,
)
from .correction import _appliquer_contenu, _appliquer_quand, _appliquer_relations, _envoye
from .courriels import (
    _partager_sur_le_groupe,
    envoyer_email_syndic_cs,
)
from app.utils.corrections import (
    PREFIXE_CORRECTION,
    PREFIXE_CORRECTION_AUTEUR,
    SEPARATEUR_CORRECTION,
)
from app.utils.cloche import sonner

#  Seul sous-router à porter le préfixe : ses deux routes de collection ont un
#  chemin VIDE (`GET /tickets`, `POST /tickets`), et FastAPI refuse un chemin
#  vide sur un router sans préfixe. Les trois autres sous-modules déclarent des
#  chemins nus et reçoivent le préfixe au montage (cf. `__init__.py`).

router = APIRouter(prefix="/tickets", tags=["tickets"])


#: Les champs qui décrivent la DEMANDE, par opposition à ceux qui décrivent son
#: suivi (`statut`, `priorite`) ou sa diffusion. Un membre du CS peut agir sur
#: les seconds, jamais sur les premiers.
#:
#: ⚠️ Liste BLANCHE inversée : on énumère ce qui est du contenu, et tout champ
#: ajouté demain y échappe par défaut. C'est le sens le moins risqué — un
#: nouveau champ mal classé sera au pire trop ouvert au CS, jamais fermé à
#: l'auteur. Le contraire bloquerait l'auteur en silence.
CHAMPS_DE_CONTENU = (
    "titre",
    "description",
    "categorie",
    "perimetre_cible",
    "photos_urls",
    "fichiers_urls",
    "batiment_id",
    "public_cible",
    "reserve_perimetre",
)


#  🔴 `debut` et `fin` ne sont plus du CONTENU depuis le 23/09/2026 : la
#  section « Quand » se planifie par le conseil syndical seul
#  (`correction._appliquer_quand`), comme le suivi — et non par l'auteur.


def _touche_au_contenu(body) -> bool:
    """Cette modification porte-t-elle sur la demande elle-même ?"""
    return any(getattr(body, champ, None) is not None for champ in CHAMPS_DE_CONTENU)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: int,
    body: TicketUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = ou_404(session, Ticket, ticket_id, "Ticket")

    #  🔴 DEUX droits, pas un — arbitré le 18/08/2026 : le conseil syndical
    #  commente et fait avancer le suivi, mais **ne réécrit pas** la demande d'un
    #  résident. Il le pouvait : `is_cs_admin` ouvrait TOUT le contenu de
    #  n'importe quel ticket à n'importe quel membre du CS.
    #
    #  ⚠️ Et l'auteur ne pouvait pas toujours : « saisi pour » ne comptait pas.
    #  Un ticket déposé par le CS AU NOM d'un résident échappait donc à ce
    #  résident — le seul à ne pas pouvoir corriger ce qui parle de lui.
    #
    #  Les deux règles vivent dans `auth/deps.py`, jamais ici : l'audit du
    #  26/07/2026 a trouvé trois dérives nées d'un contrôle écrit dans un routeur.
    is_cs_admin = est_moderateur(user)
    if not peut_commenter(ticket, user):
        raise HTTPException(403, "Accès refusé")
    #  Le CS franchit la porte pour le statut et la priorité (plus bas), pas pour
    #  le contenu.
    if not peut_editer(ticket, user) and _touche_au_contenu(body):
        raise HTTPException(
            403,
            "Le conseil syndical peut commenter et faire avancer le suivi, "
            "mais seul l'auteur (ou un administrateur) modifie le contenu",
        )
    #  Les affaires liées (#1342) : le conseil seul les corrige depuis le
    #  30/09/2026 — la règle vit dans `utils/affaires_liees`, qui refuse.
    if "affaires_liees" in body.model_fields_set:
        poser_liens(session, ticket, body.affaires_liees, user)

    ancien_statut = ticket.statut
    suivi_avant = ticket.suivi_actualite  # l'état du suivi d'une actualité, s'il change
    #  L'etat des CANAUX avant modification. La Diffusion est rouverte a
    #  l'edition depuis le 18/08/2026 (arbitrage utilisateur) : le conseil
    #  syndical doit pouvoir decider d'envoyer au syndic un ticket deja saisi.
    #
    #  Seule la TRANSITION decoche -> coche envoie. Un canal deja coche ne
    #  repart pas a chaque enregistrement : c'est ce qui distingue « je decide
    #  d'envoyer » de « je corrige une faute de frappe », et ce qui evite
    #  l'incident du triple envoi WhatsApp du 14/08/2026.
    #
    #  Sans ce bloc, rouvrir la section serait pire que la fermer : la case
    #  cocherait un drapeau que rien ne consommerait, et l'ecran promettrait un
    #  envoi qui n'aurait pas lieu — le defaut de `non_relancable` (#435).
    syndic_avant = ticket.destinataire_syndic
    cs_avant = ticket.destinataire_cs
    #  Une actualité qui QUITTE la réserve du conseil fait partir ce qui était
    #  coché et retenu (règle de l'ancienne publication : « brouillon publié »).
    reservee_avant = reservee_au_conseil(ticket)
    #  🔴 L'ACTUALITÉ (#1091) : en faire une, ou cesser d'en être une, est un
    #  geste du conseil — c'est la promotion, qui ne convertit plus rien. Et elle
    #  n'a pas d'état à corriger : `publie` ne se pose, ni ne se quitte, que par
    #  la catégorie (`nature_affaire.statut_pour`).
    nature_changee = change_de_nature(ticket, body.categorie)
    if nature_changee and not is_cs_admin:
        raise HTTPException(
            403, "Seul le conseil syndical fait d'une affaire une actualité, ou l'inverse"
        )
    #  Passer VERS une catégorie réservée (Étude & travaux, Entretien) est aussi
    #  un geste du conseil ; GARDER celle qu'on a ne l'est pas — l'auteur d'une
    #  ancienne étude corrige son texte sans rien demander.
    vers_reservee = body.categorie is not None and valeur(body.categorie) != valeur(
        ticket.categorie
    )
    if vers_reservee and categorie_reservee(body.categorie) and not is_cs_admin:
        raise HTTPException(403, "Cette catégorie est réservée au conseil syndical")
    #  🔴 Jugé sur la catégorie FINALE, jamais sur celle d'avant : l'écran qui
    #  fait d'une actualité une Étude & travaux envoie « Ouvert » avec la
    #  nouvelle catégorie, et ce PATCH légitime répondait 422 (29/09/2026,
    #  TK-A00017). À l'inverse, un état demandé avec « Actualité » est refusé.
    categorie_finale = body.categorie if body.categorie is not None else ticket.categorie
    if body.statut is not None and (
        body.statut in STATUTS_TICKET_SANS_CYCLE or valeur(categorie_finale) == ACTUALITE
    ):
        raise HTTPException(
            422, "Une actualité n'a pas d'état de suivi : c'est sa catégorie qui en décide"
        )

    # Statut et priorité : CS/admin uniquement
    if body.statut is not None or body.priorite is not None:
        if not is_cs_admin:
            raise HTTPException(
                403, "Seul le CS ou un administrateur peut modifier le statut ou la priorité"
            )
        if body.statut is not None:
            refuser_si_absorbee(ticket)  # son suivi vit dans la principale (#1704)
            ticket.statut = body.statut
            if body.statut in STATUTS_TICKET_CLOS:
                ticket.ferme_le = horloge.maintenant()
        if body.priorite is not None:
            ticket.priorite = body.priorite

    #  🔴 CONFIDENTIEL — CS/admin UNIQUEMENT, et posé ici avec le statut et la
    #  priorité parce que c'est la même nature de décision : elle appartient au
    #  conseil, pas à l'auteur (#710).
    #
    #  ⚠️ Il ne passe PAS par `_appliquer_contenu` : un auteur peut corriger son
    #  texte, il ne décide pas qui a le droit de le lire. Le mettre là aurait
    #  ouvert le drapeau à quiconque peut éditer le ticket.
    #  🔴 LES OPTIONS DE PUBLICATION — CS/admin uniquement, et posées ici avec
    #  le statut et la priorité parce que c'est la même nature de décision :
    #  elle appartient au conseil, pas à l'auteur (#710).
    #
    #  ⚠️ Elles ne passent PAS par `_appliquer_contenu` : un auteur peut corriger
    #  son texte, il ne décide pas qui a le droit de le lire.
    #
    #  ⚠️ Le REFUS reste explicite pour un non-CS qui demande `confidentiel` :
    #  `appliquer_options` se contente d'ignorer, ce qui conviendrait mal ici —
    #  ce chemin répondait 403 depuis #710, et un silence ferait croire au client
    #  que sa correction a été prise.
    if body.confidentiel is not None and not is_cs_admin:
        raise HTTPException(
            403, "Seul le CS ou un administrateur peut rendre un ticket confidentiel"
        )
    appliquer_options(ticket, body, est_cs=is_cs_admin)

    #  Champs du CONTENU — le droit a déjà été vérifié plus haut
    #  (`peut_editer`) : auteur, « saisi pour », ou admin.
    changes: list[str] = []
    content_fields = _touche_au_contenu(body)
    if content_fields:
        #  Une contrainte de PLUS, et elle ne vise pas l'admin : celui qui a
        #  déposé la demande ne la réécrit que tant qu'elle est ouverte. Une fois
        #  le suivi engagé, corriger le texte ferait mentir ce que le CS a lu
        #  avant d'agir. L'admin, lui, intervient précisément quand il y a un
        #  problème — c'est sa raison d'être dans cette règle.
        if not user.has_role(RoleUtilisateur.admin) and ticket.statut not in (
            StatutTicket.ouvert,
            StatutTicket.publie,
        ):
            raise HTTPException(403, "Modification impossible : le ticket n'est plus ouvert")
        changes += _appliquer_contenu(body, ticket, est_cs=is_cs_admin)
        if est_bug(ticket.categorie):  # le périmètre d'un bogue est verrouillé (#1191)
            ticket.perimetre_cible = perimetre_bug()
        if nature_changee:
            #  L'état que le conseil a demandé dans la même correction est
            #  retenu (la liste blanche est celle de `statut_pour`) : il avait
            #  été posé plus haut, et ce bloc l'écrasait en « Ouvert ».
            demande = valeur(body.statut) if body.statut is not None else None
            ticket.statut = statut_pour(ticket.categorie, demande, est_cs=is_cs_admin)
            #  Le public visé d'une actualité ne suit pas l'affaire qu'elle
            #  devient (#1343) : il déciderait qui la lit sans que personne l'ait
            #  choisi pour elle. Envoyé dans la même correction, il est retenu.
            if not est_actualite(ticket) and "public_cible" not in body.model_fields_set:
                ticket.public_cible = None
    #  Le suivi d'une actualité ne suit pas l'affaire suivie qu'elle devient ;
    #  le sien se corrige comme l'état d'une affaire (10/10/2026).
    normaliser_suivi(ticket)
    poser_etat_saisi(ticket, body.suivi_actualite, est_cs=is_cs_admin)
    #  APRÈS le contenu : la récurrence dépend de la catégorie FINALE.
    changes += appliquer_intervenant(ticket, body, session, est_cs=is_cs_admin)
    #  La prochaine visite d'un contrat (#1092) — APRÈS l'intervenant (#1445) :
    #  une même correction qui pose le contrat et « Résolu » avance CE contrat.
    #  Elle était appelée avec le statut, donc sur le contrat d'avant.
    if body.statut is not None:
        apres_cloture(ticket, session)
    #  Close : la synthèse d'une affaire du carnet entre en file (#1643).
    inscrire_si_eligible(session, ticket, statut_avant=ancien_statut)
    #  « Quand » : planifié par le conseil seul — ignoré pour un autre, comme
    #  l'intervenant (l'écran ne lui ouvre pas la section).
    if is_cs_admin:
        changes += _appliquer_quand(body, ticket)

    # Champs relationnels/destinataires : CS/admin uniquement
    #  ⚠️ Un champ absent de cette liste n'entre jamais dans `_appliquer_relations` :
    #  le bouton « ne plus relancer » (retiré le 10/10/2026, #1797) répondait 200
    #  sans rien écrire (#435). Un 200 qui n'écrit
    #  rien est pire qu'un 422 : il fabrique la confiance qu'il devrait retirer.
    #  La liste teste la PRÉSENCE et non la non-nullité — sinon effacer un champ
    #  (le remettre à `null`) n'y entrerait pas davantage.
    extra_fields = any(
        _envoye(body, c)
        for c in (
            "lot_id",
            "batiment_id",
            "destinataire_syndic",
            "destinataire_cs",
            "partager_whatsapp",
            "saisi_pour_user_id",
            "saisi_pour_nom",
            "saisi_pour_email",
            "archive_manuel",
        )
    )
    if extra_fields:
        if not is_cs_admin:
            raise HTTPException(403, "Seul le CS ou un administrateur peut modifier ces champs")
        changes += _appliquer_relations(body, ticket, session)

    ticket.mis_a_jour_le = horloge.maintenant()

    #  🔴 UNE ÉDITION ÉCRIT UNE CORRECTION, PAS UNE TRANSITION (cadre #430, #431)
    #
    #  Ce bloc écrivait une `TicketEvolution(type="etat")` dès que le statut
    #  changeait — la même forme, au même endroit du fil, que le changement d'état
    #  volontaire du conseil syndical. Tant que l'édition ne rouvrait pas le
    #  workflow, cela ne se voyait pas. Depuis que le cadre l'y rouvre — *l'édition
    #  corrige, et l'état s'y corrige comme les autres champs* —, corriger un état
    #  mal saisi apparaîtrait dans l'Historique comme une ÉTAPE DU WORKFLOW : le
    #  ticket aurait « été » en cours, alors qu'il n'y est jamais passé.
    #
    #  La correction reste **visible** — rien ne devient muet — mais elle se
    #  présente pour ce qu'elle est : une ligne de correction parmi les autres,
    #  sans `ancien_statut`/`nouveau_statut`, donc sans jalon de suivi.
    #
    #  La transition, elle, n'a pas disparu : elle passe par
    #  `POST /tickets/{id}/evolutions` (`evolutions.py`), qui l'inscrit avec sa
    #  date, son auteur, son courriel à l'auteur du ticket et ses canaux. C'est
    #  désormais le seul chemin qui la produit — les boutons « Changer le statut »
    #  de la fiche l'empruntent depuis #431.
    if body.statut is not None and body.statut != ancien_statut:
        changes.insert(
            0,
            f"État : {STATUT_LABELS.get(ancien_statut or '', 'Aucun')} → "
            f"{STATUT_LABELS.get(body.statut, body.statut)}",
        )

    #  🔴 CORRIGER UN CHAMP N'ÉCRIT PLUS RIEN DANS L'HISTORIQUE (18/08/2026).
    #
    #  Signalé à l'écran : « j'ai fait une édition d'un ticket pour corriger sa
    #  catégorie et ça m'a créé un historique ! c'est à supprimer ». L'Historique
    #  raconte la VIE du dossier — ce que le conseil syndical a fait, où en est la
    #  demande. Une faute de frappe rattrapée n'en fait pas partie : elle ajoute une
    #  ligne qui n'apprend rien, et pousse vers le bas celles qui apprennent quelque
    #  chose.
    #
    #  ⚠️ Le changement d'ÉTAT, lui, continue de laisser une trace : ce n'est pas une
    #  correction de saisie mais un mouvement de workflow, et savoir quand un ticket
    #  est passé « En cours » est précisément ce que le fil sert à conserver. Il
    #  reste inscrit comme une CORRECTION et non comme une transition — sans
    #  `ancien_statut`/`nouveau_statut`, donc sans jalon de suivi — pour la raison
    #  détaillée juste au-dessus : le ticket n'a pas « été » dans un état qu'on
    #  corrige. C'est ce que `test_correction_pas_transition.py` verrouille.
    #
    #  ⚠️ Ce que ce lot NE fait pas : les publications et le calendrier gardent leur
    #  auto-log de correction. R5 — un écran à la fois, constaté avant d'être
    #  généralisé. La divergence est donc VOULUE et temporaire ; elle est nommée
    #  dans le test, qui vérifie chaque entité séparément.
    etat_a_change = body.statut is not None and body.statut != ancien_statut
    #  Le suivi d'une actualité laisse la même trace de correction que l'état.
    if ticket.suivi_actualite != suivi_avant:
        changes.insert(
            0,
            f"Suivi : {STATUT_LABELS.get(suivi_avant or '', 'Aucun')} → "
            f"{STATUT_LABELS.get(ticket.suivi_actualite or '', 'Aucun')}",
        )
        etat_a_change = True
    if changes and etat_a_change:
        #  Le préfixe et son assemblage viennent de `app/utils/corrections.py` :
        #  la chaîne était écrite quatre fois, et le fil avait besoin d'un
        #  cinquième pour la RECONNAÎTRE (01/09/2026).
        session.add(
            TicketEvolution(
                ticket_id=ticket.id,
                type="commentaire",
                contenu=(PREFIXE_CORRECTION if is_cs_admin else PREFIXE_CORRECTION_AUTEUR)
                + SEPARATEUR_CORRECTION.join(changes),
                auteur_id=user.id,
                cree_le=horloge.maintenant(),
            )
        )

    #  🔀 Une correction qui CLÔT peut absorber des affaires liées (#1704) —
    #  sans courriel, comme toute correction : la cloche seule.
    absorbees = []
    if body.fusionner and etat_a_change and valeur(ticket.statut) in STATUTS_TICKET_CLOS:
        absorbees = fusionner(
            session,
            ticket,
            body.fusionner,
            user,
            None,
            conciliations_par_affaire(body.conciliations),
        )

    # Notification auteur (in-app) — sauf si c'est l'auteur lui-même qui modifie
    #  Une actualité se corrige entre membres du conseil : l'auteur n'en est pas
    #  « prévenu » comme d'une affaire qui avance.
    if user.id != ticket.auteur_id and not est_actualite(ticket):
        sonner(
            session,
            destinataire_id=ticket.auteur_id,
            type="ticket_update",
            titre=f"Ticket #{ticket.numero} mis à jour",
            corps=" ; ".join(changes)
            if changes
            else f"Nouveau statut : {STATUT_LABELS.get(valeur(ticket.statut), valeur(ticket.statut))}",
            lien=lien_ticket(ticket.id),
        )
    if est_actualite(ticket):
        appliquer_acces(ticket, session)
    session.add(ticket)

    #  ⚠️ PLUS DE COURRIEL « changement de statut » ICI (#431).
    #
    #  Ce chemin envoyait `ticket_statut_change` à l'auteur du ticket dès que le
    #  statut bougeait par un `PATCH`. Or un `PATCH` est désormais une
    #  **correction** : la Diffusion est absente de l'édition, motif `geste` —
    #  *une correction n'est pas une nouvelle*, et rejouer un canal à chaque
    #  faute de frappe rattrapée est exactement l'incident du triple envoi
    #  WhatsApp du 14/08/2026.
    #
    #  L'auteur n'est pas laissé dans le noir : la notification in-app ci-dessus
    #  part toujours, et elle porte le détail des corrections. Le courriel, lui,
    #  reste attaché à la vraie transition, dans `evolutions.py::_notifier_auteur`.
    session.commit()
    session.refresh(ticket)
    prevenir_auteurs(
        session, background_tasks, absorbees, user, courriel=False, deja={ticket.auteur_id}
    )

    #  Une ACTUALITÉ diffuse par son module (#1091) : les canaux cochés à
    #  l'instant, plus ceux que la réserve du conseil retenait si elle vient
    #  d'être levée.
    if est_actualite(ticket) and is_cs_admin:
        sortie = reservee_avant and not reservee_au_conseil(ticket)
        diffuser_actualite(
            session,
            ticket,
            user,
            background_tasks,
            whatsapp=bool(body.partager_whatsapp),
            syndic=ticket.destinataire_syndic and (not syndic_avant or sortie),
            cs=ticket.destinataire_cs and (not cs_avant or sortie),
            auteur=bool(getattr(body, "envoyer_auteur", False)),
            affiche=bool(body.annonce_hall),
        )
        return ticket_read(ticket, session, user)

    #  L'ENVOI, et seulement sur la transition decoche -> coche (voir plus haut).
    #  Apres le commit : un courriel qui part sur une transaction annulee annonce
    #  une decision qui n'a pas ete prise.
    #  Le partage WhatsApp est un ACTE, pas un champ : `Ticket` n'a pas cette
    #  colonne. Cocher la case demande un envoi, ici et maintenant — il n'y a rien
    #  à comparer à un état antérieur, et rien ne repart tout seul au prochain
    #  enregistrement puisque la case revient décochée.
    #  Le contrôle de rôle est DANS la condition, et non chez l'appelant :
    #  `test_canaux_notification` lit l'arbre syntaxique et refuse toute condition
    #  portant `partager_whatsapp` sans rôle. Une garde qu'un contrôle ne peut pas
    #  voir ne le protège pas de la refonte qui déplacera l'appel.
    #  Même règle qu'à la création : réservé au conseil ⇒ pas de groupe WhatsApp.
    if body.partager_whatsapp and is_cs_admin and not reservee_au_conseil(ticket):
        _partager_sur_le_groupe(session, ticket, background_tasks)

    #  La copie à l'auteur est un ACTE, comme WhatsApp : la case revient décochée,
    #  rien à comparer à un état antérieur (03/10/2026).
    copie_auteur = bool(getattr(body, "envoyer_auteur", False))
    if (
        (ticket.destinataire_syndic and not syndic_avant)
        or (ticket.destinataire_cs and not cs_avant)
        or copie_auteur
    ):
        envoyer_email_syndic_cs(
            ticket,
            user,
            background_tasks,
            session,
            syndic=ticket.destinataire_syndic and not syndic_avant,
            cs=ticket.destinataire_cs and not cs_avant,
            pieces_jointes=chemins_locaux(pieces_du_ticket(ticket)),
            auteur=copie_auteur,
        )

    return ticket_read(ticket, session, user)
