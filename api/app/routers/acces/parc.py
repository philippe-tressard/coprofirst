"""Le **parc** de badges — ce que le conseil syndical voit, et ce qu'il en fait.

## Pourquoi ce module (14/09/2026, #953)

`resident.py` portait déjà les deux LECTURES du conseil syndical, et son en-tête
le disait : « les badges vus par leur porteur — et la vue d'ensemble du conseil
syndical ». Les gestes demandés — ajouter, corriger, retirer, exporter — l'ont
fait franchir les 500 lignes, et le plafond de modularité a désigné la couture
qui existait déjà.

🔴 **Deux lecteurs, deux questions.** Un résident demande *« quels sont MES
badges ? »* ; le conseil syndical demande *« qui a le badge 4521 ? »*. Ce n'est
pas la même requête, ce ne sont pas les mêmes droits, et ce ne sont pas les mêmes
gestes.

## Ce qui a changé le 14/09/2026 — et ce que cela renverse

L'écran était **délibérément en lecture seule** depuis le 06/09 (#805) : trois
routes d'écriture avaient été supprimées ce jour-là, au motif qu'enregistrer un
badge était déjà couvert deux fois — l'import en masse, et `declarer-badge` par
le résident.

Ce choix est **renversé, sur demande explicite** :

> « dans Espace CS / Badges & télécommandes : l'export, la suppression, l'ajout
>   ou la modification d'un vigik / télécommande n'est pas (encore) possible ⇒ à
>   mettre en priorité haute »

⚠️ Ce qui aurait été fautif n'était pas d'ouvrir l'écriture, c'était de la
**recopier**. Les gestes passent donc par le descripteur `utils/types_acces`
(v1.36.8), celui-là même dont l'absence avait laissé diverger le report du
`lot_id` entre vigik et télécommande.

🔒 **Les droits vivent dans `auth/deps`**, jamais ici : `require_cs_or_admin`
pour voir et corriger, `require_admin` pour supprimer définitivement.
"""

import csv
import io
from app.utils import horloge, valeurs
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_admin, require_cs_or_admin
from app.database import get_session
from app.models.core import (
    StatutAcces,
    Telecommande,
    Ticket,
    Utilisateur,
    Vigik,
)
from app.routers.acces.vues import AccesOut
from app.utils.acces_choix import valider_acces
from app.utils.acces_detachement import detacher_acces
from app.utils.acces_gestes import (
    _acces_json,
    _prevenir_porteur,
    _tracer_sur_ticket,
    journaliser_acces,
)
from app.utils.porteurs_acces import noms_des_porteurs
from app.utils.resolution_acces import exiger_code_libre, synchroniser_import
from app.utils.dates_fr import date_courte
from app.utils.perimetres import perimetre_label
from app.utils.types_acces import TELECOMMANDE, TYPES_ACCES, TypeAcces, VIGIK
from app.utils.recuperer import ou_404

router = APIRouter()


def type_acces_demande(type_cle: str) -> TypeAcces:
    """Le descripteur du type nommé dans l'URL, ou **422** — une seule écriture.

    ⚠️ Ces trois lignes étaient recopiées dans chaque route paramétrée par
    `{type_cle}` (création, correction, suppression), et l'export allait en faire
    une quatrième. Une garde d'entrée recopiée est une garde qui se corrige à
    moitié : le jour où l'on y ajoute quelque chose — une trace, un autre code —
    on l'ajoute là où on regarde.

    Employée en `Depends`, elle rend le type **résolu** : la route reçoit un
    `TypeAcces`, pas une chaîne à valider. C'est la même forme que les
    dépendances d'autorisation de `auth/deps` — le contrôle est dans la
    signature, donc il ne peut pas être oublié dans le corps.
    """
    type_acces = TYPES_ACCES.get(type_cle)
    if type_acces is None:
        raise HTTPException(422, "Type invalide : " + " ou ".join(TYPES_ACCES))
    return type_acces


