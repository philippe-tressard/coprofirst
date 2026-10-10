"""Le code de l'application, lu UNE fois pour tous les tests (#1495).

## Pourquoi cette aide existe (30/09/2026)

Soixante-huit fichiers de tests parcouraient `app/**/*.py` chacun à sa façon :
`rglob` puis filtre de `__pycache__` — ou pas —, lecture, `ast.parse`, et un
plancher de cas zéro choisi à la main (> 25, > 40, > 50, > 100), quand il y en
avait un. Chaque copie était correcte le jour de son écriture ; ensemble, elles
avaient déjà divergé sur ce qu'elles lisaient (`standards/05` §9, corollaire :
**une portée recopiée diverge**).

## Ce qu'elle garantit

- **Une seule portée** : tous les modules de `app/`, triés, sans `__pycache__`.
- **Un cas zéro intégré** : l'arbre entier compte au moins `PLANCHER_APP`
  modules, et chaque sous-dossier demandé au moins `minimum` — un chemin qui a
  bougé fait échouer le test qui le lit, au lieu de le rendre vert sur rien
  (`standards/04` §2).
- **Une lecture par session** : source et arbre syntaxique sont mis en cache.
  ⚠️ L'arbre est PARTAGÉ entre les tests : on le parcourt, on ne le modifie pas.
"""

from __future__ import annotations

import ast
import functools
import pathlib
from dataclasses import dataclass

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Le nombre de modules sous lequel `app/` n'est plus lu en entier. Il y en a
#: près de 300 : un plancher bas ne rate aucune croissance, et attrape la
#: portée cassée qui ne voit plus rien.
PLANCHER_APP = 100


@dataclass(frozen=True)
class Module:
    """Un module de `app/` : son chemin, son chemin relatif, son texte."""

    chemin: pathlib.Path
    rel: str  #: relatif à `app/`, séparateur « / » — `routers/tickets/crud.py`
    source: str

    @functools.cached_property
    def arbre(self) -> ast.Module:
        return ast.parse(self.source, filename=str(self.chemin))

    @property
    def lignes(self) -> list[str]:
        return self.source.splitlines()


@functools.lru_cache(maxsize=None)
def _tous() -> tuple[Module, ...]:
    modules = tuple(
        Module(p, p.relative_to(APP).as_posix(), p.read_text(encoding="utf-8"))
        for p in sorted(APP.rglob("*.py"))
        if "__pycache__" not in p.parts
    )
    assert len(modules) >= PLANCHER_APP, (
        f"`app/` ne compte que {len(modules)} module(s) lus (plancher {PLANCHER_APP}) : "
        "la portée des contrôles a changé, et ils ne mesurent plus rien."
    )
    return modules


def modules_app(sous_dossier: str = "", *, minimum: int = 1) -> tuple[Module, ...]:
    """Les modules de `app/` — ou d'un sous-dossier (`"routers"`, `"utils/email"`).

    Lève si la portée rend moins de `minimum` modules : c'est le cas zéro de
    chaque contrôle qui l'emploie, écrit une fois ici.
    """
    prefixe = f"{sous_dossier.strip('/')}/" if sous_dossier else ""
    trouves = tuple(m for m in _tous() if m.rel.startswith(prefixe))
    assert len(trouves) >= minimum, (
        f"`app/{prefixe}` ne rend que {len(trouves)} module(s) (plancher {minimum}) : "
        "le dossier a bougé, et le contrôle qui le lit ne mesure plus rien."
    )
    return trouves


def docstrings(arbre: ast.AST) -> set[int]:
    """Les `id()` des nœuds qui sont des docstrings — module, classe, fonction.

    Un contrôle qui lit les chaînes littérales du code les écarte : une docstring
    raconte, elle n'exécute rien, et elle doit pouvoir CITER la forme refusée.
    Écrite QUATRE fois jusqu'au 07/10/2026 (#1725), dont deux qui ne vérifiaient pas
    que la constante fût une chaîne, et une qui écartait aussi la première chaîne
    d'un `if` ou d'un `for`.
    """
    vus: set[int] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corps = noeud.body
            if (
                corps
                and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)
            ):
                vus.add(id(corps[0].value))
    return vus


def chaines_du_code(arbre: ast.AST) -> list[ast.Constant]:
    """Les chaînes littérales d'un arbre, docstrings exclues (l'AST ignore les commentaires)."""
    exclues = docstrings(arbre)
    return [
        n
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in exclues
    ]


def module_app(rel: str) -> Module:
    """Un module précis de `app/`, par son chemin relatif — ou lève s'il a disparu."""
    for m in _tous():
        if m.rel == rel:
            return m
    raise AssertionError(f"`app/{rel}` est introuvable : le contrôle vise un module disparu.")


def routeurs_declares() -> dict:
    """Chaque `APIRouter` DÉFINI au niveau d'un module de `app/routers/`, par nom.

    Un routeur importé d'ailleurs (`from .parc import router as …`) ou un paquet
    agrégateur qui inclut ses sous-routeurs n'est compté qu'une fois : là où ses
    routes sont déclarées. Écrite dans `test_routeurs_montes.py` jusqu'au
    02/10/2026, remontée ici quand un second contrôle a dû parcourir les mêmes
    routeurs (#1535).
    """
    import importlib
    import pkgutil

    from fastapi import APIRouter

    import app.routers as paquet

    trouves: dict = {}
    for info in pkgutil.walk_packages(paquet.__path__, paquet.__name__ + "."):
        module = importlib.import_module(info.name)
        for nom, valeur in vars(module).items():
            if isinstance(valeur, APIRouter) and _defini_dans(valeur, module):
                trouves[f"{info.name}.{nom}"] = valeur
    return trouves


def _defini_dans(routeur, module) -> bool:
    """Un routeur « appartient » au module où ses routes sont déclarées.

    Un routeur vide (paquet agrégateur) appartient au module qui l'expose sous
    le nom `router` — c'est la convention de tous les `__init__.py` du dépôt.
    """
    for route in routeur.routes:
        point = getattr(route, "endpoint", None)
        if point is not None:
            return getattr(point, "__module__", None) == module.__name__
    return True


def routes_declarees() -> list:
    """Chaque route d'API (`APIRoute`) déclarée dans `app/routers/`, une fois.

    Lit les routeurs, pas l'application montée : importée seule, celle-ci n'en
    expose presque aucune (le montage dépend du démarrage).
    """
    from fastapi.routing import APIRoute

    return [
        route
        for routeur in routeurs_declares().values()
        for route in routeur.routes
        if isinstance(route, APIRoute)
    ]


def operations_montees(routeur, prefixe: str = ""):
    """Chaque opération montée — `(méthode, chemin complet, route)` —, masquées comprises.

    Cette version de FastAPI n'aplatit plus les routes incluses : `app.routes` rend
    des `_IncludedRouter` opaques, et un parcours naïf n'y voit qu'UNE route. On
    descend par `original_router` en cumulant les préfixes. Elle vivait dans
    `test_routes_uniques.py` ; le test d'étanchéité en a eu besoin (#1746).
    """
    for route in getattr(routeur, "routes", []):
        sous = getattr(route, "original_router", None)
        if sous is None and hasattr(route, "routes") and not getattr(route, "path", None):
            sous = route
        if sous is not None and getattr(sous, "routes", None):
            yield from operations_montees(sous, prefixe + (getattr(sous, "prefix", "") or ""))
        elif getattr(route, "path", None):
            for methode in sorted(getattr(route, "methods", []) or []):
                yield methode, prefixe + route.path, route
