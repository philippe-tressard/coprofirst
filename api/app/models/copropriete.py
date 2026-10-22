"""Copropriété, bâtiments et lots — le patrimoine PHYSIQUE.

Extrait de `core.py` le 13/08/2026. Ce fichier-là dépasse 1 500 lignes, et la
règle de modularité (rang 1) refuse qu'un fichier au-delà de 500 lignes
grossisse pour une nouvelle fonctionnalité — ici l'ajout du décompte des lots
principaux. La coupe suit une frontière réelle : ces trois tables décrivent ce
qui est BÂTI, quand `core.py` garde les personnes, les échanges et l'exploitation.

⚠️ À ne pas confondre avec `perimetre.py`, qui décrit le patrimoine LOGIQUE —
l'arborescence éditable qui sert à localiser une demande. Un bâtiment existe ici
en tant que construction, et là-bas en tant que cible possible.

Ces noms restent importables depuis `app.models.core`, qui les réexporte : sept
modules les y prennent déjà, dont `auth.py` (736 lignes) qu'une ligne d'import
de plus ferait refuser par le même contrôle de modularité.
"""

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

#  Références différées vers `core.py`. Sous `TYPE_CHECKING` uniquement :
#  à l'exécution, `core.py` importe CE module (réexportation), et un import
#  réciproque réel formerait un cycle. SQLAlchemy, lui, résout ces noms par
#  son registre de classes, pas par l'espace de noms du module — d'où les
#  chaînes. Sans cette déclaration, `ruff` signale F821 à juste titre : rien
#  dans ce fichier ne dit ce qu'est un `Ticket`.
if TYPE_CHECKING:  # pragma: no cover
    from app.models.core import ContratEntretien, Ticket, UserLot


class TypeLot(str, Enum):
    appartement = "appartement"
    cave = "cave"
    parking = "parking"


# ──────────────────────────────────────────────
#  Copropriété
# ──────────────────────────────────────────────


class Copropriete(SQLModel, table=True):
    __tablename__ = "copropriete"
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    adresse: str
    annee_construction: Optional[int] = None
    #: Les DEUX décomptes de la fiche du registre national (ANAH), qui ne
    #: disent pas la même chose et qu'un seul champ confondait :
    #:  - `nb_lots_total` — TOUS les lots, caves et parkings compris ;
    #:  - `nb_lots_principaux` — ceux à usage d'habitation, de commerces et de
    #:    bureaux, le décompte qui porte les seuils réglementaires et qui
    #:    répond à « combien de foyers ici ».
    #: Exemple réel : 195 et 63. Les additionner ou les confondre fait dire au
    #: produit une taille de copropriété fausse du simple au triple.
    nb_lots_total: Optional[int] = None
    nb_lots_principaux: Optional[int] = None
    numero_immatriculation: Optional[str] = None  # ANAH/ALUR
    #: Le mois (1 à 12) où commence l'exercice comptable voté en AG — `None` :
    #: l'année civile. Il borne la moyenne à laquelle la synthèse d'une affaire
    #: close se compare (#1643) ; aucune autre notion d'exercice n'existe.
    mois_debut_exercice: Optional[int] = None
    #: 🔴 LES DEUX CONTRATS DE RÉFÉRENCE DE LA FICHE.
    #:
    #: L'assurance était DÉDUITE (« le contrat actif le plus récent gagne »,
    #: #490) : une règle juste et implicite, que rien à l'écran n'énonçait. Elle
    #: devient un choix, et le syndic entre dans le même moule — le prestataire
    #: porte le CABINET, `MembreSyndic` garde les PERSONNES et le routage des
    #: courriels ne bouge pas.
    #:
    #: ⚠️ Ces deux champs désignent un contrat, jamais un prestataire. Pointer
    #: le prestataire rouvrirait la divergence que #490 a fermée : le
    #: prestataire choisi pourrait cesser d'être celui du contrat affiché, et
    #: rien ne dirait lequel fait foi.
    assurance_contrat_id: Optional[int] = Field(default=None, foreign_key="contrat_entretien.id")
    syndic_contrat_id: Optional[int] = Field(default=None, foreign_key="contrat_entretien.id")

    #  🔴 `assurance_compagnie`, `assurance_numero_police` et `assurance_echeance` ont QUITTÉ le
    #  modèle (#2059, premier temps) : gardées depuis #490 pour un retour arrière, rien ne les lisait.
    #  Les colonnes (nullables) restent en base le temps d'une version — `CONTRACTIONS` annonce
    #  leur retrait ; la fiche lit l'assurance sur le CONTRAT (`assurance_du_contrat`).
    photo_url: Optional[str] = None
    nb_parkings_communs: int = 0

    batiments: List["Batiment"] = Relationship(back_populates="copropriete")
    #  🔴 `foreign_keys` EST OBLIGATOIRE ICI depuis que la copropriété désigne
    #  ses deux contrats de référence (#553). Trois chemins relient désormais les
    #  deux tables — `contrat.copropriete_id`, `copropriete.assurance_contrat_id`
    #  et `copropriete.syndic_contrat_id` — et SQLAlchemy refuse de choisir :
    #
    #      AmbiguousForeignKeysError: there are multiple foreign key paths
    #
    #  ⚠️ Le défaut ne se voit pas à l'import : il éclate à la PREMIÈRE requête,
    #  et il emporte tout le mappage — 103 tests tombés d'un coup, dont ceux du
    #  planificateur WhatsApp, qui n'ont rien à voir. C'est la bonne façon
    #  d'échouer : bruyante et immédiate.
    contrats_entretien: List["ContratEntretien"] = Relationship(
        back_populates="copropriete",
        sa_relationship_kwargs={"foreign_keys": "[ContratEntretien.copropriete_id]"},
    )


class Batiment(SQLModel, table=True):
    __tablename__ = "batiment"
    id: Optional[int] = Field(default=None, primary_key=True)
    copropriete_id: int = Field(foreign_key="copropriete.id")
    numero: str  # A, B, C, D…
    nb_etages: int = 0
    sous_sol: bool = False
    specificites: Optional[str] = None
    nb_appartements: int = 0
    nb_caves: int = 0
    nb_parkings: int = 0
    nb_locaux_commerciaux: int = 0

    copropriete: Optional[Copropriete] = Relationship(back_populates="batiments")
    lots: List["Lot"] = Relationship(back_populates="batiment")


class Lot(SQLModel, table=True):
    __tablename__ = "lot"
    id: Optional[int] = Field(default=None, primary_key=True)
    batiment_id: Optional[int] = Field(
        default=None, foreign_key="batiment.id"
    )  # None pour les parkings
    numero: str
    type: TypeLot = TypeLot.appartement
    type_appartement: Optional[str] = None  # Studio, T1, T2…
    etage: Optional[int] = None
    superficie: Optional[float] = None

    batiment: Optional[Batiment] = Relationship(back_populates="lots")
    user_lots: List["UserLot"] = Relationship(back_populates="lot")
    tickets: List["Ticket"] = Relationship(back_populates="lot")
