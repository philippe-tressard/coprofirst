"""Le libellé d'un étage — « RDC », « 1er », « 2ème », « SS 1 ».

Un module à lui seul, et non une ligne dans `dates_fr` : un étage n'est pas une
date, et ranger une notion là où elle tombe sous la main est ce qui produit les
fichiers de mille lignes que le plafond de modularité refuse ensuite.
"""

from __future__ import annotations
from app.utils.valeurs import valeur

#: Les bornes d'un étage saisi. Au-delà, ce n'est pas une donnée, c'est une faute
#: de frappe : un `4` devenu `44`, un signe en trop.
#:
#: 🔴 Elles étaient écrites **en clair dans `auth.py`** (#835), et le commentaire
#: qui les accompagnait disait déjà pourquoi elles devaient être vérifiées côté
#: serveur — *« un champ borné côté client se poste directement »*. Le jour où un
#: second écran a permis de saisir un étage (celui d'un LOT, 09/09/2026), la
#: règle allait être recopiée : elle vit ici, avec le libellé qu'elle borne.
ETAGE_MIN = -2
ETAGE_MAX = 50

#: Le message rendu à qui sort des bornes — une seule formulation, pour que les
#: deux écrans disent la même chose.
ETAGE_HORS_BORNES = f"Étage attendu entre {ETAGE_MIN} et {ETAGE_MAX}."


def etage_hors_bornes(etage: int) -> bool:
    """L'étage saisi est-il hors de ce qu'un immeuble peut porter ?"""
    return not ETAGE_MIN <= etage <= ETAGE_MAX


def etage_label(etage, *, suffixe: bool = False) -> str:
    """« RDC », « 1er », « 2ème », « SS 1 » — le libellé d'un étage, côté serveur.

    `suffixe` ajoute « étage » à un étage au-dessus du sol (« 2ème étage ») : le
    paramètre de même nom du front, pour une ligne de texte plutôt qu'une valeur
    de définition. L'annuaire le sert ainsi (`etage_libelle`, #2505).

    ## Pourquoi ici, et pourquoi une copie (08/09/2026)

    Le pendant de `front/src/lib/utils.ts::etageLabel`. Les contextes de build
    sont `./api` et `./front` : le partage d'un fichier est impossible, seule la
    copie l'est — comme `KANBAN_LABELS` et la correspondance du kanban.
    `api/tests/test_etage_label.py` échoue si les deux dérivent.

    🔴 Ce qu'elle remplace, dans `fiche_arrivant.py` :

        etage_html = f"Étage {m['etage']}" if m.get("etage") else ""

    Deux défauts en une ligne. Le second est le plus grave :

    1. « Étage 0 » pour un rez-de-chaussée, « Étage -1 » pour un sous-sol —
       alors que tout le reste du site écrit « RDC » et « SS 1 » ;
    2. 🔴 **`if m.get("etage")` est un test de VÉRITÉ** : `0` est faux en
       Python. Un conseiller du rez-de-chaussée n'avait donc **aucun étage**
       sur la fiche d'accueil remise aux nouveaux arrivants — pas un étage
       faux, un étage absent. Le seul cas où l'information manque est
       précisément celui où elle est la plus simple à donner.

    ⚠️ Rend une chaîne **vide** pour `None`, jamais « — » : c'est l'appelant qui
    décide de ce qu'il affiche à la place.
    """
    if etage is None or etage == "":
        return ""
    #  🔴 La donnée n'est PAS toujours un entier, et je l'avais supposé : la
    #  fiche arrivant construit ses dictionnaires depuis la base ET depuis un
    #  import, où l'étage peut arriver en chaîne. Neuf tests l'ont dit tout de
    #  suite — `'<' not supported between instances of 'str' and 'int'`.
    #
    #  ⚠️ Une valeur illisible est rendue TELLE QUELLE, jamais effacée : c'est la
    #  même règle que `lotTypeLabel` pour un type inconnu. Perdre l'information
    #  serait pire que l'afficher sans la mettre en forme — et c'est précisément
    #  le défaut que cette fonction corrige.
    try:
        niveau = int(etage)
    except (TypeError, ValueError):
        return str(etage)
    if niveau == 0:
        return "RDC"
    if niveau < 0:
        return f"SS {abs(niveau)}"
    rang = "1er" if niveau == 1 else f"{niveau}ème"
    return f"{rang} étage" if suffixe else rang


