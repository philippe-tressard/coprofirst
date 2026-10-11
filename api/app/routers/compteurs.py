"""Relevés de compteurs et configuration des compteurs.

Sortis de `prestataires.py` le 29/08/2026 : ce fichier dépassait 630 lignes et
le contrôle de modularité (rang 1) a refusé qu'il grossisse — à raison. La coupe
suit le SUJET, pas la commodité : un relevé d'eau ne parle ni d'un prestataire ni
d'un contrat d'entretien, il parle d'un compteur, de sa configuration et de sa
photo justificative.

⚠️ Le préfixe d'URL reste `/prestataires` et le routeur est monté à part dans
`main.py`. Changer les chemins aurait cassé le client TypeScript et les liens
existants pour un gain nul : c'est le RANGEMENT du code qui change, pas l'API.
"""

import logging
import os
from datetime import date, datetime
from app.utils import horloge
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import CompteurConfig, ReleveCompteur, Utilisateur
from app.utils.fichiers import enregistrer_televersement, nom_lisible
from app.utils.stockage import DOSSIER_PRIVE, stockage
from app.utils.recuperer import fichier_ou_404, ou_404

#  Même préfixe que `prestataires.py` : les deux routeurs servent le même écran.
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prestataires", tags=["prestataires"])


# ── Relevés compteurs ────────────────────────────────────────────────────────


class ReleveCreate(BaseModel):
    type_compteur: str
    date_releve: date
    index: Optional[int] = None
    note: Optional[str] = None
    prestataire_id: Optional[int] = None


class ReleveUpdate(BaseModel):
    date_releve: Optional[date] = None
    index: Optional[int] = None
    note: Optional[str] = None
    prestataire_id: Optional[int] = None


class ReleveRead(BaseModel):
    id: int
    type_compteur: str
    date_releve: date
    index: Optional[int] = None
    note: Optional[str] = None
    photo_url: Optional[str] = None
    prestataire_id: Optional[int] = None
    cree_le: datetime
    cree_par_id: Optional[int] = None

    class Config:
        from_attributes = True


