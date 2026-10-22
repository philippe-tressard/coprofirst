"""Visibilité par entité — publication, sondage, événement, ticket.

⚠️ Fragment de `app/utils/visibility/` : le découpage en trois modules et sa couture
sont expliqués UNE fois, dans l'en-tête de `__init__.py` (#1564).
"""

from __future__ import annotations

import json
from datetime import datetime

from app.utils.nature_affaire import est_actualite
from app.models.core import (
    Evenement,
    Idee,
    PetiteAnnonce,
    RoleUtilisateur,
    Sondage,
    Ticket,
    TypeEvenement,
    Utilisateur,
)
from app.utils.perimetres import a_portee_globale, arbre, parse_perimetres

from .socle import (
    _codes_json_pour_acces,
    _parse_json_list,
    cible_visible,
    perimetre_visible,
    public_cible_visible,
    reserve_au_conseil,
)
from app.auth.deps import est_moderateur

from .defauts_affaire import (
    _DEFAUTS_FERMES,
    CONCERNE,
    destinataires_par_defaut,
    lus_dans_toute_la_residence,
)
#  ⚠️ `public_cible_visible` en direct : une seule règle l'appelle sans
#  `cible_visible`, et c'est voulu — « tous les copropriétaires » d'une affaire
#  au défaut ne consulte PAS le périmètre (standard du 30/09/2026). Toutes les
#  autres passent par `cible_visible`, qui pose les deux axes.

# ── Règles actualité ────────────────────────────────────────────────────────


def actualite_visible(ticket: Ticket, user: Utilisateur) -> bool:
    """L'utilisateur peut-il voir cette actualité ?

    🔴 Une affaire de catégorie « Actualité » depuis le 23/09/2026 (#1091) :
    c'était `publication_visible(pub, user)`, renommée avec l'entité. Le
    « confidentiel » de la publication s'appelle `reserve_perimetre` (l'Accès),
    et `ticket_visible` l'appelle pour toute actualité — auteur et conseil
    sortis avant elle, comme avant.

    Périmètre puis public cible : c'est `cible_visible` qui les pose, et elle est
    la SEULE écriture de cette règle depuis le 06/09/2026 (#782). Ce corps
    portait les mêmes onze lignes que `sondage_accessible`, au paramètre
    d'ouverture près.

    #  `ouvert_a_la_copropriete` : une actualité ciblée sur un autre bâtiment
    #  reste lisible (#339). La vie d'une copropriété se passe rarement dans un
    #  seul bâtiment — un chantier, une coupure, une réunion concernent souvent
    #  sans être « chez soi ». Le résident qui préfère l'ancien fonctionnement
    #  coche « n'afficher que mes bâtiments » dans son profil.
    #
    #  ⚠️ Ce n'est QUE l'axe bâtiment. Le public cible n'est pas touché, et c'est
    #  lui qui protège : une agence, un bailleur non résident ou un mandataire
    #  qui ne voyaient pas cette publication ne la voient pas davantage.
    #
    #  `confidentiel` (#347) ne fait que **refermer** cette ouverture-là, et rien
    #  d'autre : il n'existe pas de seconde règle d'accès pour les actualités
    #  confidentielles — c'est le paramètre à sa valeur par défaut, c'est-à-dire
    #  le comportement d'avant #339. Une règle à part aurait dû être maintenue en
    #  parallèle de celle-ci, et c'est ainsi que deux règles divergent.
    """
    return cible_visible(
        ticket.perimetre_cible,
        ticket.public_cible,
        user,
        ouvert_a_la_copropriete=not ticket.reserve_perimetre,
    )


# ── Règles sondage ────────────────────────────────────────────────────────────


def sondage_clos(sondage: Sondage, maintenant: datetime) -> bool:
    """Ce sondage est-il terminé — de force, ou parce que l'échéance est passée ?

    Les DEUX voies comptent, et c'est tout l'intérêt d'une écriture unique : la
    même expression était recopiée quatre fois côté API (fiche du sondage, vote,
    modification, fil d'activité) et une cinquième côté front (`estCloture`).
    Le compteur du tableau de bord, lui, ne regardait que `cloture_forcee` — il
    annonçait donc « actifs » des sondages que tous les autres écrans donnaient
    pour clos, jusqu'à ce que quelqu'un pense à cliquer sur « clôturer ». Deux
    définitions coexistaient, et c'est la plus permissive qui alimentait la
    pastille (#399).

    `maintenant` est passé en paramètre, jamais lu ici : le fil calcule son
    instant une fois par requête (`ContexteFlux.now`) et douze rubriques qui
    appelleraient `utcnow()` chacune ne dateraient plus la même clôture.
    """
    return bool(
        sondage.cloture_forcee
        or (sondage.cloture_le is not None and sondage.cloture_le < maintenant)
    )


