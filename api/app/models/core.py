"""
Modèles SQLModel — version 0.1
Correspond au modèle de données défini dans specs/architecture/modele-donnees.md
"""

from datetime import date
from app.utils import horloge
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel
from pydantic import NaiveDatetime

#  Réexportation : `Copropriete`, `Batiment`, `Lot` et `TypeLot` vivent dans
#  `copropriete.py` depuis le 13/08/2026 (modularité, rang 1). Ils restent
#  importables ici pour ne pas avoir à toucher sept modules appelants — dont
#  `auth.py`, que sa taille empêche de recevoir une ligne d'import de plus.
from app.models.copropriete import (
    Batiment as Batiment,
    Copropriete as Copropriete,
    Lot as Lot,
    TypeLot as TypeLot,
)

#  Réexportation : les rôles, les statuts et la hiérarchie qui les départage
#  vivent dans `roles.py` depuis le 15/09/2026 (modularité, rang 1). Ce
#  fichier était à 924 lignes et ne pouvait plus grossir pour recevoir la
#  règle — qui, elle, était écrite deux fois trente lignes plus bas. Ils
#  restent importables ici : aucun des appelants ne change, et SQLModel
#  continue de connaître les énumérations.
from app.models.roles import (
    PRIORITE_ROLE as PRIORITE_ROLE,
    RoleUtilisateur as RoleUtilisateur,
    StatutUtilisateur as StatutUtilisateur,
    rang_role as rang_role,
    role_principal,
)
from app.models.acces import (
    StatutAcces as StatutAcces,
    StatutImport as StatutImport,
    Telecommande as Telecommande,
    TelecommandeImport as TelecommandeImport,
    Vigik as Vigik,
    VigikImport as VigikImport,
)
from app.utils.valeurs import valeur


# ──────────────────────────────────────────────
#  Enums
# ──────────────────────────────────────────────


class TypeLien(str, Enum):
    propriétaire = "propriétaire"  # copropriétaire résident (occupe le lot)
    bailleur = "bailleur"  # copropriétaire non-résident (loue le lot)
    locataire = "locataire"  # locataire d'un bailleur
    mandataire = "mandataire"  # mandataire de gestion (se substitue au bailleur)


#  Le ticket — son vocabulaire (17/08/2026, #415) et ses trois tables
#  (28/09/2026, #779) — vit dans `tickets.py`. Ré-exporté ici, donc aucun des
#  appelants ne change, et les tables restent enregistrées auprès de SQLModel.
from app.models.tickets import (  # noqa: E402
    STATUTS_TICKET_ACTIFS as STATUTS_TICKET_ACTIFS,
    STATUTS_TICKET_CLOS as STATUTS_TICKET_CLOS,
    STATUTS_TICKET_HISTORIQUES as STATUTS_TICKET_HISTORIQUES,
    CategorieTicket as CategorieTicket,
    IntervenantMixin as IntervenantMixin,
    MessageTicket as MessageTicket,
    PrioriteTicket as PrioriteTicket,
    StatutTicket as StatutTicket,
    Ticket as Ticket,
    TicketEvolution as TicketEvolution,
)


#  `TypePrestataire` et `TypeEquipement` sont parties avec leurs modèles dans
#  `models/prestataires.py` ; elles sont réimportées plus bas, avec eux.
#  `StatutDevis` a suivi la prestation ponctuelle (#603) et n'existe plus.


#  `FaqItem` et `RegleResidence` vivent dans `models/residence.py` depuis le
#  30/10/2026 (#2316) ; ré-exportées plus bas, avec les autres.


# ──────────────────────────────────────────────
#  Utilisateurs
# ──────────────────────────────────────────────


