"""Modèles de la télémétrie d'usage et de son agrégation.

Extraits de `models/core.py` le 12/08/2026 en y ajoutant la colonne `noeud`
(#312) : ce fichier atteignait 1545 lignes et le garde-fou de modularité — rang
1, sans exception — refuse qu'un fichier de plus de 500 lignes grossisse. La
règle est « on découpe QUAND on y touche », et c'est ce domaine-ci que ce lot
touchait.

Ces quatre modèles forment un ensemble autonome : aucune clé étrangère, aucun
type partagé avec le reste des modèles. C'est ce qui rend l'extraction sûre.

⚠️ `core.py` les réimporte, donc `from app.models.core import TelemetryEvent`
continue de fonctionner — c'est la forme utilisée partout, et un lot de
découpage n'a pas à réécrire ses appelants. L'import y est aussi ce qui
enregistre ces tables dans les métadonnées SQLModel : le retirer les ferait
disparaître de la création de schéma.
"""

from app.utils import horloge
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel
from pydantic import NaiveDatetime

# ──────────────────────────────────────────────
#  Télémétrie
# ──────────────────────────────────────────────


class TelemetryEvent(SQLModel, table=True):
    """Événement brut de télémétrie — conservé 30 jours puis agrégé.

    ⚠️ `user_id` a été retirée par la 0246 (#1545) puis RÉTABLIE par la 0247 le
    même jour : son retrait supprimait les statistiques par utilisateur sans
    l'accord de l'utilisateur du produit. Elle revient en colonne simple, SANS
    clé étrangère, comme en production — déclarer `foreign_key` ici ferait
    diverger une base neuve de celle-là.
    """

    __tablename__ = "telemetry_event"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = None
    page: str = Field(index=True)  # ex: /actualites, /tickets
    action: str = "view"  # view | click | submit
    detail: Optional[str] = None  # ex: bouton cliqué, id ticket
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant, index=True)


#: Le drapeau « gestionnaire » des agrégats (0254, 03/10/2026). Les lignes
#: agrégées se séparent en deux séries : celles du GESTIONNAIRE DU SITE
#: (`destinataires.site_manager_user_id` au moment de l'agrégation) et celles de
#: tout le monde d'autre — l'écran les additionne (« avec ») ou n'en lit qu'une
#: (« sans »). Les deux ensembles de comptes sont DISJOINTS, donc les uniques
#: s'additionnent, ce qu'une somme de distincts n'autorise jamais autrement.
#:
#: `None` = ligne agrégée AVANT le drapeau : on ne sait pas la séparer, elle
#: compte dans les deux lectures, et l'écran dit jusqu'à quand c'est le cas
#: (`telemetrie_tableau.non_distingue_jusqu_au`). Les trente derniers jours
#: sont réagrégés depuis les évènements à la première exécution, le reste est
#: de l'historique.
GESTIONNAIRE_DOC = "True : le gestionnaire du site ; False : les autres ; None : non distingué"


class TelemetryDaily(SQLModel, table=True):
    """Agrégation journalière — conservée 12 mois, en deux séries (`gestionnaire`)."""

    __tablename__ = "telemetry_daily"
    id: Optional[int] = Field(default=None, primary_key=True)
    jour: str = Field(index=True)  # YYYY-MM-DD
    page: str
    action: str = "view"
    utilisateurs_uniques: int = 0
    total: int = 0
    gestionnaire: Optional[bool] = Field(default=None, description=GESTIONNAIRE_DOC)


class TelemetryMonthly(SQLModel, table=True):
    """Agrégation mensuelle — conservée 10 ans, en deux séries (`gestionnaire`)."""

    __tablename__ = "telemetry_monthly"
    id: Optional[int] = Field(default=None, primary_key=True)
    mois: str = Field(index=True)  # YYYY-MM
    page: str
    action: str = "view"
    utilisateurs_uniques: int = 0
    total: int = 0
    gestionnaire: Optional[bool] = Field(default=None, description=GESTIONNAIRE_DOC)


