"""Le point d'inscription du registre — `POST /plateforme/inscriptions` (R1 #1877, §4.11).

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
from app.registre import conditions, signature
from app.registre.base import get_session_plateforme, registre_actif
from app.registre.contrat import (
    VERSION_CONTRAT,
    DemandeInscription,
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

#: L'en-tête qui porte la signature de la demande (Ed25519, base64).
EN_TETE_SIGNATURE = "X-Signature-Installation"

#: L'auteur d'un geste fait par le registre lui-même, et non par l'opérateur.
SYSTEME = "système"


def _servi_ici(request: Request) -> None:
    """404 hors de la référence, ou sous un autre nom que le nom dédié du registre."""
    attendu = nom_d_hote(get_settings().hote_registre)
    servi = registre_actif() and nom_d_hote(request.headers.get("host", "")) == attendu
    present_ou_404(servi or None, "Not Found")


def _refus(code: int, detail: str) -> HTTPException:
    return HTTPException(code, detail)


async def _lire_demande(request: Request) -> tuple[bytes, DemandeInscription]:
    """Les octets reçus, et la demande qu'ils portent — ou le refus qui dit pourquoi."""
    corps = await request.body()
    if len(corps) > TAILLE_MAX:
        raise _refus(413, "Demande trop volumineuse.")
    try:
        demande = DemandeInscription.model_validate_json(corps)
    except ValidationError:
        raise _refus(422, "Demande illisible : elle ne suit pas le contrat de données.") from None
    if demande.version_contrat != VERSION_CONTRAT:
        raise _refus(400, f"Version du contrat de données attendue : {VERSION_CONTRAT}.")
    en_vigueur = conditions.version_en_vigueur()
    if demande.conditions_acceptees != en_vigueur:
        raise _refus(400, f"Les conditions en vigueur sont celles de la version {en_vigueur}.")
    if demande.empreinte_conditions != conditions.empreinte(en_vigueur):
        raise _refus(400, "Le texte des conditions accepté n'est pas celui de la référence.")
    if not signature.cle_publique_valide(demande.cle_publique) or not signature.verifier(
        demande.cle_publique, corps, request.headers.get(EN_TETE_SIGNATURE, "")
    ):
        raise _refus(401, "Signature de l'installation absente ou invalide.")
    return corps, demande


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
    session.add(
        DecisionRegistre(
            installation_id=inst.id,
            geste="conditions_acceptees",
            motif=f"conditions v{version} acceptées",
            auteur=SYSTEME,
        )
    )


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
        raise _refus(503, "Le registre n'accepte pas de nouvelle inscription pour l'instant.")
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
    session.add(
        DecisionRegistre(installation_id=inst.id, geste="inscription", auteur=SYSTEME)
    )
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
    _, demande = await _lire_demande(request)
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
        raise _refus(503, "Le registre est indisponible.") from None
    reponse = ReponseInscription(identifiant=inst.identifiant, etat=inst.etat.value)
    return JSONResponse(reponse.model_dump(), status_code=201 if neuve else 200)
