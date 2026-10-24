"""L'atelier de l'état descriptif du règlement — téléverser, contrôler, appliquer (#2213).

Inclus par `routers/lots.py`, comme l'atelier de la liste du syndic
(`lots_imports.py`) : même préfixe `/lots/admin/…`, même dépendance
(`require_cs_or_admin`), même onglet de l'administration (Imports, source « État
descriptif »).

La lecture, les contrôles et l'application vivent dans `utils/etat_descriptif` et
`utils/etat_descriptif_application` : ce routeur ne fait que les exposer.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.copropriete import Batiment
from app.models.core import Utilisateur
from app.utils.batiments import libelle_batiment
from app.utils.etat_descriptif import EN_TETES_FIXES, applicable, lettre_de, nature_de
from app.utils.etat_descriptif_application import (
    EtatDescriptifRefuse,
    appliquer,
    constats,
    en_attente,
    poser,
)
from app.utils.fichiers import lire_tableur_recu
from app.utils.import_xlsx import lignes_du_classeur
from app.utils.recuperer import ou_404

router = APIRouter()

_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ConstatLu(BaseModel):
    code: str
    gravite: str
    message: str
    lots: list[str] = []


class CleLue(BaseModel):
    code: str
    libelle: str
    denominateur: int


class LigneLue(BaseModel):
    rang: int
    lot: str
    batiment: Optional[str] = None
    nature: Optional[str] = None
    #: La nature reconnue (`NatureLot`), `None` si la mention est illisible.
    nature_lue: Optional[str] = None
    numero_usage: Optional[str] = None
    niveau: Optional[str] = None
    circulation: Optional[str] = None
    lot_origine: Optional[str] = None
    source: Optional[str] = None
    quotes: dict[str, int] = {}


class BatimentLettre(BaseModel):
    id: int
    libelle: str
    lettre_rcp: Optional[str] = None


class EtatDescriptifLu(BaseModel):
    """L'écran de l'atelier : le fichier en attente, ses contrôles, la correspondance."""

    importe_le: Optional[datetime] = None
    applique_le: Optional[datetime] = None
    cles: list[CleLue] = []
    lignes: list[LigneLue] = []
    constats: list[ConstatLu] = []
    #: Les lettres que le fichier cite (bâtiment et circulation), triées.
    lettres_citees: list[str] = []
    batiments: list[BatimentLettre] = []
    applicable: bool = False


class Correspondance(BaseModel):
    batiment_id: int
    #: Vide efface la lettre.
    lettre_rcp: Optional[str] = None


class Correspondances(BaseModel):
    correspondances: list[Correspondance]


class Application(BaseModel):
    lots: int
    cles_creees: int
    quotes_modifiees: int
    perimetres_modifies: int


def _etat(session: Session) -> EtatDescriptifLu:
    batiments = [
        BatimentLettre(id=b.id, libelle=libelle_batiment(b), lettre_rcp=b.lettre_rcp)
        for b in session.exec(select(Batiment).order_by(Batiment.id)).all()
    ]
    imp = en_attente(session)
    if imp is None:
        return EtatDescriptifLu(batiments=batiments)
    lecture, trouves = constats(session, imp)
    nature = {lu.rang: nature_de(lu.nature) for lu in lecture.lignes}
    return EtatDescriptifLu(
        importe_le=imp.importe_le,
        applique_le=imp.applique_le,
        cles=[CleLue(**vars(c)) for c in lecture.cles],
        lignes=[
            LigneLue(**vars(lu), nature_lue=nature[lu.rang].value if nature[lu.rang] else None)
            for lu in lecture.lignes
        ],
        constats=[ConstatLu(**{**vars(c), "lots": list(c.lots)}) for c in trouves],
        lettres_citees=sorted(
            {
                lettre_de(brut)
                for lu in lecture.lignes
                for brut in (lu.batiment, lu.circulation)
                if lettre_de(brut)
            }
        ),
        batiments=batiments,
        applicable=imp.applique_le is None and applicable(trouves),
    )


@router.get("/admin/etat-descriptif", response_model=EtatDescriptifLu)
def lire_etat_descriptif(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return _etat(session)


@router.get("/admin/etat-descriptif/gabarit")
def gabarit_etat_descriptif(_: Utilisateur = Depends(require_cs_or_admin)):
    """Le classeur VIDE, en-têtes seuls : produit par la même source que la lecture."""
    import openpyxl

    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "Etat descriptif"
    feuille.append([*EN_TETES_FIXES, "Charges générales /10000"])
    tampon = io.BytesIO()
    classeur.save(tampon)
    tampon.seek(0)
    return StreamingResponse(
        tampon,
        media_type=_TYPE_XLSX,
        headers={"Content-Disposition": 'attachment; filename="etat-descriptif.xlsx"'},
    )


@router.post("/admin/etat-descriptif", response_model=EtatDescriptifLu, status_code=201)
async def televerser_etat_descriptif(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Remplace le fichier en attente ; rien ne touche au patrimoine avant « Appliquer »."""
    contenu = await lire_tableur_recu(file, user)
    poser(session, lignes_du_classeur(contenu))
    session.commit()
    return _etat(session)


@router.put("/admin/etat-descriptif/lettres", response_model=EtatDescriptifLu)
def saisir_lettres(
    body: Correspondances,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """La lettre de l'acte de chaque bâtiment — saisie, jamais déduite de l'ordre."""
    for corr in body.correspondances:
        batiment = ou_404(session, Batiment, corr.batiment_id, "Bâtiment")
        lettre = (corr.lettre_rcp or "").strip() or None
        batiment.lettre_rcp = lettre[:8] if lettre else None
        session.add(batiment)
    session.commit()
    return _etat(session)


@router.post("/admin/etat-descriptif/appliquer", response_model=Application)
def appliquer_etat_descriptif(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    try:
        bilan = appliquer(session)
    except EtatDescriptifRefuse as exc:
        session.rollback()
        raise HTTPException(409, str(exc))
    session.commit()
    return Application(**bilan)