class PresenceMensuelle(SQLModel, table=True):
    """Un compte est VENU ce mois-là — et rien d'autre (0254, 03/10/2026).

    Les évènements bruts, seuls à porter `user_id`, vivent 30 jours : au-delà,
    « Qui vient » ne savait plus qui était venu, et la vue Année ne pouvait pas
    le dire. Cette table garde, par mois et par compte, le seul fait « venu »
    — ni page, ni heure, ni nombre —, pendant 12 mois comme l'agrégat
    journalier. Écrite par l'agrégation (une ligne par couple, jamais deux :
    réagréger un jour ne compte personne deux fois), purgée avec elle,
    exportée et effacée avec le reste depuis le profil (`auth_telemetrie`).
    La politique de confidentialité le dit (`TELEMETRIE_CONSERVATION`).
    """

    __tablename__ = "presence_mensuelle"
    __table_args__ = (UniqueConstraint("mois", "user_id", name="uq_presence_mensuelle"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    mois: str = Field(index=True)  # YYYY-MM, mois de Paris
    user_id: int = Field(index=True)


class DerniereVisite(SQLModel, table=True):
    """Le JOUR de la dernière visite d'un compte — un seul, et rien d'autre (#1629, 04/10/2026).

    « Sans visite depuis 60 jours » ne se calculait pas : les évènements, seuls à
    porter le compte au jour près, vivent 30 jours ; la présence mensuelle ne
    sait que le mois. `Utilisateur.derniere_connexion` ne suffit pas non plus :
    elle ne bouge qu'à la saisie du mot de passe, et la session se renouvelle
    seule pendant 7 jours glissants (`/auth/refresh`) — un résident qui vient
    chaque semaine ne se reconnecte jamais, et passerait pour dormant.

    Une ligne par compte, écrite par l'agrégation quotidienne depuis les
    évènements (`utils/retour_comptes.noter_visites`), JAMAIS pour un compte qui
    a refusé la mesure — son refus l'efface. Purgée après 12 mois d'absence,
    exportée et effacée depuis le profil (`auth_telemetrie`). La politique de
    confidentialité le dit (`TELEMETRIE_DERNIERE_VISITE`).
    """

    __tablename__ = "derniere_visite"
    user_id: int = Field(primary_key=True)
    jour: str = Field(index=True)  # YYYY-MM-DD, jour de Paris


class ErreurNavigateur(SQLModel, table=True):
    """Une erreur vue par les résidents, COMPTÉE par jour, page et code (#1631).

    Pas un événement : un compteur, et SANS `user_id` — savoir qu'un écran casse
    ne demande pas de savoir chez qui. Écrit et lu par `utils/erreurs_navigateur`,
    purgé après `CONSERVATION_JOURS` par l'agrégation quotidienne.
    """

    __tablename__ = "erreur_navigateur"
    id: Optional[int] = Field(default=None, primary_key=True)
    jour: str = Field(index=True)  # YYYY-MM-DD, jour de Paris
    page: str
    code: str  # produit par `codeErreur` (front/src/lib/telemetry.ts)
    total: int = 0
    premiere_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    derniere_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class MesureAffichage(SQLModel, table=True):
    """Une durée d'affichage d'écran, telle que le navigateur l'a mesurée (#1632).

    Une ligne par mesure — les centiles ne se calculent pas sur des compteurs —,
    datée au JOUR et SANS `user_id`. Écrite et lue par `utils/mesures_affichage`,
    purgée après `CONSERVATION_JOURS` par l'agrégation quotidienne.
    """

    __tablename__ = "mesure_affichage"
    id: Optional[int] = Field(default=None, primary_key=True)
    jour: str = Field(index=True)  # YYYY-MM-DD, jour de Paris
    page: str  # identifiants masqués : /tickets/#
    indicateur: str  # chargement | navigation
    duree_ms: int


class GesteFormulaire(SQLModel, table=True):
    """Les ouvertures et les envois d'un formulaire, COMPTÉS par jour et par geste (#1633).

    Pas un événement : un compteur, SANS `user_id` — savoir qu'un formulaire
    décourage ne demande pas de savoir qui l'a abandonné. `geste` est un
    IDENTIFIANT de la liste fermée du front (`#lib/gestes`), jamais un contenu.
    Écrit et lu par `utils/gestes_formulaire`, purgé après `CONSERVATION_JOURS`
    par l'agrégation quotidienne.
    """

    __tablename__ = "geste_formulaire"
    id: Optional[int] = Field(default=None, primary_key=True)
    jour: str = Field(index=True)  # YYYY-MM-DD, jour de Paris
    geste: str  # « objet.verbe » : affaire.creer, sondage.voter…
    ouvertures: int = 0
    envois: int = 0


class HistoriqueTelemetrie(SQLModel, table=True):
    """Historique des exécutions d'agrégation de la télémétrie."""

    __tablename__ = "historique_telemetrie"
    id: Optional[int] = Field(default=None, primary_key=True)
    declenchee_par: str = "cron"  # cron | manuelle
    #: Nœud qui a exécuté la tâche — renseigné À L'ÉCRITURE, jamais déduit à
    #: la lecture (cf. `utils/noeud.py`). Nullable et sans valeur par défaut :
    #: les lignes antérieures au 12/08/2026 resteront `None`, et c'est correct
    #: — personne ne sait sur quel nœud elles ont tourné, et l'inventer serait
    #: la faute retirée le 11/08 (#312).
    noeud: Optional[str] = Field(default=None, index=True)  # rpi1 | rpi2
    statut: str = "en_cours"  # en_cours | succes | erreur
    jours_agreges: int = 0
    mois_agreges: int = 0
    events_purges: int = 0
    daily_purges: int = 0
    monthly_purges: int = 0
    duree_secondes: Optional[float] = None
    erreur: Optional[str] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    terminee_le: Optional[NaiveDatetime] = None
