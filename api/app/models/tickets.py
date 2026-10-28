"""Le vocabulaire d'un ticket — états du workflow, catégories, priorités.

Extrait de `core.py` le 17/08/2026, au fil de l'eau : le fichier faisait déjà
1 245 lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé
qu'il grossisse pour recevoir la correction de #415. La règle est « on découpe
le fichier QUAND on y touche ».

## Ce que ce module porte, et ce qu'il ne porte pas

Il porte le **vocabulaire** : les valeurs qu'un ticket peut prendre, et les
réponses aux deux questions qu'on lui pose partout — « demande-t-il encore du
suivi ? », « est-il clos ? ». C'est précisément ce que #415 a trouvé recopié
dans neuf endroits, divergent dans les deux sens.

Il porte aussi les **tables** (`Ticket`, `MessageTicket`, `TicketEvolution`)
depuis le 28/09/2026 (#779). Elles étaient restées dans `core.py` de peur d'un
cycle d'import — leurs `Relationship` croisent `Utilisateur` et `Lot`. Le cycle
ne se forme pas : ces deux noms ne sont importés que sous `TYPE_CHECKING`, et
SQLAlchemy les résout par son registre de classes, comme `copropriete.py` le
fait depuis le 13/08. La vérification que ce paragraphe demandait est celle de
tout ré-export : `test_modeles_enregistres.py`, et la suite qui charge l'API.

Les noms restent **ré-exportés par `core.py`** : aucun des dix-huit modules
appelants n'a une ligne à changer, comme pour `copropriete.py` (13/08),
`communaute.py` (16/08) et `validations.py` (17/08).
"""

from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, Relationship, SQLModel

from app.models.evolution import EvolutionMixin
from app.utils import horloge
from app.utils.assiste_ia import AssisteIAMixin
from app.utils.perimetres import perimetre_cible_json
from app.utils.saisi_pour import SaisiPourMixin

#  Références différées vers `core.py` et `copropriete.py` : `core` importe CE
#  module (ré-export), un import réciproque réel formerait un cycle.
if TYPE_CHECKING:  # pragma: no cover
    from app.models.copropriete import Lot
    from app.models.core import Utilisateur


class StatutTicket(str, Enum):
    """Les quatre états du workflow d'un ticket — et il n'y en a pas d'autre.

    `fermé` a vécu ici jusqu'au 17/08/2026 sous la mention « conservé pour
    compatibilité données existantes ». Il ne se distinguait de `résolu` par
    rien : même clôture, même sortie de la liste active, même exclusion des
    relances. C'était un reliquat du modèle d'origine (`2792b76`), pas une étape
    de vie — et il était pourtant le seul état que le formulaire d'évolution de
    la fiche proposait en plus des trois évidents, pendant que `annulé` y était
    refusé (#415). La migration 0149 a basculé les tickets concernés en `résolu`.

    C'est cette énumération qui fait foi, partout : les deux endpoints qui
    changent l'état d'un ticket valident par elle (`TicketUpdate.statut`,
    `TicketEvolutionCreate.nouveau_statut`), et `#lib/tickets.ts` lui répond
    côté écran. `api/tests/test_statuts_tickets.py` échoue si l'un des deux
    dérive.
    """

    ouvert = "ouvert"
    #  🆕 Les deux colonnes du kanban qu'aucun état ne disait (#1092, lot 5,
    #  arbitré le 23/09/2026) : un dossier soumis au vote de l'AG, un dossier
    #  chez le prestataire. Les événements du calendrier les portaient ; en
    #  devenant des affaires, ils ne devaient pas perdre OÙ en est le dossier.
    en_ag = "en_ag"
    en_cours = "en_cours"
    chez_prestataire = "chez_prestataire"
    résolu = "résolu"
    annulé = "annulé"
    #  🔴 HORS du workflow (#1091, 23/09/2026) : l'état d'une affaire de
    #  catégorie « Actualité », qui n'a pas de cycle de vie — elle PÉRIME au lieu
    #  de se clore. Jamais proposé (`STATUTS_TICKET_SANS_CYCLE`), jamais atteint
    #  par une transition : seul un changement de catégorie y mène, ou en sort.
    #  Un état plutôt qu'un test de catégorie chez chaque consommateur : il sort
    #  PAR CONSTRUCTION des états actifs, des colonnes du kanban et des relances.
    publie = "publie"


