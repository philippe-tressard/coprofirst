"""Admin — l'onglet « Installations » de la référence : le registre, en LECTURE (R4a #1880).

Spec §4.11 : la référence voit les installations qui se sont déclarées à elle — leur
état, leur canal, leur version, l'administrateur qui en répond, le contrat qu'il a
accepté (archivé sous l'identifiant, D26), le journal des décisions, le dernier
rapport nocturne — et ses ALERTES (R4b #1960), calculées par `registre/alertes`
à chaque lecture : la carte les montre toutes, le courriel de l'opérateur ne
porte que les graves (`utils/sante_plateforme`).

Les GESTES de l'opérateur — valider, suspendre, rétablir, résilier, accorder des
services — passent par `registre/decisions.py`, qui tient les transitions et le
journal ; ils voyagent dans le bail au prochain renouvellement (la référence ne
pousse jamais, règle 5). SUPPRIMER une installation résiliée passe par
`registre/conservation.py` : elle quitte la liste, et sa fiche répond 404.

Réservé à l'OPÉRATEUR de la plateforme (§4.7, règle 7 de §4.11), jamais à
l'administrateur de la copropriété. Ce qu'il lit vient de la base `plateforme` —
jamais d'une copropriété : les seules données personnelles sont celles de
l'administrateur d'INSTALLATION, que le contrat d'inscription lui destine
(`docs/conditions-inscription.md`).

Hors de la référence, ou registre éteint, la liste répond `actif: false` et rien
d'autre : l'écran le dit, au lieu d'une erreur.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, func, select

from app.auth.deps import require_operateur
from app.models.core import Utilisateur
from app.registre import alertes as registre_alertes
from app.registre import base, canaux, conservation, decisions
from app.registre.contrat import Rapport
from app.registre.versions import versions_proposees
from app.registre.modeles import (
    AcceptationConditions,
    ContactInstallation,
    DecisionRegistre,
    Installation,
    RapportInstallation,
    VersionDisponible,
)
from app.utils import horloge
from app.utils.lecture import lire_objet
from app.utils.noms import nom_affiche
from app.utils.recuperer import present_ou_404
from app.utils.services import SERVICES, SERVICES_AUTORISABLES

logger = logging.getLogger("hostachy.registre")

router = APIRouter()


class AlerteLue(BaseModel):
    code: str
    #: le nom de l'alerte (`registre/alertes.GENRES`)
    libelle: str
    #: ce qui a été constaté, avec sa mesure
    message: str
    #: grave → l'opérateur en reçoit un courriel
    grave: bool


class ResumeInstallation(BaseModel):
    identifiant: str
    #: en_attente · active · suspendue · resiliee
    etat: str
    #: `urgence`, une version `X.Y.Z` choisie, ou `main` (la référence) — `canaux.suivi_de`
    canal: str
    version_logicielle: Optional[str] = None
    cree_le: datetime
    #: la dernière fois que l'installation s'est adressée à la référence
    vue_le: Optional[datetime] = None
    #: « Prénom NOM » de l'administrateur d'installation, s'il est connu
    administrateur: Optional[str] = None
    conditions_acceptees: Optional[int] = None
    dernier_rapport_le: Optional[datetime] = None
    #: les services que la référence lui accorde — le bail les porte
    services_autorises: list[str] = []
    #: quand elle reçoit la version de son canal (`registre/canaux.VAGUES`)
    vague: int = 1
    #: la version que son prochain bail portera ; vide : aucune mise à jour
    version_cible: Optional[str] = None
    #: ce que la référence lui reproche, dans l'ordre de la spec (R4b #1960)
    alertes: list[AlerteLue] = []


class ServiceAccordable(BaseModel):
    code: str
    libelle: str


class VersionLue(BaseModel):
    version: str
    #: la date du tag, d'où se comptent les 7 jours
    publiee_le: datetime

    class Config:
        from_attributes = True


class VagueLue(BaseModel):
    code: int
    libelle: str
    #: ce qu'elle installe, en une phrase
    detail: str
    #: offerte quand le canal est Urgence ; sinon, quand c'est une version choisie
    avec_urgence: bool
    #: celle d'une inscription neuve, et du canal Urgence quand on y revient
    defaut: bool = False
    #: ce qu'elle installe aujourd'hui, pour une vague du canal Urgence
    cible: Optional[VersionLue] = None


class VersionsLues(BaseModel):
    #: les dernières mineures, à leur dernier correctif — la liste du canal
    proposees: list[VersionLue] = []
    #: la dernière lecture des releases ; vide : jamais lues
    lues_le: Optional[datetime] = None


class RegistreLu(BaseModel):
    #: le registre est-il servi ici ? Sinon, la liste est vide et l'écran le dit
    actif: bool
    installations: list[ResumeInstallation]
    #: ce que la référence peut accorder — la liste de `utils/services`, seule
    services_accordables: list[ServiceAccordable]
    #: les versions publiées, d'où se choisit le canal (#2210)
    versions: VersionsLues = VersionsLues()
    vagues: list[VagueLue] = []


class DemandeDecision(BaseModel):
    geste: Literal["valider", "suspendre", "retablir", "resilier"]
    motif: str = Field(min_length=1, max_length=400)


class DemandeSuppression(BaseModel):
    motif: str = Field(min_length=1, max_length=400)


class DemandeServices(BaseModel):
    services: list[str]
    motif: str = Field(min_length=1, max_length=300)


class DemandeDistribution(BaseModel):
    #: `urgence`, ou une version `X.Y.Z` publiée
    canal: str = Field(min_length=1, max_length=60)
    vague: int
    motif: str = Field(min_length=1, max_length=300)


class ContactLu(BaseModel):
    prenom: str
    nom: str
    courriel: str
    telephone: Optional[str] = None
    mis_a_jour_le: datetime

    class Config:
        from_attributes = True


class ContratAccepte(BaseModel):
    version: int
    empreinte: str
    texte: str
    accepte_par: str
    accepte_le: datetime

    class Config:
        from_attributes = True


class DecisionLue(BaseModel):
    geste: str
    motif: str
    auteur: str
    cree_le: datetime

    class Config:
        from_attributes = True


class FicheInstallation(ResumeInstallation):
    contact: Optional[ContactLu] = None
    #: les contrats acceptés, le plus récent en tête — le texte EXACT, jamais réécrit
    contrats: list[ContratAccepte]
    #: le journal des décisions, le plus récent en tête
    decisions: list[DecisionLue]
    dernier_rapport: Optional[Rapport] = None
    #: les gestes que l'opérateur peut faire maintenant (`decisions.gestes_possibles`)
    gestes_possibles: list[str] = []
    #: ses services peuvent-ils s'accorder ? Pas pour la référence
    services_modifiables: bool = False


def _alertes_lues(liste: list[registre_alertes.Alerte]) -> list[AlerteLue]:
    return [
        AlerteLue(
            code=a.code,
            libelle=registre_alertes.GENRES[a.code].libelle,
            message=a.message,
            grave=a.grave,
        )
        for a in liste
    ]


def _resume(
    inst: Installation,
    coordonnees: Optional[ContactInstallation],
    dernier_rapport_le: Optional[datetime],
    alertes: list[registre_alertes.Alerte],
    versions: list[VersionDisponible],
    schema: type[ResumeInstallation] = ResumeInstallation,
    **derives,
) -> ResumeInstallation:
    canal, vague = canaux.suivi_de(inst)
    return lire_objet(
        schema,
        inst,
        etat=inst.etat.value,
        canal=canal,
        vague=vague,
        version_cible=canaux.version_cible(inst, versions, horloge.maintenant()),
        administrateur=nom_affiche(coordonnees.prenom, coordonnees.nom) if coordonnees else None,
        dernier_rapport_le=dernier_rapport_le,
        services_autorises=decisions.services_de(inst),
        alertes=_alertes_lues(alertes),
        **derives,
    )


def _lire_rapport(ligne: Optional[RapportInstallation]) -> Optional[Rapport]:
    """Le dernier rapport, relu contre le contrat — illisible, il se tait et se journalise."""
    if ligne is None:
        return None
    try:
        return Rapport.model_validate_json(ligne.corps)
    except ValidationError:
        logger.warning("registre : rapport %s illisible au contrat en vigueur", ligne.id)
        return None


def _accordables() -> list[ServiceAccordable]:
    return [ServiceAccordable(code=c, libelle=SERVICES[c].libelle) for c in SERVICES_AUTORISABLES]


def _vagues(versions: list[VersionDisponible]) -> list[VagueLue]:
    maintenant = horloge.maintenant()

    def cible(code: int) -> Optional[VersionLue]:
        retenue = canaux.CIBLES[code](versions, maintenant) if code in canaux.CIBLES else None
        return VersionLue.model_validate(retenue) if retenue else None

    return [
        VagueLue(
            code=c,
            libelle=v.libelle,
            detail=v.detail,
            avec_urgence=v.avec_urgence,
            defaut=c == canaux.VAGUE_DEFAUT,
            cible=cible(c),
        )
        for c, v in canaux.VAGUES.items()
    ]


def _versions_lues(versions: list[VersionDisponible]) -> VersionsLues:
    return VersionsLues(
        proposees=[VersionLue.model_validate(v) for v in versions_proposees(versions)],
        lues_le=max((v.lue_le for v in versions), default=None),
    )


@router.get("/installations", response_model=RegistreLu)
def lister_installations(_: Utilisateur = Depends(require_operateur)):
    if not base.registre_actif():
        return RegistreLu(
            actif=False, installations=[], services_accordables=_accordables(), vagues=_vagues([])
        )
    with Session(base.moteur()) as session:
        installations = session.exec(
            select(Installation)
            .where(Installation.effacee_le.is_(None))
            .order_by(Installation.identifiant)
        ).all()
        contacts = {c.installation_id: c for c in session.exec(select(ContactInstallation)).all()}
        derniers = dict(
            session.exec(
                select(
                    RapportInstallation.installation_id, func.max(RapportInstallation.recu_le)
                ).group_by(RapportInstallation.installation_id)
            ).all()
        )
        par_installation = registre_alertes.alertes_du_registre(session)
        versions = canaux.versions_disponibles(session)
        return RegistreLu(
            actif=True,
            installations=[
                _resume(
                    i,
                    contacts.get(i.id),
                    derniers.get(i.id),
                    par_installation[i.id],
                    versions,
                )
                for i in installations
            ],
            services_accordables=_accordables(),
            versions=_versions_lues(versions),
            vagues=_vagues(versions),
        )


@contextmanager
def _session_registre() -> Iterator[Session]:
    """Une session sur la base `plateforme` — 404 si le registre n'est pas servi ici."""
    present_ou_404(base.registre_actif() or None, "Registre des installations éteint")
    with Session(base.moteur()) as session:
        yield session


