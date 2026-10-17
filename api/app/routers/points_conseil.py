"""Le **point conseil syndical / syndic** du Reporting CS (#2041, maquettes A1 et C1).

Un membre du CS ouvre un point pendant une réunion avec le syndic et prend le
compte rendu en direct, affaire par affaire. Toutes les routes sont réservées au
conseil syndical et à l'administration. Les règles vivent dans
`utils/points_conseil` ; ce routeur ne fait que les appeler.

| Route | Ce qu'elle fait |
|---|---|
| `GET /points-conseil/participants` | l'annuaire du CS et du syndic, les lieux proposés |
| `GET /points-conseil/courant?mode=` | le point du mode, son CR global, et le point à reprendre |
| `POST /points-conseil` | ouvrir un point |
| `PATCH /points-conseil/{id}` | corriger son Quand, son Où, son Qui |
| `PUT /points-conseil/{id}/affaires/{ticket_id}` | écrire le CR d'une affaire (vide : le retirer) |
| `POST /points-conseil/{id}/terminer` | terminer : le CR passe à valider |
| `DELETE /points-conseil/{id}` | abandonner un point ouvert par erreur |
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.models.points_conseil import (
    EN_COURS,
    NATURES_PRESENT,
    PRESENT_INVITE,
    CompteRenduAffaire,
    PointConseil,
    PresentPoint,
)
from app.utils import horloge
from app.utils import points_conseil as regles
from app.utils.annuaire import membres_du_conseil, membres_du_syndic
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/points-conseil", tags=["points-conseil"])

#: Une ligne de bandeau, pas un texte : les champs de l'invité et le lieu.
COURT = 120


# ── Schémas propres à ce routeur ─────────────────────────────────────────


class PresentEntree(BaseModel):
    nature: str
    #: Pour un membre du CS ou du syndic : sa fiche, d'où le nom est recopié.
    membre_id: Optional[int] = None
    #: Pour un invité : tout est facultatif (arbitré le 17/10/2026).
    prenom: Optional[str] = Field(default=None, max_length=COURT)
    nom: Optional[str] = Field(default=None, max_length=COURT)
    entreprise: Optional[str] = Field(default=None, max_length=COURT)
    fonction: Optional[str] = Field(default=None, max_length=COURT)
    telephone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=COURT)


class PointEntree(BaseModel):
    debut: datetime
    fin: Optional[datetime] = None
    a_distance: bool = False
    lieu: Optional[str] = Field(default=None, max_length=COURT)
    presents: list[PresentEntree] = []


class PointCreate(PointEntree):
    mode: str


class PointUpdate(BaseModel):
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    a_distance: Optional[bool] = None
    lieu: Optional[str] = Field(default=None, max_length=COURT)
    presents: Optional[list[PresentEntree]] = None


class CrEntree(BaseModel):
    #: Le texte riche ; vide, le compte rendu de l'affaire est retiré.
    contenu: str = Field(default="", max_length=50_000)
    brouillon: bool = False
    conseil_seul: bool = False


class PresentRead(BaseModel):
    id: int
    nature: str
    membre_cs_id: Optional[int] = None
    membre_syndic_id: Optional[int] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    entreprise: Optional[str] = None
    fonction: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True


class CrRead(BaseModel):
    ticket_id: int
    contenu: str
    brouillon: bool
    conseil_seul: bool
    mis_a_jour_le: datetime

    class Config:
        from_attributes = True


class PointRead(BaseModel):
    id: int
    mode: str
    etat: str
    debut: datetime
    fin: Optional[datetime] = None
    a_distance: bool
    lieu: Optional[str] = None
    cree_le: datetime
    termine_le: Optional[datetime] = None
    valide_le: Optional[datetime] = None

    class Config:
        from_attributes = True


class AffaireCiteeRead(BaseModel):
    id: int
    numero: str
    titre: str

    class Config:
        from_attributes = True


class AbordeeRead(BaseModel):
    affaire: AffaireCiteeRead
    cr: CrRead


class CompteRenduRead(BaseModel):
    point: PointRead
    presents: list[PresentRead]
    abordees: list[AbordeeRead]
    non_traitees: list[AffaireCiteeRead]


class RepriseRead(BaseModel):
    """Ce qu'un point ouvert dans un autre mode, il y a moins de deux heures, propose."""

    mode: str
    debut: datetime
    fin: Optional[datetime] = None
    a_distance: bool
    lieu: Optional[str] = None
    cree_le: datetime
    presents: list[PresentRead]


class CourantRead(BaseModel):
    compte_rendu: Optional[CompteRenduRead] = None
    reprise: Optional[RepriseRead] = None


class MembreRead(BaseModel):
    id: int
    prenom: str
    nom: str
    fonction: Optional[str] = None


class LieuRead(BaseModel):
    libelle: str
    adresse: str

    class Config:
        from_attributes = True


class ParticipantsRead(BaseModel):
    conseil: list[MembreRead]
    syndic: list[MembreRead]
    lieux: list[LieuRead]


# ── Lectures ─────────────────────────────────────────────────────────────


def _presents_read(presents: list[PresentPoint]) -> list[PresentRead]:
    return [PresentRead.model_validate(p) for p in presents]