def resultats_sondage_visibles(resultats_publics: bool, cloture: bool) -> bool:
    """Les décomptes de ce sondage peuvent-ils quitter le serveur ?

    `resultats_publics` signifie « visibles **avant** la clôture » : une fois le
    sondage clos, ils le sont dans tous les cas.

    ⚠️ Cette règle décide de ce que l'API **envoie**, pas de ce que le front
    affiche. Jusqu'au 17/08/2026 elle n'existait pas : `GET /sondages/{id}`
    renvoyait `nb_votes` et les réponses en texte libre sans aucune condition, et
    seul le front tentait de les masquer. Décocher la case ne cachait donc rien —
    les résultats restaient lisibles dans la réponse réseau par tout destinataire
    avant son vote, alors que la case existe précisément pour qu'un vote en cours
    n'influence pas les suivants (#397).

    L'audience, elle, n'est PAS gérée ici : c'est celle du sondage, décidée par
    `sondage_accessible` (périmètre + public cible). Cette fonction ne répond
    qu'à la question du calendrier — avant ou après la clôture.

    Aucune exception pour l'auteur ni pour le conseil syndical : ils sont donc
    aveugles à la participation jusqu'à la clôture quand la case est décochée.
    C'est ce que l'option promet littéralement, et le défaut le plus sûr pour
    l'intégrité du vote — à rouvrir si l'usage montre que c'est trop strict.
    """
    return bool(resultats_publics or cloture)


def sondage_accessible(sondage: Sondage, user: Utilisateur) -> bool:
    """L'utilisateur peut-il voir ce sondage et y voter ?

    - CS / Admin : toujours True.
    - `perimetre_cible` (JSON de codes) : vide = aucune restriction géographique.
    - `public_cible` (JSON de codes) : vide = tous les profils.

    C'est **exactement** la règle des publications, à une exception près et elle
    est délibérée : `ouvert_a_la_copropriete` reste à sa valeur par défaut, donc
    faux. Une actualité ciblée sur un bâtiment reste lisible de toute la
    copropriété (#339) parce qu'elle informe ; un sondage, lui, fait **voter** —
    l'ouvrir changerait qui pèse sur le résultat.

    Depuis le 06/09/2026 (#782), « exactement la même règle » n'est plus une
    phrase de docstring : c'est le même appel.
    """
    return cible_visible(sondage.perimetre_cible, sondage.public_cible, user)


# ── Règles événement ──────────────────────────────────────────────────────────


def evenement_visible(ev: Evenement, user: Utilisateur) -> bool:
    """
    Retourne True si l'utilisateur peut voir cet événement.

    - AG invisible pour les locataires, mandataires, syndics et aidants.
    - maintenance_recurrente invisible pour tous (usage interne uniquement).
    - Périmètre géographique (champ CSV ev.perimetre).
    """
    if est_moderateur(user):
        # CS/Admin voient tout sauf maintenance_recurrente (usage interne)
        if ev.type == TypeEvenement.maintenance_recurrente:
            return False
        return True

    if ev.type == TypeEvenement.maintenance_recurrente:
        return False

    #  🛡️ Réservé au conseil syndical (#939, 13/09/2026) : le CS et l'admin sont
    #  déjà sortis plus haut, donc quiconque arrive ici ne doit pas le voir.
    #
    #  🔴 Placé AVANT la règle d'AG et celle de périmètre, et c'est voulu : un
    #  événement réservé l'est pour tout le monde, quels que soient son type et
    #  son périmètre. Le mettre après aurait fait dépendre la réserve d'une autre
    #  règle — et un jour, l'une des deux aurait bougé sans l'autre.
    if ev.reserve_cs:
        return False

    if ev.type == TypeEvenement.ag:
        if not user.has_role(RoleUtilisateur.propriétaire):
            return False

    #  `parse_perimetres` porte le repli : un événement sans périmètre désigne le
    #  nœud racine à portée globale, désigné par les données et non par une chaîne
    #  « résidence » écrite ici — une autre copropriété peut l'avoir renommé.
    return perimetre_visible(parse_perimetres(ev.perimetre), user)


