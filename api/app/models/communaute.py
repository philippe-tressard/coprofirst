"""Modèles de la rubrique **Communauté** — sondages, petites annonces, idées.

Extraits de `core.py` le 16/08/2026, au fil de l'eau : le fichier faisait 1 415
lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé qu'il
grossisse en recevant le ciblage standard du sondage. La règle est « on découpe
le fichier QUAND on y touche ».

Le périmètre retenu est la RUBRIQUE, pas un intervalle de lignes : ses morceaux
ne se suivaient pas dans `core.py` — l'annuaire CS et les diagnostics étaient
intercalés, et y restent. Un premier découpage contigu les avait emportés, ce
qui aurait produit un module dont le nom mentait sur le contenu.

Même geste que `copropriete.py` (13/08) et `annonce_hall.py` (15/08), et même
précaution : les noms restent **ré-exportés par `core.py`**, si bien qu'aucun des
modules appelants n'a une ligne à changer. C'est aussi ce qui garantit que les
tables restent enregistrées dans les métadonnées SQLModel — un modèle défini dans
un module que personne n'importe n'existe pas pour Alembic.
"""

from app.utils import horloge
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel

from app.utils.perimetres import perimetre_cible_json

from app.utils.assiste_ia import AssisteIAMixin
from pydantic import NaiveDatetime

# ──────────────────────────────────────────────
#  Sondages
# ──────────────────────────────────────────────


class Sondage(AssisteIAMixin, table=True):
    __tablename__ = "sondage"
    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    description: Optional[str] = None
    cloture_le: Optional[NaiveDatetime] = None
    resultats_publics: bool = True  # visibles avant clôture
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    #  Ciblage : None/vide = tous. MÊMES deux champs que `Publication`, et c'est
    #  le point — le sondage avait les siens (`batiments_ids`, `profils_autorises`),
    #  seul de tout le site, si bien qu'on ne pouvait cibler ni le parking, ni
    #  l'AFUL, ni un espace de bâtiment. Unifié le 16/08/2026 (migration 0147).
    perimetre_cible: Optional[str] = Field(default=None)  # JSON de codes de périmètre
    public_cible: Optional[str] = Field(default=None)  # JSON de codes de public
    cloture_forcee: bool = Field(default=False)
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False

    options: List["OptionSondage"] = Relationship(back_populates="sondage")
    votes: List["VoteSondage"] = Relationship(back_populates="sondage")


class OptionSondage(SQLModel, table=True):
    __tablename__ = "option_sondage"
    id: Optional[int] = Field(default=None, primary_key=True)
    sondage_id: int = Field(foreign_key="sondage.id")
    libelle: str
    ordre: int = 0
    champ_libre: bool = Field(default=False)

    sondage: Optional[Sondage] = Relationship(back_populates="options")
    votes: List["VoteSondage"] = Relationship(back_populates="option")


class VoteSondage(SQLModel, table=True):
    __tablename__ = "vote_sondage"
    id: Optional[int] = Field(default=None, primary_key=True)
    sondage_id: int = Field(foreign_key="sondage.id")
    option_id: int = Field(foreign_key="option_sondage.id")
    user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    reponse_libre: Optional[str] = Field(default=None)

    sondage: Optional[Sondage] = Relationship(back_populates="votes")
    option: Optional[OptionSondage] = Relationship(back_populates="votes")


# ──────────────────────────────────────────────
#  Petites annonces
# ──────────────────────────────────────────────


class TypeAnnonce(str, Enum):
    vente = "vente"
    don = "don"
    recherche = "recherche"


class CategorieAnnonce(str, Enum):
    appartement = "appartement"
    parking_cave = "parking_cave"
    mobilier = "mobilier"
    electromenager = "electromenager"
    high_tech = "high_tech"
    vehicule = "vehicule"
    vetements = "vetements"
    services = "services"
    divers = "divers"


class StatutAnnonce(str, Enum):
    """Le WORKFLOW d'une annonce — arbitré le 18/08/2026.

    🔴 Contredit la déclaration de la veille (`front/src/lib/entites/annonce.ts`),
    qui posait `sansObjet` sur la section 3 : *« une annonce n'a pas d'étapes de
    vie suivies à plusieurs »*. C'était mon arbitrage, pas celui du produit —
    l'utilisateur a tranché l'inverse, et la déclaration a été corrigée avec.

    ⚠️ `archive` n'en fait PAS partie, et c'est délibéré : l'archivage n'est pas
    une étape que quelqu'un choisit, c'est une conséquence du temps. Il se
    CALCULE (`_est_archivee`), comme pour les actualités. En faire un sixième
    état aurait donné deux notions pour la même chose — celle qu'on pose et
    celle qui arrive — libres de se contredire.
    """

    en_cours = "en_cours"
    reserve = "reserve"
    vendu = "vendu"
    donne = "donne"
    annule = "annule"


