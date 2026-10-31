"""Admin — le rôle de cette installation et l'écart de sa version (#1761).

Lu par le bloc « Installation » d'Administration › Maintenance. La règle vit dans
`utils/installation.py` ; ce routeur ne fait que l'assembler pour l'écran.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_operateur
from app.database import get_session
from app.models.core import Utilisateur
from app.utils import installation
from app.utils.config_site import config_site
from app.utils.services import SERVICE_VERIF_VERSION, cle_actif, service_actif

router = APIRouter()


class EtatInstallation(BaseModel):
    role: str  #: reference · replique · inconnu
    libelle: str
    branche: Optional[str] = None
    empreinte: str = ""
    demarree_le: datetime
    verification_active: bool
    #: a_jour · en_retard · ecart · non_verifie
    etat: str
    retard: int = 0
    detail: str = ""
    #: Une seule copropriété, ou une installation commune (#2400) — un constat.
    commune: bool = False
    #: `None` : la déclaration de l'installation commune ne peut pas servir.
    nombre_coproprietes: Optional[int] = 1
    detail_coproprietes: str = ""


@router.get("/installation", response_model=EtatInstallation)
def etat_installation(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_operateur),
):
    role = installation.role_installation()
    libelle, branche = installation.ROLES.get(role, ("Inconnu", None))
    empreinte = installation.empreinte()
    active = service_actif(
        config_site(session, cle_actif(SERVICE_VERIF_VERSION)), SERVICE_VERIF_VERSION
    )
    if branche is None:
        verif = installation.Verification(
            "non_verifie", detail="rôle non déclaré : ROLE_INSTALLATION absent ou mal écrit"
        )
    elif not active:
        verif = installation.Verification(
            "non_verifie", detail="service « Vérification de la version » coupé"
        )
    else:
        verif = installation.verifier(empreinte, branche)
    servies = installation.coproprietes_servies()
    return EtatInstallation(
        role=role,
        libelle=libelle,
        branche=branche,
        empreinte=empreinte,
        demarree_le=installation.DEMARREE_LE,
        verification_active=active,
        etat=verif.etat,
        retard=verif.retard,
        detail=verif.detail,
        commune=servies.commune,
        nombre_coproprietes=servies.nombre,
        detail_coproprietes=servies.detail,
    )
