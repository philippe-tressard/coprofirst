"""Les demandes qu'une administration doit **trancher** — accès, profil.

Extraites de `core.py` le 17/08/2026, au fil de l'eau : le fichier faisait 1 269
lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé qu'il
grossisse pour recevoir `Utilisateur.decision_compte_le` (#399). La règle est
« on découpe le fichier QUAND on y touche ».

Le périmètre retenu est la **rubrique**, pas un intervalle de lignes : ces deux
files vivaient à 900 lignes l'une de l'autre dans `core.py` alors qu'elles sont
la même notion — une demande déposée par un résident, qui attend une décision, et
qui alimente les mêmes écrans (l'onglet « Comptes & accès » de l'Espace CS, la
file de `/admin`) et le même compteur de tableau de bord.

La **troisième** file, les comptes en attente de validation, n'a pas de table à
elle : c'est un état de `Utilisateur`, qui reste dans `core.py` avec le reste du
modèle. La question « ce compte attend-il une décision ? » vit, elle, dans
`app/utils/comptes.py` — un seul endroit, parce qu'elle était écrite trois fois.

Même geste que `copropriete.py` (13/08), `annonce_hall.py` (15/08) et
`communaute.py` (16/08), et même précaution : les noms restent **ré-exportés par
`core.py`**, si bien qu'aucun module appelant n'a une ligne à changer. C'est
aussi ce qui garantit que les tables restent enregistrées dans les métadonnées
SQLModel — un modèle défini dans un module que personne n'importe n'existe pas
pour `create_all`, ni pour Alembic.
"""

from app.utils import horloge
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel
from pydantic import NaiveDatetime

# ──────────────────────────────────────────────
#  Accès (Vigik / Télécommandes)
# ──────────────────────────────────────────────


class StatutCommande(str, Enum):
    en_attente = "en_attente"
    acceptee = "acceptee"
    refusee = "refusee"


class CommandeAcces(SQLModel, table=True):
    __tablename__ = "commande_acces"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    lot_id: int = Field(foreign_key="lot.id")
    type: str  # vigik | telecommande
    quantite: int = 1
    motif: Optional[str] = None
    statut: StatutCommande = StatutCommande.en_attente
    traite_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    motif_refus: Optional[str] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    traite_le: Optional[NaiveDatetime] = None


# ──────────────────────────────────────────────
#  Demandes de modification de profil
# ──────────────────────────────────────────────


class StatutDemandeProfil(str, Enum):
    en_attente = "en_attente"
    approuvee = "approuvee"
    rejetee = "rejetee"


class DemandeModificationProfil(SQLModel, table=True):
    """Demande de modification du type de résident ou du bâtiment, soumise à validation CS."""

    __tablename__ = "demande_modification_profil"

    id: Optional[int] = Field(default=None, primary_key=True)
    utilisateur_id: int = Field(foreign_key="utilisateur.id", index=True)
    statut_souhaite: Optional[str] = None  # valeur de StatutUtilisateur souhaitée
    batiment_id_souhaite: Optional[int] = Field(default=None, foreign_key="batiment.id")
    motif: Optional[str] = None  # justification libre de l'utilisateur
    statut_demande: StatutDemandeProfil = StatutDemandeProfil.en_attente
    motif_refus: Optional[str] = None
    traite_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    traite_le: Optional[NaiveDatetime] = None


# ──────────────────────────────────────────────
#  Demandes de suppression de compte (#2699)
# ──────────────────────────────────────────────


class StatutDemandeSuppression(str, Enum):
    ouverte = "ouverte"
    traitee = "traitee"
    retiree = "retiree"


class DemandeSuppressionCompte(SQLModel, table=True):
    """Une personne demande l'effacement de SON compte ; l'administration le traite (#2699).

    Même famille que les deux files ci-dessus : une demande déposée par un
    résident, qui attend un geste de l'administration. La référence au compte
    est OBLIGATOIRE : la ligne part avec le compte qu'elle demande d'effacer
    (`suppression_compte.CONTENUS_PERSONNELS`) — le journal de sécurité garde,
    lui, la seule trace du traitement. Règles : `utils/demande_suppression`.
    """

    __tablename__ = "demande_suppression_compte"

    id: Optional[int] = Field(default=None, primary_key=True)
    utilisateur_id: int = Field(foreign_key="utilisateur.id", index=True)
    motif: Optional[str] = None  # facultatif, libre ; effacé avec la ligne
    #  Une chaîne, pas un type énuméré de PostgreSQL : un statut de plus ne
    #  demande alors aucune migration de type (même choix que `courriel_a_classer`).
    statut: str = Field(default=StatutDemandeSuppression.ouverte.value, index=True)
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    traitee_le: Optional[NaiveDatetime] = None
    traitee_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    retiree_le: Optional[NaiveDatetime] = None