def _installation(session: Session, identifiant: str) -> Installation:
    """L'installation de cet identifiant, ou 404 — une installation supprimée aussi."""
    return present_ou_404(
        session.exec(
            select(Installation).where(
                Installation.identifiant == identifiant, Installation.effacee_le.is_(None)
            )
        ).first(),
        "Installation inconnue",
    )


def _fiche(session: Session, inst: Installation) -> FicheInstallation:
    """La fiche complète : contact, contrats archivés, journal, dernier rapport."""
    contact = session.exec(
        select(ContactInstallation).where(ContactInstallation.installation_id == inst.id)
    ).first()
    contrats = session.exec(
        select(AcceptationConditions)
        .where(AcceptationConditions.installation_id == inst.id)
        .order_by(AcceptationConditions.accepte_le.desc())
    ).all()
    journal = session.exec(
        select(DecisionRegistre)
        .where(DecisionRegistre.installation_id == inst.id)
        .order_by(DecisionRegistre.cree_le.desc(), DecisionRegistre.id.desc())
    ).all()
    rapport = session.exec(
        select(RapportInstallation)
        .where(RapportInstallation.installation_id == inst.id)
        .order_by(RapportInstallation.recu_le.desc())
    ).first()
    return _resume(
        inst,
        contact,
        rapport.recu_le if rapport else None,
        registre_alertes.alertes_du_registre(session)[inst.id],
        canaux.versions_disponibles(session),
        FicheInstallation,
        contact=ContactLu.model_validate(contact) if contact else None,
        contrats=[ContratAccepte.model_validate(c) for c in contrats],
        decisions=[DecisionLue.model_validate(d) for d in journal],
        dernier_rapport=_lire_rapport(rapport),
        gestes_possibles=decisions.gestes_possibles(inst),
        services_modifiables=decisions.decidable(inst),
    )