#: Un ticket dans l'un de ces états ne demande plus de suivi : il quitte la liste
#: active, sort des relances syndic et des compteurs « à traiter ». **Source
#: unique** — quatre modules réécrivaient cette liste chacun de leur côté, et
#: elles avaient divergé (`annulé` manquait à deux d'entre elles).
STATUTS_TICKET_CLOS: tuple[str, ...] = (StatutTicket.résolu.value, StatutTicket.annulé.value)

#: Les états où une Étude & travaux sans choix du conseil sort du conseil pour
#: tous les copropriétaires (standard du 30/09/2026, `visibility/defauts_affaire`) :
#: à l'AG, où ils la votent, chez le prestataire, et close. Miroir à l'écran :
#: `STATUTS_ETUDE_OUVERTE` (`#lib/tickets`).
STATUTS_ETUDE_OUVERTE: frozenset[str] = frozenset(
    {StatutTicket.en_ag.value, StatutTicket.chez_prestataire.value, *STATUTS_TICKET_CLOS}
)

#: Le complément : un ticket qui demande encore du suivi. Écrit `("ouvert",
#: "en_cours")` à la main dans deux modules de `flux/`, où il aurait fallu penser
#: à l'ajouter le jour où un cinquième état serait apparu.
#: L'état sans cycle — ni actif, ni clos, jamais proposé (#1091). Déclaré ici
#: comme les valeurs historiques le sont plus bas : affichable, pas saisissable.
STATUTS_TICKET_SANS_CYCLE: tuple[str, ...] = (StatutTicket.publie.value,)

STATUTS_TICKET_ACTIFS: tuple[str, ...] = tuple(
    s.value
    for s in StatutTicket
    if s.value not in STATUTS_TICKET_CLOS and s.value not in STATUTS_TICKET_SANS_CYCLE
)

#: Valeurs qu'aucun ticket ne porte plus, mais que l'historique du fil
#: (`ticket_evolution.ancien_statut` / `nouveau_statut`) conserve : elles doivent
#: rester **affichables** — jamais proposables.
STATUTS_TICKET_HISTORIQUES: tuple[str, ...] = ("fermé",)


