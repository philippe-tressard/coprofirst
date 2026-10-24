"""Les points du registre — `POST /plateforme/inscriptions` (R1 #1877), `/baux` (R2 #1878)
et `/rapports` (R3 #1879).

Une route PUBLIQUE : une installation qui s'inscrit n'a pas de compte chez la référence.
Ce qui la garde, dans l'ordre :

1. **Elle n'existe que chez la référence** dont le registre est déclaré
   (`base.registre_actif`), et **sous son nom dédié** (`HOTE_REGISTRE`) — ailleurs,
   404, comme une route inconnue. Le nom dédié ne désigne aucune copropriété : le
   préfixe `/plateforme/` échappe à leur résolution (`contexte.PREFIXE_PLATEFORME`).
2. **Débit plafonné** par adresse (`LIMITE_INSCRIPTION_INSTALLATION`), **taille
   plafonnée** (`TAILLE_MAX`), et un **plafond d'inscriptions en attente** : le
   registre ne se remplit pas de demandes que personne n'a validées.
3. **Signée** par la clé de l'installation, sur les octets REÇUS : la demande
   prouve qu'elle vient de qui détient la clé privée — et la même clé, plus tard,
   retrouve la même inscription.
4. **Au contrat** (`contrat.DemandeInscription`, champs inconnus refusés), avec les
   conditions EN VIGUEUR, dont l'empreinte doit être celle du texte que la référence
   archive (`conditions`).

Rien de ce que la demande contient n'est renvoyé dans un message d'erreur.

Le BAIL (`POST /plateforme/baux`, R2) suit les mêmes gardes 1 à 3 : signé par la
clé de l'installation, il rend un bail signé par la clé des baux (`registre/baux`).
Deux clés sous un même identifiant sont un CLONE : refusé, et inscrit au journal
des décisions.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, func, select

from app.config import get_settings
from app.contexte import nom_d_hote
from app.registre import baux, canaux, conditions, rapports, signature
from app.registre.decisions import consigner
from app.registre.base import get_session_plateforme, registre_actif
from app.registre.contrat import (
    EN_TETE_SIGNATURE,
    VERSION_CONTRAT,
    BailSigne,
    DemandeBail,
    DemandeInscription,
    Rapport,
    ReponseInscription,
)
from app.registre.modeles import (
    AcceptationConditions,
    ContactInstallation,
    DecisionRegistre,
    EtatInscription,
    Installation,
    identifiant_de,
)
from app.utils import horloge
from app.utils.limiter import LIMITE_INSCRIPTION_INSTALLATION, limiter
from app.utils.noms import nom_affiche
from app.utils.recuperer import present_ou_404

logger = logging.getLogger("hostachy.registre")

router = APIRouter(prefix="/plateforme", tags=["plateforme"])

#: Une demande d'inscription pèse moins d'un kilo-octet ; au-delà de 16, ce n'en est pas une.
TAILLE_MAX = 16 * 1024

#: Au-delà, le registre refuse de nouvelles inscriptions jusqu'à ce que l'opérateur
#: en ait validé ou refusé : un remplissage ne peut pas l'engorger.
PLAFOND_EN_ATTENTE = 50

#: Le refus d'une installation que la référence ne connaît pas (bail, rapport).
INCONNUE = "Installation inconnue du registre."


def _servi_ici(request: Request) -> None:
    """404 hors de la référence, ou sous un autre nom que le nom dédié du registre."""
    attendu = nom_d_hote(get_settings().hote_registre)
    servi = registre_actif() and nom_d_hote(request.headers.get("host", "")) == attendu
    present_ou_404(servi or None, "Not Found")


async def _lire_signee(request: Request, schema):
    """La demande que portent les octets reçus, SIGNÉE par la clé qu'elle déclare.

    Taille, contrat, version et signature — les gardes communes à tout envoi
    d'une installation ; le refus dit lequel a manqué, jamais ce qu'il a lu.
    """
    corps = await request.body()
    if len(corps) > TAILLE_MAX:
        raise HTTPException(413, "Demande trop volumineuse.")
    try:
        demande = schema.model_validate_json(corps)
    except ValidationError:
        raise HTTPException(
            422, "Demande illisible : elle ne suit pas le contrat de données."
        ) from None
    if demande.version_contrat != VERSION_CONTRAT:
        raise HTTPException(400, f"Version du contrat de données attendue : {VERSION_CONTRAT}.")
    if not signature.cle_publique_valide(demande.cle_publique) or not signature.verifier(
        demande.cle_publique, corps, request.headers.get(EN_TETE_SIGNATURE, "")
    ):
        raise HTTPException(401, "Signature de l'installation absente ou invalide.")
    return demande


async def _lire_demande(request: Request) -> DemandeInscription:
    """La demande d'inscription — signée, et sur les conditions EN VIGUEUR."""
    demande = await _lire_signee(request, DemandeInscription)
    en_vigueur = conditions.version_en_vigueur()
    if demande.conditions_acceptees != en_vigueur:
        raise HTTPException(
            400, f"Les conditions en vigueur sont celles de la version {en_vigueur}."
        )
    if demande.empreinte_conditions != conditions.empreinte(en_vigueur):
        raise HTTPException(400, "Le texte des conditions accepté n'est pas celui de la référence.")
    return demande