# ── Règle AG (helper rapide) ──────────────────────────────────────────────────


def can_see_ag(user: Utilisateur) -> bool:
    """True si l'utilisateur peut voir les événements AG."""
    return user.has_role(
        RoleUtilisateur.propriétaire,
        RoleUtilisateur.conseil_syndical,
        RoleUtilisateur.admin,
    )


# ── Règles ticket ─────────────────────────────────────────────────────────────
def ticket_visible(ticket: Ticket, user: Utilisateur) -> bool:
    """Qui peut LIRE ce ticket — jamais qui peut y écrire.

    ## L'ouverture du 02/09/2026 (#710)

    > « Les copropriétaires et locataires peuvent désormais voir les tickets de
    >   leur périmètre. »

    Un résident voit les tickets dont le périmètre recoupe **ses bâtiments**, et
    ceux à portée globale. La règle n'est pas réécrite ici : `perimetre_visible`
    la porte, `mes_batiments` porte « quels bâtiments sont les siens ». Ce corps
    ne fait que les **composer** — aucune liste de périmètres, aucun
    `batiment_id`, aucun rôle en dur.

    🔴 ET CE N'EST PAS LA RÈGLE DES ACTUALITÉS, malgré l'apparence. La première
    écriture de cette fonction passait `ouvert_a_la_copropriete=not confidentiel`,
    par analogie avec l'actualité (`actualite_visible`) — deux tests l'ont refusée dans la
    minute, et ils avaient raison deux fois :

    - ce paramètre ne restreint pas au périmètre, il **l'ignore** : un résident
      sans préférence de restriction voyait alors TOUS les tickets, y compris
      ceux d'un bâtiment où il n'a rien. L'ouverture demandée était « son
      périmètre », pas « tout » ;
    - et il rendait le drapeau `confidentiel` **inopérant** sur le cas le plus
      courant, un ticket à portée « résidence » : la portée globale est décidée
      avant lui, donc il ne refermait rien du tout.

    Une actualité s'adresse à la copropriété et son ciblage n'est qu'un accent
    (#339) ; un ticket est une **affaire**, et son périmètre dit qui elle
    regarde. Le même mot, deux règles — les composer pareil était l'erreur.

    ## Ce que cette fonction n'ouvre PAS

    Elle décide de la **lecture**. Commenter, faire avancer le suivi, corriger la
    demande passent par `peut_commenter` / `peut_editer` (`auth/deps.py`), qui ne
    l'appellent pas : élargir la lecture ne donne donc aucun droit d'écriture.
    C'est ce qui rend le « lecture seule » du ticket structurel plutôt que promis.

    ## `confidentiel` — le filet

    Un litige de voisinage, un impayé, un dégât des eaux qui nomme quelqu'un :
    ces tickets existent, et l'ouverture les rendrait lisibles de tout un
    bâtiment. Le drapeau les ramène à ce qu'ils étaient hier — **l'auteur, la
    personne pour qui le ticket a été saisi, le CS**, et personne d'autre. Ces
    trois cas sont traités AVANT, et le drapeau ne les touche pas.

    ⚠️ Il refuse donc SANS consulter le périmètre, et c'est délibéré : un ticket
    confidentiel à portée « résidence » doit se refermer comme les autres. Écrit
    dans l'autre ordre, le drapeau n'aurait mordu que sur les tickets déjà les
    plus restreints — ceux dont on n'a pas besoin de lui.
    """
    if est_moderateur(user):
        return True
    if ticket.auteur_id == user.id:
        return True
    if ticket.saisi_pour_user_id is not None and ticket.saisi_pour_user_id == user.id:
        return True

    #  🔴 UNE ACTUALITÉ SUIT LA RÈGLE DE L'ACTUALITÉ (#1091, 23/09/2026).
    #
    #  Elle est devenue une catégorie d'affaire, mais elle s'adresse toujours à
    #  la copropriété : périmètre + public visé, par `actualite_visible`, et
    #  par la MÊME fonction (`cible_visible`). Placée AVANT la règle des
    #  locataires, qui vise les affaires suivies — un locataire lisait les
    #  actualités, il les lit encore. `confidentiel` est l'ancien « réservé au
    #  conseil » (auteur et CS, déjà sortis plus haut) ; `reserve_perimetre`,
    #  l'Accès « Réservé au périmètre » (#1096).
    if est_actualite(ticket):
        if ticket.confidentiel:
            return False
        return actualite_visible(ticket, user)

    if ticket.confidentiel:
        return False

    #  🔴 LE CONSEIL A CHOISI À QUI ELLE S'ADRESSE (#1343, 26/09/2026).
    #
    #  Demandé à l'écran : *« il n'est toujours pas possible de choisir son
    #  destinataire ! c'est urgent »*. Une affaire porte désormais ses
    #  Destinataires, présélectionnés selon la règle de sa nature et modifiables
    #  par le conseil à tout moment — création, correction, Suite.
    #
    #  Vides, rien ne change : la règle par défaut ci-dessous décide. Choisis,
    #  ils décident À SA PLACE, par la MÊME fonction que l'actualité
    #  (`cible_visible`) — mais sans l'ouverture à la copropriété : le
    #  périmètre d'une affaire dit qui elle regarde.
    #
    #  ⚠️ Une liste illisible retombe sur la règle par défaut, la plus fermée
    #  des deux : une donnée abîmée ne peut que restreindre (#789).
    if _parse_json_list(ticket.public_cible, []):
        return cible_visible(ticket.perimetre_cible, ticket.public_cible, user)
    #  Sans choix, la catégorie en décide (#1343, #1436) — et TOUTES en
    #  décident depuis le 29/09/2026. La règle historique « les copropriétaires
    #  du périmètre, jamais les locataires ni les mandataires » (#710, #1311,
    #  #1428) valait sans choix du conseil ; Étude & travaux, sa dernière
    #  catégorie, est passée au conseil seul, et la règle est partie avec elle
    #  plutôt que de rester écrite sans servir. Ce qu'elle protégeait tient par
    #  la table : aucun défaut n'ouvre aux locataires, hors « Tous » (Espaces
    #  verts) et la Panne de leur bâtiment, arbitrés tous deux.
    defaut = destinataires_par_defaut(ticket)
    if defaut == [CONCERNE]:
        #  L'auteur, le « saisi pour » et le conseil sont sortis plus haut.
        return False
    #  🔴 « TOUS LES COPROPRIÉTAIRES » (standard du 30/09/2026) : le copropriétaire
    #  que le défaut vise lit l'affaire dans toute la résidence — ce que le carnet
    #  d'entretien lui montre, les affaires et le kanban le lui montrent aussi.
    #  Le périmètre n'est pas consulté : il ne peut donc rien ouvrir de plus.
    partout = lus_dans_toute_la_residence(ticket)
    if partout and public_cible_visible(json.dumps(partout, ensure_ascii=False), user):
        return True
    return cible_visible(ticket.perimetre_cible, json.dumps(defaut, ensure_ascii=False), user)