class PetiteAnnonce(AssisteIAMixin, table=True):
    __tablename__ = "petite_annonce"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    description: str  # rich-text HTML
    type_annonce: TypeAnnonce = TypeAnnonce.vente
    categorie: CategorieAnnonce = CategorieAnnonce.divers
    prix: Optional[float] = None
    negotiable: bool = False
    photos_json: str = Field(default="[]")  # JSON array of up to 5 URLs
    #  Le PÉRIMÈTRE — section 4 du cadre #430. Ajouté le 18/08/2026 sur demande
    #  utilisateur : une annonce n'était PAS sans périmètre, elle était sans
    #  MOYEN d'en porter un. Le formulaire disait « l'annonce n'a ni périmètre
    #  ni destinataires : elle s'adresse à tous les résidents par nature » — une
    #  absence de notion que l'écran avait décrétée, pas le produit.
    #
    #  ⚠️ Même forme que `Publication.perimetre_cible` et `Evenement.perimetre` :
    #  du JSON de codes (`["bat:1","parking"]`), pas un texte
    #  libre. La forme se recopie parce que la NOTION est la même — c'est
    #  `PerimetrePicker` et `perimetreLabel` qui la lisent, et ils ne savent lire
    #  que celle-là.
    perimetre_cible: Optional[str] = Field(default_factory=perimetre_cible_json)
    #  Le PUBLIC CIBLE — section 5 du cadre #430, ajouté le 06/09/2026 (#782).
    #  Le périmètre dit *de quoi* il s'agit ; celui-ci dit *à qui* on s'adresse.
    #
    #  🔴 Il filtre la VISIBILITÉ, pas seulement les notifications — décision de
    #  Philippe, qui renverse le « sans objet » que la déclaration d'écran portait
    #  la veille. `cible_visible` en décide, la même fonction que pour le sondage
    #  et la publication : une règle d'accès recopiée se durcit une fois sur deux.
    #
    #  ⚠️ `None` = TOUT LE MONDE, jamais « personne ». C'est ce que
    #  `public_cible_visible` fait d'une valeur absente, et ce que les annonces
    #  déjà déposées doivent continuer de valoir. L'inverse les aurait toutes fait
    #  disparaître en silence.
    public_cible: Optional[str] = None
    statut: StatutAnnonce = StatutAnnonce.en_cours
    #  🔴 L'horodatage du DERNIER CHANGEMENT D'ÉTAT, et non de la dernière
    #  modification. C'est lui qui décide de l'archivage automatique à un mois.
    #
    #  ⚠️ Mesurer sur `mis_a_jour_le` aurait paru équivalent et ne l'est pas :
    #  corriger une faute de frappe sur une annonce vendue repousserait son
    #  archivage d'un mois, indéfiniment, à chaque retouche. `Publication` porte
    #  le même champ (`statut_change_le`) pour exactement cette raison.
    statut_change_le: Optional[NaiveDatetime] = None
    contact_visible: bool = True  # montrer l'adresse — le nom, toujours (`adresse_de_contact`)
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: Optional[NaiveDatetime] = None


class CommentaireSondage(SQLModel, table=True):
    __tablename__ = "commentaire_sondage"
    id: Optional[int] = Field(default=None, primary_key=True)
    sondage_id: int = Field(foreign_key="sondage.id")
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    contenu: str
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


# ──────────────────────────────────────────────
#  Boîte à idées
# ──────────────────────────────────────────────


class Idee(AssisteIAMixin, table=True):
    __tablename__ = "idee"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    description: str
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    statut: str = "ouverte"  # ouverte | retenue | rejetee | realisee
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    #  Quand la décision a été prise — pas quand l'idée a été déposée. C'est
    #  cette date, et elle seule, qui déclenche l'archivage automatique
    #  (`app/utils/archivage.py`) : une idée retenue en janvier ne doit pas
    #  s'archiver à l'anniversaire de son dépôt. `PetiteAnnonce` et
    #  `Publication` portent le même champ, sous le même nom, pour la même
    #  raison. Ajoutée par la migration 0155 ; six objets sur sept l'avaient
    #  déjà, et c'est le test de concordance qui a montré le manque.
    statut_change_le: Optional[NaiveDatetime] = None
    #  ⚠️ MÊME forme que `Publication.perimetre_cible`, `PetiteAnnonce` et
    #  `Sondage` : du JSON de codes. Une quatrième forme diverge — c'est ce que le
    #  sondage avait fait (`batiments_ids`), et il a fallu une migration pour l'en
    #  sortir (#316, 0147). Migration 0153.
    perimetre_cible: Optional[str] = Field(default_factory=perimetre_cible_json)
    #  Le PUBLIC CIBLE — même champ, même forme et même règle que la petite
    #  annonce ci-dessus et que le sondage (#782, migration 0176). `None` = tout
    #  le monde : les idées déjà déposées ne changent pas d'audience.
    public_cible: Optional[str] = None

    votes: List["VoteIdee"] = Relationship(back_populates="idee")