def _executer(session: Session, geste) -> None:
    """Exécute un geste de l'opérateur et l'enregistre ; un refus des règles devient un 409."""
    try:
        geste()
    except decisions.DecisionRefusee as exc:
        raise HTTPException(409, str(exc)) from None
    session.commit()


def _appliquer(session: Session, inst: Installation, geste) -> FicheInstallation:
    """Applique un geste de l'opérateur, et rend la fiche qu'il laisse."""
    _executer(session, geste)
    session.refresh(inst)
    return _fiche(session, inst)


@router.get("/installations/{identifiant}", response_model=FicheInstallation)
def lire_installation(identifiant: str, _: Utilisateur = Depends(require_operateur)):
    with _session_registre() as session:
        return _fiche(session, _installation(session, identifiant))


@router.post("/installations/{identifiant}/decisions", response_model=FicheInstallation)
def decider_installation(
    identifiant: str, body: DemandeDecision, user: Utilisateur = Depends(require_operateur)
):
    """Valider, suspendre, rétablir, résilier — motivé, inscrit au journal."""
    with _session_registre() as session:
        inst = _installation(session, identifiant)
        auteur = decisions.auteur_de(user.id)
        return _appliquer(
            session,
            inst,
            lambda: decisions.decider(session, inst, body.geste, body.motif, auteur),
        )