def reservee_au_conseil(ticket: Ticket) -> bool:
    """Rien ne sort de cette affaire : ni groupe WhatsApp, ni courriel, ni affiche.

    Deux écritures pour un même geste : `confidentiel` (l'ancien « réservé au
    conseil » des actualités migrées) et Destinataires = « Conseil syndical »
    SEUL, qui en tient lieu depuis l'arbitrage #1096 (23/09/2026).
    """
    if ticket.confidentiel or reserve_au_conseil(ticket.public_cible):
        return True
    #  🔴 …OU SANS CHOIX, SA CATÉGORIE LA FERME (#1436) : une nuisance au défaut
    #  « Résident concerné » ne part pas plus sur le groupe ni au hall qu'une
    #  affaire cochée. Un choix du conseil prime, comme dans `ticket_visible`.
    if _parse_json_list(ticket.public_cible, []):
        return False
    return destinataires_par_defaut(ticket) in _DEFAUTS_FERMES


def hors_du_hall(ticket: Ticket) -> bool:
    """Cette affaire peut-elle paraître sur une affiche de hall ? Non, si ceci est vrai.

    Un hall est lu par TOUT LE MONDE, sans contrôle d'accès : une affaire
    réservée au conseil, ou réservée à son périmètre (🔒), n'y va pas. La
    génération de l'affiche ET la liste des éléments reprenables l'appellent —
    deux écritures divergeraient sur le cas limite, et l'une des deux
    publierait au mur ce que l'autre refuse.

    « Réservée à son périmètre » est la règle du groupe WhatsApp,
    `contenu_hors_du_groupe` : une affaire suivie d'un bâtiment comprise —
    arbitré par l'utilisateur le 22/10/2026, après le code d'ascenseur parti
    sur le groupe. Le hall et le groupe sont deux lieux lus par tous.
    """
    return reservee_au_conseil(ticket) or contenu_hors_du_groupe(ticket)


