"""Schémas partagés et garde d'accès à la rubrique Communauté.

Extrait de `sondages.py` le 17/08/2026 lors du découpage (cf. `__init__.py`).
Ce module ne porte AUCUN endpoint : il est importé par `crud` et par
`participation`, qui en dépendent tous les deux.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.utils.lecture_pastille.modele import Lecture
from app.utils.assiste_ia import AssisteIACorrection, AssisteIAEntree, AssisteIASortie

from app.schemas import ListeJson
from app.schemas_communaute import ReponseCommunauteRead
from app.utils.perimetres.servi import AvecPerimetreLibelle


# ── helpers ──────────────────────────────────────────────────────────────────


# ── schémas ──────────────────────────────────────────────────────────────────


class OptionCreate(BaseModel):
    libelle: str
    ordre: int = 0
    champ_libre: bool = False


class SondageCreate(AssisteIAEntree):
    question: str
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    resultats_publics: bool = True
    options: list[OptionCreate]
    #  MÊMES deux champs que les publications : codes de périmètre et codes de
    #  public. `None`/vide = aucune restriction, des deux côtés.
    perimetre_cible: Optional[List[str]] = None
    public_cible: Optional[List[str]] = None
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False
    #  « Envoyer une copie à … » — la 4e case de la Diffusion (31/08/2026).
    #  Elle s'affichait sur cet écran sans être lue nulle part. Un sondage ne
    #  se crée que par son auteur : ici les deux personnes coïncident toujours,
    #  et c'est le seul des quatre écrans où c'est vrai.
    envoyer_auteur: bool = False


class GestesSondages(BaseModel):
    """`GET /sondages/gestes` — ce que CE lecteur peut faire de la rubrique (#2654).

    Modifier ou stopper un sondage reste un geste PAR sondage (`peut_editer` :
    l'auteur ou l'administrateur) ; seul celui de créer se sert ici."""

    peut_creer: bool


class SondageRead(AssisteIASortie, AvecPerimetreLibelle):
    id: int
    question: str
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    cloture_forcee: bool = False
    resultats_publics: bool
    auteur_id: Optional[int] = None  # compte supprimé (#1821)
    cree_le: datetime
    #  Exposés en LISTES, comme les publications et les tickets : la colonne est
    #  du texte JSON, mais aucun appelant ne doit avoir à le savoir. La page des
    #  sondages découpait la chaîne à la main et affichait les codes bruts.
    perimetre_cible: ListeJson = []
    public_cible: ListeJson = []
    nb_votants: int = 0
    #  « Ce sondage est-il terminé ? » — répondu par le SERVEUR, via l'unique
    #  `sondage_clos()`, et transporté. Il n'était exposé que sur la fiche : la
    #  liste n'avait donc pas le choix, elle recalculait la règle en JavaScript
    #  (`estCloture`). Deux implémentations d'une même question, dont une seule
    #  fait autorité — et elles divergeaient déjà sur le fuseau, le front
    #  comparant à l'heure LOCALE du navigateur quand le serveur date en UTC
    #  (#468). Un écran ne tranche pas ce genre de question (`ux-patterns` §16).
    cloture: bool = False
    #: Règle du SITE (`utils/archivage`, #515) : 30 jours après la date de
    #: clôture. Un sondage clos reste donc un mois sous les yeux avant de
    #: rejoindre les Archives — c'est le délai unique, réglable en
    #: administration, et non une valeur propre à cet écran.
    archivee: bool = False
    #: Le badge NEW — `utils/nouveaute.est_nouveau`, la règle du serveur (#2506).
    nouveau: bool = False
    #: Qui le lit (`utils/lecture_pastille`, #2633) — posé par la liste.
    lecture: Optional[Lecture] = None

    class Config:
        from_attributes = True


class OptionRead(BaseModel):
    id: int
    libelle: str
    ordre: int
    nb_votes: int = 0
    champ_libre: bool = False

    class Config:
        from_attributes = True


class OptionCorrection(BaseModel):
    """Correction du LIBELLÉ d'une option existante — et rien d'autre.

    L'`id` est obligatoire et doit désigner une option **de ce sondage** : c'est ce
    qui rend l'ajout et le retrait impossibles par construction, sans dépendre
    d'une vérification qu'on pourrait oublier. Un schéma qui accepterait une
    option sans `id` créerait une option ; un schéma qui accepterait une liste
    complète en supprimerait les absentes.

    🔴 Décision de l'utilisateur, 19/08/2026 (#467) : **le texte se corrige, la
    liste des choix ne bouge pas**. Un vote sur une option retirée n'a pas de repli
    honnête — le compter ailleurs fausse le résultat, le supprimer efface
    l'expression de quelqu'un sans le lui dire. Aucune des deux issues n'est
    acceptable pour un sondage qui prépare une décision de copropriété.
    """

    id: int
    libelle: str


class SondageUpdate(AssisteIACorrection):
    """Ce qu'un sondage accepte de voir corrigé après sa création.

    Les champs de CIBLAGE (`perimetre_cible`, `public_cible`) n'y sont
    volontairement pas : restreindre un périmètre après coup masquerait le sondage
    à des gens qui ont déjà voté. La question reste ouverte (#467), et tant
    qu'elle n'est pas tranchée, l'absence du champ vaut refus — un champ qu'on
    n'expose pas ne se contourne pas.
    """

    question: Optional[str] = None
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    resultats_publics: Optional[bool] = None
    options: Optional[List[OptionCorrection]] = None


class OptionFiche(BaseModel):
    """Une option sur la FICHE d'un sondage.

    `nb_votes` et `reponses_libres` sont ABSENTS — pas à zéro — quand les
    résultats ne sont pas visibles : « 0 vote » se lirait « personne n'a voté ».
    La route rend donc sans les champs non posés (`response_model_exclude_unset`).
    """

    id: int
    libelle: str
    ordre: int
    champ_libre: bool = False
    nb_votes: Optional[int] = None
    reponses_libres: Optional[List[str]] = None


class SondageDetail(BaseModel):
    """La FICHE d'un sondage — `GET /sondages/{id}` (#2506).

    🔴 Ce schéma existait sans qu'aucune route le déclare, et il ne disait pas ce
    que la fiche rend : elle ne porte ni `nb_votants`, ni `archivee`, ni
    `assiste_ia` de la liste, et ajoute ses options, ses commentaires et la
    décision d'afficher les résultats. Le contrat la déclarait `{}`.
    """

    id: int
    question: str
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    resultats_publics: bool
    auteur_id: Optional[int] = None  # compte supprimé (#1821)
    cree_le: datetime
    perimetre_cible: List[str] = []
    public_cible: List[str] = []
    options: List[OptionFiche] = []
    #: L'option votée par le lecteur, ou `None` s'il n'a pas voté.
    mon_vote: Optional[int] = None
    cloture: bool = False
    cloture_forcee: bool = False
    commentaires: List[ReponseCommunauteRead] = []
    #: Source UNIQUE de la décision d'afficher les résultats (#397).
    resultats_visibles: bool = False
    nouveau: bool = False