def _archiver_acceptation(session: Session, inst: Installation, demande: DemandeInscription):
    """Le contrat accepté, archivé tel quel et rattaché à l'installation (R0 #1876)."""
    admin = demande.administrateur
    version = demande.conditions_acceptees
    session.add(
        AcceptationConditions(
            installation_id=inst.id,
            version=version,
            empreinte=conditions.empreinte(version),
            texte=conditions.texte(version),
            accepte_par=f"{nom_affiche(admin.prenom, admin.nom)} <{admin.courriel}>",
        )
    )
    consigner(session, inst, "conditions_acceptees", f"conditions v{version} acceptées")


def _ecrire_contact(session: Session, inst: Installation, demande: DemandeInscription) -> None:
    admin = demande.administrateur
    contact = session.exec(
        select(ContactInstallation).where(ContactInstallation.installation_id == inst.id)
    ).first() or ContactInstallation(installation_id=inst.id, prenom="", nom="", courriel="")
    contact.prenom, contact.nom = admin.prenom, admin.nom
    contact.courriel, contact.telephone = str(admin.courriel), admin.telephone
    contact.mis_a_jour_le = horloge.maintenant()
    session.add(contact)


def _reinscrire(session: Session, inst: Installation, demande: DemandeInscription) -> None:
    """La même clé revient : mêmes identifiant et état ; contact et version mis à jour."""
    deja = session.exec(
        select(AcceptationConditions).where(
            AcceptationConditions.installation_id == inst.id,
            AcceptationConditions.version == demande.conditions_acceptees,
        )
    ).first()
    if deja is None:
        _archiver_acceptation(session, inst, demande)
    _ecrire_contact(session, inst, demande)
    if inst.effacee_le is not None:
        #  Supprimée après sa résiliation, elle revient : l'opérateur la revoit, résiliée.
        inst.effacee_le = None
        consigner(session, inst, "retour_apres_suppression")
    inst.version_logicielle = demande.version_logicielle
    inst.conditions_acceptees = demande.conditions_acceptees
    inst.vue_le = inst.mis_a_jour_le = horloge.maintenant()
    session.add(inst)


def _inscrire(session: Session, demande: DemandeInscription) -> Installation:
    en_attente = session.exec(
        select(func.count())
        .select_from(Installation)
        .where(Installation.etat == EtatInscription.en_attente)
    ).one()
    if en_attente >= PLAFOND_EN_ATTENTE:
        raise HTTPException(
            503, "Le registre n'accepte pas de nouvelle inscription pour l'instant."
        )
    #  Un identifiant provisoire unique, remplacé dans la même transaction par celui
    #  que donne le numéro de la ligne : `CF-000042`.
    inst = Installation(
        identifiant=f"tmp-{uuid4().hex[:16]}",
        cle_publique=demande.cle_publique,
        empreinte_cle=signature.empreinte(demande.cle_publique),
        version_logicielle=demande.version_logicielle,
        conditions_acceptees=demande.conditions_acceptees,
        vue_le=horloge.maintenant(),
    )
    session.add(inst)
    session.flush()
    inst.identifiant = identifiant_de(inst.id)
    session.add(inst)
    consigner(session, inst, "inscription")
    _archiver_acceptation(session, inst, demande)
    _ecrire_contact(session, inst, demande)
    return inst