@router.put("/installations/{identifiant}/services", response_model=FicheInstallation)
def accorder_services(
    identifiant: str, body: DemandeServices, user: Utilisateur = Depends(require_operateur)
):
    """Les services que l'installation pourra allumer — portés par son prochain bail."""
    with _session_registre() as session:
        inst = _installation(session, identifiant)
        auteur = decisions.auteur_de(user.id)
        return _appliquer(
            session,
            inst,
            lambda: decisions.accorder_services(session, inst, body.services, body.motif, auteur),
        )


@router.put("/installations/{identifiant}/distribution", response_model=FicheInstallation)
def regler_distribution(
    identifiant: str, body: DemandeDistribution, user: Utilisateur = Depends(require_operateur)
):
    """Canal et vague — la version cible de son prochain bail (#2210)."""
    with _session_registre() as session:
        inst = _installation(session, identifiant)
        auteur = decisions.auteur_de(user.id)
        return _appliquer(
            session,
            inst,
            lambda: canaux.regler_distribution(
                session,
                inst,
                canal=body.canal,
                vague=body.vague,
                motif=body.motif,
                auteur=auteur,
            ),
        )


@router.post("/installations/{identifiant}/suppression", status_code=204)
def supprimer_installation(
    identifiant: str, body: DemandeSuppression, user: Utilisateur = Depends(require_operateur)
):
    """Supprime une installation résiliée — motivé, inscrit au journal (`conservation`)."""
    with _session_registre() as session:
        inst = _installation(session, identifiant)
        auteur = decisions.auteur_de(user.id)
        _executer(session, lambda: conservation.supprimer(session, inst, body.motif, auteur))
