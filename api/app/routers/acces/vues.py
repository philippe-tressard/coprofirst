"""Ce qu'un accès MONTRE — le noyau commun, et ce que le conseil syndical y ajoute.

## Pourquoi ce module (15/09/2026, #953)

Deux écrans lisent les mêmes objets et n'en montrent pas autant :

| Qui | Ce qu'il voit | Où |
|---|---|---|
| le porteur | ses badges : code, état, **ce qu'ils ouvrent** | `/mon-lot/badges` |
| le conseil syndical | tout le parc, **et qui détient quoi** | Espace CS |

La vue du résident rendait jusqu'ici l'objet **brut** — `session.exec(select(Vigik))`
sérialisé tel quel par FastAPI. Cela marchait tant qu'on n'affichait que le code
et l'état ; ça cesse de marcher au premier champ qui demande une lecture :
`perimetre_cible` est stocké en **JSON dans une colonne texte**, et l'écran
recevait la chaîne `'["bat:2"]'` là où `BadgePerimetre` attend une liste.

🔴 **Le remède n'est pas de parser dans l'écran.** Le front porte déjà un
assainisseur de périmètres pour les contenus, et en ajouter un ici ferait deux
lectures du même champ — celle qui a produit le défaut du fil d'activité, qui
comparait un libellé à une chaîne écrite en dur (14/09/2026).

## L'héritage, et ce qu'il évite

`AccesAdminOut` **dérive** de `AccesPorteur` : les champs communs sont déclarés une
fois, et `champs_communs()` les remplit une fois. Deux modèles jumeaux auraient
divergé au premier ajout — c'est ce qui était arrivé au `lot_id` entre vigik et
télécommande, et ce que le descripteur `utils/types_acces` a corrigé.

⚠️ Ce module ne connaît **ni route, ni droit** : il dit ce qu'un accès montre,
pas qui a le droit de le regarder. Les droits vivent dans `auth/deps`.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.models.copropriete import Lot
from app.models.core import StatutAcces, UserLot
from app.utils.batiments import libelle_lot
from app.utils.perimetres import SEPARATEUR_ELEMENT, parse_json_perimetres
from app.utils.types_acces import TypeAcces
from app.utils.valeurs import valeur
from app.utils.perimetres.servi import AvecPerimetreLibelle


def libelle_lots(session: Session, type_acces: TypeAcces, objet) -> Optional[str]:
    """Le LOT d'un accès — celui de sa NATURE, pas celui qu'on lui a collé.

    🔴 Corrigé le 15/09/2026, signalé à l'écran :

    > « la colonne lot correspond : pour les vigik à celui ou ceux de(s)
    >   l'appartement(s), pour les télécommandes à ceux des garages »

    La colonne montrait `objet.lot_id`, quel qu'il soit. Or l'import des
    télécommandes — comme le formulaire du conseil syndical — y posait
    volontiers l'appartement du copropriétaire, faute de mieux : on lisait donc
    « Appartement 314 » en face d'une télécommande de parking, ce qui ne désigne
    aucune place.

    ## La règle, en entier

    | Ce qui est enregistré | Ce qu'on affiche |
    |---|---|
    | un lot **de la bonne nature** | lui, et lui seul — c'est une décision prise |
    | un lot d'une autre nature, ou rien | **tous** les lots du porteur de la bonne nature |

    ⚠️ La seconde ligne affiche plusieurs lots, séparés comme partout ailleurs
    (`SEPARATEUR_ELEMENT`). C'est ce que la demande dit — *« celui ou ceux »* — et
    c'est plus honnête qu'un choix arbitraire : un copropriétaire qui a deux
    places de parking n'en désigne aucune en particulier par sa télécommande.

    ⚠️ Cela ne **modifie** rien : `lot_id` reste ce qu'il est. Réécrire la
    donnée sur une déduction d'affichage effacerait une saisie volontaire, et on
    ne saurait plus laquelle des deux est la décision.
    """
    if objet.lot_id:
        lot = session.get(Lot, objet.lot_id)
        if lot and valeur(lot.type) in type_acces.types_lot:
            return libelle_lot(lot)
    lots = session.exec(
        select(Lot)
        .join(UserLot, UserLot.lot_id == Lot.id)
        .where(UserLot.user_id == objet.user_id, UserLot.actif == True)  # noqa: E712
    ).all()
    libelles = [libelle_lot(lot) for lot in lots if valeur(lot.type) in type_acces.types_lot]
    return SEPARATEUR_ELEMENT.join(x for x in libelles if x) or None


class AccesPorteur(AvecPerimetreLibelle):
    """Un accès tel que son PORTEUR a besoin de le voir.

    ⚠️ `bail_id` et `chez_locataire` en font partie : un bailleur lit cette même
    liste pour savoir ce qu'il a confié, et les retirer casserait sa vue par
    locataire sans qu'aucun test ne le dise.

    Nommée `AccesOut` jusqu'au 04/11/2026 : homonyme du schéma du bailleur
    (`routers/bailleur/acces.py`), elle aurait donné à l'un et l'autre un nom de
    module dans le contrat, dès qu'une route la déclare (#2507). C'est le nom que
    le client du site lui donnait déjà.
    """

    id: int
    code: str
    statut: StatutAcces
    chez_locataire: bool
    bail_id: Optional[int] = None
    lot_id: Optional[int] = None
    #: 🔹 Ce que l'accès OUVRE — des CODES de périmètre, jamais un libellé.
    #:
    #: ⚠️ L'écran les met en forme lui-même (`BadgePerimetre`), comme partout
    #: ailleurs : envoyer un libellé obligerait le serveur à décider d'un rendu,
    #: et ferait de chaque route un endroit où le nom d'un périmètre s'écrit.
    perimetre_cible: list[str] = []
    #: 🏠 Le lot, tel qu'un humain le lit — voir `libelle_lots` pour la règle
    #: de NATURE, qui est tout le sujet de cette colonne.
    lot_libelle: Optional[str] = None
    cree_le: datetime

    @classmethod
    def champs_communs(cls, session: Session, type_acces: TypeAcces, objet) -> dict:
        """Les champs que les deux vues partagent, lus une seule fois.

        C'est le point d'héritage : une vue enrichie appelle ceci et ajoute les
        siens. Recopier ces huit lignes dans la seconde vue serait exactement la
        duplication que ce module existe pour supprimer.
        """
        return {
            "id": objet.id,
            "code": objet.code,
            "statut": objet.statut,
            "chez_locataire": objet.chez_locataire,
            "bail_id": objet.bail_id,
            "lot_id": objet.lot_id,
            "perimetre_cible": parse_json_perimetres(objet.perimetre_cible),
            "lot_libelle": libelle_lots(session, type_acces, objet),
            "cree_le": objet.cree_le,
        }

    @classmethod
    def depuis(cls, session: Session, type_acces: TypeAcces, objets) -> list["AccesPorteur"]:
        """La liste, dans l'ordre reçu — le tri appartient à l'appelant."""
        return [cls(**cls.champs_communs(session, type_acces, o)) for o in objets]
