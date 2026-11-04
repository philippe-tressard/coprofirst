"""L'inventaire du contrat, et ce qu'un écart casserait chez un client (#2456).

Le schéma OpenAPI entier change à chaque docstring retouchée : la version du
contrat ne se juge pas sur lui, mais sur ce qu'un client généré LIT et ENVOIE.

Par opération (`GET /tickets/{ticket_id}`) :
- `deprecie` — l'opération est annoncée au retrait (`deprecated=True` sur la route) ;
- `entree` — ce que le client DOIT envoyer : paramètres requis (`query:nom`,
  `path:nom`…) et champs requis du corps (`corps.nom`) ;
- `reponse` — chaque champ des réponses 2xx, par son chemin (`$.auteur.nom`,
  `$[].id`, `$.{}` pour les valeurs d'un dictionnaire) et son type ; `?` quand il
  peut manquer ou valoir `null`, ` déprécié` quand il est annoncé au retrait
  (`Field(json_schema_extra={"deprecated": True})`).

## Ce qui casse un client, et ce qui ne le casse pas

Ajouter une opération ou un champ : libre. Retirer une opération ou un champ,
changer son type, le rendre facultatif : un client décodait ce champ — refusé,
sauf retrait annoncé (`retraits.py`). Le resserrer (`string?` → `string`, ou typer une
réponse libre) : libre.
Exiger une entrée neuve d'une opération existante : refusé — elle est facultative,
ou c'est une opération neuve.

Ce que l'inventaire ne voit pas : les VALEURS d'une énumération (une valeur neuve
peut faire échouer un décodage strict côté client), et les corps non JSON.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

_DEPRECIE = " déprécié"
_CORPS = ("application/json", "multipart/form-data", "application/x-www-form-urlencoded")


def _resoudre(sch: dict, defs: dict) -> tuple[dict, str | None]:
    nom = None
    while "$ref" in sch:
        nom = sch["$ref"].rsplit("/", 1)[-1]
        sch = defs[nom]
    return sch, nom


def _variantes(sch: dict, defs: dict) -> tuple[list[dict], bool]:
    """Les branches non nulles d'un schéma (`anyOf`, `oneOf`, `allOf` d'un seul), et s'il admet `null`."""
    sch, _ = _resoudre(sch, defs)
    for cle in ("anyOf", "oneOf"):
        if cle in sch:
            branches = [b for b in sch[cle] if _resoudre(b, defs)[0].get("type") != "null"]
            return branches, len(branches) < len(sch[cle])
    if len(sch.get("allOf", [])) == 1:
        return _variantes(sch["allOf"][0], defs)
    t = sch.get("type")
    if isinstance(t, list):
        return [{**sch, "type": next((x for x in t if x != "null"), None)}], "null" in t
    return [sch], False


def _libelle(sch: dict, defs: dict) -> str:
    sch, _ = _resoudre(sch, defs)
    if "properties" in sch or sch.get("type") == "object":
        return (
            "dictionnaire"
            if "properties" not in sch and sch.get("additionalProperties")
            else "objet"
        )
    if sch.get("type") == "array":
        return "liste"
    if not sch.get("type"):
        return "libre"
    return f"{sch['type']}({sch['format']})" if "format" in sch else sch["type"]


def _type(sch: dict, defs: dict, facultatif: bool) -> str:
    branches, nullable = _variantes(sch, defs)
    libelle = "|".join(sorted({_libelle(b, defs) for b in branches})) or "libre"
    return (
        libelle
        + ("?" if facultatif or nullable else "")
        + (_DEPRECIE if sch.get("deprecated") else "")
    )


