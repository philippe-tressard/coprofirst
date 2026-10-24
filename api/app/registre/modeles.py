"""Les tables du REGISTRE DES INSTALLATIONS — base `plateforme`, jamais celle de la résidence.

Elles ont leur PROPRE registre SQLAlchemy (`registre_plateforme`), donc leurs propres
métadonnées : `SQLModel.metadata`, celle de la résidence, ne les connaît pas. Ni
`create_all`, ni le schéma initial, ni les migrations de la résidence ne les posent
dans la base d'une copropriété — et le module ne vit pas sous `app/models/` pour la
même raison. Leurs migrations sont celles d'`alembic_plateforme/` (D17, §4.11, règle 7).

Les coordonnées de l'administrateur vivent dans une table À PART
(`contact_installation`) : ce sont les seules données personnelles du registre, et
les effacer à leur échéance (`docs/conditions-inscription.md` §4) supprime une ligne
sans toucher à l'historique de l'installation.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import NaiveDatetime
from sqlalchemy import Text
from sqlalchemy.orm import registry
from sqlmodel import Field, SQLModel

from app.utils import horloge

registre_plateforme = registry()


class TablePlateforme(SQLModel, registry=registre_plateforme):
    """La base des tables de la plateforme : leurs métadonnées sont les SIENNES."""


#: L'identifiant de la référence dans son propre registre (§4.11, règle 7).
IDENTIFIANT_REFERENCE = "CF-000000"


def identifiant_de(numero: int) -> str:
    """L'identifiant qu'on lit dans l'onglet de la référence : `CF-000042`."""
    return f"CF-{numero:06d}"


class EtatInscription(str, Enum):
    en_attente = "en_attente"  # déclarée, pas encore validée : mode limité
    active = "active"
    suspendue = "suspendue"  # lecture seule, export ouvert (D20)
    resiliee = "resiliee"


class Installation(TablePlateforme, table=True):
    __tablename__ = "installation"

    id: Optional[int] = Field(default=None, primary_key=True)
    identifiant: str = Field(unique=True, max_length=20)
    #: Absente pour la référence tant qu'elle n'a pas de clé (R2, R8).
    cle_publique: Optional[str] = Field(default=None, unique=True, max_length=60)
    empreinte_cle: Optional[str] = Field(default=None, max_length=16)
    etat: EtatInscription = Field(default=EtatInscription.en_attente)
    #: `urgence` (la dernière version publiée) ou une version `X.Y.Z` choisie ; `main`
    #: pour la référence seule (`registre/canaux`, #2210).
    canal: str = Field(default="urgence", max_length=60)
    #: Quand elle reçoit la version de son canal (`registre/canaux.VAGUES`).
    vague: int = Field(default=2, sa_column_kwargs={"server_default": "2"})
    #: Plus écrite depuis #2210 — la version choisie est le canal. Relue par
    #: `canaux.suivi_de` tant qu'une image précédente peut la poser.
    version_epinglee: Optional[str] = Field(default=None, max_length=40)
    version_logicielle: Optional[str] = Field(default=None, max_length=40)
    conditions_acceptees: Optional[int] = None
    #: Les services que la référence autorise, en JSON (`registre/decisions.py`) —
    #: portés par le bail ; aucun tant que l'opérateur n'en a pas accordé.
    services_autorises: str = Field(default="[]", sa_type=Text)
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: Optional[NaiveDatetime] = None
    #: La dernière fois que l'installation s'est adressée à la référence.
    vue_le: Optional[NaiveDatetime] = None
    #: Supprimée par l'opérateur après sa résiliation (`registre/conservation`) : hors
    #: de la liste, ses coordonnées et ses rapports effacés. La LIGNE reste — son
    #: numéro fait l'identifiant, qui ne se réattribue jamais.
    effacee_le: Optional[NaiveDatetime] = None


