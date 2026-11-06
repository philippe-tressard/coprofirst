"""Un **accès** — vigik ou télécommande — décrit une fois, par un objet.

## 🔴 Pourquoi (14/09/2026, #779)

`routers/acces/resident.py` portait **quatre paires de fonctions jumelles** :
lister les miens, signaler une perte, supprimer, déclarer. Chaque paire disait
la même chose deux fois, à trois mots près — le modèle, sa table de liaison, et
le nom du champ qui porte la référence (``code`` pour le vigik, ``reference``
pour la télécommande).

Le dépôt savait déjà que c'était un défaut : ``_acces_admin_out`` porte, écrit à
la main, *« les deux ont les mêmes champs utiles, et deux fonctions jumelles
auraient divergé au premier ajout »*. Et ``detacher_acces`` avait été factorisé
pour la même raison (#546) — au prix de **six paramètres** que chaque appelant
devait rappeler dans le bon ordre.

🔴 **Elles avaient bel et bien divergé**, et personne ne l'avait vu : à la
déclaration d'un badge, la branche vigik recopiait le ``lot_id`` de la ligne
d'import sur l'objet créé, la branche télécommande non. Une télécommande
déclarée par son porteur restait donc **sans lot** dans la vue du conseil
syndical, alors que l'import connaissait le lot. La factorisation corrige ce
défaut en passant — c'est ce qu'elle a de mieux à offrir.

## Ce que cet objet est, et ce qu'il n'est pas

Il ne remplace pas les deux modèles : ``Vigik`` et ``Telecommande`` restent deux
tables, parce que ce sont deux objets physiques distincts que l'on compte
séparément. Il décrit **ce qui, dans le code, change de l'un à l'autre** — et
rien d'autre. Tout ce qui n'est pas ici est commun, donc s'écrit une fois.

⚠️ Un troisième accès (une clé, un bip de portail) s'ajoute en déclarant une
entrée ici. S'il fallait en plus recopier quatre fonctions, il serait ajouté à
moitié — c'est précisément ce qui est arrivé au ``lot_id``.
"""

from dataclasses import dataclass

from app.models.validations import StatutCommande
from app.utils.valeurs import valeur
from app.models.core import (
    Telecommande,
    TelecommandeImport,
    Vigik,
    VigikImport,
)


@dataclass(frozen=True)
class TypeAcces:
    """Ce qui distingue un vigik d'une télécommande — la liste complète."""

    #: La valeur employée dans les URL et les corps de requête : `vigik`…
    cle: str
    #: Ce qu'un humain lit dans un message d'erreur.
    libelle: str
    #: La table de l'objet remis au porteur.
    modele: type
    #: La table de staging de l'import Excel.
    modele_import: type
    #: La colonne de l'import qui pointe l'objet une fois résolu.
    colonne_import: str
    #: 🔴 La SEULE divergence de vocabulaire : le classeur des vigiks nomme sa
    #: référence `code`, celui des télécommandes `reference`. C'est cette
    #: différence-là qui rendait les deux branches « pas tout à fait pareilles »,
    #: et donc impossibles à relire ensemble.
    colonne_code_import: str
    #: 🔹 L'accès de cet objet se DÉDUIT-il du lot de son porteur ?
    #:
    #: 🔴 Vrai pour un vigik, faux pour une télécommande — corrigé le 14/09/2026,
    #: signalé à l'écran : *« Télécommande n'est pas accessible à un bâtiment mais
    #: à Parking résidence / portail d'accès + AFUL / portail public »*.
    #:
    #: La première version déduisait le bâtiment pour les DEUX, parce que la règle
    #: écrite ne parlait que du vigik. Une télécommande ouvre des portails,
    #: toujours les mêmes, et n'a rien à voir avec le bâtiment où l'on habite.
    #:
    #: ⚠️ C'est ici — et pas dans un `if` au fil des appels — parce que c'est la
    #: huitième différence entre ces deux objets, et que les sept autres sont déjà
    #: là. Ce qui les sépare se lit d'un seul endroit, ou se dérive.
    acces_suit_le_lot: bool
    #: 🏠 Les natures de lot que cet accès concerne — `TypeLot`, par leur valeur.
    #:
    #: 🔴 Corrigé le 15/09/2026, signalé à l'écran : *« la colonne lot correspond,
    #: pour les vigik à celui ou ceux de(s) l'appartement(s), pour les
    #: télécommandes à ceux des garages »*.
    #:
    #: La colonne montrait le lot ENREGISTRÉ, quel qu'il soit — et l'import des
    #: télécommandes, comme le formulaire, y posait volontiers l'appartement du
    #: copropriétaire. On lisait donc « Appartement 314 » en face d'une
    #: télécommande de parking, ce qui ne désigne aucune porte.
    #:
    #: ⚠️ Un tuple, pas une valeur : rien ne dit qu'un troisième accès ne
    #: concernera pas deux natures à la fois. Une valeur unique se serait
    #: transformée en liste au premier cas, et les appelants avec elle.
    types_lot: tuple[str, ...]

    @property
    def champ_code_import(self):
        """La colonne de l'import, prête pour un `where`."""
        return getattr(self.modele_import, self.colonne_code_import)

    #  🔴 `attribuer` et `attribuer_aux_coproprietaires` ont été RETIRÉS le
    #  23/09/2026 (#1194) : les porteurs d'un badge se déduisent de son lot
    #  (`utils/porteurs_acces`), plus rien ne les écrit.


VIGIK = TypeAcces(
    cle="vigik",
    libelle="Vigik",
    modele=Vigik,
    modele_import=VigikImport,
    colonne_import="vigik_id",
    colonne_code_import="code",
    acces_suit_le_lot=True,
    types_lot=("appartement",),
)

TELECOMMANDE = TypeAcces(
    cle="telecommande",
    libelle="Télécommande",
    modele=Telecommande,
    modele_import=TelecommandeImport,
    colonne_import="telecommande_id",
    colonne_code_import="reference",
    acces_suit_le_lot=False,
    types_lot=("parking",),
)

#: Les accès connus, par leur clé d'URL — la source unique de « quels types
#: existent ». Un écran ou un routeur qui énumérerait « vigik ou telecommande »
#: à la main serait une seconde liste, libre de diverger.
TYPES_ACCES = {t.cle: t for t in (VIGIK, TELECOMMANDE)}


def libelle_type_acces(cle) -> str:
    """« vigik » → « Vigik » — ce qu'un résident lit dans une notification ou un courriel.

    Une notification disait « Nouvelle demande de vigik » et un courriel « Votre
    demande de telecommande » : la clé d'URL, pas un mot (05/11/2026). Une clé
    inconnue est rendue telle quelle — un libellé manquant doit se voir.
    """
    brut = str(valeur(cle))
    type_acces = TYPES_ACCES.get(brut)
    return type_acces.libelle if type_acces else brut


#: Comment le SORT d'une commande d'accès se dit — `StatutCommande`
#: (`models/validations`). En minuscules : il suit « Commande Vigik : … ».
LIBELLES_STATUT_COMMANDE: dict[str, str] = {
    StatutCommande.en_attente.value: "en attente",
    StatutCommande.acceptee.value: "acceptée",
    StatutCommande.refusee.value: "refusée",
}


def libelle_statut_commande(statut) -> str:
    """« acceptee » → « acceptée ». Une clé inconnue est rendue telle quelle."""
    cle = str(valeur(statut))
    return LIBELLES_STATUT_COMMANDE.get(cle, cle)
