"""Les badges vus par leur porteur — et la vue d'ensemble du conseil syndical.

Un résident déclare son badge, signale une perte, commande un accès. Le CS y
ajoute deux LECTURES : tous les vigiks, toutes les télécommandes, avec leur
porteur.

🔴 Trois routes d'ÉCRITURE ont été supprimées de ce module le 06/09/2026
(#805) : créer un vigik, créer une télécommande, changer un statut. Le
commentaire qui les remplace dit pourquoi — enregistrer un badge est déjà
couvert deux fois, et une troisième voie jamais exercée dérive.
"""

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
)
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import est_rattache_au_lot, get_current_user
from app.database import get_session
from app.models.core import (
    CommandeAcces,
    StatutAcces,
    StatutImport,
    Utilisateur,
    Lot,
)
from app.routers.acces.resident_schemas import (
    AccesSignalePerdu,
    BadgeDeclare,
    CommandeAccesCreate,
    CommandeAccesRead,
    DeclarerBadgeBody,
)
from app.routers.acces.vues import AccesPorteur
from app.utils.types_acces import TELECOMMANDE, TYPES_ACCES, TypeAcces, VIGIK, libelle_type_acces
from app.utils.destinataires import membres_cs_notifiables
from app.utils.noms import contexte_personne, nom_affiche
from app.auth.appartenance import exiger_acces_du_porteur
from app.utils.porteurs_acces import acces_de, lot_unique_de_nature, porteurs
from app.utils.resolution_acces import exiger_code_libre, rattacher
from app.utils.cloche import sonner

router = APIRouter()


#  ── L'ACCÈS, écrit une fois ────────────────────────────────────────────────
#
#  🔴 Quatre paires de fonctions jumelles vivaient ici — lister, signaler perdu,
#  supprimer, déclarer — identiques à trois mots près. `utils/types_acces.py`
#  porte ces trois mots ; ce qui suit porte les gestes.
#
#  ⚠️ Les ROUTES restent distinctes (`/vigiks/…` et `/telecommandes/…`) : ce sont
#  les adresses que le front appelle déjà, et les fondre serait une rupture pour
#  un gain nul. Ce sont les CORPS qui étaient recopiés, pas les URL.


#  La règle « ce badge est le mien » vit dans `auth/appartenance` (#1028) :
#  404 et non 403, et le conseil syndical n'y est PAS admis — deux décisions
#  qui se lisent maintenant à côté de celle du bail, avec laquelle elles
#  divergent volontairement.


def _mes_acces(session: Session, type_acces: TypeAcces, user: Utilisateur) -> list[AccesPorteur]:
    """Les accès d'un porteur : les siens, plus ceux qui lui sont attribués.

    ⚠️ Le dédoublonnage n'est pas décoratif : un copropriétaire peut être à la
    fois porteur direct et attributaire du même objet, et la liste l'affichait
    alors deux fois.

    🔴 **Une VUE, plus l'objet brut** (15/09/2026, demandé à l'écran : *« ajouter
    la colonne Accès »*). La liste rendait `session.exec(select(Vigik))` tel
    quel, donc `perimetre_cible` sous sa forme de stockage — la chaîne
    `'["bat:2"]'` là où l'écran attend une liste de codes. Parser côté écran
    aurait fait une seconde lecture du même champ ; `AccesPorteur` la fait une fois,
    et la vue du conseil syndical en dérive.
    """
    #  🔴 Les porteurs se DÉDUISENT du lot depuis #1194 — conjoint compris. La
    #  liste lisait `user_id` plus les tables d'attribution, que sept chemins
    #  écrivaient et dont un seul servait le conjoint inscrit après coup.
    sortie = acces_de(session, type_acces, user.id)
    return AccesPorteur.depuis(session, type_acces, sortie)


def _signaler_perdu(
    session: Session, type_acces: TypeAcces, objet_id: int, user: Utilisateur
) -> AccesSignalePerdu:
    objet = exiger_acces_du_porteur(session, type_acces, objet_id, user)
    objet.statut = StatutAcces.perdu
    session.add(objet)
    session.commit()
    return AccesSignalePerdu(statut=objet.statut)