class Utilisateur(SQLModel, table=True):
    __tablename__ = "utilisateur"
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    prenom: str
    email: str = Field(unique=True, index=True)
    telephone: Optional[str] = None
    hashed_password: Optional[str] = None
    statut: StatutUtilisateur = StatutUtilisateur.copropriétaire_résident
    role: RoleUtilisateur = RoleUtilisateur.résident  # rôle principal (legacy + fallback)
    roles_json: str = Field(
        default=""
    )  # rôles cumulés, virgule-séparés : "résident,conseil_syndical"
    actif: bool = Field(default=False)  # False = pas (ou plus) autorisé à se connecter
    #  La PREMIÈRE décision de l'administration (#399), puis la fermeture en
    #  cours — `refus` ou `desactivation`, et depuis quand — que la purge compte
    #  (#1822). Ni lues ni écrites à la main : `app/utils/comptes.py`.
    decision_compte_le: Optional[NaiveDatetime] = Field(default=None)
    fermeture_compte: Optional[str] = None
    compte_ferme_le: Optional[NaiveDatetime] = None
    email_verifie: bool = Field(default=False)  # False = email non confirmé
    onboarding_complete: bool = False
    onboarding_etape: int = 0  # 0-4
    photo_url: Optional[str] = None
    #  Où la personne HABITE — facultatif, et distinct de `Lot.etage`, qui
    #  décrit un BIEN (un bailleur a un lot au 4ᵉ et habite ailleurs).
    #  Le pourquoi et la prudence RGPD : migration 0178.
    etage: Optional[int] = None
    societe: Optional[str] = None
    fonction: Optional[str] = None
    consentement_rgpd: bool = False
    opt_out_telemetrie: bool = Field(default=False)
    communaute_interdit: bool = Field(default=False)  # ban permanent (2e infraction)
    communaute_ban_count: int = Field(default=0)  # 0=jamais banni, 1=1er ban, 2+=permanent
    communaute_ban_jusqu_au: Optional[NaiveDatetime] = Field(default=None)  # fin du ban temporaire
    #  Deux clés depuis le 14/08/2026 (#339) — `utils/preferences_mail.py` fait foi
    #  et réapplique ces défauts à la lecture, quel que soit l'état du champ.
    preferences_notifications: str = Field(
        default='{"mon_batiment_mail": true, "autres_batiments_mail": false}'
    )
    #  Préférence d'AFFICHAGE, jamais un droit : ne voir que ses bâtiments (#339).
    #  Elle ne protège rien — la confidentialité reste portée par `public_cible`
    #  et les profils d'accès aux documents, que ce lot ne touche pas.
    restreindre_a_mes_batiments: bool = Field(default=False)
    demarche_arrivant: Optional[str] = Field(default=None)  # nouvel_arrivant | deja_resident | None
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    nom_proprietaire: Optional[str] = None  # pour les locataires : nom du propriétaire bailleur
    nom_aide: Optional[str] = None  # pour aidant/mandataire : nom du copropriétaire aidé
    prenom_aide: Optional[str] = None  # pour aidant/mandataire : prénom du copropriétaire aidé
    last_seen_actualites: Optional[NaiveDatetime] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    derniere_connexion: Optional[NaiveDatetime] = None
    #  L'avertissement avant purge pour inactivité (#1580) — `utils/purge_comptes`.
    purge_avertie_le: Optional[NaiveDatetime] = None

    user_lots: List["UserLot"] = Relationship(back_populates="utilisateur")

    # ── Gestion multi-rôles ──────────────────────────────────────────────────

    @property
    def roles(self) -> list[str]:
        """Liste des rôles de cet utilisateur (depuis roles_json, fallback sur role)."""
        if not self.roles_json:
            v = str(valeur(self.role))
            return [v]
        return [r.strip() for r in self.roles_json.split(",") if r.strip()]

    def has_role(self, *roles: "RoleUtilisateur") -> bool:
        """Retourne True si l'utilisateur possède au moins un des rôles donnés."""
        user_roles = self.roles
        for r in roles:
            rv = str(valeur(r))
            if rv in user_roles:
                return True
        return False

    def ajouter_role(self, role: "RoleUtilisateur | str") -> None:
        """Ajoute un rôle sans doublon. Met aussi à jour `role` (rôle principal)."""
        rv = str(valeur(role))
        current = self.roles
        if rv not in current:
            current.append(rv)
        self.roles_json = ",".join(current)
        self.role = role_principal(current, defaut=rv) or self.role

    def retirer_role(self, role: "RoleUtilisateur | str") -> None:
        """Retire un rôle. Garde au minimum un rôle DE la copropriété (rang > 0) :
        `résident` à défaut — un opérateur sans Admin (#2029) gardait sinon `admin`
        en rôle principal, `role_principal` ne classant pas l'opérateur."""
        rv = str(valeur(role))
        current = [r for r in self.roles if r != rv]
        if not any(rang_role(r) for r in current):
            current.append(RoleUtilisateur.résident.value)
        self.roles_json = ",".join(current)
        self.role = role_principal(current, defaut=RoleUtilisateur.résident.value) or self.role

    tickets: List["Ticket"] = Relationship(
        back_populates="auteur", sa_relationship_kwargs={"foreign_keys": "[Ticket.auteur_id]"}
    )


