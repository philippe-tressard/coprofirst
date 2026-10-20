"""Les SCHÉMAS du point CS / Syndic (#2041, #2042, #2082) — propres aux deux
routeurs `points_conseil` et `points_conseil_validation`, à côté d'eux.

Sortis du routeur de la saisie (#2082) pour qu'il reste sous 500 lignes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.points_conseil import IdentitePresent

#: Une ligne de bandeau, pas un texte : les champs de l'invité et le lieu.
COURT = 120


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
    #: Le moyen (`regles.MOYENS`) ; absent, d'un client d'avant le moyen,
    #: `a_distance` fait foi.
    moyen: Optional[str] = None
    a_distance: bool = False
    lieu: Optional[str] = Field(default=None, max_length=COURT)
    presents: list[PresentEntree] = []


class PointCreate(PointEntree):
    mode: str


class PointUpdate(BaseModel):
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    moyen: Optional[str] = None
    a_distance: Optional[bool] = None
    lieu: Optional[str] = Field(default=None, max_length=COURT)
    presents: Optional[list[PresentEntree]] = None


class CrEntree(BaseModel):
    #: Le texte riche ; vide, le compte rendu de l'affaire est retiré.
    contenu: str = Field(default="", max_length=50_000)
    brouillon: bool = False
    #: « CS et présents » (#2082) — le nom de colonne est resté.
    conseil_seul: bool = False
    #: L'état que l'affaire prend À LA VALIDATION (`points_conseil_etats`).
    etat_cible: Optional[str] = None


class PresentRead(IdentitePresent):
    id: int
    #: A reçu la demande de validation (#2042), et quand il a validé.
    destinataire: bool = False
    valide_le: Optional[datetime] = None
    #: Validé POUR lui par l'administrateur, avec son accord (#2082).
    par_derogation: bool = False

    class Config:
        from_attributes = True


class CrRead(BaseModel):
    ticket_id: int
    contenu: str
    brouillon: bool
    conseil_seul: bool
    etat_cible: Optional[str] = None
    mis_a_jour_le: datetime

    class Config:
        from_attributes = True


class PointRead(BaseModel):
    id: int
    mode: str
    etat: str
    debut: datetime
    fin: Optional[datetime] = None
    moyen: Optional[str] = None
    a_distance: bool
    lieu: Optional[str] = None
    #: Le Où tel que le CR l'écrit (`regles.ou_du_point`) — l'écran ne le recompose pas.
    ou: str
    cree_le: datetime
    termine_le: Optional[datetime] = None
    valide_le: Optional[datetime] = None
    #: Le nombre d'envois aux présents (#2082).
    revision: int = 0
    #: Le PDF du CR validé est-il rangé ?
    pdf_range: bool = False

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
    #: « Modifié en révision N » (#2082), ou rien.
    marque: Optional[str] = None


class ValidationRead(BaseModel):
    destinataires: int
    valides: int
    suspendue: bool
    echeance: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommentaireRead(BaseModel):
    auteur: str
    contenu: str
    cree_le: datetime
    #: L'accord écrit par l'administrateur pour le présent (#2082).
    par_derogation: bool = False


class CompteRenduRead(BaseModel):
    point: PointRead
    presents: list[PresentRead]
    abordees: list[AbordeeRead]
    non_traitees: list[AffaireCiteeRead]
    #: Où en est la validation par les présents (#2042).
    validation: ValidationRead
    commentaires: list[CommentaireRead]
    #: La révision que le document montre (#2082) — 0 tant que rien n'est parti.
    revision: int = 0


class RepriseRead(BaseModel):
    """Ce qu'un point ouvert dans un autre mode, il y a moins de deux heures, propose."""

    mode: str
    debut: datetime
    fin: Optional[datetime] = None
    moyen: Optional[str] = None
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


class MoyenRead(BaseModel):
    cle: str
    libelle: str
    avec_lieu: bool

    class Config:
        from_attributes = True


class EtatRead(BaseModel):
    cle: str
    libelle: str


class ParticipantsRead(BaseModel):
    conseil: list[MembreRead]
    syndic: list[MembreRead]
    lieux: list[LieuRead]
    moyens: list[MoyenRead]
    #: Ce que la saisie d'un CR propose pour l'état à la validation (#2082).
    etats_validation: list[EtatRead]


class PointHistoriqueRead(BaseModel):
    """Un point validé, dans l'historique du mode (#2082)."""

    id: int
    debut: datetime
    ou: str
    valide_le: Optional[datetime] = None
    abordees: int
    pdf_range: bool