class VersionDisponible(TablePlateforme, table=True):
    """Une version PUBLIÉE : son tag a sa release et l'archive de déploiement (#2210).

    Relue chaque nuit sur le dépôt public (`registre/canaux.relire_versions`) ; c'est
    la liste où l'opérateur choisit, et d'où se calcule la version cible du bail.
    """

    __tablename__ = "version_disponible"

    id: Optional[int] = Field(default=None, primary_key=True)
    version: str = Field(unique=True, max_length=40)
    #: la date du tag — d'où se comptent les 7 jours de l'attente standard
    publiee_le: NaiveDatetime
    lue_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class CanalDistribution(TablePlateforme, table=True):
    """Un CANAL-BRANCHE (`replica`, `special-<nom>`) — PLUS LU depuis #2210.

    Une installation suit désormais Urgence ou une version choisie (`registre/canaux`).
    La table reste le temps qu'une image précédente puisse la lire (migrations
    compatibles sur une version) ; elle se retire dans un second temps.
    """

    __tablename__ = "canal_distribution"

    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(unique=True, max_length=60)
    version: Optional[str] = Field(default=None, max_length=40)
    #: ce que reçoit une vague dont le tour n'est pas venu
    version_precedente: Optional[str] = Field(default=None, max_length=40)
    #: quand `version` a changé — l'instant d'où se comptent les vagues
    avance_le: Optional[NaiveDatetime] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class ContactInstallation(TablePlateforme, table=True):
    """L'administrateur d'une installation — données PERSONNELLES (contrat, `personnel=True`)."""

    __tablename__ = "contact_installation"

    id: Optional[int] = Field(default=None, primary_key=True)
    installation_id: int = Field(foreign_key="installation.id", unique=True)
    prenom: str = Field(max_length=80)
    nom: str = Field(max_length=80)
    courriel: str = Field(max_length=254)
    telephone: Optional[str] = Field(default=None, max_length=30)
    mis_a_jour_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class DecisionRegistre(TablePlateforme, table=True):
    """Le journal des décisions sur une inscription : qui, quand, quoi, pourquoi (§4.11)."""

    __tablename__ = "decision_registre"

    id: Optional[int] = Field(default=None, primary_key=True)
    installation_id: int = Field(foreign_key="installation.id", index=True)
    geste: str = Field(max_length=40)
    motif: str = Field(default="", max_length=500)
    #: « système » pour un geste automatique ; l'identifiant de l'opérateur sinon (R4).
    auteur: str = Field(max_length=60)
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class AcceptationConditions(TablePlateforme, table=True):
    """L'ARCHIVE d'un contrat accepté, rattachée à l'installation (R0 #1876).

    Le texte exact, son empreinte, la date et qui l'a accepté : la preuve de ce qui a
    été convenu, pour l'une et l'autre partie. Une ligne par version acceptée ; elle
    ne se modifie jamais. Conservée 5 ans après la résiliation (conditions §4).
    """

    __tablename__ = "acceptation_conditions"

    id: Optional[int] = Field(default=None, primary_key=True)
    installation_id: int = Field(foreign_key="installation.id", index=True)
    version: int
    empreinte: str = Field(max_length=64)
    texte: str = Field(sa_type=Text)
    #: « Prénom Nom <courriel> » de qui a validé — donnée personnelle (conditions §4).
    accepte_par: str = Field(max_length=300)
    accepte_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class RapportInstallation(TablePlateforme, table=True):
    """Le rapport nocturne d'une installation (R3 #1879), reçu tel quel.

    Aucune donnée de résident (D5) : le contrat le garantit (`contrat.Rapport`),
    et le corps n'est rangé qu'après avoir été validé contre lui. Gardé
    `rapports.CONSERVATION` — l'onglet de la référence (R4) lit le dernier, et
    les alertes l'historique récent.
    """

    __tablename__ = "rapport_installation"

    id: Optional[int] = Field(default=None, primary_key=True)
    installation_id: int = Field(foreign_key="installation.id", index=True)
    recu_le: NaiveDatetime = Field(default_factory=horloge.maintenant, index=True)
    version_logicielle: Optional[str] = Field(default=None, max_length=40)
    #: le rapport, en JSON — validé contre le contrat avant d'être rangé
    corps: str = Field(sa_type=Text)
