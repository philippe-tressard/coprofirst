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

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app import contexte
from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.copropriete import Batiment
from app.models.core import Utilisateur
from app.utils.batiments import libelle_batiment
from app.utils.constats import Constat, applicable
from app.utils.etat_descriptif import EN_TETES_FIXES, Cle, Ligne, lettre_de, nature_de
from app.utils.etat_descriptif_application import (
    LECTURE_ECHEC,
    LECTURE_EN_COURS,
    EtatDescriptifRefuse,
    appliquer,
    constats,
    en_attente,
    entete,
    ouvrir_lecture_ia,
    poser,
)
from app.utils.etat_descriptif_ia import USAGE_LECTURE_ETAT_DESCRIPTIF, remplir_en_tache_de_fond
from app.utils.fichiers import lire_tableur_recu
from app.utils.import_xlsx import lignes_du_classeur
from app.utils.recuperer import ou_404

router = APIRouter()

_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class LigneLue(Ligne):
    #: La nature reconnue (`NatureLot`), `None` si la mention est illisible.
    nature_lue: Optional[str] = None


class BatimentLettre(BaseModel):
    id: int
    libelle: str
    lettre_rcp: Optional[str] = None


class EtatDescriptifLu(BaseModel):
    """L'écran de l'atelier : le fichier en attente, ses contrôles, la correspondance."""

    importe_le: Optional[datetime] = None
    applique_le: Optional[datetime] = None
    cles: list[Cle] = []
    lignes: list[LigneLue] = []
    constats: list[Constat] = []
    #: Les lettres que le fichier cite (bâtiment et circulation), triées.
    lettres_citees: list[str] = []
    batiments: list[BatimentLettre] = []
    applicable: bool = False
    #: L'assistant peut-il lire le règlement ? (usage activé, clé et modèle — #2218)
    ia_disponible: bool = False
    #: L'issue de la lecture qui a rempli l'import : `en_cours`, `terminee`, `echec` —
    #: `None` pour un fichier téléversé.
    lecture_ia: Optional[str] = None
    erreur_ia: Optional[str] = None


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
    from app.utils.llm import config_llm

    ia = config_llm(session, USAGE_LECTURE_ETAT_DESCRIPTIF).pret
    imp = en_attente(session)
    if imp is None:
        return EtatDescriptifLu(batiments=batiments, ia_disponible=ia)
    issue = entete(imp)
    if issue.get("lecture_ia") in (LECTURE_EN_COURS, LECTURE_ECHEC):
        #  Rien à contrôler : la lecture n'a pas (encore) posé de ligne.
        return EtatDescriptifLu(
            importe_le=imp.importe_le,
            batiments=batiments,
            ia_disponible=ia,
            lecture_ia=issue["lecture_ia"],
            erreur_ia=issue.get("erreur_ia"),
        )
    lecture, trouves = constats(session, imp)
    nature = {lu.rang: nature_de(lu.nature) for lu in lecture.lignes}
    return EtatDescriptifLu(
        importe_le=imp.importe_le,
        applique_le=imp.applique_le,
        cles=lecture.cles,
        lignes=[
            LigneLue(
                **lu.model_dump(), nature_lue=nature[lu.rang].value if nature[lu.rang] else None
            )
            for lu in lecture.lignes
        ],
        constats=trouves,
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
        ia_disponible=ia,
        lecture_ia=issue.get("lecture_ia"),
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


@router.post(
    "/admin/etat-descriptif/lire-reglement", response_model=EtatDescriptifLu, status_code=202
)
def lire_le_reglement(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """L'assistant lit le règlement versé et remplit l'atelier, en tâche de fond (#2218).

    Rend aussitôt l'état « lecture en cours » : l'écran le relit jusqu'à l'issue.
    Le fichier en attente est remplacé ; rien ne touche au patrimoine avant « Appliquer ».
    """
    from app.utils import llm_limites
    from app.utils.llm import config_llm
    from app.utils.question_reglement.texte import assembler

    if not config_llm(session, USAGE_LECTURE_ETAT_DESCRIPTIF).pret:
        raise HTTPException(
            400, "L'assistant n'est pas activé pour cette lecture (Admin › Assistant IA)."
        )
    if assembler(session) is None:
        raise HTTPException(400, "Aucun règlement n'est versé (Ma résidence › Règlement).")
    #  La limite d'appels se dit AVANT d'ouvrir la lecture : la tâche la verrait
    #  aussi (`demander`), mais l'écran aurait remplacé ce qui attendait pour rien.
    refus = llm_limites.refus_avant_envoi(session, USAGE_LECTURE_ETAT_DESCRIPTIF, user.id)
    if refus:
        raise HTTPException(429, refus[1])
    imp = ouvrir_lecture_ia(session)
    session.commit()
    background_tasks.add_task(remplir_en_tache_de_fond, contexte.courante(), imp.id, user.id)
    return _etat(session)