class CategorieTicket(str, Enum):
    """Ce que le ticket EST — jamais son degré d'urgence.

    🔴 « urgence » a été retirée le 07/09/2026, et c'est une correction de
    conception, pas un retrait de fonctionnalité. Elle mélangeait deux axes :
    une panne peut être urgente, une nuisance aussi. Un résident dont
    l'ascenseur est bloqué avec quelqu'un dedans devait choisir entre « Panne »
    et « Urgence », et perdait l'autre moitié de l'information quel que soit son
    choix.

    Le remplacement existait DÉJÀ et servait déjà : `PrioriteTicket.haute`, que
    la case « Urgent » du formulaire écrit depuis #766. Le commentaire de
    `front/src/lib/tickets.ts` le disait en toutes lettres — « `urgente` →
    `priorite === 'haute'`, ce que la catégorie Urgence pose déjà ». Les deux
    axes se recoupaient, et le code le savait.

    ⚠️ Les quatre catégories ajoutées le même jour ne le sont pas pour enrichir
    la liste : chacune change ce qu'on FAIT du ticket — le destinataire, le
    délai ou le geste attendu. Une catégorie qui ne change rien au traitement
    est un filtre décoratif, et elle rend le choix plus difficile pour rien.

    ## Ce que la consolidation a corrigé dans la première estimation

    Le relevé initial proposait « Dégât des eaux ». La documentation des
    assureurs et des syndics montre que **le dégât des eaux n'est qu'un cas** :
    incendie, vandalisme, bris de glace et catastrophe naturelle suivent la
    MÊME procédure — constat, photos, devis, et déclaration à l'assurance
    multirisque sous **cinq jours ouvrés**. C'est la procédure qui fait la
    catégorie, pas la cause. « Sinistre » les couvre toutes ; « Dégât des eaux »
    en laissait trois sans catégorie, donc en « Panne », où rien ne dit qu'un
    délai légal court.

    « Espaces verts » vient du même recoupement : elle figure dans toutes les
    applications de signalement (municipales comme résidentielles), et le
    prestataire n'est ni celui du nettoyage ni celui de la technique.

    Deux candidates ÉCARTÉES bien qu'omniprésentes ailleurs : « Éclairage »
    (c'est une panne d'équipement) et « Stationnement » (déjà nommé dans la
    description de « Nuisance »). Les ajouter aurait dispersé le choix sans rien
    changer au traitement.

    ## `acces_accueil`, la neuvième — et elle ferme deux trous d'un coup

    🔴 Signalé le 07/09/2026, cas concret à l'appui : *« le syndic n'a rien fait
    depuis deux semaines et le locataire a créé lui-même un ticket »*.

    Le parcours « Nouvel arrivant » envoyait une notification au conseil et un
    e-mail au syndic — **et rien d'autre**. La notification se lit une fois puis
    quitte la pile, l'e-mail tombe dans une boîte, le résident n'a aucune trace,
    et personne ne voit que ça traîne. C'est la règle du projet enfreinte à
    l'envers : *vérifier le comportement, jamais l'artefact* — le message parti
    est l'artefact, la démarche faite est le fait (`standards/04` §14).

    Le second trou est plus discret : **corriger son nom sur l'interphone ou la
    boîte aux lettres hors d'une arrivée** — faute d'orthographe, départ d'un
    colocataire, changement de nom — n'avait AUCUN chemin. Le parcours arrivant
    ne se déclenche qu'une fois, à la création du compte.

    ⚠️ Elle ne couvre PAS la commande d'un badge ou d'une télécommande :
    `CommandeAcces` porte déjà le lot, la quantité, le motif et son propre
    workflow. Un ticket y perdrait tout. Cette catégorie est pour ce qui n'a pas
    de circuit dédié.

    ## 🔴 `proprete` a été FUSIONNÉE dans `nuisance` le soir même (migration 0179)

    Je l'avais créée sur l'argument « autre prestataire : le nettoyage, pas le
    technique ». Signalé le 07/09/2026 : *« très sincèrement, Propreté je la
    regrouperais dans Nuisance en complétant le libellé »*. C'est juste, et
    l'erreur était la mienne :

    * dans les faits le **geste est le même** — le conseil relaie au syndic ou au
      prestataire, il ne fait pas deux choses différentes ;
    * le recouvrement, je l'avais **déjà admis** en écrivant qu'« un encombrant
      abandonné dans le hall est les deux à la fois » ;
    * et j'avais dû **expliquer la frontière dans le manuel**. Une frontière qu'il
      faut expliquer est une frontière qui n'existe pas.

    ## Où passe la limite entre `panne` et `sinistre`

    Questionné le même jour sur deux cas concrets. La réponse tient en un mot, et
    ce n'est pas « eau » :

    * **une fuite au goutte-à-goutte dans les communs → `panne`.** On appelle le
      plombier. Aucun dommage, aucun tiers lésé, aucun délai d'assurance.
    * **une panne électrique — ampoule grillée, interrupteur HS → `panne`.**
      C'est le cœur de la catégorie, et c'est pourquoi « Éclairage » a été écartée
      comme catégorie séparée.
    * **`sinistre` commence au DOMMAGE** : de l'eau chez quelqu'un, un plafond
      taché, un parquet gondolé. C'est le dommage qui déclenche la déclaration,
      pas la fuite.

    ⚠️ Les descriptions le disent désormais en toutes lettres (« à réparer » /
    « dégât constaté »). Elles ne le disaient pas, et c'est ce qui rendait la
    question nécessaire.
    """

    panne = "panne"
    nuisance = "nuisance"  # comportement ET propreté — voir la note ci-dessous
    espaces_verts = "espaces_verts"  # autre prestataire, et une saisonnalité
    sinistre = "sinistre"  # constat + déclaration à l'assurance sous 5 jours ouvrés
    etude_travaux = "etude_travaux"  # le dossier long que le conseil syndical suit
    acces_accueil = "acces_accueil"  # interphone, BAL, badge — installer quelqu'un
    question = "question"
    bug = "bug"
    #  🆕 Le passage d'un prestataire — visite, maintenance, récurrente ou non
    #  (#1092, lot 5) : les maintenances du calendrier en deviennent. Bâti, donc
    #  au carnet ; réservée au conseil, qui tient les contrats.
    entretien = "entretien"
    #  🔴 Une INFORMATION, pas une demande (#1091, arbitré les 22 et 23/09/2026) :
    #  l'actualité a cessé d'être un objet pour devenir une catégorie d'affaire.
    #  Réservée au conseil syndical, sans cycle (`StatutTicket.publie`). Elle
    #  change bien ce qu'on FAIT de l'affaire — personne n'agit, elle périme.
    actualite = "actualite"