def contenu_hors_du_groupe(ticket: Ticket) -> bool:
    """Le groupe de la résidence ne reçoit-il que le titre et le lien de cette affaire ?

    Le groupe est lu par TOUS les résidents : le contenu n'y part que si tous
    peuvent le lire. Création, Suite et aperçu le demandent ici, par
    `tickets/groupe.diffuser_l_affaire` — trois points d'envoi, dont un seul
    transmettait la réserve, ont laissé partir un code d'accès (22/10/2026).

    - 🔒 « Réservé au périmètre » coché (une actualité) ;
    - une affaire SUIVIE dont le périmètre n'est pas global : elle n'est lue que
      dans son périmètre (`ticket_visible`), et l'écran le montre coché et
      verrouillé (`TICKET_CONFIDENTIEL_ACQUIS`). Une actualité, elle, s'adresse à
      la copropriété et son périmètre n'est qu'un accent (#339) ;
    - un périmètre illisible : une donnée abîmée ne peut que restreindre (#789).

    Une copropriété SANS périmètres configurés n'en restreint aucun (`arbre`,
    état valide) : aucune affaire n'y vise un bâtiment, rien n'est amputé.

    Le public visé (`public_cible`) est jugé à côté, par le canal
    (`message_sans_contenu`), à qui l'appelant le transmet.
    """
    if ticket.reserve_perimetre:
        return True
    if est_actualite(ticket):
        return False
    codes = _codes_json_pour_acces(ticket.perimetre_cible)
    if codes is None:
        return True
    return bool(codes) and bool(arbre()) and not a_portee_globale(codes)


# ── Règles Communauté : petite annonce et idée ────────────────────────────────
#
#  🔴 CES DEUX FONCTIONS N'ONT PAS DE CORPS, ET C'EST LE SUJET.
#
#  Le public cible leur a été ouvert le 06/09/2026 (#782, migration 0176), avec
#  la même sémantique que le sondage : il filtre la VISIBILITÉ, pas seulement les
#  notifications. Écrire ici « if user.has_role(admin, cs): return True » suivi
#  des deux axes aurait donné une TROISIÈME et une QUATRIÈME copie de la même
#  règle — et une règle d'accès en quatre exemplaires se durcit une fois sur
#  quatre. Ce dépôt a déjà payé ce prix (`utils/destinataires.py`, quatre copies
#  jusqu'au 31/08 ; `_require_bailleur`, doublon de `require_proprietaire` avec
#  dix-sept endpoints dessus, que la spec documentait comme officiel).
#
#  Elles existent quand même, plutôt qu'un appel direct à `cible_visible` chez
#  l'appelant, pour deux raisons : elles NOMMENT la décision (« cette annonce
#  est-elle visible ? » se lit mieux que trois arguments), et elles sont l'endroit
#  où s'écrira une divergence FUTURE, si le produit en décide une — avec son
#  motif, à un seul endroit.


def annonce_visible(annonce: PetiteAnnonce, user: Utilisateur) -> bool:
    """Cette petite annonce est-elle visible de cet utilisateur ?

    `ouvert_a_la_copropriete` reste faux : une annonce s'adresse à qui son auteur
    a choisi. L'ouverture qui vaut pour une actualité — elle informe, donc elle
    déborde son bâtiment (#339) — n'aurait ici aucun sens : on ne propose pas un
    lave-linge à des voisins qu'on a explicitement écartés.
    """
    return cible_visible(
        annonce.perimetre_cible,
        annonce.public_cible,
        user,
        auteur_id=annonce.auteur_id,
    )


def idee_visible(idee: Idee, user: Utilisateur) -> bool:
    """Cette idée est-elle visible de cet utilisateur ?

    ⚠️ Une idée ciblée est privée des voix qui la porteraient — c'est exactement
    l'objection que la déclaration d'écran opposait à cette section, et elle
    reste vraie. Elle a été tranchée : le ciblage est un choix de l'auteur, pas
    un défaut du produit. Ne pas le contourner ici en ouvrant discrètement
    l'audience ; ce serait décider à sa place, sans que rien ne le dise.
    """
    return cible_visible(
        idee.perimetre_cible,
        idee.public_cible,
        user,
        auteur_id=idee.auteur_id,
    )