def _descendre(sch: dict, defs: dict, chemin: str, pile: frozenset, sortie: dict) -> None:
    """Les champs SOUS `chemin` — un cycle de références s'arrête à sa première reprise."""
    _, nom = _resoudre(sch, defs)
    if nom in pile:
        return
    pile = pile | {nom} if nom else pile
    for branche in _variantes(sch, defs)[0]:
        corps, nom_branche = _resoudre(branche, defs)
        if nom_branche in pile and nom_branche != nom:
            continue
        sous_pile = pile | {nom_branche} if nom_branche else pile
        requis = set(corps.get("required", []))
        for nom_champ, enfant in corps.get("properties", {}).items():
            cle = f"{chemin}.{nom_champ}"
            sortie.setdefault(cle, _type(enfant, defs, nom_champ not in requis))
            _descendre(enfant, defs, cle, sous_pile, sortie)
        if corps.get("type") == "array" and "items" in corps:
            cle = f"{chemin}[]"
            sortie.setdefault(cle, _type(corps["items"], defs, False))
            _descendre(corps["items"], defs, cle, sous_pile, sortie)
        if isinstance(corps.get("additionalProperties"), dict) and corps["additionalProperties"]:
            cle = f"{chemin}.{{}}"
            sortie.setdefault(cle, _type(corps["additionalProperties"], defs, False))
            _descendre(corps["additionalProperties"], defs, cle, sous_pile, sortie)


def _reponse(op: dict, defs: dict) -> dict[str, str]:
    sortie: dict[str, str] = {}
    for code, reponse in sorted(op.get("responses", {}).items()):
        contenu = reponse.get("content", {})
        sch = contenu.get("application/json", {}).get("schema")
        if code.startswith("2") and sch is not None:
            sortie.setdefault("$", _type(sch, defs, False))
            _descendre(sch, defs, "$", frozenset(), sortie)
        elif code.startswith("2") and contenu:
            #  Un fichier (PDF, image…) : le client le lit en octets (#2505).
            sortie.setdefault("$", "fichier")
    return dict(sorted(sortie.items()))


def _entree(op: dict, defs: dict) -> list[str]:
    requises = {f"{p['in']}:{p['name']}" for p in op.get("parameters", []) if p.get("required")}
    corps = op.get("requestBody", {})
    for type_mime in _CORPS:
        sch = corps.get("content", {}).get(type_mime, {}).get("schema")
        if sch is None:
            continue
        if corps.get("required"):
            requises.add("corps")
        for branche in _variantes(sch, defs)[0]:
            resolu, _ = _resoudre(branche, defs)
            requises |= {f"corps.{nom}" for nom in resolu.get("required", [])}
    return sorted(requises)


def inventaire(schema: dict) -> dict[str, dict]:
    """L'inventaire d'un schéma OpenAPI : `{"GET /chemin": {deprecie, entree, reponse}}`."""
    defs = schema.get("components", {}).get("schemas", {})
    return {
        f"{methode.upper()} {chemin}": {
            "deprecie": bool(op.get("deprecated")),
            "entree": _entree(op, defs),
            "reponse": _reponse(op, defs),
        }
        for chemin, methodes in sorted(schema.get("paths", {}).items())
        for methode, op in sorted(methodes.items())
    }


