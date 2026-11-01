"""Prestataires, contrats d'entretien et notations.

Extrait de `core.py` le 20/08/2026, au fil de l'eau : ce fichier a dépassé son
plafond en recevant la valeur `assurance` (#490), et le garde-fou de
modularité l'a refusé — à juste titre. `core.py` porte encore mille deux cents
lignes et huit domaines ; celui-ci en sort entier.

La coupe suit le domaine, pas la taille : les quatre modèles ci-dessous se
citent les uns les autres (`Prestataire` ↔ `ContratEntretien` ↔
`NotationPrestataire`) et ne sont cités du reste que par leurs clés étrangères.
C'est ce qui rend le déplacement sûr.

⚠️ Ils étaient QUATRE : `DevisPrestataire` est parti avec la prestation
ponctuelle (#603). Sa TABLE, elle, n'est pas supprimée — aucune migration ne la
touche. Un modèle retiré cesse d'être lu ; une table supprimée emporte ses
données, et un retour arrière du code ne les retrouve pas.

⚠️ **`core.py` doit continuer de les importer.** Un modèle défini dans un module
que personne n'a chargé n'existe pas pour `SQLModel.metadata.create_all` : la
table manquerait, sans le moindre message. C'est la raison écrite dans
`models/__init__.py`, et elle vaut ici mot pour mot.
"""

from datetime import date
from app.utils import horloge
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.utils.perimetres import perimetre_cible_json

from app.utils.assiste_ia import AssisteIAMixin
from pydantic import NaiveDatetime

if TYPE_CHECKING:  # pragma: no cover — uniquement pour les annotations
    from app.models.copropriete import Copropriete


class TypePrestataire(str, Enum):
    """Ce que FAIT l'entreprise — son métier, jamais le cadre d'une intervention.

    🔴 « Contrat récurrent » et « Dépannage » en étaient deux valeurs jusqu'au
    28/09/2026 (#1444) : elles disaient le CADRE, qui appartient à chaque
    intervention et non à l'entreprise. Otis entretient l'ascenseur sous contrat
    et le dépanne hors contrat — aucune des deux ne lui allait. Elles sont
    fondues en `maintenance_depannage` (migration 0233) ; « sous contrat » se
    DÉDUIT des contrats actifs de la fiche, il ne se saisit plus.
    """

    maintenance_depannage = "maintenance_depannage"
    travaux = "travaux"
    reglementaire = "reglementaire"
    etudes_expertise = "etudes_expertise"
    gestion = "gestion"


#  `TypeEquipement` est devenu une table administrée (#2442) : `models/equipements`,
#  et `utils/equipements` pour ce que le code en connaît encore (assurance,
#  syndic, autre). ⚠️ Le champ `type_equipement` d'un contrat garde son nom : il
#  désigne la CATÉGORIE du contrat — une assurance ou un mandat de syndic n'est
#  pas un équipement (#490) —, et le renommer toucherait quinze appels.


# ──────────────────────────────────────────────
#  FAQ
# ──────────────────────────────────────────────


#  La marque de l'assistant par le MIXIN (#1327) : la fiche porte désormais une
#  section Description, et toute entité qui en porte une porte la marque.
class Prestataire(AssisteIAMixin, table=True):
    __tablename__ = "prestataire"
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    specialite: str
    type_prestataire: TypePrestataire = TypePrestataire.maintenance_depannage
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts_json: Optional[str] = None  # JSON: [{prenom, nom, fonction, email, telephone}]
    #: Facultatifs (#1327, 25/09/2026) : l'adresse de l'entreprise, texte libre sur
    #: plusieurs lignes, et sa description (HTML riche, section Description).
    adresse: Optional[str] = None
    description: Optional[str] = None
    actif: bool = True
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)

    contrats: List["ContratEntretien"] = Relationship(back_populates="prestataire")