class AccesAdminOut(AccesOut):
    """Un badge tel que le conseil syndical a besoin de le VOIR.

    🔴 Les deux listes rendaient l'objet BRUT (`select(Vigik)`), donc `user_id`
    et `lot_id` — deux nombres. Un écran bâti dessus aurait affiché « badge 4521
    → utilisateur 37 », c'est-à-dire rien : la question qu'on pose à cette liste
    est *« qui a ce badge ? »*, et elle n'y répondait pas.

    C'est pourquoi enrichir la lecture faisait partie du lot qui l'expose : une
    route sans appelant n'est jamais mise à l'épreuve de la question à laquelle
    elle est censée répondre (#805).

    ## Ce qu'elle AJOUTE, et rien d'autre (15/09/2026)

    Elle **dérive** de la vue du porteur (`routers/acces/vues`) depuis que
    celui-ci a besoin de voir ce que son badge ouvre : les champs communs sont
    déclarés une fois, et seuls les trois qui répondent à « qui détient quoi ? »
    sont ici. Deux modèles jumeaux auraient divergé au premier ajout — c'est
    exactement ce qui était arrivé au `lot_id`.
    """

    porteur_nom: str
    #: Qui l'a en main — inconnu pour un badge rattaché à un lot sans compte (#1194).
    porteur_id: Optional[int] = None
    lot_libelle: Optional[str] = None


def _acces_admin_out(objets, session: Session, type_acces: TypeAcces) -> list[AccesAdminOut]:
    """Sérialise une liste de Vigik OU de Telecommande — les deux ont les mêmes
    champs utiles, et deux fonctions jumelles auraient divergé au premier ajout.

    ⚠️ Le TYPE est requis depuis le 15/09/2026 : la colonne « Lot » dépend de
    la NATURE de l'accès (`libelle_lots`), et la déduire de la classe de l'objet
    ferait une seconde table de correspondance à côté de `TYPES_ACCES`.
    """
    sortie = []
    #  Les PORTEURS, déduits du lot (#1194) — le conjoint aussi ; sans compte,
    #  le copropriétaire du fichier ; sans lot, « En stock ».
    noms = noms_des_porteurs(session, objets)
    for o in objets:
        sortie.append(
            AccesAdminOut(
                **AccesOut.champs_communs(session, type_acces, o),
                porteur_nom=noms[o.id],
                porteur_id=o.user_id,
            )
        )
    #  Par code : c'est ce qu'on a sous les yeux quand on cherche « à qui est ce
    #  badge ? », un numéro gravé sur un objet physique.
    return sorted(sortie, key=lambda a: a.code)


class AccesAdminBody(BaseModel):
    """Ce que le conseil syndical saisit — à la création comme à la correction.

    ⚠️ **Tous les champs sont optionnels**, y compris à la création : c'est un
    `PATCH` partiel qui les réemploie. Le seul vraiment requis à la création est
    le `code`, et c'est le geste qui l'exige, pas le schéma — un schéma qui
    rendrait `code` obligatoire empêcherait de s'en servir pour la correction.
    """

    code: Optional[str] = None
    #: Le copropriétaire pour qui l'accès est enregistré — le « saisi pour » des
    #: tickets, appliqué à un objet physique.
    porteur_id: Optional[int] = None
    lot_id: Optional[int] = None
    #: 🔹 Ce que le badge ouvre. `None` = ne pas changer ; `[]` = « on ne sait pas ».
    perimetre_cible: Optional[list[str]] = None
    statut: Optional[StatutAcces] = None
    #: Le numéro du ticket auquel rattacher ce geste — saisi à la main,
    #: **vérifié** : un numéro inconnu refuse la saisie plutôt que d'enregistrer
    #: le badge sans le lien. Un rattachement silencieusement perdu est pire
    #: qu'une erreur affichée.
    ticket_numero: Optional[str] = None


def _acces_admin(session: Session, type_acces: TypeAcces, objet_id: int):
    """L'objet vu par le conseil syndical — sans condition de propriété.

    🔒 Le pendant de `_acces_du_porteur`, et la différence est tout le sujet : le
    CS voit le parc ENTIER, un résident ne voit que le sien. Deux questions, deux
    fonctions — les fondre en une avec un drapeau `est_cs` ferait de ce drapeau
    la seule chose qui sépare « mes badges » de « tous les badges ».
    """
    objet = ou_404(session, type_acces.modele, objet_id, type_acces.libelle)
    return objet


