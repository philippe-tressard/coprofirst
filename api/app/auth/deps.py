from collections.abc import Iterable

from fastapi import Depends, HTTPException, Cookie, status
from sqlmodel import Session

from app.auth.jwt import decode_token, empreinte_secret
from app.database import get_session
from app.utils.nature_affaire import est_actualite
from app.utils.recuperer import ou_404
from app.utils.valeurs import valeur
from app.models.core import (
    Notification,
    RoleUtilisateur,
    Utilisateur,
)
from app.models.roles import ROLE_OPERATEUR


def _get_current_user(
    access_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> Utilisateur:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non authentifié")

    payload = decode_token(access_token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide")

    user_id: int = payload.get("sub")
    user = session.get(Utilisateur, int(user_id))
    if not user or not user.actif:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable ou inactif"
        )

    #  🔴 Le jeton d'accès est AUTOPORTEUR : sans cette comparaison, rien côté
    #  serveur ne peut l'invalider avant ses 120 minutes — ni un changement de
    #  mot de passe, ni une déconnexion (#1063). Le compte vient d'être chargé
    #  pour vérifier qu'il est actif : l'empreinte est donc gratuite.
    #
    #  ⚠️ Un jeton émis avant le 22/09/2026 n'en porte pas : il est refusé, et
    #  le front renouvelle en silence sur 401. Accepter l'absence rouvrirait le
    #  trou pour 120 minutes — et pour toujours, le jour où quelqu'un
    #  réintroduirait un appelant qui ne pose pas l'empreinte.
    if payload.get("pwd") != empreinte_secret(user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalidée — reconnectez-vous.",
        )
    return user


def get_current_user(user: Utilisateur = Depends(_get_current_user)) -> Utilisateur:
    return user


def utilisateur_ou_anonyme(
    access_token: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> Utilisateur | None:
    """Le compte de la session, ou `None` pour un visiteur — sans jamais refuser.

    Pour une route publique qui RATTACHE ce qu'elle reçoit au compte s'il y en a
    un (la mesure d'audience). Même chaîne que `get_current_user` — `actif`,
    empreinte du mot de passe — : un second lecteur du cookie ne suivrait pas
    ses durcissements (#1595).
    """
    if not access_token:
        return None
    try:
        return _get_current_user(access_token, session)
    except HTTPException:
        return None


#  🔴 `get_acting_user` A ÉTÉ RETIRÉE le 02/10/2026 (#1534). Elle lisait
#  l'en-tête `X-Acting-As` que le front posait pour « Agir pour… », et AUCUNE
#  route ne l'a jamais prise : l'aidant écrivait sous sa propre identité
#  pendant que l'écran disait « Vous agissez pour ». Arbitré : la délégation
#  est en LECTURE SEULE — l'aidant lit ce que lit la personne qu'il aide, par
#  `utils/delegations_actives` (#1303), sans en-tête ni commutateur.
#  L'action déléguée pourra revenir comme fonctionnalité : elle devra alors
#  dire QUELS gestes elle couvre, et être prise par leurs routes —
#  `test_autorisation.py` refuse une dépendance qu'aucune route ne prend.
#
#  `require_role`, fabrique qu'aucune route n'a jamais appelée, est partie le
#  même jour pour la même raison : une règle d'accès qui ne s'applique nulle
#  part n'est qu'une promesse.


def est_proprietaire_ou_conseil(user: Utilisateur) -> bool:
    """Copropriétaire, conseil syndical ou administration — le PRÉDICAT que
    `require_proprietaire` refuse. Le fil d'activité le demande sans lever
    (une question au règlement, 11/10/2026) : la règle s'appelle, ne se recopie pas."""
    return user.has_role(
        RoleUtilisateur.propriétaire, RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin
    )


def require_proprietaire(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not est_proprietaire_ou_conseil(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Réservé aux propriétaires"
        )
    return user


def require_cs_or_admin(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    #  Le REFUS s'appuie sur le PRÉDICAT, il ne le redérive pas : deux écritures
    #  de « qui modère » divergeraient sans que rien ne le dise — l'une
    #  répondrait oui, l'autre lèverait un 403 (#1028).
    if not est_moderateur(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Réservé au conseil syndical et à l'admin"
        )
    return user


def require_admin(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not user.has_role(RoleUtilisateur.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Réservé à l'admin")
    return user


def est_operateur(user: Utilisateur) -> bool:
    """Cet utilisateur est-il l'OPÉRATEUR de la plateforme (#1750, spec §4.7) ?

    Il supervise l'installation — santé, contrôles de fiabilité, base — et ne
    lit aucune donnée personnelle (D5) : ce qu'il lit, `test_operateur_sans_donnee_personnelle.py`
    le vérifie. Distinct de l'administrateur de copropriété, qu'il n'est pas
    forcément, et qui n'est pas forcément lui.
    """
    return user.has_role(ROLE_OPERATEUR)


def require_operateur(user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not est_operateur(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Réservé à l'opérateur de la plateforme"
        )
    return user


def peut_poser_questions_reglement(user: Utilisateur, session: Session) -> bool:
    """Ce copropriétaire, ce membre du conseil, peut-il interroger le règlement ?

    Le conseil syndical et l'administration, toujours ; les copropriétaires, si
    l'administration leur a ouvert l'usage (Admin › Assistant IA, case décochée
    par défaut). Le PRÉDICAT : l'onglet le demande pour se montrer
    (`GET /reglement/acces`), la dépendance ci-dessous pour refuser. Il ne juge
    pas le rôle de copropriétaire : la dépendance l'exige avant lui.
    """
    from app.utils.question_reglement.production import ouvert_aux_coproprietaires

    return est_moderateur(user) or ouvert_aux_coproprietaires(session)


def require_questions_reglement(
    user: Utilisateur = Depends(require_proprietaire),
    session: Session = Depends(get_session),
) -> Utilisateur:
    """Les questions au règlement de copropriété (Ma résidence › Règlement, 11/10/2026).

    Les copropriétaires — occupants ou bailleurs —, le conseil syndical et
    l'administration : la règle du carnet d'entretien (`require_proprietaire`),
    qui laisse dehors locataires, mandataires, aidants et syndic ; puis
    `peut_poser_questions_reglement`, qui ne laisse entrer les copropriétaires
    que si l'usage leur est ouvert.
    """
    if not peut_poser_questions_reglement(user, session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les questions au règlement sont réservées au conseil syndical pour le moment.",
        )
    return user


def question_reglement_visible(question, user: Utilisateur, session: Session) -> bool:
    """Ce lecteur voit-il cette question au règlement ? — l'onglet et le fil d'activité.

    Il faut d'abord passer la porte de l'onglet (`require_questions_reglement` :
    copropriétaire ou conseil, usage ouvert aux copropriétaires), puis être son
    AUTEUR, ou modérer : une question dit souvent ce qu'on envisage chez soi.
    L'administration refermant l'usage, les questions d'un copropriétaire quittent
    aussi son fil (arbitré le 11/10/2026 : « les mêmes droits de visibilité »).
    """
    return (
        est_proprietaire_ou_conseil(user)
        and peut_poser_questions_reglement(user, session)
        and (est_moderateur(user) or est_auteur(question, user))
    )


def est_moderateur(user: Utilisateur) -> bool:
    """Cet utilisateur MODÈRE-t-il — conseil syndical, ou administration ?

    C'est LA définition, et la seule. Le conseil syndical et l'administration
    voient plus, corrigent plus et font avancer ce qu'ils n'ont pas écrit : c'est
    la même notion partout — visibilité d'un document réservé, message interne
    d'un ticket, champs de commandement, catégories, flux de santé.

    POURQUOI ICI (16/08/2026, élargi le 20/09). La règle était écrite en ligne,
    une fois par champ — `destinataire_syndic if est_cs else False`, répété cinq
    fois. Elle a été ramenée ici, et c'était la bonne place ; mais sous le nom
    `peut_commander`, qui décrivait **un geste** au lieu du rôle. Un nom qui parle
    d'un usage n'est appelé que par cet usage : les vingt-cinq autres endroits ont
    continué de redériver `has_role(conseil_syndical, admin)` en ligne, sans voir
    qu'ils posaient la même question (#1028). Renommé, pas aliasé — un alias
    laisserait croire à deux notions (`standards/02` §1.6).

    C'est un PRÉDICAT, pas une dépendance FastAPI : il DIT, il ne refuse pas.
    `require_cs_or_admin` est l'autre geste — il lève un 403 — et il s'appuie sur
    celui-ci. Refuser n'est pas toujours juste : un résident a le droit de créer
    un ticket, simplement pas d'en fixer l'adressage ni l'étape.

    🔒 `api/tests/test_moderateur_source_unique.py` refuse toute redérivation en
    ligne, lit l'arbre syntaxique (les vingt-six occurrences d'origine
    s'écrivaient de quatre façons), et vérifie que ce prédicat existe encore —
    un contrôle qui ne trouve plus sa source passerait au vert sans rien mesurer.
    """
    return user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)


#  ── Qui peut ÉDITER, qui peut COMMENTER ─────────────────────────────────────
#
#  🔴 Deux droits distincts, arbitrés par l'utilisateur le 18/08/2026 :
#
#    > « Seul l'auteur peut l'éditer ou le commenter, avec l'admin (en cas de
#    >   Pb), mais aussi le CS peut commenter, pas éditer (s'il est au courant de
#    >   certaines choses et influer sur le workflow ou émettre un commentaire) »
#
#  Le conseil syndical sait des choses et doit pouvoir peser sur le suivi ;
#  réécrire le ticket d'un résident n'est pas son rôle. C'était pourtant le cas :
#  `update_ticket` acceptait tout membre du CS sur n'importe quel ticket.
#
#  ⚠️ Ces fonctions vivent ICI et nulle part ailleurs. L'audit du 26/07/2026 a
#  trouvé trois dérives installées sans que rien ne les signale, dont un doublon
#  de `require_proprietaire` écrit dans un routeur et documenté comme officiel
#  dans les specs — la spec légitimait la dérive au lieu de la signaler.
#
#  Elles sont PURES (pas de `Depends`) : l'objet n'est connu qu'après lecture en
#  base, une dépendance FastAPI ne peut donc pas trancher. C'est aussi ce qui les
#  rend vérifiables sans monter d'application.


def est_rattache_au_lot(
    user: Utilisateur, lot_id: int, *, comme: Iterable[str] | None = None
) -> bool:
    """Ce lot est-il rattaché à cet utilisateur par une association ACTIVE ?

    `comme` restreint la NATURE du lien (`TypeLien`, en valeurs) : « rattaché
    comme copropriétaire » n'est pas « rattaché ». Donner un lot à bail l'exige
    (#1535) — le locataire d'un lot n'en est pas le bailleur. Sans lui, tout lien
    actif répond oui, ce que veulent l'étage du lot et la commande d'un badge.
    Un paramètre et non une seconde fonction : deux écritures de la question
    divergeraient sur `actif`, et c'est exactement le défaut de #1028.

    🔴 La question était écrite **deux fois** avant le 19/09/2026 (#1028), et les
    deux écritures divergeaient sur le cas qui compte : `routers/lots.py` exigeait
    le lien actif, `routers/acces/resident.py::creer_commande` non. Un ancien
    occupant, dont le rattachement avait été désactivé, pouvait donc encore
    commander un badge Vigik ou une télécommande pour ce lot.

    Le refus existait à dix lignes de là, dans un autre fichier. C'est la forme
    ordinaire de ce défaut : **un accès donné à trop de monde ne fait aucun
    bruit** — personne ne se plaint de pouvoir faire quelque chose, et on ne
    l'apprend que le jour où quelqu'un s'en sert.

    ⚠️ `actif` n'est pas un détail de mise en œuvre : c'est **la** règle. Un
    `UserLot` désactivé est l'historique d'un rattachement, pas un rattachement.
    `api/tests/test_appartenance_lot_source_unique.py` refuse qu'une décision
    d'accès relise `UserLot` pour son propre compte, **et** que cette fonction-ci
    cesse de regarder `actif` — une source unique relâchée ne protège plus rien,
    elle garantit seulement que tout le monde se trompe au même endroit.

    C'est un PRÉDICAT, comme `est_moderateur` : il dit, il ne refuse pas.
    L'appelant choisit son code d'erreur, parce que 403 et 404 ne disent pas la
    même chose de ce que le demandeur a le droit de savoir.
    """
    natures = None if comme is None else set(comme)
    return any(
        ul.lot_id == lot_id and ul.actif and (natures is None or valeur(ul.type_lien) in natures)
        for ul in user.user_lots
    )


def est_auteur(objet, user: Utilisateur) -> bool:
    """L'objet est-il *celui de* cet utilisateur ?

    🔴 PUBLIQUE depuis le 29/08/2026. Elle s'appelait `_est_concerne` et n'était
    lue que par les deux fonctions ci-dessous — pendant que QUATORZE sites
    réécrivaient `objet.auteur_id != user.id` à la main, avec CINQ définitions
    différentes de « ou quelqu'un de plus haut ». Une règle d'accès privée n'est
    pas centralisée : elle est seulement inaccessible.

    ⚠️ « Saisi pour » compte comme auteur, et c'est la raison d'être du champ :
    un membre du CS qui dépose un ticket **au nom d'un résident** ne le dépossède
    pas de sa demande. Sans cela, le résident concerné serait le seul à ne pas
    pouvoir corriger ce qui parle de lui.
    """
    uid = user.id
    #  ⚠️ Sans identifiant, on ne compare rien : `None == None` rendrait VRAI sur
    #  tout objet dont l'auteur est nul, et ouvrirait l'édition à qui n'a pas
    #  d'identité. Un utilisateur authentifié en a toujours un — c'est donc une
    #  garde défensive, et son jumeau `#lib/droits.ts` la portait déjà. Les deux
    #  écritures d'une même règle doivent dire la même chose jusque dans leurs cas
    #  limites, sinon les comparer côte à côte ne prouve rien.
    if uid is None:
        return False
    return (
        getattr(objet, "auteur_id", None) == uid
        or getattr(objet, "saisi_pour_user_id", None) == uid
    )


def peut_editer(objet, user: Utilisateur) -> bool:
    """Corriger le CONTENU : titre, description, pièces, périmètre…

    L'auteur (ou le « saisi pour »), et l'admin en cas de problème. **Pas le
    conseil syndical** : il agit sur le suivi, il ne réécrit pas la demande.

    ⚠️ Une ACTUALITÉ (#1091) : c'est une information du conseil, et le conseil
    la corrige — comme il corrigeait l'ancienne publication, quel qu'en soit
    l'auteur. Son auteur aussi : l'arrivant corrige sa propre annonce de
    bienvenue (#821), sans décider pour autant qui la lit (`correction.py`).
    La règle vit ici, avec l'autre, et non dans un routeur.
    """
    if est_actualite(objet):
        return est_moderateur(user) or est_auteur(objet, user)
    return est_auteur(objet, user) or user.has_role(RoleUtilisateur.admin)


def exiger_non_externe(user: Utilisateur, geste: str) -> None:
    """Un compte EXTERNE ne contribue pas — il consulte (lève 403 sinon).

    ## Pourquoi cette fonction existe (06/09/2026)

    Cette condition était écrite **cinq fois**, mot pour mot :

    | Fichier | Geste refusé |
    |---|---|
    | `routers/idees.py` | soumettre une idée |
    | `routers/idees.py` | voter pour une idée |
    | `routers/reponses_communaute.py` | répondre |
    | `routers/sondages/participation.py` | voter à un sondage |
    | `routers/tickets/crud.py` | ouvrir un ticket |

    🔴 **Une règle d'autorisation en cinq exemplaires se durcit une fois sur
    cinq.** C'est exactement ce qui était arrivé aux destinataires d'e-mail
    (`utils/destinataires.py`, quatre copies jusqu'au 31/08) et à
    `_require_bailleur`, doublon de `require_proprietaire` posé hors du module
    central avec dix-sept endpoints dessus — que la spec documentait comme
    officiel. Ici, le jour où un sixième rôle devra être écarté, ou où la
    dérogation du conseil syndical devra tomber, il y aura **un** endroit.

    ⚠️ Le CS et l'admin gardent la main **même externes** : c'est la dérogation
    que portaient les cinq copies, et elle n'est pas anodine — un conseiller
    syndical qui n'habite plus la résidence reste conseiller.

    `geste` complète le message lu par l'utilisateur (« … ne peuvent pas
    <geste> ») : c'est la seule chose qui variait entre les cinq.
    """
    if user.has_role(RoleUtilisateur.externe) and not est_moderateur(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Les utilisateurs externes ne peuvent pas {geste}",
        )


def peut_commenter(objet, user: Utilisateur) -> bool:
    """Ajouter une entrée d'Historique, et faire avancer le workflow.

    Les mêmes, **plus le conseil syndical** — c'est lui qui suit les dossiers.
    """
    return peut_editer(objet, user) or user.has_role(RoleUtilisateur.conseil_syndical)


def lit_les_notes_internes(user: Utilisateur) -> bool:
    """Les messages `interne` d'une affaire : le conseil syndical et l'admin."""
    return est_moderateur(user)


def ma_notification(
    notif_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
) -> Notification:
    """La notification demandée, **si elle est adressée à celui qui la demande**.

    ## Pourquoi elle est ici (18/09/2026)

    « Une notification n'appartient qu'à son destinataire » s'écrivait **quatre
    fois** : deux fois dans `routers/notifications.py`, et deux fois de plus dans
    `routers/admin/communications.py` — qui doublait purement et simplement ces
    routes, sous un préfixe `/admin` qui laissait croire à autre chose.

    ⚠️ Ces deux routes-là étaient déclarées « sans consommateur front » avec pour
    raison « API d'administration exposée pour l'exploitation ». C'était faux :
    elles rendaient les notifications de l'utilisateur CONNECTÉ, exactement ce
    que `/notifications` donne déjà. Une exception dont la raison est fausse est
    pire qu'absente — elle ferme la question.

    ⚠️ Répond **404** et non 403 : un 403 confirmerait l'existence d'une
    notification qu'on n'a pas le droit de voir. C'est le choix qu'avaient déjà
    fait les quatre copies, et il se garde.
    """
    return ou_404(
        session, Notification, notif_id, "Notification", sous={"destinataire_id": user.id}
    )
