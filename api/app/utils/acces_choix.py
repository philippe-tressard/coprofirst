"""Ce qu'un accès a le DROIT d'ouvrir — la liste fermée, et une seule.

## La demande (14/09/2026, #953)

> « Est-ce possible de restreindre pour badges & télécommandes que le périmètre
>   soit parmi :
>   * pour les vigik : copropriété entière ; bâtiment x
>   * pour les télécommandes : "Parking résidence / portail d'accès" + "AFUL /
>     portail public" »

Oui — et c'est la même décision que celle déjà prise pour la déduction, prise une
fois de plus : **un accès n'est pas un périmètre libre**. Le sélecteur ouvrait
l'arbre entier, si bien qu'un badge pouvait se voir attribuer « Bât. 2 › Local
poubelles », qui ne correspond à aucune serrure.

## Pourquoi ici, et pas dans l'écran

🔒 **Une restriction qui ne vit que dans le formulaire n'est pas une
restriction** : la route accepterait toujours n'importe quel code, et le premier
appel direct — ou un écran futur — passerait à côté. La liste est donc calculée
ici, servie à l'écran pour qu'il propose, **et** opposée à la requête pour qu'il
ne dispose pas. Deux usages, une écriture (`standards/03-securite.md` §1).

## D'où sortent les codes — de l'arbre, jamais du code source

| Type | Ce qui est autorisé | D'où ça vient |
|---|---|---|
| vigik | la copropriété entière, chaque bâtiment, **et les portillons** | `code_par_defaut()`, les nœuds qui **portent** un `batiment_id`, plus la clé `acces_fixes_vigik` |
| télécommande | les portails | la clé `acces_fixes_telecommande` |

Les deux clés de `config_site` sont posées par la migration 0191 et administrées
ensuite. « Fixes » dit ce qu'elles portent : des accès qui ne dépendent **d'aucun
lot** — un portillon s'ouvre pareil pour tout le monde. C'est la seule chose qui
sépare les deux types ici : un vigik ajoute ses fixes à ce qu'il déduit, une
télécommande n'a QUE des fixes.

⚠️ Les portillons ont été ajoutés le 15/09/2026, sur correction : *« pour les
vigik : copropriété entière ou bâtiment x et Extérieurs / portillons »*. Une
seconde clé plutôt qu'une règle en dur — parce que la première version de ce
lot avait justement fait l'erreur inverse pour les télécommandes.

⚠️ Aucun code de périmètre n'est écrit ici. « Parking résidence », « AFUL » et
« Bâtiment 1 » sont des nœuds de CETTE arborescence : les nommer serait la faute
déjà corrigée pour l'AFUL (0189) et pour le nom du site (v1.36.7) — le produit
doit servir une copropriété qui n'a ni AFUL, ni quatre bâtiments.

⚠️ **Un arbre vide n'autorise rien de particulier, il n'interdit rien** : la
liste est alors vide, et `valider_acces` laisse passer. Une restriction qui se
retourne en blocage total sur une donnée absente ferait d'une copropriété non
configurée une copropriété paralysée — c'est le « cas zéro » de
`standards/04-fiabilite-des-controles.md` §2.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.core import ConfigSite
from app.utils.config_site import ecrire_cle
from app.utils.perimetres import arbre, code_par_defaut
from app.utils.types_acces import TYPES_ACCES, TypeAcces


def cle_config(type_acces: TypeAcces) -> str:
    """La clé de `config_site` qui porte les accès **fixes** de ce type.

    Composée, pas énumérée : un troisième type d'accès (une clé, un bip)
    apporterait sa clé sans qu'on touche à ce fichier.
    """
    return f"acces_fixes_{type_acces.cle}"


def _codes_configures(session: Session, cle: str) -> list[str]:
    """Les codes lus dans la configuration — liste vide si rien de lisible.

    ⚠️ Une valeur illisible rend une liste **vide**, pas une erreur : la
    configuration est administrable, et une saisie malheureuse ne doit pas rendre
    l'écran des badges inutilisable. Elle se voit alors — plus aucun choix n'est
    proposé — ce qui est le bon sens de l'échec.
    """
    ligne = session.exec(select(ConfigSite).where(ConfigSite.cle == cle)).first()
    if not ligne or not ligne.valeur:
        return []
    try:
        codes = json.loads(ligne.valeur)
    except ValueError:
        return []
    if not isinstance(codes, list):
        return []
    return [str(c) for c in codes if c]


def types_fixes_par_code(session: Session) -> dict[str, list[str]]:
    """{code de périmètre: [clés des types d'accès qui l'ouvrent d'office]}.

    Ce que l'écran des périmètres coche (#2060) : les deux listes de la
    configuration lues à l'envers, nœud par nœud.
    """
    par_code: dict[str, list[str]] = {}
    for type_acces in TYPES_ACCES.values():
        for code in _codes_configures(session, cle_config(type_acces)):
            par_code.setdefault(code, []).append(type_acces.cle)
    return par_code


def fixer_acces(session: Session, code: str, types: list[str]) -> None:
    """Ce périmètre est un accès fixe des `types` cités, et de ceux-là seuls (#2060).

    🔴 Les clés `acces_fixes_*` étaient lues ici sans qu'aucun écran ne les écrive :
    un portillon ne s'ajoutait que par un `PUT /config` composé à la main. Elles
    se règlent désormais sur le périmètre qu'elles nomment, et la liste se
    compose ICI — `PUT /config` les refuse. Sans valider la transaction.
    """
    inconnus = set(types) - TYPES_ACCES.keys()
    if inconnus:
        raise HTTPException(422, f"Type d'accès inconnu : {', '.join(sorted(inconnus))}.")
    for type_acces in TYPES_ACCES.values():
        codes = _codes_configures(session, cle_config(type_acces))
        voulu = type_acces.cle in types
        if voulu == (code in codes):
            continue
        codes = codes + [code] if voulu else [c for c in codes if c != code]
        ecrire_cle(session, cle_config(type_acces), json.dumps(codes, ensure_ascii=False))


def codes_batiments() -> list[str]:
    """Les nœuds de l'arbre qui SONT un bâtiment, dans l'ordre de l'arbre.

    Seul le nœud « bâtiment » porte un `batiment_id` ; ses espaces (hall,
    ascenseur…) l'héritent de leur ancêtre — c'est écrit dans
    `perimetre_du_batiment`, et c'est ce qui rend ce filtre exact sans qu'on ait à
    reconnaître un préfixe de code.
    """
    noeuds = [
        n for n in arbre().values() if n.batiment_id is not None and n.actif and n.selectionnable
    ]
    return [n.code for n in sorted(noeuds, key=lambda n: (n.ordre, n.code))]


def codes_autorises(session: Session, type_acces: TypeAcces) -> list[str]:
    """Les périmètres que ce type d'accès peut ouvrir — la liste fermée.

    🔴 **La distinction ne s'écrit pas ici en `if type == "telecommande"`** : elle
    est portée par le descripteur (`TypeAcces.acces_suit_le_lot`), comme les six
    autres différences entre les deux types. Un `if` sur la clé serait une
    huitième façon de dire « ces deux objets ne sont pas pareils », libre de
    diverger des sept autres.
    """
    fixes = _codes_configures(session, cle_config(type_acces))
    if not type_acces.acces_suit_le_lot:
        return fixes
    defaut = code_par_defaut()
    #  ⚠️ L'ordre est celui de l'écran : ce qui englobe, puis les bâtiments, puis
    #  les accès qui ne dépendent d'aucun lot. Un `set` rendrait la même liste
    #  dans un ordre différent à chaque démarrage, et la rangée de pastilles
    #  changerait de forme sous les yeux de qui la lit.
    autorises = ([defaut] if defaut else []) + codes_batiments()
    return autorises + [c for c in fixes if c not in autorises]


def acces_par_defaut(session: Session, type_acces: TypeAcces) -> Optional[list[str]]:
    """L'accès d'un objet dont le périmètre ne se déduit pas d'un lot.

    Une télécommande ouvre **les** portails, pas l'un d'eux : ses accès fixes sont
    donc aussi sa valeur par défaut. Les deux notions coïncident, et les écrire
    séparément les ferait diverger au premier portail ajouté.

    ⚠️ Réservé aux types dont l'accès ne suit PAS le lot. Pour un vigik, le défaut
    se déduit du bâtiment (`utils/acces_perimetre`) : ses portillons sont une
    faculté, pas une valeur par défaut — les lui poser d'office attribuerait un
    accès que personne n'a décidé.
    """
    codes = _codes_configures(session, cle_config(type_acces))
    return codes or None


def valider_acces(session: Session, type_acces: TypeAcces, codes: Optional[list[str]]) -> None:
    """Refuse un accès qui sort de la liste — 422, en nommant le fautif.

    ⚠️ Trois cas passent, et chacun est une décision :

    * `None` — le champ n'est pas transmis : il n'y a rien à valider ;
    * `[]` — « on ne sait pas », déjà reconnu partout ailleurs comme une valeur
      légitime (`_acces_json`) ;
    * liste vide d'autorisés — l'arbre n'est pas configuré, voir l'en-tête.
    """
    if not codes:
        return
    permis = codes_autorises(session, type_acces)
    if not permis:
        return
    intrus = [c for c in codes if c not in permis]
    if intrus:
        raise HTTPException(
            422,
            f"Accès impossible pour un(e) {type_acces.libelle} : " + ", ".join(intrus),
        )
