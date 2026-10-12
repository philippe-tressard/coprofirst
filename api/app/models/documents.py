"""Modèles de la BIBLIOTHÈQUE DOCUMENTAIRE — profils d'accès, catégories, documents.

⚠️ Fragment de `app/models/` — extrait de `core.py` le 27/08/2026 (modularité,
rang 1 : `core.py` était à 1 108 lignes et la règle est « on découpe le fichier
QUAND on y touche »). La surface publique NE BOUGE PAS : `core.py` les réexporte,
et les modules qui écrivent `from app.models.core import Document` — ils sont une
vingtaine — n'ont pas une ligne à changer.

La couture est réelle et non un point de coupe arbitraire : ces trois classes
forment l'algorithme d'accès aux documents, celui que `utils/visibility/documents.py`
implémente à lui seul. `Document` est le seul modèle du site dont la lecture passe
par un contrôle à trois couches.

⚠️ Ce module N'IMPORTE PAS `core.py`, et il ne doit jamais le faire : `core.py`
l'importe. Les clés étrangères sont déclarées par CHAÎNE (`foreign_key="ticket.id"`),
ce qui n'exige aucun import — c'est ce qui rend le découpage possible sans cycle.
"""

from datetime import date
from app.utils import horloge
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel
from pydantic import NaiveDatetime


# ──────────────────────────────────────────────
#  Documents
# ──────────────────────────────────────────────


class ProfilAccesDocument(SQLModel, table=True):
    __tablename__ = "profil_acces_document"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)
    libelle: str
    description: str = ""
    roles_autorises: str  # JSON array des statuts
    require_cs: bool = False
    actif: bool = True

    categories: List["CategorieDocument"] = Relationship(back_populates="profil_acces")


class CategorieDocument(SQLModel, table=True):
    __tablename__ = "categorie_document"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)
    libelle: str
    profil_acces_id: int = Field(foreign_key="profil_acces_document.id")
    perimetre_defaut: str = "résidence"
    surcharge_autorisee: bool = False
    actif: bool = True

    profil_acces: Optional[ProfilAccesDocument] = Relationship(back_populates="categories")
    documents: List["Document"] = Relationship(back_populates="categorie")


class Document(SQLModel, table=True):
    __tablename__ = "document"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    fichier_nom: str
    #  La CLÉ du fichier dans le stockage (`prive/…`, #1816) — `stockage().cle_de`.
    #  L'ancien chemin absolu (`fichier_chemin`) reste en base pour la version
    #  précédente, qui le relit (#1757), et part en second temps (`CONTRACTIONS`).
    fichier_cle: Optional[str] = None
    taille_octets: Optional[int] = None
    mime_type: str = "application/octet-stream"
    categorie_id: Optional[int] = Field(default=None, foreign_key="categorie_document.id")
    contrat_id: Optional[int] = Field(default=None, foreign_key="contrat_entretien.id")
    #  Pièces jointes de ticket et d'événement (#390, migration 0158). Une pièce
    #  jointe déposée dans une ÉVOLUTION appartient à son PORTEUR — les trois
    #  tables d'évolution en ont chacune un —, jamais à l'évolution elle-même.
    ticket_id: Optional[int] = Field(default=None, foreign_key="ticket.id")
    evenement_id: Optional[int] = Field(default=None, foreign_key="evenement.id")
    #  Les ANNEXES d'une fiche de « Ma résidence » (migration 0278) : un plan, un
    #  règlement ou un CR d'AG (`document_parent_id`), un rapport de diagnostic,
    #  une règle. Une annexe n'a pas de catégorie : elle se lit comme sa fiche
    #  (`utils/visibility/documents`), et ses gestes vivent dans `utils/annexes`.
    #  ⚠️ Sans `foreign_key` : posées par un `add_column`, que SQLite refuse
    #  d'accompagner d'une contrainte (`CLAUDE.md`, « Migrations Alembic ») — la
    #  déclarer ici ferait diverger une base neuve d'une base migrée.
    document_parent_id: Optional[int] = None
    diagnostic_rapport_id: Optional[int] = None
    regle_residence_id: Optional[int] = None
    profil_acces_override_id: Optional[int] = Field(
        default=None, foreign_key="profil_acces_document.id"
    )
    perimetre: str = "résidence"
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")
    publie_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    publie_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    #  🔴 La DESCRIPTION, ajoutée le 08/09/2026 (#852). Demandée à l'écran :
    #  *« ajouter aussi un champ descriptif »*.
    #
    #  ⚠️ Elle ne double pas le titre : le titre NOMME le document, la
    #  description dit ce qu'il couvre, d'où il vient et ce qu'il ne dit pas.
    #  Sur un règlement de copropriété, c'est la différence entre « Règlement
    #  2024 » et « remplace celui de 1998 ; les annexes 3 et 4 sont chez le
    #  syndic ».
    description: str = ""
    # Champs spécifiques aux CR d'AG
    annee: Optional[int] = None
    date_ag: Optional[date] = Field(default=None)
    #  La date DU DOCUMENT — un règlement de copropriété (migration 0280). La
    #  gouttière de sa fiche la montre ; `publie_le` n'est que la date du dépôt.
    date_document: Optional[date] = Field(default=None)
    #  🔴 DÉPRÉCIÉE au profit de `perimetre_cible` (#470, migration 0160). Elle
    #  n'est plus LUE par le code applicatif ; elle reste comme trace de ce que le
    #  CS avait choisi — l'arborescence des périmètres est administrée, elle bouge,
    #  et l'identifiant de bâtiment reste vrai quand un code est renommé.
    batiments_ids_json: Optional[str] = None  # JSON array ex: "[1,2]" — historique
    #  De quoi PARLE ce document, en codes de périmètre (`["bat:3"]`). Même
    #  convention que `publication.perimetre_cible`.
    #
    #  ⚠️ Descriptif, JAMAIS restrictif : ce sont `perimetre` / `batiment_id` /
    #  `lot_id` qui gouvernent les droits de lecture (`utils/visibility`). La
    #  distinction est l'arbitrage du 29/08/2026 — une AG est visible de tous les
    #  copropriétaires, quel que soit le bâtiment dont elle parle (#617).
    perimetre_cible: Optional[str] = None

    categorie: Optional[CategorieDocument] = Relationship(back_populates="documents")