class UserLot(SQLModel, table=True):
    __tablename__ = "user_lot"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    lot_id: int = Field(foreign_key="lot.id")
    type_lien: TypeLien = TypeLien.propriétaire
    quote_part: Optional[float] = None  # en millièmes
    actif: bool = True

    utilisateur: Optional[Utilisateur] = Relationship(back_populates="user_lots")
    lot: Optional[Lot] = Relationship(back_populates="user_lots")


class Mandat(SQLModel, table=True):
    __tablename__ = "mandat"
    id: Optional[int] = Field(default=None, primary_key=True)
    mandataire_id: int = Field(foreign_key="utilisateur.id")
    bailleur_id: int = Field(foreign_key="utilisateur.id")
    lot_id: int = Field(foreign_key="lot.id")
    type_mandat: str = "location"  # location | juridique
    date_debut: date = Field(default_factory=horloge.aujourd_hui)
    date_fin: Optional[date] = None
    actif: bool = True


# ──────────────────────────────────────────────
#  Files de validation (accès, demandes de profil)
# ──────────────────────────────────────────────
#  Les tables vivent dans `models/validations.py` depuis le 17/08/2026
#  (modularité, rang 1). Ré-exportées ici : les imports existants ne bougent
#  pas, et les modèles restent enregistrés auprès de SQLModel.
from app.models.validations import (  # noqa: E402,F401
    CommandeAcces as CommandeAcces,
    DemandeModificationProfil as DemandeModificationProfil,
    StatutCommande as StatutCommande,
    StatutDemandeProfil as StatutDemandeProfil,
)


#  `Publication` et `PublicationEvolution` — copie gelée des actualités d'avant
#  0210 — ont été supprimées avec leurs tables le 30/09/2026 (#1177, migration
#  0238). Une actualité EST une affaire ; seul `Ticket.promu_depuis_publication_id`
#  garde l'ancien numéro, pour la redirection des liens envoyés.


# ──────────────────────────────────────────────
#  Règles & recommandations de la résidence
# ──────────────────────────────────────────────


from app.models.residence import (  # noqa: E402,F401
    FaqItem as FaqItem,
    RegleResidence as RegleResidence,
)

#  La délégation aidant vit dans `delegations.py` depuis le 28/09/2026 (#779).
from app.models.delegations import (  # noqa: E402,F401
    Delegation as Delegation,
    StatutDelegation as StatutDelegation,
)


# ──────────────────────────────────────────────
#  Prestataires / Contrats
# ──────────────────────────────────────────────
#  Les quatre modèles vivent dans `models/prestataires.py` depuis le
#  20/08/2026 (#490). L'import n'est PAS décoratif : c'est lui qui enregistre
#  les tables auprès de SQLModel avant `create_all`.
from app.models.prestataires import (  # noqa: E402,F401
    ContratEntretien as ContratEntretien,
    NotationPrestataire as NotationPrestataire,
    Prestataire as Prestataire,
    TypeEquipement as TypeEquipement,
    TypePrestataire as TypePrestataire,
)

# ──────────────────────────────────────────────
#  Compteurs — relevés et configuration
# ──────────────────────────────────────────────
#  Les tables vivent dans `models/compteurs.py` depuis le 21/09/2026
#  (modularité, rang 1) : ce fichier était à 831 lignes et le contrôle a refusé
#  qu'il grossisse d'une colonne. Même motif qu'`evenement` (19/08) et
#  `exploitation` (20/09) — ré-exportées, donc les imports existants ne bougent
#  pas et les modèles restent enregistrés auprès de SQLModel.
#
#  Ces deux-là parce qu'elles ne portent AUCUNE `Relationship` : l'extraction
#  ne pouvait rien casser, et c'est ce qui l'a désignée plutôt qu'une autre au
#  milieu d'un lot qui parlait d'autre chose.
from app.models.compteurs import (  # noqa: E402,F401
    CompteurConfig as CompteurConfig,
    ReleveCompteur as ReleveCompteur,
)