#  🔴 `_supprimer_acces` A ÉTÉ RETIRÉ LE 15/09/2026, avec ses deux routes —
#  demandé à l'écran :
#
#      « sur la page Mes lots & accès : enlève la poubelle. Un résident ne peut
#        pas supprimer un accès, il peut juste signaler qu'il a perdu. »
#
#  Et c'est une correction de FOND, pas de présentation. Le geste détruisait la
#  ligne : l'attribution partait, l'import se déliait, l'objet disparaissait.
#  Or **le badge, lui, existe toujours** — il est dans une poche, dans un tiroir,
#  ou perdu. Le parc cessait de pouvoir dire qu'il circule, et l'import le
#  reproposait à la résolution suivante comme s'il n'avait jamais été remis.
#
#  C'est la règle déjà déployée partout : archiver sur la vue principale,
#  supprimer réservé à l'admin (`ux-patterns` §8). Elle vaut ici aussi — et la
#  suppression définitive existe, chez l'administrateur, sur l'écran du parc.
#
#  ⚠️ Retirer le bouton **sans retirer la route** aurait laissé le geste
#  accessible à qui appelle l'API directement : un écran n'est pas un contrôle
#  d'accès. Le détachement, lui, reste employé par le parc — il vit dans
#  `utils/acces_detachement`, et c'est pour cela qu'il n'était pas écrit ici.


def _declarer_acces(
    session: Session, type_acces: TypeAcces, code: str, user: Utilisateur
) -> BadgeDeclare:
    """Un porteur déclare un accès qu'il détient déjà.

    Si le code correspond à une ligne d'import non résolue, celle-ci est marquée
    résolue et **son lot est repris sur l'objet créé**.

    🔴 C'est la correction que la factorisation apporte (14/09/2026) : la branche
    vigik reprenait le `lot_id` de l'import, la branche télécommande ne le
    faisait pas. Une télécommande déclarée par son porteur restait donc sans lot
    dans la vue du conseil syndical, alors que l'import le connaissait. Les deux
    branches se ressemblaient assez pour qu'on ne relise jamais les deux.
    """
    existant = session.exec(select(type_acces.modele).where(type_acces.modele.code == code)).first()
    if existant and user.id in porteurs(session, existant):
        raise HTTPException(400, f"{type_acces.libelle} déjà enregistré sur votre compte")
    exiger_code_libre(session, type_acces, code)

    #  🔴 La ligne du fichier n'est plus CAPTURÉE par son seul code (#1194) : la
    #  déclaration la résolvait au nom du déclarant, quel que soit le lot qu'elle
    #  désigne. Elle ne se rattache que si ce lot est le sien.
    ligne = session.exec(
        select(type_acces.modele_import).where(
            type_acces.champ_code_import == code,
            type_acces.modele_import.statut.in_(
                [StatutImport.en_attente, StatutImport.proprietaire_lie]
            ),
        )
    ).first()
    if ligne and ligne.lot_id and not est_rattache_au_lot(user, ligne.lot_id):
        raise HTTPException(
            400,
            "Ce code figure au fichier du syndic pour un autre lot : "
            "le conseil syndical peut le corriger",
        )
    if ligne and ligne.lot_id:
        ligne.user_proprietaire_id = ligne.user_proprietaire_id or user.id
        objet = rattacher(type_acces, ligne, session)
    else:
        objet = type_acces.modele(
            code=code,
            user_id=user.id,
            statut=StatutAcces.actif,
            lot_id=lot_unique_de_nature(session, type_acces, user.id),
        )
        session.add(objet)
        ligne = None

    session.commit()
    session.refresh(objet)
    return BadgeDeclare(
        type=type_acces.cle, id=objet.id, code=code, import_resolu=ligne is not None
    )


# ── Vue résident ────────────────────────────────────────────────────────────