class ContratEntretien(SQLModel, table=True):
    __tablename__ = "contrat_entretien"
    id: Optional[int] = Field(default=None, primary_key=True)
    copropriete_id: int = Field(foreign_key="copropriete.id")
    #: 🔴 DÉRIVÉ de `perimetre_cible`, jamais saisi (10/09/2026). Le serveur le
    #: recalcule à chaque écriture : un seul bâtiment ciblé → son identifiant,
    #: sinon `NULL`.
    #:
    #: Il reste parce que d'autres lectures s'y appuient, et parce qu'un
    #: `DROP COLUMN` sur une colonne portant une clé étrangère est exactement le
    #: genre de migration qui bloque le conteneur au démarrage (`set -e` dans
    #: `start.sh`, arrivé deux fois). Ce n'est PAS une seconde source de vérité :
    #: il n'a plus qu'un seul point d'écriture.
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    #: Le périmètre que ce contrat couvre — même vocabulaire que `Ticket` et
    #: `Publication` : `["résidence"]`, `["bat:3"]`, `["parking"]`…
    #:
    #: Ajouté le 10/09/2026 : un contrat ne pouvait dire QUE son bâtiment, et le
    #: carnet d'entretien ne savait donc pas filtrer sur « Parking » ou
    #: « Caves », qui n'en sont pas. C'est l'arborescence administrée qui décrit
    #: le patrimoine, pas la table des bâtiments — et elle s'enrichit sans
    #: migration, ce qu'une colonne ne sait pas faire.
    perimetre_cible: Optional[str] = Field(default_factory=perimetre_cible_json)
    prestataire_id: int = Field(foreign_key="prestataire.id")

    #: Le CODE d'un équipement (`models/equipements`), en texte depuis la 0321.
    type_equipement: str = Field(default="autre")
    libelle: str
    numero_contrat: Optional[str] = None
    date_debut: date = Field(default_factory=horloge.aujourd_hui)
    duree_initiale_valeur: Optional[int] = None
    duree_initiale_unite: Optional[str] = None  # "mois" ou "ans"
    frequence_type: Optional[str] = None  # "semaines", "mois", "fois_par_an"
    frequence_valeur: Optional[int] = None
    prochaine_visite: Optional[date] = None
    actif: bool = True
    notes: Optional[str] = None
    document_id: Optional[int] = Field(default=None, foreign_key="document.id")

    #  ⚠️ Annotation en CHAÎNE : `Copropriete` n'est importée que sous
    #  `TYPE_CHECKING`, donc absente à l'exécution. La forme non citée
    #  fonctionne aujourd'hui — SQLModel n'évalue pas cette annotation-là —
    #  mais elle dépend d'un détail d'implémentation et d'un ordre d'import.
    #  La citer coûte deux guillemets et supprime la question.
    #  Le pendant du `foreign_keys` posé côté `Copropriete` : les deux bouts
    #  d'une relation doivent désigner le MÊME chemin, sinon SQLAlchemy en
    #  déduit deux relations qui se contredisent.
    copropriete: Optional["Copropriete"] = Relationship(
        back_populates="contrats_entretien",
        sa_relationship_kwargs={"foreign_keys": "[ContratEntretien.copropriete_id]"},
    )
    prestataire: Optional[Prestataire] = Relationship(back_populates="contrats")


class NotationPrestataire(SQLModel, table=True):
    """Notation d'un prestataire (1-5 étoiles), après une visite sous contrat."""

    __tablename__ = "notation_prestataire"
    id: Optional[int] = Field(default=None, primary_key=True)
    prestataire_id: int = Field(foreign_key="prestataire.id")
    note: int  # 1 à 5
    commentaire: Optional[str] = None
    #  ⚠️ `devis_id` n'est plus MAPPÉ (#603) : la prestation ponctuelle a disparu,
    #  et une clé étrangère vers une table démappée empêcherait SQLAlchemy de
    #  configurer ses mappers. La COLONNE reste en base avec ses valeurs — les
    #  notations posées sur un devis gardent leur rattachement, et un retour
    #  arrière du code le retrouve. On cesse de la lire ; on n'efface rien.
    contrat_id: Optional[int] = Field(default=None, foreign_key="contrat_entretien.id")
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