# ──────────────────────────────────────────────
#  Notifications
# ──────────────────────────────────────────────


#  Dans `models/notifications.py` depuis le 30/10/2026 (#2316).
from app.models.notifications import Notification as Notification  # noqa: E402,F401

# ──────────────────────────────────────────────
#  Import lots (staging depuis Excel)
# ──────────────────────────────────────────────


#  Les deux vivent dans `models/lot_import.py` depuis le 28/09/2026 (modularité,
#  #779). Ré-exportées ici : les imports existants ne bougent pas.
from app.models.lot_import import LotImport, StatutLotImport  # noqa: E402,F401


# ──────────────────────────────────────────────
#  Calendrier
# ──────────────────────────────────────────────
#  Les tables vivent dans `models/evenement.py` depuis le 19/08/2026
#  (modularité, rang 1) — le module ne portait jusque-là que l'HISTORIQUE d'un
#  événement, pendant que l'événement lui-même restait ici : un module nommé
#  d'après une entité qui ne la contient pas. Ré-exportées : les imports
#  existants ne bougent pas, et les modèles restent enregistrés auprès de
#  SQLModel.
from app.models.evenement import (  # noqa: E402,F401
    Evenement as Evenement,
    StatutKanban as StatutKanban,
    TypeEvenement as TypeEvenement,
)


# ──────────────────────────────────────────────
#  Communauté (sondages, petites annonces, boîte à idées)
# ──────────────────────────────────────────────
#  Les tables vivent dans `models/communaute.py` depuis le 16/08/2026
#  (modularité, rang 1). Ré-exportées ici : les imports existants ne bougent
#  pas, et les modèles restent enregistrés auprès de SQLModel.
from app.models.communaute import (  # noqa: E402,F401
    CategorieAnnonce as CategorieAnnonce,
    CommentaireSondage as CommentaireSondage,
    FluxMasque as FluxMasque,
    Idee as Idee,
    OptionSondage as OptionSondage,
    PetiteAnnonce as PetiteAnnonce,
    ReponseCommunaute as ReponseCommunaute,
    Signalement as Signalement,
    Sondage as Sondage,
    StatutAnnonce as StatutAnnonce,
    TypeAnnonce as TypeAnnonce,
    VoteIdee as VoteIdee,
    VoteSondage as VoteSondage,
)


# ────────────────────────────────────────────
#  Annuaire CS & Syndic
# ────────────────────────────────────────────
#  Les quatre tables vivent dans `models/gouvernance.py` depuis le 22/09/2026
#  (modularité). Ré-exportées ici : les imports existants ne bougent pas, et la
#  table reste enregistrée auprès de SQLModel.
from app.models.gouvernance import (  # noqa: E402
    AgCsInfo as AgCsInfo,
    GenreCivilite as GenreCivilite,
    MembreCS as MembreCS,
    MembreSyndic as MembreSyndic,
    SyndicInfo as SyndicInfo,
)


# ──────────────────────────────────────────────
#  Diagnostics et Contrôles Réglementaires
# ──────────────────────────────────────────────


#  Les deux tables vivent dans `models/diagnostics.py` depuis le 28/09/2026
#  (modularité, #1412). Ré-exportées ici : les imports existants ne bougent pas.
from app.models.diagnostics import DiagnosticRapport, DiagnosticType  # noqa: E402,F401


# ──────────────────────────────────────────────
#  Annonces Hall (Espace CS)
# ──────────────────────────────────────────────
#  La table vit dans `models/annonce_hall.py` depuis le 15/08/2026 (modularité).
#  Ré-exportée ici : les imports existants ne bougent pas.
from app.models.annonce_hall import AnnonceHall  # noqa: E402,F401