#: Les catégories qu'un résident ne pose pas — ni à la création, ni en changeant
#: celle d'une affaire. La règle est lue par `nature_affaire`, jamais recopiée.
#: Étude & travaux et Entretien y sont entrées le 23/09/2026 (#1098, #1092) :
#: lancer une étude, tenir un contrat, sont des décisions du conseil ; un résident
#: signale une panne ou pose une question.
CATEGORIES_RESERVEES_AU_CS: tuple[str, ...] = (
    CategorieTicket.actualite.value,
    CategorieTicket.etude_travaux.value,
    CategorieTicket.entretien.value,
)


class PrioriteTicket(str, Enum):
    basse = "basse"
    normale = "normale"
    haute = "haute"


class IntervenantMixin(SQLModel):
    """Ce que le CONSEIL pose sur une affaire du bâti : qui intervient, à quel
    rythme, et sur quoi. Les règles vivent dans `utils/intervenant`.

    - `prestataire_id`, `frequence_*` : #1092, lot 5 (migration 0211) ;
    - `equipement` : #1097 (migration 0216) — la **valeur** de `TypeEquipement`,
      posée par le conseil et jamais demandée au résident : il voit une flaque,
      il ne sait pas si c'est la plomberie ou la toiture. C'est elle qui range
      une affaire résolue au carnet d'entretien.

    Colonnes simples, **sans clé étrangère**, comme en production : une base
    neuve porte le même schéma qu'elle.
    """

    prestataire_id: Optional[int] = None
    #: Le CADRE de l'intervention (#1445, migration 0235) : le contrat sous
    #: lequel le prestataire intervient, `None` hors contrat. Sans clé étrangère,
    #: comme ses voisins — `utils/intervenant.contrat_valide` en tient la règle.
    contrat_id: Optional[int] = None
    frequence_type: Optional[str] = None  # « semaines » · « mois » · « fois_par_an »
    frequence_valeur: Optional[int] = None
    equipement: Optional[str] = None


