"""Le **point conseil syndical / syndic** et son compte rendu (#2041).

## Ce que les trois tables portent

Pendant une réunion du conseil avec le syndic, un membre du CS ouvre un point
depuis le Reporting › Suivi des affaires et prend le compte rendu en direct,
affaire par affaire. Les règles vivent dans `utils/points_conseil` ; ce module ne
porte que la forme.

| Table | Ce qu'elle porte |
|---|---|
| `point_conseil` | le Quand, le Où, l'état — un point par MODE du rapport |
| `point_conseil_present` | le Qui : membres du CS, du syndic, invités |
| `point_conseil_cr` | le compte rendu d'UNE affaire dans ce point |

| `etat` | ce qu'il dit |
|---|---|
| `en_cours` | la réunion a lieu ; le CR se saisit |
| `a_valider` | « Terminer le point » : les non traitées sont figées |
| `valide` | le CR fait foi (#2042 : validation par les présents) |

## 🔴 Les présents sont FIGÉS

Le nom, la fonction et l'entreprise d'un présent sont recopiés au moment où on
le coche : un CR validé ne doit pas changer parce qu'un membre a quitté
l'annuaire ou changé de nom. Le lien vers la fiche (`membre_cs_id`,
`membre_syndic_id`) reste, sans clé étrangère : la fiche peut disparaître, la
ligne du CR non.

## L'invité (arbitré le 17/10/2026)

Tous ses champs sont facultatifs. Il figure au CR — coordonnées comprises, pour
le rappeler si un complément est nécessaire — et ne reçoit JAMAIS ni le CR ni la
demande de validation. Ses données vivent et s'effacent avec le point.
"""

from __future__ import annotations

from typing import Optional

from pydantic import NaiveDatetime
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.utils import horloge

#: Les modes du rapport qui portent un point — un point par mode (17/10/2026).
MODE_AFFAIRES = "affaires"

#: Les trois états d'un point.
EN_COURS = "en_cours"
A_VALIDER = "a_valider"
VALIDE = "valide"

#: La nature d'un présent.
PRESENT_CS = "cs"
PRESENT_SYNDIC = "syndic"
PRESENT_INVITE = "invite"
NATURES_PRESENT = (PRESENT_CS, PRESENT_SYNDIC, PRESENT_INVITE)


class PointConseil(SQLModel, table=True):
    __tablename__ = "point_conseil"
    id: Optional[int] = Field(default=None, primary_key=True)
    #: Le mode du rapport dont le point traite les affaires.
    mode: str = Field(default=MODE_AFFAIRES, index=True)
    etat: str = Field(default=EN_COURS, index=True)
    #: Quand : le début (requis), la fin (facultative). Heure de Paris, naïve,
    #: telle que saisie — une réunion se date à l'heure murale.
    debut: NaiveDatetime
    fin: Optional[NaiveDatetime] = None
    #: Où : à distance, ou sur place au lieu dit.
    a_distance: bool = False
    lieu: Optional[str] = None
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    #: Les affaires non traitées, figées à « Terminer » : tableau JSON de
    #: `{"id", "numero", "titre"}`. Vide tant que le point est en cours.
    non_traitees_json: str = "[]"
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    termine_le: Optional[NaiveDatetime] = None
    valide_le: Optional[NaiveDatetime] = None
    valide_par_id: Optional[int] = None


class PresentPoint(SQLModel, table=True):
    __tablename__ = "point_conseil_present"
    id: Optional[int] = Field(default=None, primary_key=True)
    point_id: int = Field(foreign_key="point_conseil.id", index=True)
    nature: str
    #: La fiche de l'annuaire, pour un membre du CS ou du syndic — sans clé
    #: étrangère : la ligne du CR survit à la fiche.
    membre_cs_id: Optional[int] = None
    membre_syndic_id: Optional[int] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    entreprise: Optional[str] = None
    fonction: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None


class CompteRenduAffaire(SQLModel, table=True):
    __tablename__ = "point_conseil_cr"
    #: Un compte rendu par affaire et par point — la saisie l'écrase.
    __table_args__ = (
        UniqueConstraint("point_id", "ticket_id", name="uq_point_conseil_cr_affaire"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    point_id: int = Field(foreign_key="point_conseil.id", index=True)
    ticket_id: int = Field(foreign_key="ticket.id", index=True)
    #: Le texte riche (HTML), assaini à l'affichage, rendu en texte au PDF.
    contenu: str = ""
    #: Enregistré en passant à une autre affaire, sans « Sauvegarder ».
    brouillon: bool = False
    #: 🛡️ Lu par le conseil syndical seul.
    conseil_seul: bool = False
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