@router.get("/releves", response_model=list[ReleveRead])
def list_releves(
    type_compteur: Optional[str] = None,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    q = select(ReleveCompteur)
    if type_compteur:
        q = q.where(ReleveCompteur.type_compteur == type_compteur)
    return session.exec(q.order_by(ReleveCompteur.date_releve.desc())).all()


@router.post("/releves", response_model=ReleveRead, status_code=201)
def create_releve(
    body: ReleveCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    r = ReleveCompteur(**body.model_dump(), cree_le=horloge.maintenant(), cree_par_id=user.id)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@router.patch("/releves/{r_id}", response_model=ReleveRead)
def update_releve(
    r_id: int,
    body: ReleveUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    r = ou_404(session, ReleveCompteur, r_id, "Relevé")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


@router.delete("/releves/{r_id}", status_code=204)
def delete_releve(
    r_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    r = ou_404(session, ReleveCompteur, r_id, "Relevé")
    session.delete(r)
    session.commit()


# ── Photo relevé ──────────────────────────────────────────


@router.post("/releves/{r_id}/photo", response_model=ReleveRead)
async def upload_releve_photo(
    r_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    r = ou_404(session, ReleveCompteur, r_id, "Relevé")
    raw_name = file.filename or "photo"
    #  Les 16 premiers octets suffisent à toutes les signatures connues ;
    #  🔴 Validation ET écriture en un seul geste (#825) : lire seize octets,
    #  rembobiner, vérifier la signature, journaliser, refuser, nommer, copier.
    #  Ces neuf lignes étaient recopiées dans trois routeurs — une copie qui
    #  oublie le `seek(0)` écrit un fichier tronqué sans que rien ne le dise.
    dest = enregistrer_televersement(file, raw_name, user)
    r.photo_url = f"/api/prestataires/releves/{r.id}/photo/{os.path.basename(dest)}"
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


# ── Compteurs config ──────────────────────────────────────


class CompteurConfigCreate(BaseModel):
    type_compteur: str
    label: str
    prestataire_id: Optional[int] = None
    ordre: int = 0


class CompteurConfigUpdate(BaseModel):
    label: Optional[str] = None
    prestataire_id: Optional[int] = None
    ordre: Optional[int] = None


class CompteurConfigRead(BaseModel):
    id: int
    type_compteur: str
    label: str
    prestataire_id: Optional[int] = None
    actif: bool
    ordre: int

    class Config:
        from_attributes = True


@router.get("/compteurs-config", response_model=list[CompteurConfigRead])
def list_compteurs_config(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return session.exec(
        select(CompteurConfig).where(CompteurConfig.actif == True).order_by(CompteurConfig.ordre)  # noqa: E712
    ).all()


@router.post("/compteurs-config", response_model=CompteurConfigRead, status_code=201)
def create_compteur_config(
    body: CompteurConfigCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    # Ensure unique type_compteur slug
    existing = session.exec(
        select(CompteurConfig).where(CompteurConfig.type_compteur == body.type_compteur)
    ).first()
    if existing:
        raise HTTPException(400, "Ce type de compteur existe déjà")
    cfg = CompteurConfig(**body.model_dump())
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


@router.patch("/compteurs-config/{cfg_id}", response_model=CompteurConfigRead)
def update_compteur_config(
    cfg_id: int,
    body: CompteurConfigUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    cfg = ou_404(session, CompteurConfig, cfg_id, "Compteur")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(cfg, k, v)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


@router.delete("/compteurs-config/{cfg_id}", status_code=204)
def delete_compteur_config(
    cfg_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    cfg = ou_404(session, CompteurConfig, cfg_id, "Compteur")
    cfg.actif = False
    session.add(cfg)
    session.commit()


# ── Téléchargement des pièces (CS/admin) ─────────────────────────────────────
#
# Ces fichiers — conditions d'assurance, relevés de
# compteur — vivaient à la racine du volume `uploads`, servi en statique. Deux
# conséquences, corrigées ici le 03/08/2026 :
#
#   1. avant le durcissement du 03/08, ils étaient **publics** ;
#   2. après, `forward_auth` les protégeait — mais il ne vérifie que la présence
#      d'une session, PAS le rôle. Or l'écran qui les affiche est réservé au CS :
#      n'importe quel résident disposant de l'URL pouvait donc les lire.
#
# Servis par ces endpoints, ils suivent enfin la même règle que la bibliothèque
# documentaire : fichier hors du tronc servi, autorisation appliquée à la lecture.


def _servir_fichier_prive(nom: str, noms_autorises: set[str], libelle: str) -> FileResponse:
    """Sert un fichier de `prive/`, à condition qu'il appartienne à la ressource.

    ⚠️ La validation par appartenance n'est pas une formalité : `prive/` contient
    aussi les PV d'assemblée générale et les rapports de diagnostic, qui ont leur
    propre contrôle d'accès. Servir un nom arbitraire depuis cet endpoint le
    contournerait — on ne se contente donc pas d'un `basename`.
    """
    if nom not in noms_autorises:
        raise HTTPException(404, f"{libelle} introuvable")
    chemin = fichier_ou_404(stockage().chemin(f"{DOSSIER_PRIVE}/{nom}"))
    return FileResponse(chemin, filename=nom_lisible(nom))


@router.get("/releves/{r_id}/photo/{nom}")
def download_photo_releve(
    nom: str,
    r_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Photo d'un relevé de compteur — CS et admin uniquement.

    Le nom du fichier est DANS l'URL. La
    première version stockait `/releves/{id}/photo` puis redemandait le nom à
    cette même URL : `basename` rendait alors « photo », et la migration 0125
    avait détruit la seule copie du vrai nom. Toutes les photos de relevé sont
    devenues introuvables (03/08/2026, réparé par la migration 0126).
    """
    r = session.get(ReleveCompteur, r_id)
    if not r or not r.photo_url:
        raise HTTPException(404, "Relevé ou photo introuvable")
    return _servir_fichier_prive(nom, {os.path.basename(r.photo_url)}, "Photo")
