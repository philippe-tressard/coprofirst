"""Admin — Cycle de vie d'un utilisateur existant : rôles, modification, suppression, bannissement.

Extrait de `admin.py` (2057 lignes) le 06/08/2026, sans modification de logique.
Voir `__init__.py` pour la règle de découpage.

L'effacement d'un compte n'est plus écrit ici depuis le 04/10/2026 (#1580) : la
route l'appelle dans `utils/suppression_compte`, que la purge des comptes inactifs
appelle aussi — une seule façon de supprimer un compte.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.auth.deps import require_admin, require_cs_or_admin
from app.database import get_session
from app.utils.journal_securite import journaliser_securite
from app.models.core import (
    LocationBail,
    RoleUtilisateur,
    StatutUtilisateur,
    UserLot,
    Utilisateur,
)
from app.schemas import UserRead
from app.utils.comptes import DESACTIVATION, condition_hors_comptes_techniques, marquer_decide
from app.utils.porteurs_acces import ids_detenteurs
from app.utils.etiquettes_compte import etiquettes
from app.models.copropriete import Lot
from app.auth.operateur import designe_par_l_exploitant
from app.models.roles import ROLE_OPERATEUR
from app.utils.valeurs import valeur
from app.utils.suppression_compte import supprimer_compte
from app.utils.types_acces import TELECOMMANDE, VIGIK
from app.utils.roles_libelles import libelle_role
from app.utils import horloge
from typing import Optional
from app.utils.communaute import notification_de_ban
from app.utils.recuperer import ou_404
from app.utils.etages import ETAGE_HORS_BORNES, etage_hors_bornes
from app.schemas_communs import NomMajuscules
from app.utils.cloche import sonner_systeme
from app.utils.verification_adresse import demander_changement_adresse

router = APIRouter()


# ── Gestion des utilisateurs (rôles) ────────────────────────────────────────────


@router.get("/utilisateurs")
def list_utilisateurs(
    session: Session = Depends(get_session),
    appelant: Utilisateur = Depends(require_cs_or_admin),
):
    """Liste les utilisateurs avec leurs rôles cumulés (CS et admin) + tags de liaison.

    Le conseil syndical ne reçoit pas les comptes techniques (#1985) : cette liste
    alimente ses choix de personne, où ils n'ont rien à faire. L'administration
    les garde, pour les gérer.
    """
    requete = select(Utilisateur).order_by(Utilisateur.cree_le.desc())
    if not appelant.has_role(RoleUtilisateur.admin):
        requete = requete.where(condition_hors_comptes_techniques())
    users = session.exec(requete).all()

    # Batch : user_ids ayant au moins 1 lot lié
    loti_ids = set(
        session.exec(
            select(UserLot.user_id).where(UserLot.actif == True).distinct()  # noqa: E712
        ).all()
    )
    #  « A un badge » : UNE définition, `utils/porteurs_acces` (#1194). Celle
    #  d'ici comptait aussi les badges perdus et ignorait le conjoint.
    tc_ids = ids_detenteurs(session, TELECOMMANDE)
    vigik_ids = ids_detenteurs(session, VIGIK)
    # Batch : user_ids liés via un bail (bailleur ou locataire)
    bail_bailleur_ids = set(session.exec(select(LocationBail.bailleur_id).distinct()).all())
    bail_locataire_ids = set(
        session.exec(
            select(LocationBail.locataire_id).where(LocationBail.locataire_id != None).distinct()  # noqa: E711
        ).all()
    )
    lie_ids = bail_bailleur_ids | bail_locataire_ids
    #  Les TYPES de lot de chaque compte : ce qui rend une étiquette « sans objet »
    #  (`utils/etiquettes_compte`) — pas de parking, pas de télécommande à porter.
    types_lots: dict[int, set[str]] = {}
    for user_id, type_lot in session.exec(
        select(UserLot.user_id, Lot.type)
        .join(Lot, Lot.id == UserLot.lot_id)
        .where(UserLot.actif == True)  # noqa: E712
    ).all():
        types_lots.setdefault(user_id, set()).add(valeur(type_lot))

    result = []
    for u in users:
        d = UserRead.from_orm_with_roles(u).model_dump()
        d["has_lots"] = u.id in loti_ids
        d["has_tc"] = u.id in tc_ids
        d["has_vigik"] = u.id in vigik_ids
        d["has_bail"] = u.id in lie_ids
        d["etiquettes"] = etiquettes(
            a_lot=d["has_lots"],
            a_tc=d["has_tc"],
            a_vigik=d["has_vigik"],
            a_bail=d["has_bail"],
            types_lots=types_lots.get(u.id, set()),
            statut=valeur(u.statut),
            types_tc=TELECOMMANDE.types_lot,
            types_vigik=VIGIK.types_lot,
        )
        result.append(d)
    return result


class RoleAction(BaseModel):
    role: str  # résident | conseil_syndical | admin | operateur


def _role_demande(nom: str) -> RoleUtilisateur | str:
    """Le rôle que nomme le corps : un rôle de la copropriété, ou l'opérateur.

    L'opérateur n'est pas dans `RoleUtilisateur` (`models/roles.ROLE_OPERATEUR`) :
    il se nomme par sa chaîne, et `ajouter_role` / `retirer_role` l'écrivent dans
    `roles_json` seulement — jamais en rôle principal.
    """
    if nom == ROLE_OPERATEUR:
        return ROLE_OPERATEUR
    try:
        return RoleUtilisateur(nom)
    except ValueError:
        raise HTTPException(400, f"Rôle invalide : {nom}")


#: Les rôles qui ne restent jamais VACANTS : sans administrateur, plus personne
#: ne gère les comptes ; sans opérateur, plus personne ne supervise l'installation.
#: Chacun se retire — à soi-même compris —, sauf à son dernier titulaire actif.
ROLES_JAMAIS_VACANTS = (RoleUtilisateur.admin.value, ROLE_OPERATEUR)


def _exiger_geste_operateur(
    cible: Utilisateur, role: RoleUtilisateur | str, *, retrait: bool
) -> None:
    """Les règles du rôle Opérateur, accordé ou retiré depuis Admin › Utilisateurs.

    Il s'**accorde** à un administrateur : c'est parmi eux qu'on choisit qui
    supervise l'installation. Il se **garde** ensuite sans lui : un opérateur
    qui se retire — ou à qui l'on retire — le rôle Admin ouvre encore ses écrans
    de supervision, et eux seuls (arbitrage du 16/10/2026, #2029, spec §4.7).
    Ce refus-là, « retirer Admin à un opérateur », a existé de #1750 à v2.167.0 :
    il interdisait de quitter l'administration sans quitter la supervision.

    Tout administrateur l'accorde ou le retire, à lui-même compris (arbitrage du
    15/10/2026) : la règle « seul un opérateur l'accorde » (#1750) est levée. Le
    mode démo, lui, refuse toute écriture sur `/admin/utilisateurs/` — son
    administrateur publié ne se donne donc pas ce rôle (#1985).

    Sur une instance COMMUNE, ni l'un ni l'autre : l'opérateur y est désigné par
    l'exploitant (`auth/operateur`, 31/10/2026). L'administrateur d'une
    copropriété hébergée se serait sinon fait opérateur de toute l'instance.
    """
    if role == ROLE_OPERATEUR and designe_par_l_exploitant():
        raise HTTPException(
            409,
            "L'opérateur de cette instance est désigné par son exploitant, "
            "dans la déclaration des copropriétés.",
        )
    if role == ROLE_OPERATEUR and not retrait and not cible.has_role(RoleUtilisateur.admin):
        raise HTTPException(
            400, "Le rôle Opérateur s'accorde à un administrateur : ajoutez d'abord le rôle Admin."
        )


def _exiger_un_autre_titulaire(
    session: Session, cible: Utilisateur, role: RoleUtilisateur | str
) -> None:
    """Refuse de retirer un rôle de `ROLES_JAMAIS_VACANTS` à son dernier titulaire actif.

    Lu en Python, par `has_role` : un `roles_json` vide retombe sur la colonne
    `role`, qu'un filtre SQL sur la chaîne ne verrait pas.
    """
    nom = valeur(role)
    if nom not in ROLES_JAMAIS_VACANTS:
        return
    autres = session.exec(
        select(Utilisateur).where(
            Utilisateur.actif == True,  # noqa: E712
            Utilisateur.id != cible.id,
        )
    ).all()
    if not any(u.has_role(nom) for u in autres):
        raise HTTPException(
            400,
            f"Il ne resterait plus aucun compte {libelle_role(role)} : "
            "accordez d'abord ce rôle à un autre compte.",
        )


@router.post("/utilisateurs/{user_id}/ajouter-role", response_model=UserRead)
def ajouter_role(
    user_id: int,
    body: RoleAction,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Ajouter un rôle à un utilisateur sans retirer les existants."""
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
    if not user.actif:
        raise HTTPException(400, "Impossible de modifier un compte inactif.")
    role = _role_demande(body.role)
    _exiger_geste_operateur(user, role, retrait=False)
    user.ajouter_role(role)
    #  🔴 En WARNING : c'est le geste qui donne des droits. La `Notification` part
    #  au concerné et ne dit pas QUI a agi — le journal, lui, nomme l'admin.
    journaliser_securite("role_ajoute", acteur_id=admin.id, cible_id=user.id, detail=valeur(role))
    sonner_systeme(
        session,
        "compte",
        destinataire_id=user.id,
        type="system",
        titre="Rôle ajouté",
        corps=f"Le rôle {libelle_role(role)} vous a été attribué.",
        lien="/profil",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    from app.schemas import UserRead

    return UserRead.from_orm_with_roles(user)


@router.post("/utilisateurs/{user_id}/retirer-role", response_model=UserRead)
def retirer_role(
    user_id: int,
    body: RoleAction,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Retirer un rôle d'un utilisateur (le rôle 'résident' ne peut pas être retiré).

    À soi-même compris : Admin et Opérateur se quittent, sauf par leur dernier
    titulaire actif (`_exiger_un_autre_titulaire`).
    """
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
    if body.role == RoleUtilisateur.résident.value:
        raise HTTPException(
            400, "Le rôle 'Résident' est le rôle de base, il ne peut pas être retiré."
        )
    role = _role_demande(body.role)
    _exiger_geste_operateur(user, role, retrait=True)
    _exiger_un_autre_titulaire(session, user, role)
    user.retirer_role(role)
    journaliser_securite("role_retire", acteur_id=admin.id, cible_id=user.id, detail=valeur(role))
    sonner_systeme(
        session,
        "compte",
        destinataire_id=user.id,
        type="system",
        titre="Rôle retiré",
        corps=f"Le rôle {libelle_role(role)} vous a été retiré.",
        lien="/profil",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    from app.schemas import UserRead

    return UserRead.from_orm_with_roles(user)


class AdminUserUpdate(BaseModel):
    nom: NomMajuscules = None
    prenom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    societe: Optional[str] = None
    statut: Optional[StatutUtilisateur] = None
    batiment_id: Optional[int] = None
    actif: Optional[bool] = None
    #  Corriger une saisie de l'inscription (#1155) : où la personne habite, et,
    #  pour un locataire, le nom de son bailleur — ce qui sert à la rapprocher
    #  de son lot. Mêmes règles qu'à l'inscription : bornes, capitales.
    etage: Optional[int] = None
    nom_proprietaire: NomMajuscules = None
    #  Le mot de passe de l'ADMINISTRATEUR — exigé seulement si l'adresse change
    #  (#1549). Sans lui, une session d'administration volée détournait n'importe
    #  quel compte : son adresse, puis « mot de passe oublié » sur celle-ci.
    mot_de_passe_actuel: Optional[str] = None


#: Ce que le formulaire porte sans que ce soit un champ de la fiche à recopier :
#: l'adresse passe par sa demande de changement, le mot de passe ne s'écrit pas.
_HORS_FICHE = {"email", "mot_de_passe_actuel"}


@router.patch("/utilisateurs/{user_id}", response_model=UserRead)
def modifier_utilisateur(
    user_id: int,
    body: AdminUserUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Modifier les informations d'un utilisateur (admin).

    🔴 L'adresse ne s'écrit pas ici (#1549) : comme sur le profil, c'est une
    DEMANDE — mot de passe de l'administrateur, lien de confirmation envoyé à la
    nouvelle adresse, avis à l'ancienne, qui reste celle du compte jusqu'au clic.
    """
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
    if body.etage is not None and etage_hors_bornes(body.etage):
        raise HTTPException(400, ETAGE_HORS_BORNES)
    bascule_actif = body.actif is not None and body.actif != user.actif
    if body.email is not None:
        demander_changement_adresse(
            session,
            cible=user,
            acteur=admin,
            nouvelle_adresse=body.email,
            mot_de_passe=body.mot_de_passe_actuel,
            background_tasks=background_tasks,
        )
    for field, val in body.model_dump(exclude_unset=True, exclude=_HORS_FICHE).items():
        setattr(user, field, val)
    #  Basculer `actif` — dans un sens comme dans l'autre — EST une décision de
    #  l'administration sur ce compte. Sans cette ligne, désactiver un résident
    #  qui déménage le renvoyait dans la file des comptes à valider, où plus rien
    #  ne le distinguait d'une inscription du jour (#399).
    if body.actif is not None:
        marquer_decide(user, None if body.actif else DESACTIVATION)
    session.add(user)
    session.commit()
    #  Seulement si l'état CHANGE (#1548) : renvoyer le même état n'ouvre ni ne
    #  ferme rien. Le changement d'adresse, lui, est journalisé par `demander_changement_adresse`.
    if bascule_actif:
        journaliser_securite(
            "compte_reactive" if body.actif else "compte_desactive",
            acteur_id=admin.id,
            cible_id=user.id,
        )
    session.refresh(user)
    return UserRead.from_orm_with_roles(user)


@router.delete("/utilisateurs/{user_id}", status_code=204)
def supprimer_utilisateur(
    user_id: int,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Supprimer définitivement un utilisateur (admin). Impossible de se supprimer soi-même.
    Nettoie toutes les interactions liées : lots, tokens, accès, notifications, votes, baux, etc."""
    if admin.id == user_id:
        raise HTTPException(400, "Vous ne pouvez pas supprimer votre propre compte.")
    ou_404(session, Utilisateur, user_id, "Utilisateur")

    #  Le corps de l'effacement vit dans `utils/suppression_compte` depuis #1580 :
    #  la purge des comptes inactifs l'appelle aussi, et une seconde écriture
    #  divergerait au premier modèle ajouté. Ce qu'il fait des objets de la
    #  personne — règles métier d'abord, puis `purger` — est écrit là-bas.
    supprimer_compte(session, user_id)
    session.commit()
    #  Après l'effacement, plus rien en base ne dit qui l'a fait : cette ligne
    #  est la seule trace qui reste (#1548).
    journaliser_securite("compte_supprime", acteur_id=admin.id, cible_id=user_id)


#  🔴 `POST /utilisateurs/{user_id}/changer-role` A ÉTÉ SUPPRIMÉ le 06/09/2026
#  (#801). Il « remplaçait tous les rôles par un seul », et sa docstring le
#  donnait pour de la « compatibilité ascendante » — avec rien : aucun écran,
#  aucun script, aucun test ne l'appelait, et son client TypeScript figurait au
#  relevé des méthodes sans appelant. Le produit a des rôles MULTIPLES depuis
#  longtemps ; `ajouter-role` et `retirer-role`, juste au-dessus, sont les deux
#  gestes réels.
#
#  ⚠️ Il portait la TROISIÈME copie de la table des libellés de rôles, et un
#  passe-droit que les deux autres n'ont pas : il écrivait `user.role` et
#  `user.roles_json` directement au lieu de passer par `ajouter_role()` /
#  `retirer_role()` du modèle. Un endpoint sans appelant n'est pas seulement du
#  code mort — c'est du code qui n'est plus corrigé quand la règle bouge.


class BanCommunauteBody(BaseModel):
    interdit: bool


@router.patch("/utilisateurs/{user_id}/ban-communaute", response_model=UserRead)
def ban_communaute(
    user_id: int,
    body: BanCommunauteBody,
    session: Session = Depends(get_session),
    admin: Utilisateur = Depends(require_admin),
):
    """Bannir ou débannir un utilisateur de la rubrique Communauté.

    1er ban → probatoire 1 mois. 2e ban → définitif.
    """
    user = ou_404(session, Utilisateur, user_id, "Utilisateur")
    if body.interdit and user.has_role(RoleUtilisateur.admin):
        raise HTTPException(400, "Un administrateur ne peut pas être exclu de la communauté")

    if body.interdit:
        from datetime import timedelta

        user.communaute_ban_count = (user.communaute_ban_count or 0) + 1
        if user.communaute_ban_count >= 2:
            # 2e infraction → ban permanent
            user.communaute_interdit = True
            user.communaute_ban_jusqu_au = None
            notif_titre, notif_corps = notification_de_ban(definitif=True)
        else:
            # 1re infraction → ban 1 mois (30 jours)
            user.communaute_ban_jusqu_au = horloge.maintenant() + timedelta(days=30)
            notif_titre, notif_corps = notification_de_ban(definitif=False)
        journaliser_securite(
            "ban_communaute",
            acteur_id=admin.id,
            cible_id=user.id,
            detail=f"infraction {user.communaute_ban_count}",
        )
        sonner_systeme(
            session,
            "compte",
            destinataire_id=user.id,
            type="system",
            titre=notif_titre,
            corps=notif_corps,
            lien="/sondages",
        )
    else:
        # Débannir
        user.communaute_interdit = False
        user.communaute_ban_jusqu_au = None
        # On ne remet PAS ban_count à zéro : l'historique est conservé

    session.add(user)
    session.commit()
    session.refresh(user)
    from app.schemas import UserRead

    return UserRead.from_orm_with_roles(user)