def empreinte(operations: dict[str, dict]) -> str:
    """L'empreinte d'un inventaire : deux lots qui le changent se rencontrent sur elle."""
    texte = json.dumps(operations, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


@dataclass
class Ecarts:
    """Ce qui sépare l'inventaire du code de la référence."""

    retraits: list[str] = field(default_factory=list)  #: `GET /x` ou `GET /x → $.champ`
    exigences: list[str] = field(default_factory=list)  #: `GET /x ← corps.champ`
    modifie: bool = False


def _sans_marque(type_: str) -> str:
    return type_.removesuffix(_DEPRECIE)


def _compatible(ancien: str, nouveau: str) -> bool:
    """Un champ qui change de type reste lisible : même type, ou resserré (`T?` → `T`).

    Une réponse LIBRE (aucun schéma, `{}`) qui se type est un resserrement aussi
    (#2506) : le client la décodait en JSON quelconque, il lit la forme typée. Ce qui
    était libre et facultatif (`libre?`) peut devenir présent et typé. L'inverse — un
    type qui redevient libre — reste un retrait.

    De même un DICTIONNAIRE libre (`list[dict]`) qui devient un objet (#2505) : le
    client le lisait en table de valeurs quelconques, il lit l'objet ; des valeurs
    typées, s'il en avait, restent gardées par leur chemin (`$.{}`). Une réponse
    libre qui devient un `fichier` (`REPONSE_FICHIER`) suit la règle du libre.
    """
    a, n = _sans_marque(ancien), _sans_marque(nouveau)
    if a == "libre?" or (a == "libre" and not n.endswith("?")):
        return True
    if a.removesuffix("?") == "dictionnaire" and n in ("objet", a.replace("dictionnaire", "objet")):
        return True
    return a == n or (a.endswith("?") and a[:-1] == n)


def comparer(reference: dict[str, dict], courant: dict[str, dict]) -> Ecarts:
    """Les écarts de `courant` à `reference` (deux inventaires)."""
    ecarts = Ecarts(modifie=reference != courant)
    for cle, avant in reference.items():
        apres = courant.get(cle)
        if apres is None:
            ecarts.retraits.append(cle)
            continue
        for chemin, type_ in avant["reponse"].items():
            if chemin not in apres["reponse"] or not _compatible(type_, apres["reponse"][chemin]):
                ecarts.retraits.append(f"{cle} → {chemin}")
        neuves = set(apres["entree"]) - set(avant["entree"])
        ecarts.exigences += [f"{cle} ← {e}" for e in sorted(neuves)]
    return ecarts


def _version(texte: str) -> tuple[int, ...]:
    return tuple(int(x) for x in texte.split("."))


def _annonce(cible: str, retraits: dict[str, tuple[str, str]]) -> str | None:
    """L'annonce qui couvre `cible` : elle-même, son opération, ou un champ parent."""
    operation, _, chemin = cible.partition(" → ")
    if operation in retraits:
        return operation
    for annonce in retraits:
        op_annonce, _, chemin_annonce = annonce.partition(" → ")
        if (
            op_annonce == operation
            and chemin_annonce
            and (
                chemin == chemin_annonce
                or chemin.startswith((chemin_annonce + ".", chemin_annonce + "["))
            )
        ):
            return annonce
    return None


def refus(ecarts: Ecarts, retraits: dict[str, tuple[str, str]], version_app: str) -> list[str]:
    """Ce qui casserait un client : un retrait non annoncé, ou annoncé dans CETTE version ; une exigence neuve."""
    messages = []
    for cible in ecarts.retraits:
        annonce = _annonce(cible, retraits)
        if annonce is None:
            messages.append(f"{cible} : retiré sans avoir été annoncé (`retraits.RETRAITS`)")
        elif _version(retraits[annonce][0]) >= _version(version_app):
            messages.append(
                f"{cible} : annoncé en {retraits[annonce][0]}, retiré dans la même version — "
                "le retrait vient dans une version ultérieure"
            )
    messages += [
        f"{e} : une entrée neuve d'une opération existante est facultative"
        for e in ecarts.exigences
    ]
    return messages


def annonces_non_marquees(
    courant: dict[str, dict], retraits: dict[str, tuple[str, str]]
) -> list[str]:
    """Les retraits annoncés dont la cible est encore servie SANS être dépréciée dans le contrat."""
    manquantes = []
    for annonce in retraits:
        operation, _, chemin = annonce.partition(" → ")
        op = courant.get(operation)
        if op is None or (chemin and chemin not in op["reponse"]):
            continue  # déjà retirée : l'annonce reste, c'est la trace du retrait
        marquee = op["reponse"][chemin].endswith(_DEPRECIE) if chemin else op["deprecie"]
        if not marquee:
            manquantes.append(annonce)
    return manquantes


def version_suivante(version: str, ecarts: Ecarts) -> str:
    """Majeure + 1 sur un retrait (annoncé), mineure + 1 sur tout autre écart, sinon inchangée."""
    majeure, mineure, _ = _version(version)
    if ecarts.retraits:
        return f"{majeure + 1}.0.0"
    if ecarts.modifie:
        return f"{majeure}.{mineure + 1}.0"
    return version
