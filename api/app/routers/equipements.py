"""Les équipements — lus par tous, administrés par l'administrateur (#2442).

La liste se lit par toute session : un contrat, une affaire ou une fiche de
prestataire affiche le libellé et l'icône de son équipement, retiré compris. Elle
s'écrit dans Admin › Copropriété › Équipements, réservé à l'administrateur comme
les périmètres — c'est un référentiel qui range les contrats et le carnet.

Les règles (codes système, ce qui se refuse) vivent dans `utils/equipements` ;
ce routeur ne fait que les appliquer.
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.models.equipements import Equipement, EquipementPerimetre
from app.utils import horloge
from app.utils.equipements import (
    CODES_SYSTEME,
    perimetres_lies,
    poser_perimetres,
    pour_affaires,
    tous,
    usages,
)
from app.utils.lecture import lire_objet
from app.utils.recuperer import ou_404
from app.utils.slug import en_slug

router = APIRouter(prefix="/equipements", tags=["equipements"])

#: Un code s'écrit comme ceux de l'ancienne énumération : `porte_parking`.
_FORME_CODE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")
#: Le mot de gouttière tient dans `--largeur-gouttiere`.
ABREVIATION_MAX = 8


class EquipementRead(BaseModel):
    id: int
    code: str
    libelle: str
    abreviation: Optional[str] = None
    icone: str
    description: Optional[str] = None
    ordre: int
    actif: bool
    #: Dérivés : `utils/equipements` en décide, l'écran ne les recopie pas.
    systeme: bool = False
    pour_affaires: bool = True
    perimetres: list[str] = []

    class Config:
        from_attributes = True


class EquipementCreate(BaseModel):
    #: Proposé par l'écran depuis le libellé ; déduit ici s'il manque.
    code: Optional[str] = None
    libelle: str
    abreviation: Optional[str] = None
    icone: str = "wrench"
    description: Optional[str] = None
    ordre: int = 0
    actif: bool = True
    perimetres: list[str] = []


class EquipementUpdate(BaseModel):
    """Tout, sauf le code — immuable : il est enregistré dans ce qui le cite."""

    libelle: Optional[str] = None
    abreviation: Optional[str] = None
    icone: Optional[str] = None
    description: Optional[str] = None
    ordre: Optional[int] = None
    actif: Optional[bool] = None
    perimetres: Optional[list[str]] = None


class UsagesRead(BaseModel):
    contrats: int
    affaires: int
    prestataires: int


def _lire(e: Equipement, lies: dict[int, list[str]]) -> EquipementRead:
    return lire_objet(
        EquipementRead,
        e,
        systeme=e.code in CODES_SYSTEME,
        pour_affaires=pour_affaires(e.code),
        perimetres=lies.get(e.id, []),
    )


def _un(session: Session, e: Equipement) -> EquipementRead:
    return _lire(e, perimetres_lies(session, [e.id]))


def _nettoyer(donnees: dict) -> dict:
    """Libellé obligatoire, abréviation en capitales et bornée, textes vides → `None`."""
    if "libelle" in donnees:
        donnees["libelle"] = (donnees["libelle"] or "").strip()
        if not donnees["libelle"]:
            raise HTTPException(422, "Le libellé est obligatoire.")
    if "abreviation" in donnees:
        abreviation = (donnees["abreviation"] or "").strip().upper()
        if len(abreviation) > ABREVIATION_MAX:
            raise HTTPException(
                422, f"L'abréviation tient en {ABREVIATION_MAX} caractères au plus."
            )
        donnees["abreviation"] = abreviation or None
    if "description" in donnees:
        donnees["description"] = (donnees["description"] or "").strip() or None
    if "icone" in donnees and not (donnees["icone"] or "").strip():
        donnees["icone"] = "wrench"
    return donnees


@router.get("", response_model=list[EquipementRead])
def lister_equipements(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    """Tous, retirés compris : ce qui cite un équipement retiré l'affiche encore."""
    liste = tous(session)
    lies = perimetres_lies(session, [e.id for e in liste])
    return [_lire(e, lies) for e in liste]


@router.get("/{equipement_id}/usages", response_model=UsagesRead)
def usages_equipement(
    equipement_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Ce qui cite cet équipement — l'écran le dit AVANT qu'on tente de le supprimer."""
    e = ou_404(session, Equipement, equipement_id, "Équipement")
    return usages(session, e.code)


@router.post("", response_model=EquipementRead, status_code=201)
def creer_equipement(
    body: EquipementCreate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    donnees = _nettoyer(body.model_dump(exclude={"perimetres", "code"}))
    code = (body.code or "").strip() or en_slug(donnees["libelle"]).replace("-", "_")
    if not _FORME_CODE.match(code):
        raise HTTPException(
            422, "Le code s'écrit en minuscules, chiffres et tirets bas : « porte_garage »."
        )
    if session.exec(select(Equipement).where(Equipement.code == code)).first():
        raise HTTPException(422, f"Le code « {code} » est déjà utilisé.")
    e = Equipement(code=code, **donnees)
    session.add(e)
    session.flush()
    poser_perimetres(session, e, body.perimetres)
    session.commit()
    return _un(session, e)


@router.patch("/{equipement_id}", response_model=EquipementRead)
def modifier_equipement(
    equipement_id: int,
    body: EquipementUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    e = ou_404(session, Equipement, equipement_id, "Équipement")
    donnees = _nettoyer(body.model_dump(exclude_unset=True))
    perimetres = donnees.pop("perimetres", None)
    if donnees.get("actif") is False and e.code in CODES_SYSTEME:
        raise HTTPException(
            422, f"« {e.libelle} » est un équipement système : il ne se retire pas."
        )
    for champ, valeur in donnees.items():
        setattr(e, champ, valeur)
    if perimetres is not None:
        poser_perimetres(session, e, perimetres)
    e.modifie_le = horloge.maintenant()
    session.add(e)
    session.commit()
    return _un(session, e)


@router.delete("/{equipement_id}", status_code=204)
def supprimer_equipement(
    equipement_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Supprime un équipement que plus rien ne cite ; sinon, on le retire (📦)."""
    e = ou_404(session, Equipement, equipement_id, "Équipement")
    if e.code in CODES_SYSTEME:
        raise HTTPException(
            409, f"« {e.libelle} » est un équipement système : il ne se supprime pas."
        )
    cites = usages(session, e.code)
    if any(cites.values()):
        raise HTTPException(
            409,
            f"« {e.libelle} » est cité par {cites['contrats']} contrat(s), "
            f"{cites['affaires']} affaire(s) et {cites['prestataires']} prestataire(s). "
            "Retirez-le de la saisie : ce qui le cite gardera son libellé.",
        )
    for lien in session.exec(
        select(EquipementPerimetre).where(EquipementPerimetre.equipement_id == e.id)
    ).all():
        session.delete(lien)
    session.flush()
    session.delete(e)
    session.commit()
