"""Admin — l'inscription de cette installation au registre, et son bail (R2 #1878).

Lu et écrit par la carte « Inscription au registre » d'Administration › Maintenance,
réservée à l'OPÉRATEUR (arbitrage du 13/10/2026) : c'est lui qui saisit les
coordonnées de l'administrateur d'installation et accepte les conditions.

🔴 **Mode constat** : l'état rendu s'AFFICHE ; rien ne l'applique encore (R6 #1882).
La règle vit dans `app/inscription/` ; ce routeur l'assemble pour l'écran.
"""

from dataclasses import asdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.auth.deps import require_operateur
from app.config import get_settings
from app.inscription import client, depot
from app.inscription.depot import Contact
from app.models.core import Utilisateur
from app.registre import conditions
from app.utils.lecture import lire_objet
from app.utils.services import SERVICES

router = APIRouter()


class VueInscription(BaseModel):
    #: reference · essai · limitee · active · suspendue — CONSTATÉ, jamais appliqué
    etat: str
    raison: str
    identifiant: Optional[str] = None
    canal: Optional[str] = None
    version_cible: Optional[str] = None
    epoque: Optional[int] = None
    #: les LIBELLÉS des services que la référence autorise (`None` : aucune
    #: restriction) — une réplique n'allume qu'eux (`utils/services.autorise_par_la_reference`)
    services: Optional[list[str]] = None
    echeance: Optional[datetime] = None
    renouvellement_en_retard: bool = False
    inscrite_le: Optional[str] = None
    dernier_renouvellement_le: Optional[str] = None
    dernier_rapport_le: Optional[str] = None
    derniere_erreur: Optional[str] = None
    contact: Optional[Contact] = None
    conditions_acceptees: Optional[int] = None
    conditions_en_vigueur: int
    #: l'opérateur peut-il (re)déclarer l'installation ? Ni la référence, ni un essai
    peut_s_inscrire: bool
    #: `INSTALLATION_ESSAI` posé, mais refusé : ni hôte local, ni base en mémoire
    essai_refuse: bool
    registre_url: str


class ConditionsVue(BaseModel):
    version: int
    empreinte: str
    texte: str


class DemandeInscriptionAdmin(BaseModel):
    prenom: str = Field(min_length=1, max_length=80)
    nom: str = Field(min_length=1, max_length=80)
    courriel: EmailStr
    telephone: Optional[str] = Field(default=None, max_length=30)
    #: la version des conditions MONTRÉE à l'opérateur — refusée si elle a changé depuis
    conditions_acceptees: int
    accepte: bool


def _vue() -> VueInscription:
    """L'état rangé, lu tel quel ; le constat et ce qui se calcule s'y ajoutent."""
    verdict = client.constat_courant()
    etat = depot.lire()
    return lire_objet(
        VueInscription,
        etat,
        **{
            **asdict(verdict),
            "services": (
                [SERVICES[c].libelle for c in SERVICES if c in verdict.services]
                if verdict.services is not None
                else None
            ),
            "identifiant": verdict.identifiant or etat.identifiant,
            "conditions_en_vigueur": conditions.version_en_vigueur(),
            "peut_s_inscrire": verdict.etat not in ("reference", "essai"),
            "essai_refuse": client.essai_declare() and not client.essai_admis(),
            "registre_url": get_settings().registre_url,
        },
    )


def _ou_502(geste) -> VueInscription:
    try:
        geste()
    except client.RegistreInjoignable as exc:
        raise HTTPException(502, str(exc)) from None
    return _vue()


@router.get("/installation/inscription", response_model=VueInscription)
def lire_inscription(_: Utilisateur = Depends(require_operateur)):
    return _vue()


@router.get("/installation/conditions", response_model=ConditionsVue)
def lire_conditions(_: Utilisateur = Depends(require_operateur)):
    """Le texte EN VIGUEUR, tel que la référence l'archivera à l'acceptation."""
    version = conditions.version_en_vigueur()
    return ConditionsVue(
        version=version, empreinte=conditions.empreinte(version), texte=conditions.texte(version)
    )


@router.post("/installation/inscription", response_model=VueInscription)
def inscrire(corps: DemandeInscriptionAdmin, _: Utilisateur = Depends(require_operateur)):
    """Déclare l'installation à la référence — ou rectifie son contact (même clé, même ID)."""
    if not corps.accepte:
        raise HTTPException(400, "L'inscription suppose d'accepter les conditions.")
    if corps.conditions_acceptees != conditions.version_en_vigueur():
        raise HTTPException(409, "Les conditions ont changé : relisez la version en vigueur.")
    contact = Contact(
        prenom=corps.prenom.strip(),
        nom=corps.nom.strip(),
        courriel=str(corps.courriel),
        telephone=(corps.telephone or "").strip() or None,
    )
    return _ou_502(lambda: client.inscrire(contact))


@router.post("/installation/bail", response_model=VueInscription)
def renouveler_bail(_: Utilisateur = Depends(require_operateur)):
    """Demande le bail MAINTENANT, sans attendre la nuit."""
    return _ou_502(client.renouveler)