class VoteIdee(SQLModel, table=True):
    __tablename__ = "vote_idee"
    id: Optional[int] = Field(default=None, primary_key=True)
    idee_id: int = Field(foreign_key="idee.id")
    user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)

    idee: Optional[Idee] = Relationship(back_populates="votes")


class ReponseCommunaute(SQLModel, table=True):
    """Réponse à un contenu de la Communauté — table générique factorisée.

    rubrique = 'idee' | 'annonce' ; cible_id = id de l'idée ou de l'annonce.
    Les commentaires de sondage restent dans CommentaireSondage (legacy, avec
    sémantique « commentaire attaché au vote »), mais partagent les mêmes
    helpers d'enrichissement/notification et le même composant front.
    """

    __tablename__ = "reponse_communaute"
    id: Optional[int] = Field(default=None, primary_key=True)
    rubrique: str = Field(index=True)  # 'idee' | 'annonce'
    cible_id: int = Field(index=True)  # id de l'idée / annonce (polymorphe)
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    contenu: str
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class Signalement(SQLModel, table=True):
    """Signalement d'un contenu Communauté inapproprié → file de modération CS.

    cible_type : 'idee' | 'annonce' | 'sondage' | 'reponse' (ReponseCommunaute)
                 | 'commentaire' (CommentaireSondage).
    """

    __tablename__ = "signalement"
    id: Optional[int] = Field(default=None, primary_key=True)
    cible_type: str = Field(index=True)
    cible_id: int = Field(index=True)
    apercu: str = ""  # extrait/titre du contenu (pour la file)
    auteur_cible_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    signale_par_id: int = Field(foreign_key="utilisateur.id")
    motif: str
    statut: str = Field(default="en_attente")  # en_attente | traite | rejete
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    traite_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    traite_le: Optional[NaiveDatetime] = None


class FluxMasque(SQLModel, table=True):
    """Une entrée du fil que l'administrateur a retirée de la VUE.

    ## Ce que c'est, et surtout ce que ce n'est pas

    Demandé le 31/08/2026 : *« supprimer, uniquement pour l'admin sur le fil
    d'actualité — celle-ci reste tracée à l'origine : actualité, annuaire,
    ticket… »*

    🔴 **L'objet n'est PAS supprimé.** Le fil est une vue *calculée* à partir des
    sept sources ; retirer une carte n'y retire qu'une ligne d'affichage.
    L'actualité, le membre du conseil ou le ticket restent où ils sont, intacts
    et consultables depuis leur écran. C'est exactement ce que la demande dit, et
    c'est aussi ce qui la rend sûre : un geste d'affichage ne détruit rien.

    ⚠️ **La règle « archiver, pas supprimer » ne s'applique donc pas ici** —
    elle protège des objets, et il n'y en a aucun à protéger. Un fil archivé
    n'aurait aucun sens : personne ne consulte les archives d'une vue.

    ## Pourquoi l'identifiant est une CHAÎNE

    `item_id` porte la forme du fil : `pub_7`, `mcs_12`, `tk_15`, `ev_evol_3`.
    C'est un identifiant de VUE, pas de table — deux sources différentes peuvent
    porter le même numéro sans se confondre, et c'est précisément ce préfixe qui
    l'empêche. Y mettre une clé étrangère demanderait de savoir vers quelle table
    pointer, ce qui n'a pas de réponse.

    ⚠️ Conséquence assumée : si l'objet d'origine est un jour supprimé, la ligne
    de masquage lui survit sans référence. Elle est inerte — le fil ne produit
    plus la carte, donc plus rien ne la consulte — et `maintenance.sh` peut la
    purger si elle devient nombreuse. Une clé étrangère aurait été plus propre et
    n'était pas possible ; le dire vaut mieux que le taire.
    """

    __tablename__ = "flux_masque"
    id: Optional[int] = Field(default=None, primary_key=True)
    #  L'identifiant de la CARTE, tel que le fil le fabrique. Unique : masquer
    #  deux fois la même carte est le même fait, pas deux.
    item_id: str = Field(index=True, unique=True)
    #  Qui a retiré la carte. NULLABLE — et ce n'est pas une facilité : si le
    #  compte est supprimé un jour, c'est le LIEN qui disparaît, pas le
    #  masquage. La leçon du 31/08/2026, où une purge a effacé un membre du
    #  conseil syndical pour réparer une référence cassée.
    masque_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    masque_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