#  Le bail et les objets remis au locataire vivent dans `bailleur.py` depuis le
#  28/09/2026 (#779) — le domaine du paquet `routers/bailleur/`.
from app.models.bailleur import (  # noqa: E402,F401
    LocationBail as LocationBail,
    RemiseObjet as RemiseObjet,
    StatutBail as StatutBail,
    StatutObjet as StatutObjet,
    TypeObjet as TypeObjet,
)


#  `StatutDemandeProfil` et `DemandeModificationProfil` sont montés plus haut,
#  avec `CommandeAcces` : les deux files vivaient à 900 lignes l'une de l'autre
#  alors qu'elles sont la même notion (cf. `models/validations.py`).


# ──────────────────────────────────────────────
#  Configuration site (persistance multi-appareils)
# ──────────────────────────────────────────────


#  Dans `models/reglages.py` depuis le 30/10/2026 (#2316).
from app.models.reglages import ConfigSite as ConfigSite  # noqa: E402,F401

# ──────────────────────────────────────────────
#  Messages WhatsApp planifiés — extraits le 05/09/2026 dans `models/whatsapp.py`
#  (modularité, rang 1). Ré-exportés ici : aucun appelant n'a changé.
# ──────────────────────────────────────────────
from app.models.whatsapp import (  # noqa: E402,F401
    WhatsAppLog as WhatsAppLog,
    WhatsAppScheduled as WhatsAppScheduled,
)

#  Réexportation : la bibliothèque documentaire vit dans `documents.py` depuis le
#  27/08/2026 (modularité, rang 1). Ces trois classes restent importables ici —
#  une vingtaine de modules écrivent `from app.models.core import Document`, et un
#  découpage qui casse ses importateurs n'est pas un découpage.
from app.models.documents import (  # noqa: E402
    CategorieDocument as CategorieDocument,
    Document as Document,
    ProfilAccesDocument as ProfilAccesDocument,
)


#  Sauvegardes — `models/sauvegarde.py` depuis le 14/08/2026 (modularité).
from app.models.sauvegarde import (  # noqa: E402,F401
    ConfigSauvegarde,
    HistoriqueSauvegarde,
    StatutSauvegarde,
)

#  Jetons d'authentification — `models/jetons.py` (#833). ⚠️ C'est CET import,
#  comme pour la télémétrie, qui enregistre les tables auprès de SQLModel.
from app.models.jetons import (  # noqa: E402,F401
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
)

#  Télémétrie — `models/telemetrie.py` (plafond de modularité). Réimportée ici :
#  `from app.models.core import TelemetryEvent` reste valide, et c'est cet
#  import qui enregistre les tables auprès de SQLModel.
from app.models.telemetrie import (  # noqa: E402,F401
    TelemetryEvent,
    TelemetryDaily,
    TelemetryMonthly,
    PresenceMensuelle,
    HistoriqueTelemetrie,
)

#  ── L'EXPLOITATION vit dans `models/exploitation.py` (20/09/2026, #1092) ──
#
#  Courriels et maintenance sortis d'ici au titre du découpage au fil de l'eau.
#  Le ré-export garde importables les appelants qui écrivent
#  `from app.models.core import ModeleEmail` — même motif que les documents.
from app.models.exploitation import (  # noqa: E402
    HistoriqueEmail as HistoriqueEmail,
    HistoriqueMaintenance as HistoriqueMaintenance,
    ModeleEmail as ModeleEmail,
    PorteeExecution as PorteeExecution,
    TachePlanifiee as TachePlanifiee,
)
from app.models.affaires_liees import AffaireLiee as AffaireLiee  # noqa: E402,F401
from app.models.fichiers_recus import FichierRecu as FichierRecu  # noqa: E402,F401

#  La synthèse d'une affaire close (#1643) — importée ici pour qu'Alembic la voie.
from app.models.synthese import SyntheseAffaire as SyntheseAffaire  # noqa: E402,F401
from app.models.synthese import TentativeSynthese as TentativeSynthese  # noqa: E402,F401

#  Le règlement de copropriété et les questions qu'on lui pose — vu par Alembic ici.
from app.models.reglement import QuestionReglement as QuestionReglement  # noqa: E402,F401
from app.models.reglement import TexteReglement as TexteReglement  # noqa: E402,F401
