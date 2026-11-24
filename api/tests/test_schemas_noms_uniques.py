"""🔒 Aucun nom de classe `BaseModel` en double dans `app/` (#2956).

Deux schémas de même nom ne se voient pas dans le code : chacun vit dans son
module. Ils se voient dans `openapi.json`, joint à chaque release et dont l'app
iOS génère son client : Pydantic qualifie alors LES DEUX noms de leur module
(`app__schemas_communaute__MessageRead`). Le jour où l'un des deux est renommé,
l'autre perd son préfixe — et le type que l'iOS nommait disparaît à la
régénération suivante, sans qu'aucun test du contrat (qui lit des formes, pas
des noms) ne le dise.

Un schéma neuf prend donc un nom neuf. Les doublons d'avant ce contrôle sont
déclarés dans `EXCEPTIONS`, avec leur raison ; une exception qui ne sert plus
fait échouer le test, pour que la liste ne garde pas un nom mort.

Le relevé est syntaxique : une classe est un schéma si l'une de ses bases est
`BaseModel`, ou un schéma de `app/` (par nom, de proche en proche).
"""

from __future__ import annotations

import ast
from collections import defaultdict

from tests.aides_sources import modules_app

#: Nom en double → pourquoi il reste. Un ajout ici demande une raison qu'un
#: renommage ne peut pas lever.
EXCEPTIONS = {
    "MessageRead": (
        "l'iOS épingle le nom qualifié `app__routers__tickets__messages_schemas__MessageRead` "
        "(MessageAffaire.swift) : renommer celui de la Communauté le lui retirerait"
    ),
    "ContactLu": (
        "deux schémas d'administration (`admin/inscription`, `admin/installations`), "
        "qualifiés dans `openapi.json` : un renommage change le nom publié"
    ),
}


def _bases(classe: ast.ClassDef) -> set[str]:
    return {
        b.id if isinstance(b, ast.Name) else b.attr
        for b in classe.bases
        if isinstance(b, (ast.Name, ast.Attribute))
    }


def doublons(arbres: dict[str, ast.Module]) -> dict[str, list[str]]:
    """Les noms de schéma déclarés plus d'une fois, avec leurs emplacements."""
    classes = [
        (n, f"{rel}:{n.lineno}")
        for rel, arbre in arbres.items()
        for n in ast.walk(arbre)
        if isinstance(n, ast.ClassDef)
    ]
    schemas = {"BaseModel"}
    while neufs := {c.name for c, _ in classes if _bases(c) & schemas} - schemas:
        schemas |= neufs
    lieux: dict[str, list[str]] = defaultdict(list)
    for classe, lieu in classes:
        if _bases(classe) & schemas:
            lieux[classe.name].append(lieu)
    return {nom: ou for nom, ou in lieux.items() if len(ou) > 1}


def _app() -> dict[str, ast.Module]:
    return {m.rel: m.arbre for m in modules_app(minimum=100)}


def test_aucun_nom_de_schema_en_double():
    neufs = {n: ou for n, ou in doublons(_app()).items() if n not in EXCEPTIONS}
    assert not neufs, (
        "Nom de schéma déjà pris dans app/ — il se qualifierait de son module dans "
        f"openapi.json, que l'iOS génère : choisir un nom neuf. {neufs}"
    )


def test_chaque_exception_sert_encore():
    mortes = sorted(set(EXCEPTIONS) - set(doublons(_app())))
    assert not mortes, f"exceptions qui ne servent plus, à retirer : {mortes}"


def test_temoin_un_doublon_forge_est_vu():
    """Cas zéro : deux schémas forgés de même nom, l'un par héritage indirect."""
    arbres = {
        "a.py": ast.parse("class Base(BaseModel): ...\nclass Fiche(Base): ...\n"),
        "b.py": ast.parse("class Fiche(pydantic.BaseModel): ...\nclass Autre: ...\n"),
        "c.py": ast.parse("class Autre: ...\n"),
    }
    assert doublons(arbres) == {"Fiche": ["a.py:2", "b.py:1"]}