@router.get("/mes-vigiks", response_model=list[AccesPorteur])
def mes_vigiks(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _mes_acces(session, VIGIK, user)


@router.get("/mes-telecommandes", response_model=list[AccesPorteur])
def mes_telecommandes(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _mes_acces(session, TELECOMMANDE, user)


@router.get("/mes-commandes", response_model=list[CommandeAccesRead])
def mes_commandes(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return session.exec(
        select(CommandeAcces)
        .where(CommandeAcces.user_id == user.id)
        .order_by(CommandeAcces.cree_le.desc())
    ).all()


@router.post("/commandes", response_model=CommandeAccesRead, status_code=201)
def creer_commande(
    body: CommandeAccesCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    #  🔴 Cette vérification interrogeait `UserLot` elle-même, SANS regarder
    #  `actif` : un rattachement désactivé permettait encore de commander un
    #  badge pour ce lot (#1028). La question s'écrit une fois, dans
    #  `auth/deps.est_rattache_au_lot`, qui exige le lien actif.
    if not est_rattache_au_lot(user, body.lot_id):
        raise HTTPException(403, "Vous n'êtes pas associé à ce lot")

    cmd = CommandeAcces(
        user_id=user.id,
        lot_id=body.lot_id,
        type=body.type,
        quantite=body.quantite,
        motif=body.motif,
    )
    session.add(cmd)
    session.flush()

    # Numéro affichable du lot — `lot_id` est un identifiant interne, illisible
    # pour un membre du CS qui reçoit la demande.
    lot = session.get(Lot, body.lot_id)
    lot_numero = lot.numero if lot else str(body.lot_id)

    #  Notifier le CS — par ses RÔLES (`membres_cs_ou_admin`), et non par
    #  `Utilisateur.role`, le rôle principal hérité : un conseiller dont le rôle
    #  principal est « résident » n'était pas prévenu (relevé par #1187).
    from app.utils.destinataires import membres_cs_ou_admin

    for membre in membres_cs_ou_admin(session):
        sonner(
            session,
            destinataire_id=membre.id,
            type="vigik",
            titre=f"Nouvelle demande de {libelle_type_acces(body.type)}",
            corps=f"{nom_affiche(user.prenom, user.nom)} — lot {lot_numero}",
            lien="/espace-cs",
        )

    # ── Email au CS ───────────────────────────────────────────────────────
    # `vigik_commande_recue` n'était envoyé par personne : le CS ne découvrait
    # la demande qu'en ouvrant l'application. Une commande de badge attend une
    # décision humaine — elle doit atteindre son destinataire (01/08/2026).
    # Passe par `membres_cs_notifiables`, source unique des destinataires CS.
    destinataires_cs = membres_cs_notifiables(session)
    if destinataires_cs:
        from app.utils.email import send_email_group

        background_tasks.add_task(
            send_email_group,
            code="vigik_commande_recue",
            to_recipients=destinataires_cs,
            context={
                "type": libelle_type_acces(body.type),
                "lot": {"numero": lot_numero},
                "demandeur": contexte_personne(user),
            },
        )

    session.commit()
    session.refresh(cmd)
    return cmd


class SignalerPerduBody(BaseModel):
    raison: str = ""


@router.patch("/vigiks/{vigik_id}/perdu", response_model=AccesSignalePerdu)
def signaler_vigik_perdu(
    vigik_id: int,
    body: SignalerPerduBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _signaler_perdu(session, VIGIK, vigik_id, user)


@router.patch("/telecommandes/{tc_id}/perdu", response_model=AccesSignalePerdu)
def signaler_tc_perdu(
    tc_id: int,
    body: SignalerPerduBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _signaler_perdu(session, TELECOMMANDE, tc_id, user)


@router.post("/declarer-badge", response_model=BadgeDeclare, status_code=201)
def declarer_badge(
    body: DeclarerBadgeBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Un résident déclare un badge / TC qu'il possède déjà.

    Le code vide et le type inconnu sont refusés par `DeclarerBadgeBody` : un 422
    de la forme que le contrat annonce (#2507).
    """
    return _declarer_acces(session, TYPES_ACCES[body.type], body.code, user)
