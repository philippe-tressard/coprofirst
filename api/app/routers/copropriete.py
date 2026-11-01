"""Router copropriété — fiche, bâtiments, lots."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.core import (
    ContratEntretien,
    Copropriete,
    Prestataire,
    Utilisateur,
)

from app.utils.config_site import config_site, ecrire_cle
from app.utils.destinataires import syndic_principal
from app.utils.liens import nom_site
from app.utils.document_contrat import id_document_designe
from app.utils.echeance_contrat import echeance_du_contrat
from app.utils.equipements import ASSURANCE, SYNDIC
from app.utils.lecture import lire_objet
from app.utils.recuperer import connu_ou_404, premier_ou_404
from app.utils.syndic import nom_du_syndic

router = APIRouter(prefix="/copropriete", tags=["copropriété"])

#: Ce que dit le 404 quand la fiche de la copropriété n'a jamais été saisie.
COPROPRIETE_ABSENTE = "Copropriété non configurée"


class CoproprieteUpdate(BaseModel):
    nom: Optional[str] = None
    adresse: Optional[str] = None
    annee_construction: Optional[int] = None
    nb_lots_total: Optional[int] = None
    nb_lots_principaux: Optional[int] = None
    nb_parkings_communs: Optional[int] = None
    numero_immatriculation: Optional[str] = None
    #: Le mois de début de l'exercice comptable, 1 à 12 (#1643).
    mois_debut_exercice: Optional[int] = Field(default=None, ge=1, le=12)
    #  🔴 `assurance_compagnie`, `assurance_numero_police` et `assurance_echeance`
    #  ont QUITTÉ ce schéma (#490).
    #
    #  Ils décrivaient un contrat avec un prestataire — notion que
    #  `ContratEntretien` porte déjà, avec ses échéances, ses documents et ses
    #  relances. Saisis ici en texte libre, ils créaient un second assureur qui
    #  ne renvoyait à rien : le même nom pouvait exister deux fois, sans que rien
    #  ne dise que c'était le même.
    #
    #  ⚠️ Les laisser acceptés « au cas où » aurait été pire que de les retirer :
    #  l'écran aurait continué d'écrire du texte que plus personne ne lit, et la
    #  fiche aurait affiché un assureur pendant que le contrat en désignait un
    #  autre. Un champ que le serveur ne consomme plus doit disparaître de son
    #  contrat d'entrée, pas y rester par prudence.
    #
    #  L'assurance se modifie désormais là où vivent les contrats.
    #
    #  ✅ Ce que la fiche accepte à nouveau, et qui n'est PAS un retour arrière :
    #  la DÉSIGNATION du contrat. On n'y saisit pas un assureur, on y dit lequel
    #  des contrats existants fait foi. La donnée reste unique, côté contrat.
    assurance_contrat_id: Optional[int] = None
    syndic_contrat_id: Optional[int] = None


class CoproprieteRead(BaseModel):
    id: int
    nom: str
    adresse: str
    annee_construction: Optional[int] = None
    nb_lots_total: Optional[int] = None
    nb_lots_principaux: Optional[int] = None
    numero_immatriculation: Optional[str] = None
    mois_debut_exercice: Optional[int] = None
    #  ⚠️ Ces trois champs restent EN LECTURE, et leur nom ne change pas : c'est
    #  ce que `FicheResidence` affiche, et leur donner un nouveau nom aurait
    #  imposé de toucher l'écran pour un renommage sans gain.
    #
    #  Ce qui change est leur SOURCE : ils ne viennent plus des colonnes de la
    #  copropriété mais du contrat d'assurance (`_assurance_du_contrat`). Une
    #  seule vérité, donc, quel que soit l'écran qui la montre.
    assurance_compagnie: Optional[str] = None
    assurance_numero_police: Optional[str] = None
    assurance_echeance: Optional[date] = None
    #: Enrichissement demandé le 20/08/2026 : la fiche montrait trois champs sur
    #: une notion qui en porte dix. Ce qu'on lit ici vient du prestataire ET du
    #: contrat, jamais d'une saisie propre à la fiche.
    assurance_contrat_id: Optional[int] = None
    assurance_telephone: Optional[str] = None
    assurance_email: Optional[str] = None
    assurance_debut: Optional[date] = None
    assurance_document_id: Optional[int] = None
    #: `True` quand le terme initial est passé : le contrat court par
    #: RECONDUCTION TACITE. L'écran le dit, sinon l'échéance affichée ne se
    #: distingue pas d'un terme négocié (`utils/echeance_contrat.py`).
    assurance_reconduit: bool = False
    #: Le terme est passé et RIEN ne l'a prolongé. Vrai seulement pour les
    #: contrats SANS reconduction tacite — le mandat de syndic (#628).
    assurance_echu: bool = False

    #: 🔴 Le SYNDIC, même moule que l'assurance — un contrat de référence.
    #:
    #: ⚠️ `syndic_interlocuteur` vient de `MembreSyndic`, PAS du prestataire :
    #: le cabinet est l'organisation, les personnes restent dans l'annuaire, et
    #: c'est de là que partent les courriels. Deux listes des mêmes gens, c'est
    #: la faute de #490 transposée au circuit des notifications.
    syndic_contrat_id: Optional[int] = None
    syndic_cabinet: Optional[str] = None
    syndic_telephone: Optional[str] = None
    syndic_email: Optional[str] = None
    syndic_numero_mandat: Optional[str] = None
    syndic_debut: Optional[date] = None
    syndic_echeance: Optional[date] = None
    syndic_document_id: Optional[int] = None
    syndic_reconduit: bool = False
    syndic_echu: bool = False
    syndic_interlocuteur: Optional[str] = None
    syndic_interlocuteur_email: Optional[str] = None

    photo_url: Optional[str] = None
    nb_parkings_communs: int = 0

    class Config:
        from_attributes = True


class BatimentRead(BaseModel):
    id: int
    numero: str
    nb_etages: int
    specificites: Optional[str] = None
    nb_appartements: int = 0
    nb_caves: int = 0
    nb_parkings: int = 0
    nb_locaux_commerciaux: int = 0

    class Config:
        from_attributes = True


#: Les deux sections de la fiche adossées à un contrat, et ce qui les distingue.
#:
#: 🔴 UNE SEULE FONCTION LES SERT. Écrire `assurance_du_contrat` puis
#: `syndic_du_contrat` aurait donné deux copies du même geste — lire un contrat,
#: lire son prestataire, composer un préfixe — libres de diverger au premier
#: enrichissement demandé d'un seul côté (`standards/02` §2).
#:
#: `champ_id` est la colonne qui DÉSIGNE le contrat ; `type_equipement` sert
#: uniquement au repli et à la liste proposée à l'écran.
SECTIONS_CONTRAT = {
    "assurance": ("assurance_contrat_id", ASSURANCE),
    "syndic": ("syndic_contrat_id", SYNDIC),
}


def contrat_de_reference(session: Session, copro: Copropriete, section: str):
    """Le contrat que la fiche DÉSIGNE pour cette section, ou `None`.

    ## Le choix a remplacé la déduction (20/08/2026)

    L'assurance venait d'une règle implicite — *« le contrat actif le plus récent
    gagne »* (#490). La règle était juste : une copropriété change d'assureur et
    l'ancien contrat reste en base, c'est tout l'intérêt d'en avoir fait un
    contrat. Mais **rien à l'écran ne disait laquelle des lignes faisait foi**,
    et la fiche dépendait d'une comparaison de dates.

    ⚠️ **Le repli sur l'ancienne règle est conservé**, et il n'est pas de la
    prudence : la migration 0157 renseigne `assurance_contrat_id` sur les bases
    existantes, mais une copropriété créée après coup, ou un contrat saisi avant
    qu'on ait pensé à le désigner, laisserait la fiche VIDE alors que le contrat
    existe. Un écran qui dit « aucun contrat » devant un contrat est pire qu'une
    règle implicite.

    Le repli ne s'applique que si aucun contrat n'est désigné — un contrat
    désigné puis supprimé rend `None`, et l'écran le dit.
    """
    champ_id, type_equipement = SECTIONS_CONTRAT[section]
    contrat_id = getattr(copro, champ_id, None)
    if contrat_id:
        return session.get(ContratEntretien, contrat_id)
    return session.exec(
        select(ContratEntretien)
        .where(
            ContratEntretien.copropriete_id == copro.id,
            ContratEntretien.type_equipement == type_equipement,
            ContratEntretien.actif == True,  # noqa: E712
        )
        .order_by(ContratEntretien.date_debut.desc(), ContratEntretien.id.desc())
    ).first()


def _echeance_lue(prefixe: str, contrat) -> dict:
    """`<prefixe>_echeance` et `<prefixe>_reconduit`, déduits du contrat.

    🔴 L'échéance NE VIENT PLUS de `prochaine_visite`. Ce champ s'appelle
    « Prochaine visite » dans le formulaire, et c'est la bonne notion pour un
    contrat d'entretien — une chaudière se visite. Une assurance et un mandat de
    syndic n'ont pas de visite : ils ont un terme, qui se déduit de la date de
    début et de la durée initiale, et qui se reporte d'un an tant qu'il est passé
    (`utils/echeance_contrat.py`).

    ⚠️ Signalé par l'utilisateur le 29/08/2026 : une assurance non dénoncée est
    reconduite, si bien que l'échéance affichée devenait fausse le lendemain de
    sa date — et s'affichait comme un terme DÉPASSÉ. La date reste complète,
    année comprise : c'est elle qui dit si le préavis tombe cette année ou la
    suivante. Ce qui manquait n'était pas l'année, c'était le report.

    Un helper commun aux deux sections, et non deux écritures : l'invariant du
    fichier est que l'assurance et le syndic sont LE MÊME GESTE — un
    enrichissement donné à l'un doit l'être à l'autre (`test_contrats_de_reference`).
    """
    e = echeance_du_contrat(contrat)
    return {
        f"{prefixe}_echeance": e.date if e else None,
        f"{prefixe}_reconduit": bool(e and e.reconduit),
        f"{prefixe}_echu": bool(e and e.echu),
    }


def assurance_du_contrat(session: Session, copro: Copropriete) -> dict:
    """Ce que la fiche affiche comme « assurance » — lu sur le CONTRAT (#490).

    Les colonnes `assurance_*` de `copropriete` ne sont plus la source, ni même
    déclarées par le modèle (#2059) : elles subsistent en base le temps d'une
    version, pour qu'un retour arrière reste possible, et plus rien ne les lit.

    Rend un dictionnaire vide si aucun contrat n'est trouvé : la fiche masque
    alors la section, exactement comme lorsque le champ texte était vide.
    """
    contrat = contrat_de_reference(session, copro, "assurance")
    if not contrat:
        return {}
    presta = session.get(Prestataire, contrat.prestataire_id)
    return {
        "assurance_contrat_id": contrat.id,
        "assurance_compagnie": presta.nom if presta else None,
        "assurance_telephone": presta.telephone if presta else None,
        "assurance_email": presta.email if presta else None,
        "assurance_numero_police": contrat.numero_contrat,
        "assurance_debut": contrat.date_debut,
        **_echeance_lue("assurance", contrat),
        "assurance_document_id": id_document_designe(session, contrat),
    }


def syndic_du_contrat(session: Session, copro: Copropriete) -> dict:
    """Le cabinet de syndic, son mandat, et son interlocuteur principal.

    ## Deux sources, et c'est voulu

    Le **cabinet** vient du prestataire désigné par le contrat de mandat ;
    l'**interlocuteur** vient de `MembreSyndic`, la table de l'annuaire.

    ⚠️ Ce n'est pas une inconséquence : `MembreSyndic` est lu par **dix
    modules**, dont `utils/destinataires.py`, `tickets/commun.py` et les trois
    routeurs de courriels. C'est de là que partent les messages au cabinet.
    Recopier ces personnes dans les contacts du prestataire aurait donné deux
    listes des mêmes gens — la faute de #490 transposée au circuit des
    notifications, où elle ne se verrait que le jour où un courriel ne partirait
    pas.

    Le prestataire porte donc l'ORGANISATION, l'annuaire garde les PERSONNES.
    """
    contrat = contrat_de_reference(session, copro, "syndic")
    principal = syndic_principal(session)

    lu: dict = {}
    if principal:
        lu["syndic_interlocuteur"] = " ".join(
            x
            for x in (
                principal.prenom,
                principal.nom,
                f"({principal.fonction})" if principal.fonction else "",
            )
            if x
        ).strip()
        lu["syndic_interlocuteur_email"] = principal.email

    if not contrat:
        #  ⚠️ On rend quand même l'interlocuteur : le cabinet peut n'avoir pas
        #  encore de contrat saisi alors que ses membres sont dans l'annuaire
        #  depuis des mois. Rendre un dictionnaire vide effacerait de la fiche
        #  une information qu'on POSSÈDE.
        return lu

    presta = session.get(Prestataire, contrat.prestataire_id)
    lu.update(
        {
            "syndic_contrat_id": contrat.id,
            "syndic_cabinet": presta.nom if presta else None,
            "syndic_telephone": presta.telephone if presta else None,
            "syndic_email": presta.email if presta else None,
            "syndic_numero_mandat": contrat.numero_contrat,
            "syndic_debut": contrat.date_debut,
            **_echeance_lue("syndic", contrat),
            "syndic_document_id": id_document_designe(session, contrat),
        }
    )
    return lu


def copropriete_lue(session: Session, copro: Copropriete) -> CoproprieteRead:
    """`CoproprieteRead` avec l'assurance prise sur le contrat.

    Un seul point de composition : les deux endpoints qui rendent une
    copropriété passent par ici. Les laisser composer chacun de leur côté aurait
    donné deux fiches capables de se contredire — c'est exactement ce que ce lot
    supprime.
    """
    lue = CoproprieteRead.model_validate(copro)
    #  🔴 Le nom de la résidence a UNE source (#2056) : `site_nom`, celui que
    #  l'en-tête, la connexion, les courriels et les documents affichent. La
    #  colonne `copropriete.nom` n'est plus lue — elle portait un second nom, saisi
    #  dans un autre onglet sous le même libellé, que seule la fiche montrait.
    lue.nom = nom_site(config_site(session).get("site_nom"))
    #  🔴 On EFFACE d'abord, on remplit ensuite.
    #
    #  `from_attributes=True` recopiait les colonnes `assurance_*` : sans cet
    #  effacement, une copropriété SANS contrat affichait l'ancienne saisie en
    #  texte libre — donc potentiellement un assureur qui n'est plus le bon, sans
    #  que rien ne le signale. Le modèle ne les déclare plus (#2059) ; l'effacement
    #  reste la garantie que la fiche n'invente rien, et couvre toujours `syndic_*`.
    #
    #  ⚠️ Trouvé par `test_sans_contrat_la_fiche_n_invente_rien`, écrit dans le
    #  même lot : le test a attrapé le défaut du code qu'il accompagnait.
    #  ⚠️ La liste des champs à effacer se DÉDUIT du schéma : les nommer ici en
    #  aurait fait une seconde liste, et l'enrichissement du 20/08 (dix champs de
    #  plus) l'aurait laissée en arrière au premier ajout oublié.
    for cle in CoproprieteRead.model_fields:
        if cle.startswith(("assurance_", "syndic_")):
            setattr(lue, cle, None)
    for source in (assurance_du_contrat, syndic_du_contrat):
        for cle, valeur in source(session, copro).items():
            setattr(lue, cle, valeur)

    #  🔴 LE REPLI, et il n'a sa place qu'ICI.
    #
    #  `syndic_du_contrat` lit ce que porte le CONTRAT — c'est son nom, et le
    #  test `…_meme_SANS_contrat` tient à ce qu'elle n'invente rien. Mais la
    #  règle arbitrée le 29/08/2026 (#535) dit que le nom du syndic a DEUX
    #  sources, le contrat puis la saisie libre, et qu'une seule répond à la
    #  fois. Cette hiérarchie est écrite une seule fois, dans `utils/syndic.py`.
    #
    #  ⚠️ Sans ce repli, la fiche de la résidence n'affichait aucun syndic pour
    #  une copropriété sans contrat désigné, alors que l'ANNUAIRE affichait la
    #  saisie : deux écrans, deux réponses à la même question — exactement le
    #  doublon que #535 ferme, reconstitué un étage plus haut.
    #
    #  ⚠️ Et c'est bien un repli, jamais une seconde vérité : il ne s'applique
    #  que là où la première est absente (`if not lue.syndic_cabinet`).
    if not lue.syndic_cabinet:
        lue.syndic_cabinet = nom_du_syndic(session) or None
    return lue


@router.get("", response_model=CoproprieteRead)
def get_copropriete(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    copro = premier_ou_404(session, Copropriete, COPROPRIETE_ABSENTE)
    return copropriete_lue(session, copro)


@router.patch("", response_model=CoproprieteRead)
def update_copropriete(
    body: CoproprieteUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    copro = premier_ou_404(session, Copropriete, COPROPRIETE_ABSENTE)
    donnees = body.model_dump(exclude_none=True)

    #  ⚠️ La conversion de `assurance_echeance` (chaîne ISO → `date`) vivait ici.
    #  Elle a disparu AVEC le champ (#490) : l'échéance est désormais celle du
    #  contrat, saisie par l'écran des contrats, où elle est déjà typée.
    #
    #  Ce qu'elle corrigeait mérite d'être rappelé, parce que la classe d'erreur
    #  reste : affecter une CHAÎNE à une colonne `date` faisait lever SQLAlchemy
    #  et rendait TOUTE la fiche inenregistrable — y compris quand on n'avait
    #  modifié que le nom du syndic. Le défaut a vécu des semaines, personne
    #  n'ayant retouché l'échéance (13/08/2026).

    #  Le nom s'écrit là où il se lit (#2056) — jamais dans la colonne, que plus
    #  rien ne lit. Vide, il ne s'écrit pas : la fiche garderait le repli neutre.
    nom = (donnees.pop("nom", None) or "").strip()
    if nom:
        ecrire_cle(session, "site_nom", nom)
    for k, v in donnees.items():
        setattr(copro, k, v)
    session.add(copro)
    session.commit()
    session.refresh(copro)
    return copropriete_lue(session, copro)


class ContratCandidat(BaseModel):
    """Un contrat proposable comme référence de la fiche.

    ⚠️ Volontairement PAUVRE : de quoi reconnaître le contrat dans une liste, et
    rien de plus. La fiche lit les détails par `contrat_de_reference` une fois le
    choix fait — deux chemins pour la même donnée en feraient deux vérités.
    """

    id: int
    libelle: str
    prestataire: Optional[str] = None
    numero_contrat: Optional[str] = None
    date_debut: date
    actif: bool


@router.get("/contrats-candidats/{section}", response_model=list[ContratCandidat])
def contrats_candidats(
    section: str,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Les contrats parmi lesquels la fiche désigne sa référence.

    🔴 `section` est validé contre `SECTIONS_CONTRAT` — liste blanche, jamais
    l'entrée brute : sans elle, le paramètre deviendrait un moyen de lister les
    contrats de n'importe quel équipement
    (`standards/03` §2).

    Les contrats INACTIFS sont rendus, avec leur drapeau. Une copropriété désigne
    parfois un mandat échu le temps d'en signer un nouveau, et les masquer
    obligerait à les réactiver pour les choisir — donc à mentir sur leur état.
    """
    _, type_equipement = connu_ou_404(SECTIONS_CONTRAT, section, "Section inconnue")
    copro = premier_ou_404(session, Copropriete, COPROPRIETE_ABSENTE)
    contrats = session.exec(
        select(ContratEntretien)
        .where(
            ContratEntretien.copropriete_id == copro.id,
            ContratEntretien.type_equipement == type_equipement,
        )
        .order_by(ContratEntretien.date_debut.desc(), ContratEntretien.id.desc())
    ).all()
    noms = {
        p.id: p.nom
        for p in session.exec(
            select(Prestataire).where(
                Prestataire.id.in_([c.prestataire_id for c in contrats] or [0])
            )
        ).all()
    }
    return [
        lire_objet(ContratCandidat, c, prestataire=noms.get(c.prestataire_id)) for c in contrats
    ]
