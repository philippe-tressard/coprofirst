"""Les ACCÈS physiques — badges Vigik, télécommandes, et leurs imports.

## Pourquoi ce module (14/09/2026, #779 et #953)

`core.py` portait 1 076 lignes et le plafond de modularité a refusé le champ
« Accès » demandé par #953. C'était le bon refus : ces huit déclarations forment
un **domaine fermé** — l'objet remis à quelqu'un, la table qui l'attribue à
plusieurs copropriétaires, et le staging du classeur Excel qui l'alimente.

C'est le même découpage qu'a subi `routers/acces.py` le 06/09/2026, et pour la
même raison : *un domaine, un module*. On ne découpe pas parce qu'un fichier est
gros, on découpe **quand on y touche**.

⚠️ Ce groupe ne porte **aucun `Relationship` croisé**, et c'est ce qui le rend
extractible : le cycle d'import qui retient `Utilisateur`, `Publication` et
`Ticket` dans `core.py` ne l'atteint pas. Les clés étrangères sont déclarées par
leur nom de table, en chaîne — SQLModel n'a besoin d'aucun import pour cela.

⚠️ Les dix-huit fichiers qui écrivent `from app.models.core import Vigik` ne
changent pas : `core` réexporte ces noms, exactement comme il réexporte déjà
`Lot`, `Batiment` et `Copropriete` depuis `models/copropriete`. Déplacer une
déclaration ne doit pas obliger à relire dix-huit fichiers pour un gain de
rangement.
"""

from app.utils import horloge
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel
from pydantic import NaiveDatetime


class StatutAcces(str, Enum):
    actif = "actif"
    suspendu = "suspendu"
    perdu = "perdu"


class _ObjetAcces(SQLModel):
    """Les champs que partagent `Vigik` et `Telecommande` — écrits UNE fois (#1564).

    Deux tables, un même objet remis à quelqu'un : les deux déclaraient les mêmes
    colonnes, avec le même commentaire de douze lignes. Ce n'est pas une table :
    chaque sous-classe en tire ses propres colonnes.
    """

    code: str = Field(unique=True, index=True)  # référence physique
    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")
    #: Qui l'a EN MAIN, quand on le sait — jamais qui le porte : ses porteurs
    #: se déduisent du lot (`utils/porteurs_acces`, #1194). Facultatif : un
    #: badge rattaché à un lot sans compte n'est dans la main de personne.
    user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    statut: StatutAcces = StatutAcces.actif
    chez_locataire: bool = False  # True = en possession du locataire
    bail_id: Optional[int] = Field(
        default=None, foreign_key="location_bail.id"
    )  # bail actif lors du transfert
    #: 🔹 **Ce que l'accès OUVRE** — une liste de codes de périmètre au
    #: format JSON, comme `perimetre_cible` partout ailleurs.
    #:
    #: ⚠️ `None` n'est pas « toute la copropriété », c'est *« on ne sait
    #: pas »* : une valeur généreuse par défaut sur un droit d'accès se
    #: lirait comme une décision.
    #:
    #: 📖 Pourquoi un périmètre et non un drapeau, et comment il se déduit :
    #: `app/utils/acces_perimetre.py`. La reprise des données existantes :
    #: migration `0190`. Le raisonnement n'est pas recopié ici — il l'était
    #: quatre fois le jour où ce champ est né (#953).
    perimetre_cible: Optional[str] = Field(default=None)
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class Vigik(_ObjetAcces, table=True):
    __tablename__ = "vigik"
    id: Optional[int] = Field(default=None, primary_key=True)


class Telecommande(_ObjetAcces, table=True):
    __tablename__ = "telecommande"
    id: Optional[int] = Field(default=None, primary_key=True)


#  🔴 `UserVigik` et `UserTelecommande` ont été RETIRÉS le 23/09/2026 (#1194) :
#  les porteurs d'un badge se déduisent de son lot (`utils/porteurs_acces`),
#  plus rien ne les écrivait ni ne les lisait. Tables supprimées par 0214.


# ──────────────────────────────────────────────
#  Import télécommandes (staging depuis Excel)
# ──────────────────────────────────────────────


class StatutImport(str, Enum):
    en_attente = "en_attente"  # aucun user matché
    proprietaire_lie = "proprietaire_lie"  # proprio matché, locataire en attente
    resolu = "resolu"  # TC créée, tout lié
    ignore = "ignore"  # admin a choisi d'ignorer cette ligne


class _LigneImportAcces(SQLModel):
    """Résolution, possession et métadonnées d'une ligne de staging — écrites UNE fois.

    `TelecommandeImport` et `VigikImport` redisaient ces champs à l'identique
    (#1564) ; ce qui leur est propre — les colonnes brutes du classeur et le lien
    vers l'objet créé — reste dans chacune.
    """

    # ── Résolution (rempli par l'admin) ──────────────────────────────────
    statut: StatutImport = StatutImport.en_attente

    user_proprietaire_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    user_locataire_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")

    # Possession physique de l'accès
    chez_locataire: bool = False  # en possession du locataire
    refuse_par_locataire: bool = False  # locataire a refusé → reste chez proprio

    # ── Métadonnées ───────────────────────────────────────────────────────
    notes_admin: Optional[str] = None
    importe_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    resolu_le: Optional[NaiveDatetime] = None


class TelecommandeImport(_LigneImportAcces, table=True):
    """Staging des télécommandes importées depuis l'Excel, en attente de résolution
    par l'admin au fur et à mesure des inscriptions des résidents."""

    __tablename__ = "telecommande_import"

    id: Optional[int] = Field(default=None, primary_key=True)

    # ── Données brutes issues de l'Excel ──────────────────────────────────
    nom_proprietaire: str  # colonne A
    nom_locataire: Optional[str] = None  # colonne B — None si vide
    reference: Optional[str] = None  # colonne C — None sur quelques lignes spéciales

    # Lien vers la Telecommande créée lors de la résolution
    telecommande_id: Optional[int] = Field(default=None, foreign_key="telecommande.id")


# ──────────────────────────────────────────────
#  Import vigiks (staging depuis Excel)
# ──────────────────────────────────────────────


class VigikImport(_LigneImportAcces, table=True):
    """Staging des vigiks importés depuis l'Excel, en attente de résolution
    par l'admin au fur et à mesure des inscriptions des résidents."""

    __tablename__ = "vigik_import"

    id: Optional[int] = Field(default=None, primary_key=True)

    # ── Données brutes issues de l'Excel ──────────────────────────────────
    batiment_raw: Optional[str] = None  # col A — numéro de bâtiment
    appartement_raw: Optional[str] = None  # col B — numéro d'appartement
    nom_proprietaire: str  # col C
    nom_locataire: Optional[str] = None  # col D — None si vide
    code: Optional[str] = None  # col E — N° CLÉS

    # Lien vers le Vigik créé lors de la résolution
    vigik_id: Optional[int] = Field(default=None, foreign_key="vigik.id")