def _ticket_par_numero(session: Session, numero: Optional[str]):
    """Le ticket dont le numéro a été saisi — ou l'erreur qui le dit.

    ⚠️ Un numéro inconnu **refuse** la saisie. L'alternative — enregistrer le
    badge et ignorer le lien — perdrait le rattachement sans que personne le
    sache, et c'est précisément ce que le ticket #953 demandait d'éviter en
    choisissant la saisie manuelle plutôt qu'un rapprochement deviné.
    """
    if not numero or not numero.strip():
        return None
    ticket = session.exec(select(Ticket).where(Ticket.numero == numero.strip())).first()
    if not ticket:
        raise HTTPException(422, f"Aucun ticket ne porte le numéro {numero.strip()}")
    return ticket


@router.post("/admin/{type_cle}", response_model=AccesAdminOut, status_code=201)
def creer_acces_admin(
    body: AccesAdminBody,
    type_acces: TypeAcces = Depends(type_acces_demande),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Le conseil syndical enregistre un accès POUR un copropriétaire.

    🔴 Troisième voie d'écriture, et elle est assumée (#953) : l'import en masse
    et `declarer-badge` ne couvrent pas le cas d'un badge remis en main propre
    par le conseil. Ce qui aurait été fautif, c'est de la RECOPIER — elle passe
    donc par le même descripteur que les deux autres.

    ⚠️ L'accès est **déduit** quand il n'est pas donné : le bâtiment du lot, ou
    celui des lots du porteur s'il n'y en a qu'un. La règle vit dans
    `utils/acces_perimetre`, et la migration 0190 en porte l'équivalent SQL.
    """
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(422, "Code vide")
    #  Le badge appartient au lot (#1194) : un lot SUFFIT, un porteur aussi.
    if not body.porteur_id and not body.lot_id:
        raise HTTPException(422, "Lot ou porteur requis")
    porteur = ou_404(session, Utilisateur, body.porteur_id, "Porteur") if body.porteur_id else None
    exiger_code_libre(session, type_acces, code)

    ticket = _ticket_par_numero(session, body.ticket_numero)
    valider_acces(session, type_acces, body.perimetre_cible)

    objet = type_acces.modele(
        code=code,
        user_id=porteur.id if porteur else None,
        lot_id=body.lot_id,
        statut=body.statut or StatutAcces.actif,
        perimetre_cible=_acces_json(
            session,
            type_acces,
            body.perimetre_cible,
            body.lot_id,
            porteur.id if porteur else None,
        ),
    )
    session.add(objet)
    session.flush()
    journaliser_acces(user, type_acces, objet, None)  # une porte posée laisse sa trace
    synchroniser_import(session, type_acces, objet)  # le parc complète l'import
    session.commit()
    session.refresh(objet)

    _tracer_sur_ticket(session, ticket, user, type_acces, objet, "enregistré")
    if porteur:
        _prevenir_porteur(session, porteur, type_acces, objet)
    return _acces_admin_out([objet], session, type_acces)[0]


@router.patch("/admin/{type_cle}/{objet_id}", response_model=AccesAdminOut)
def modifier_acces_admin(
    objet_id: int,
    body: AccesAdminBody,
    type_acces: TypeAcces = Depends(type_acces_demande),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Corriger un accès — tous ses champs, code compris (arbitré le 14/09/2026).

    ⚠️ Corriger le CODE revient presque toujours à désigner **un autre objet
    physique**. C'est accordé, et l'historique n'en dira rien : la ligne aura
    simplement changé. Si cela pose question un jour, le remède sera de tracer le
    changement de code, pas de retirer le geste.
    """
    objet = _acces_admin(session, type_acces, objet_id)
    avant = objet.perimetre_cible
    ticket = _ticket_par_numero(session, body.ticket_numero)
    #  🔒 La MÊME validation qu'à la création, et c'est tout l'intérêt de la
    #  sortir du formulaire : une restriction qui ne vivrait que dans l'écran
    #  laisserait la correction ouverte à ce que la création refuse.
    valider_acces(session, type_acces, body.perimetre_cible)

    if body.code is not None:
        code = body.code.strip()
        if not code:
            raise HTTPException(422, "Code vide")
        exiger_code_libre(session, type_acces, code, sauf_id=objet.id)
        objet.code = code
    if body.porteur_id is not None:
        ou_404(session, Utilisateur, body.porteur_id, "Porteur")
        objet.user_id = body.porteur_id
    if body.lot_id is not None:
        objet.lot_id = body.lot_id or None
    if body.statut is not None:
        objet.statut = body.statut
    if body.perimetre_cible is not None:
        objet.perimetre_cible = _acces_json(session, type_acces, body.perimetre_cible, None, None)
    journaliser_acces(user, type_acces, objet, avant)
    session.add(objet)
    synchroniser_import(session, type_acces, objet)  # le parc complète l'import
    session.commit()
    session.refresh(objet)
    _tracer_sur_ticket(session, ticket, user, type_acces, objet, "corrigé")
    return _acces_admin_out([objet], session, type_acces)[0]


@router.delete("/admin/{type_cle}/{objet_id}", status_code=204)
def supprimer_acces_admin(
    objet_id: int,
    type_acces: TypeAcces = Depends(type_acces_demande),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_admin),
):
    """🔒 Suppression DÉFINITIVE — administrateur seulement (arbitré le 14/09/2026).

    Le conseil syndical, lui, passe un badge en « perdu » ou « suspendu » par le
    `PATCH` ci-dessus. La distinction n'est pas administrative, elle est
    factuelle : **un badge perdu a existé**, et le parc doit pouvoir dire qu'il
    circule dans la nature. Une ligne saisie par erreur, elle, n'a jamais existé.
    Les confondre ferait disparaître des badges réels.

    C'est la règle déjà déployée partout — archiver sur la vue principale,
    supprimer réservé à l'admin (`ux-patterns` §8).
    """
    _acces_admin(session, type_acces, objet_id)
    detacher_acces(session, objet_id, type_acces.modele_import, type_acces.colonne_import)
    session.delete(session.get(type_acces.modele, objet_id))
    session.commit()