@router.post(
    "/inscriptions",
    response_model=ReponseInscription,
    status_code=201,
    dependencies=[Depends(_servi_ici)],
)
@limiter.limit(LIMITE_INSCRIPTION_INSTALLATION)
async def inscrire(request: Request, session: Session = Depends(get_session_plateforme)):
    """Inscrit une installation (201), ou retrouve celle de la même clé (200)."""
    demande = await _lire_demande(request)
    try:
        inst = session.exec(
            select(Installation).where(Installation.cle_publique == demande.cle_publique)
        ).first()
        neuve = inst is None
        if neuve:
            inst = _inscrire(session, demande)
        else:
            _reinscrire(session, inst, demande)
        session.commit()
        session.refresh(inst)
    except SQLAlchemyError as exc:
        session.rollback()
        logger.warning("registre : inscription non enregistrée (%s)", type(exc).__name__)
        raise HTTPException(503, "Le registre est indisponible.") from None
    reponse = ReponseInscription(identifiant=inst.identifiant, etat=inst.etat.value)
    return JSONResponse(reponse.model_dump(), status_code=201 if neuve else 200)


def _signaler_clone(session: Session, inst: Installation) -> None:
    """Deux clés pour un identifiant : la décision s'inscrit, une fois par jour au plus."""
    depuis = horloge.maintenant().replace(hour=0, minute=0, second=0, microsecond=0)
    deja = session.exec(
        select(DecisionRegistre).where(
            DecisionRegistre.installation_id == inst.id,
            DecisionRegistre.geste == "clone_signale",
            DecisionRegistre.cree_le >= depuis,
        )
    ).first()
    if deja is None:
        consigner(
            session, inst, "clone_signale", "une autre clé a demandé le bail de cet identifiant"
        )
        session.commit()


@router.post("/baux", response_model=BailSigne, dependencies=[Depends(_servi_ici)])
@limiter.limit(LIMITE_INSCRIPTION_INSTALLATION)
async def renouveler_bail(request: Request, session: Session = Depends(get_session_plateforme)):
    """Délivre le bail d'une installation inscrite — signé par la clé des baux (R2)."""
    demande = await _lire_signee(request, DemandeBail)
    cle = baux.cle_de_signature()
    if cle is None:
        raise HTTPException(503, "Le registre ne délivre pas encore de bail.")
    try:
        inst = present_ou_404(
            session.exec(
                select(Installation).where(Installation.identifiant == demande.identifiant)
            ).first(),
            INCONNUE,
        )
        if inst.cle_publique != demande.cle_publique:
            _signaler_clone(session, inst)
            raise HTTPException(409, "Cet identifiant appartient à une autre clé.")
        inst.version_logicielle = demande.version_logicielle
        inst.vue_le = horloge.maintenant()
        session.add(inst)
        session.commit()
        session.refresh(inst)
        versions = canaux.versions_disponibles(session)
    except SQLAlchemyError as exc:
        session.rollback()
        logger.warning("registre : bail non délivré (%s)", type(exc).__name__)
        raise HTTPException(503, "Le registre est indisponible.") from None
    return baux.delivrer(inst, cle, horloge.maintenant(), versions).model_dump(mode="json")


@router.post("/rapports", status_code=202, dependencies=[Depends(_servi_ici)])
@limiter.limit(LIMITE_INSCRIPTION_INSTALLATION)
async def recevoir_rapport(request: Request, session: Session = Depends(get_session_plateforme)):
    """Le rapport nocturne d'une installation inscrite, signé par SA clé (R3)."""
    corps = await request.body()
    if len(corps) > TAILLE_MAX:
        raise HTTPException(413, "Rapport trop volumineux.")
    try:
        rapport = Rapport.model_validate_json(corps)
    except ValidationError:
        raise HTTPException(
            422, "Rapport illisible : il ne suit pas le contrat de données."
        ) from None
    if rapport.version_contrat != VERSION_CONTRAT:
        raise HTTPException(400, f"Version du contrat de données attendue : {VERSION_CONTRAT}.")
    try:
        inst = present_ou_404(
            session.exec(
                select(Installation).where(
                    Installation.identifiant == rapport.identite.identifiant,
                    #  Sans clé, elle ne peut rien signer : comme absente.
                    Installation.cle_publique.is_not(None),
                    Installation.cle_publique != "",
                )
            ).first(),
            INCONNUE,
        )
        if not signature.verifier(
            inst.cle_publique, corps, request.headers.get(EN_TETE_SIGNATURE, "")
        ):
            raise HTTPException(401, "Signature de l'installation absente ou invalide.")
        rapports.ranger(session, inst, rapport)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        logger.warning("registre : rapport non rangé (%s)", type(exc).__name__)
        raise HTTPException(503, "Le registre est indisponible.") from None
    return {"recu": True}