class Ticket(SaisiPourMixin, AssisteIAMixin, IntervenantMixin, table=True):
    __tablename__ = "ticket"
    id: Optional[int] = Field(default=None, primary_key=True)
    numero: str = Field(unique=True, index=True)
    #  D'où vient cette affaire : une publication (0210) ou un événement (0212),
    #  recopiés en affaires. Sans `foreign_key` ; la redirection des anciens liens
    #  lit ces colonnes (`routers/publications`, #1091 ; `#ev-N`, #1092).
    promu_depuis_publication_id: Optional[int] = Field(default=None, index=True)
    promu_depuis_evenement_id: Optional[int] = Field(default=None, index=True)
    titre: str
    description: str
    categorie: CategorieTicket = CategorieTicket.panne
    statut: StatutTicket = StatutTicket.ouvert
    priorite: PrioriteTicket = PrioriteTicket.normale
    #  Facultatif depuis #1688 : un compte supprimé laisse ses affaires, sans
    #  nom (« Ancien résident », `utils/noms.nom_auteur`). La purge référentielle
    #  délie une référence facultative au lieu d'emporter la ligne.
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    #  JSON de codes de l'arbre ; le défaut se lit dans les données (#1567).
    perimetre_cible: Optional[str] = Field(default_factory=perimetre_cible_json)
    photos_urls: Optional[str] = None  # JSON array of photo URLs
    # Pièces jointes non-images (PDF, bureautique). Même convention que
    # TicketEvolution.fichiers_urls : un seul nom pour la notion « fichier joint ».
    fichiers_urls: str = "[]"  # JSON array d'URLs de fichiers joints
    destinataire_syndic: bool = False
    destinataire_cs: bool = False
    #  🔴 FK redéclarée : le mixin ne la porte pas (cf. `utils/saisi_pour`).
    saisi_pour_user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    #  -- Section « Quand » (#1092) ----------------------------------
    #  `debut`/`fin` disent QUAND ÇA SE PASSE et alimentent le calendrier.
    #  `echeance` (« avant quand c'est attendu ») a été RETIRÉE le 23/09/2026
    #  (migration 0206) : ôtée du formulaire le 21/09 — la relance mensuelle
    #  couvre le besoin —, elle n'était plus ni saisie ni lue.
    debut: Optional[NaiveDatetime] = None
    fin: Optional[NaiveDatetime] = None
    #  Intervenant, récurrence et équipement : `IntervenantMixin` (#1097).
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    ferme_le: Optional[NaiveDatetime] = None
    #  Adresse `tickets+<jeton>@…` (#703) : tirée au sort, jamais dérivée de l'id.
    jeton_courriel: Optional[str] = Field(default=None, index=True)
    confidentiel: bool = False  # 🛡️ son auteur et le CS (#710, migration 0166)
    #  📌 Épinglé (05/09/2026) ; ce que chaque option écrit : migration 0175.
    epingle: bool = False
    #  Paraît-il au kanban ? SI, jamais OÙ — `utils/kanban_tickets.py` (#833).
    suivi_kanban: bool = False
    #  ✨ Le résumé de l'assistant (cinq lignes au plus), montré au Suivi des
    #  affaires et dans la relance du syndic (#2035, migration 0287). Son écriture
    #  ne touche PAS `mis_a_jour_le` : c'est la dernière avancée, qui date la relance.
    resume_ia: Optional[str] = None
    resume_ia_le: Optional[NaiveDatetime] = None
    #  🔁 Le suivi d'une ACTUALITÉ (10/10/2026) : `None` = sans suivi ; sinon
    #  « ouvert », « résolu » ou « annulé ». Un REPÈRE, distinct de `statut` qui
    #  reste `publie` : l'actualité sort ainsi, par construction, du kanban, des
    #  relances et des compteurs. Règles : `utils/suivi_actualite` (migration 0274).
    suivi_actualite: Optional[str] = None
    #  Rapatriées de `Publication` (#1091, migration 0207) : le public visé
    #  (JSON), l'Accès « Réservé au périmètre » (#1096), l'archivage manuel.
    public_cible: Optional[str] = None
    reserve_perimetre: bool = False
    archive_manuel: bool = False
    #  🔀 L'affaire qui l'a ABSORBÉE à sa clôture (#1704, migration 0265) : son
    #  fil s'y poursuit, elle sort du carnet. Sans clé étrangère, comme ses
    #  voisines ajoutées par migration. Règles : `utils/fusion_affaires`.
    fusionnee_dans_id: Optional[int] = None
    #  🗄️ La CONSERVATION (#2014, migration 0295) : le jour où l'affaire, échue,
    #  a perdu ses pièces jointes (archivées) et ses auteurs. `None` = intacte ;
    #  posée, l'affaire n'est jamais retraitée. Règles : `utils/conservation_affaires`.
    conservee_le: Optional[NaiveDatetime] = None
    #  Ce que l'auteur détaché ÉTAIT à l'échéance — « resident » ou « conseil » —,
    #  rendu « Un résident » ou « Le conseil syndical » (`utils/noms.nom_auteur`).
    auteur_qualite: Optional[str] = None

    auteur: Optional["Utilisateur"] = Relationship(
        back_populates="tickets", sa_relationship_kwargs={"foreign_keys": "[Ticket.auteur_id]"}
    )
    saisi_pour: Optional["Utilisateur"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Ticket.saisi_pour_user_id]"}
    )
    lot: Optional["Lot"] = Relationship(back_populates="tickets")
    messages: List["MessageTicket"] = Relationship(back_populates="ticket")
    evolutions: List["TicketEvolution"] = Relationship(back_populates="ticket")


class MessageTicket(SQLModel, table=True):
    __tablename__ = "message_ticket"
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id")
    auteur_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")  # #1688
    contenu: str
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    interne: bool = False  # True = visible CS seulement
    fichiers_urls: str = "[]"  # JSON array d'URLs de fichiers joints
    auteur_qualite: Optional[str] = None  # l'auteur détaché par la conservation (#2014)

    ticket: Optional[Ticket] = Relationship(back_populates="messages")


class TicketEvolution(EvolutionMixin, table=True):
    __tablename__ = "ticket_evolution"
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id")
    # type : commentaire | etat | reponse
    #  Les sept champs communs — `type`, `contenu`, les deux statuts,
    #  l'auteur, la date et les pièces jointes — viennent d'`EvolutionMixin`.
    #  Le périmètre que CETTE entrée déclare — `None` quand elle n'en parle pas,
    #  ce qui est le cas de l'immense majorité des commentaires : une évolution
    #  n'a pas de périmètre, elle en déclare un (migration 0154, #497).
    #  Même forme JSON que partout ailleurs : `["résidence"]`, `["bat:1","cave"]`.
    perimetre_cible: Optional[str] = None
    #  Le transfert de courriel qui l'a versée (#1482) — ce qui permet de
    #  défaire ce transfert d'un geste. Colonne simple (0239).
    versement_id: Optional[int] = Field(default=None, index=True)
    auteur_qualite: Optional[str] = None  # l'auteur détaché par la conservation (#2014)

    ticket: Optional[Ticket] = Relationship(back_populates="evolutions")
    auteur: Optional["Utilisateur"] = Relationship()