def type_de_lot(lot) -> str:
    """Le type d'un lot en clair — l'enum et la chaîne se lisent pareil.

    `Lot.type` est un `TypeLot`, mais les lots arrivent aussi d'un import ou d'un
    dictionnaire de test où le type est une chaîne. `auto_match_service` fait déjà
    ce `hasattr(..., "value")` sur un statut : la forme est celle du projet.

    ⚠️ Publique, et employée par `_lot_read` : la même ligne y était écrite en
    clair, et c'est la deuxième écriture qui aurait figé la première.
    """
    brut = getattr(lot, "type", None)
    return str(valeur(brut) or "")


def logement_de_reference(lots) -> object | None:
    """Le logement qui peut renseigner l'étage où l'on VIT — ou `None`.

    ## Les trois conditions, et chacune retire un cas où la réponse serait fausse

    1. **un seul logement**, sinon on ne saurait pas lequel il habite. Choisir
       « le premier appartement » donnerait une réponse plausible et parfois
       fausse, ce qui est le pire des deux : personne ne la remettrait en cause ;
    2. **de type appartement** — un copropriétaire dont l'unique lot est un
       parking ou une cave **n'habite pas son lot**. En déduire « SS 1 » serait
       une réponse à côté de la question ;
    3. **l'étage du lot est connu** — un logement sans étage saisi n'apprend
       rien, et le comparer à la saisie du résident inventerait une divergence.

    🔴 Cette règle a déjà vécu **une fois** : elle s'appelait `etageParDefaut`
    côté front (08/09/2026), et elle a été supprimée le lendemain avec son test
    quand le champ personnel a quitté le profil — puis redemandée le soir même.
    Elle vit désormais côté serveur, où l'alerte de divergence en a besoin de
    toute façon, et le front l'obtient par l'API plutôt qu'en la recalculant.
    """
    logements = [
        lot
        for lot in lots
        if type_de_lot(lot) == "appartement" and getattr(lot, "etage", None) is not None
    ]
    return logements[0] if len(logements) == 1 else None


def etage_effectif(etage_saisi: int | None, lots) -> int | None:
    """L'étage à AFFICHER : le lot fait autorité, la saisie prend le relais.

    Arbitré par Philippe le 09/09/2026 : *« préférer celle du Lot »*. L'étage
    d'un lot vient du classeur de la copropriété ; celui que le résident saisit
    est un repère de voisinage qu'il est le seul à pouvoir donner quand aucun lot
    ne le porte — un locataire, ou un bailleur qui habite ailleurs.

    ⚠️ La saisie n'est jamais **écrasée** en base : c'est elle qui permet de
    constater la divergence, et sans elle l'administrateur n'aurait rien à
    vérifier. Le lot gagne à l'affichage, pas à l'écriture.
    """
    logement = logement_de_reference(lots)
    if logement is not None:
        return logement.etage
    return etage_saisi


def divergence_etage(etage_saisi: int | None, lots) -> tuple[int, int] | None:
    """`(saisi, lot)` quand les deux se contredisent — `None` sinon.

    ⚠️ Une saisie **absente** n'est pas une divergence : ne rien dire n'est pas
    dire le contraire. Même remarque pour un lot sans étage, déjà écarté par
    `logement_de_reference`.
    """
    if etage_saisi is None:
        return None
    logement = logement_de_reference(lots)
    if logement is None or logement.etage == etage_saisi:
        return None
    return (etage_saisi, logement.etage)