#  ⚠️ Les deux seules routes du parc qui ne sont PAS paramétrées par
#  `{type_cle}`, et c'est délibéré : un `{type_cle}` avalerait les listes
#  d'import des deux autres modules. Le pourquoi est dans `__init__` —
#  « Ordre de montage », qui porte déjà cette contrainte.
@router.get("/admin/vigiks", response_model=list[AccesAdminOut])
def list_vigiks(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Tous les badges Vigik de la copropriété, avec leur porteur."""
    return _acces_admin_out(session.exec(select(Vigik)).all(), session, VIGIK)


@router.get("/admin/telecommandes", response_model=list[AccesAdminOut])
def list_telecommandes(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Toutes les télécommandes de parking, avec leur porteur."""
    return _acces_admin_out(
        session.exec(select(Telecommande)).all(),
        session,
        TELECOMMANDE,
    )


#  🔴 TROIS ROUTES D'ÉCRITURE SUPPRIMÉES ICI le 06/09/2026 (#805), sur arbitrage :
#
#      PATCH  /acces/admin/vigiks/{id}      (changer le statut)
#      POST   /acces/admin/vigiks           (créer un badge)
#      POST   /acces/admin/telecommandes    (créer une télécommande)
#
#  Aucune n'avait d'appelant, et surtout : le besoin qu'elles servaient est déjà
#  couvert DEUX fois.
#
#  | Enregistrer des badges | par où |
#  |---|---|
#  | en masse | l'import Excel + `resoudre_import_*` |
#  | à l'unité | `POST /acces/declarer-badge`, par le résident lui-même |
#
#  Une troisième voie de création, jamais exercée, est du code qui dérive sans
#  qu'on le voie : `changer-role` était dans cet état et avait accumulé un
#  passe-droit que les gestes vivants n'ont pas (#801, même journée).
#
#  ⚠️ Elles n'étaient PAS défectueuses — vérifié : `create_vigik` appelait bien
#  `_create_user_vigiks`, comme la résolution d'import. C'est leur redondance qui
#  les condamne, pas un défaut. Les retirer sur un défaut supposé aurait été un
#  mauvais motif pour une bonne décision.
#
#  Ce qui RESTE, et pourquoi : les deux LECTURES ci-dessus répondent à une
#  question qu'aucun autre écran ne sait poser — « quels badges circulent, et
#  chez qui ? ». C'est le seul trou réel qu'avait ce domaine.


#: Les colonnes d'un export, dans l'ordre.
#:
#: ⚠️ Pas de colonne « Type » : chaque fichier ne porte qu'une nature d'accès,
#: et son nom la dit. Une colonne dont toutes les lignes ont la même valeur
#: n'apprend rien et se trie pour rien.
COLONNES_EXPORT = ["Code", "Porteur", "Lot", "Accès", "Statut", "Créé le"]


def _csv_du_parc(session: Session, type_acces: TypeAcces) -> str:
    """Le CSV d'UN type — la seule écriture du format, quel que soit le type.

    ⚠️ **Séparateur `;` et BOM UTF-8**, et ce n'est pas un détail de confort :
    Excel en configuration française lit la virgule comme un séparateur décimal
    et ouvre alors tout le fichier dans une seule colonne. Le BOM lui dit que le
    fichier est en UTF-8 — sans lui, « Bâtiment » s'affiche « BÃ¢timent ». Le
    fichier est destiné à être ouvert dans un tableur, pas relu par une machine.

    ⚠️ Les dates passent par `date_courte` : c'est la règle du dépôt, et un
    `strftime` local ici serait la trente-deuxième écriture d'un format.
    """
    objets = session.exec(select(type_acces.modele)).all()
    lignes = []
    #  🔴 La fiche seule : un `zip` décalé donnait le périmètre d'un AUTRE badge (15/09).
    for fiche in _acces_admin_out(objets, session, type_acces):
        lignes.append(
            [
                fiche.code,
                fiche.porteur_nom,
                fiche.lot_libelle or "",
                perimetre_label(fiche.perimetre_cible) if fiche.perimetre_cible else "",
                str(valeurs.valeur(fiche.statut)),
                date_courte(fiche.cree_le),
            ]
        )

    tampon = io.StringIO()
    graveur = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    graveur.writerow(COLONNES_EXPORT)
    graveur.writerows(lignes)

    #  ⚠️ `\ufeff` en tête : c'est le BOM. Il est écrit ICI et nulle part
    #  ailleurs — le dépôt refuse les BOM dans ses SOURCES, ce qui est une autre
    #  question : là il est une donnée du fichier produit, pas un artefact
    #  d'éditeur.
    return "\ufeff" + tampon.getvalue()


@router.get("/admin/{type_cle}/export.csv")
def exporter_parc(
    type_acces: TypeAcces = Depends(type_acces_demande),
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Le parc d'UN type, en CSV — une ligne par accès.

    ## Deux fichiers, et non plus un (15/09/2026)

    Le 14/09, un fichier unique avait été arbitré : *« un fichier se trie et se
    filtre dans un tableur ; deux obligent à les rapprocher à la main »*.
    L'usage a tranché l'inverse :

    > « ne fais pas qu'un seul export en format CSV, mais 2 : l'un pour les vigik
    >   et l'autre pour les télécommandes »

    Et c'est cohérent avec ce que le reste du produit dit de ces deux objets :
    ils n'ont ni les mêmes accès possibles (`codes_autorises`), ni le même
    rapport au lot (`acces_suit_le_lot`), ni les mêmes colonnes utiles. Les
    empiler dans un tableur obligeait à filtrer sur « Type » avant tout usage.

    🔒 **Une seule écriture du format.** La route est paramétrée par le
    descripteur, comme les trois autres de ce fichier : ajouter un troisième
    type d'accès — une clé, un bip — donnera son export sans qu'on touche ici.
    Deux fonctions `exporter_vigiks` / `exporter_telecommandes` auraient divergé
    à la première colonne ajoutée.
    """
    horodatage = horloge.maintenant().strftime("%Y-%m-%d")
    #  Le nom du fichier porte le type : c'est ce qui remplace la colonne
    #  « Type », et c'est ce que l'utilisateur lit dans son dossier de
    #  téléchargements six mois plus tard.
    nom = f"{type_acces.cle}-{horodatage}.csv"
    return StreamingResponse(
        iter([_csv_du_parc(session, type_acces)]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nom}"'},
    )