def _compte_rendu_read(session: Session, point: PointConseil, user: Utilisateur):
    cr = regles.compte_rendu(session, point, user)
    return CompteRenduRead(
        point=PointRead.model_validate(cr.point),
        presents=_presents_read(cr.presents),
        abordees=[
            AbordeeRead(affaire=AffaireCiteeRead.model_validate(a), cr=CrRead.model_validate(c))
            for a, c in cr.abordees
        ],
        non_traitees=[AffaireCiteeRead.model_validate(a) for a in cr.non_traitees],
    )


@router.get(
    "/participants", response_model=ParticipantsRead, summary="Annuaire et lieux (CS/Admin)"
)
def participants(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return ParticipantsRead(
        conseil=[MembreRead(**m) for m in membres_du_conseil(session)],
        syndic=[MembreRead(**m) for m in membres_du_syndic(session)],
        lieux=[LieuRead.model_validate(lieu) for lieu in regles.lieux_proposes(session)],
    )


@router.get("/courant", response_model=CourantRead, summary="Le point du mode (CS/Admin)")
def courant(
    mode: str,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    regles.exiger_mode(mode)
    point = regles.point_courant(session, mode)
    reprise = regles.point_a_reprendre(session, mode)
    return CourantRead(
        compte_rendu=_compte_rendu_read(session, point, user) if point else None,
        reprise=(
            RepriseRead(
                **PointRead.model_validate(reprise).model_dump(
                    include={"mode", "debut", "fin", "a_distance", "lieu", "cree_le"}
                ),
                presents=_presents_read(regles.presents_du_point(session, reprise.id)),
            )
            if reprise
            else None
        ),
    )


# ── Gestes ───────────────────────────────────────────────────────────────


def _present(session: Session, entree: PresentEntree) -> PresentPoint:
    if entree.nature not in NATURES_PRESENT:
        raise HTTPException(422, "Nature de présent inconnue")
    if entree.nature != PRESENT_INVITE:
        return regles.present_depuis_annuaire(session, entree.nature, entree.membre_id)
    champs = entree.model_dump(exclude={"nature", "membre_id"})
    return PresentPoint(
        nature=PRESENT_INVITE, **{k: (v or "").strip() or None for k, v in champs.items()}
    )


def _lieu(lieu: Optional[str]) -> Optional[str]:
    return (lieu or "").strip() or None


@router.post(
    "", response_model=CompteRenduRead, status_code=201, summary="Ouvrir un point (CS/Admin)"
)
def ouvrir(
    body: PointCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    regles.exiger_mode(body.mode)
    courant_ = regles.point_courant(session, body.mode)
    if courant_ and courant_.etat == EN_COURS:
        raise HTTPException(409, "Un point est déjà en cours pour ce rapport")
    presents = [_present(session, p) for p in body.presents]
    point = PointConseil(
        mode=body.mode,
        debut=body.debut,
        fin=body.fin,
        a_distance=body.a_distance,
        lieu=_lieu(body.lieu),
        auteur_id=user.id,
    )
    session.add(point)
    session.flush()
    regles.remplacer_presents(session, point, presents)
    session.commit()
    session.refresh(point)
    return _compte_rendu_read(session, point, user)


@router.patch("/{point_id}", response_model=CompteRenduRead, summary="Corriger le point (CS/Admin)")
def corriger(
    point_id: int,
    body: PointUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = regles.exiger_en_cours(ou_404(session, PointConseil, point_id, "Point"))
    champs = body.model_dump(exclude_unset=True, exclude={"presents"})
    for cle, valeur in champs.items():
        setattr(point, cle, valeur)
    if "lieu" in champs:
        point.lieu = _lieu(point.lieu)
    if body.presents is not None:
        regles.remplacer_presents(session, point, [_present(session, p) for p in body.presents])
    point.mis_a_jour_le = horloge.maintenant()
    session.add(point)
    session.commit()
    session.refresh(point)
    return _compte_rendu_read(session, point, user)


@router.put(
    "/{point_id}/affaires/{ticket_id}",
    response_model=CompteRenduRead,
    summary="Écrire le CR d'une affaire (CS/Admin)",
)
def ecrire_cr(
    point_id: int,
    ticket_id: int,
    body: CrEntree,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = regles.exiger_en_cours(ou_404(session, PointConseil, point_id, "Point"))
    regles.exiger_affaire_du_point(session, point, ticket_id, user)
    cr = regles.cr_de(session, point.id, ticket_id)
    if not body.contenu.strip():
        if cr:
            session.delete(cr)
    else:
        cr = cr or CompteRenduAffaire(point_id=point.id, ticket_id=ticket_id)
        cr.contenu = body.contenu
        cr.brouillon = body.brouillon
        cr.conseil_seul = body.conseil_seul
        cr.auteur_id = user.id
        cr.mis_a_jour_le = horloge.maintenant()
        session.add(cr)
    point.mis_a_jour_le = horloge.maintenant()
    session.add(point)
    session.commit()
    session.refresh(point)
    return _compte_rendu_read(session, point, user)


@router.post(
    "/{point_id}/terminer", response_model=CompteRenduRead, summary="Terminer le point (CS/Admin)"
)
def terminer(
    point_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    point = regles.terminer(session, ou_404(session, PointConseil, point_id, "Point"), user)
    session.commit()
    session.refresh(point)
    return _compte_rendu_read(session, point, user)


@router.delete("/{point_id}", status_code=204, summary="Abandonner un point en cours (CS/Admin)")
def abandonner(
    point_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    regles.supprimer_point(session, ou_404(session, PointConseil, point_id, "Point"))
    session.commit()
