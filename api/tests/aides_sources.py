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
import re
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


@functools.lru_cache(maxsize=None)
def sources_api(dossier: str, *, minimum: int = 1) -> tuple[tuple[pathlib.Path, str], ...]:
    """Les fichiers Python d'un AUTRE dossier de `api/` (`"alembic"`, `"tests"`) : chemin
    et texte, triés, sans `__pycache__`. Même cas zéro que `modules_app` (#2959)."""
    racine = APP.parent / dossier
    trouves = tuple(
        (p, p.read_text(encoding="utf-8"))
        for p in sorted(racine.rglob("*.py"))
        if "__pycache__" not in p.parts
    )
    assert len(trouves) >= minimum, (
        f"`api/{dossier}/` ne rend que {len(trouves)} fichier(s) (plancher {minimum}) : "
        "le dossier a bougé, et le contrôle qui le lit ne mesure plus rien."
    )
    return trouves


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

    🔴 Le préfixe cumulé est celui de l'INCLUSION (`include_context.prefix`), pas
    celui du routeur inclus : le chemin d'une route porte déjà le préfixe de son
    routeur. Jusqu'au 13/10/2026 elle ajoutait `sous.prefix`, et rendait
    `/auth/auth/me` pour `/auth/me` — des chemins qui n'existent pas, que le
    balayage d'étanchéité appelait en GET et qui répondaient 404 (#1901).
    """
    for route in getattr(routeur, "routes", []):
        sous = getattr(route, "original_router", None)
        inclusion = getattr(getattr(route, "include_context", None), "prefix", "") or ""
        if sous is None and hasattr(route, "routes") and not getattr(route, "path", None):
            sous = route
        if sous is not None and getattr(sous, "routes", None):
            yield from operations_montees(sous, prefixe + inclusion)
        elif getattr(route, "path", None):
            for methode in sorted(getattr(route, "methods", []) or []):
                yield methode, prefixe + route.path, route


def chemin_concret(gabarit: str) -> str:
    """Le gabarit d'une route, chaque paramètre de chemin valant 1 — ce qu'un balayage appelle."""
    return re.sub(r"\{[^}]+\}", "1", gabarit)


def resout(dependant, appels) -> bool:
    """FastAPI résout-il l'une de ces dépendances pour cette route, à quelque niveau que ce
    soit ? Reconnue par l'IDENTITÉ de l'objet, jamais par son nom (`route.dependant`)."""
    return any(d.call in appels or resout(d, appels) for d in dependant.dependencies)


# ─── Un relevé d'appels, écrit une fois (#2912) ──────────────────────────────────
#
# « Cette fonction ATTEINT-elle une porte ? » — elle l'appelle, ou appelle une
# fonction de `app/` qui l'appelle, résolue par les IMPORTS de son module, jamais par
# son nom seul. Seul un appel compte (`ast.Call`) : un commentaire n'est pas dans
# l'AST, et un import qu'on n'appelle pas n'appelle rien. Né pour les points de
# réception de fichier (`test_signature_fichiers.py`) ; les garde-fous qui suivent un
# appel jusqu'à sa porte l'emploient au lieu d'une sous-chaîne dans un texte.

_METHODES_HTTP = {"get", "post", "put", "patch", "delete"}


def _index(modules) -> dict[str, Module]:
    if modules is None:
        modules = modules_app(minimum=PLANCHER_APP)
    return modules if isinstance(modules, dict) else {m.rel: m for m in modules}


def _module_de(nom_module: str, index) -> str | None:
    """`app.utils.fichiers` → `utils/fichiers.py` (ou le `__init__.py` d'un paquet)."""
    if not nom_module.startswith("app."):
        return None
    base = nom_module[4:].replace(".", "/")
    for rel in (f"{base}.py", f"{base}/__init__.py"):
        if rel in index:
            return rel
    return None


def _portee_des_noms(module: Module, index) -> dict[str, tuple[str, str]]:
    """Les noms visibles dans `module` : nom → (module où le chercher, nom là-bas).

    Un nom de MODULE (`from app.utils import fichiers`) rend `(module, "")` : ce sont
    ses attributs qu'on appelle. Une fonction du module masque un import homonyme.
    """
    noms: dict[str, tuple[str, str]] = {}
    paquet = module.rel.rsplit("/", 1)[0].split("/") if "/" in module.rel else []
    for noeud in ast.walk(module.arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                cible = _module_de(alias.name, index)
                if cible and alias.asname:  # `import app.utils.fichiers as fichiers`
                    noms[alias.asname] = (cible, "")
        elif isinstance(noeud, ast.ImportFrom):
            source = noeud.module or ""
            if noeud.level:  # relatif : `from .commun import x` dans `routers/tickets/`
                parents = paquet[: len(paquet) - (noeud.level - 1)]
                source = "app." + ".".join(p for p in [*parents, *source.split(".")] if p)
            for alias in noeud.names:
                sous_module = _module_de(f"{source}.{alias.name}", index)
                cible = _module_de(source, index)
                if sous_module:
                    noms[alias.asname or alias.name] = (sous_module, "")
                elif cible:
                    noms[alias.asname or alias.name] = (cible, alias.name)
    for noeud in module.arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            noms[noeud.name] = (module.rel, noeud.name)
    return noms


def _fonction(index, rel: str, nom: str):
    module = index.get(rel)
    for noeud in module.arbre.body if module else ():
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) and noeud.name == nom:
            return module, noeud
    return module, None


def atteint(rel: str, nom: str, cibles: set[str], *, modules=None, profondeur: int = 5) -> bool:
    """La fonction `nom` de `app/<rel>` APPELLE-t-elle une cible, elle ou une fonction
    de `app/` qu'elle appelle, à `profondeur` appels au plus ?

    `modules` : un index forgé (`{rel: Module}` ou une suite de `Module`) pour les
    témoins ; par défaut, tout `app/`.
    """
    index = _index(modules)
    vus, a_voir = set(), [(rel, nom, 0)]
    while a_voir:
        rel, nom, niveau = a_voir.pop()
        if (rel, nom) in vus or niveau > profondeur:
            continue
        vus.add((rel, nom))
        module, fonction = _fonction(index, rel, nom)
        if fonction is None:
            continue
        portee = _portee_des_noms(module, index)
        for appel in (n for n in ast.walk(fonction) if isinstance(n, ast.Call)):
            f = appel.func
            if isinstance(f, ast.Name):
                if f.id in cibles:
                    return True
                if f.id in portee:
                    a_voir.append((*portee[f.id], niveau + 1))
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                cible = portee.get(f.value.id)
                if cible and cible[1] == "":  # `fichiers.verifier_fichier_recu(…)`
                    if f.attr in cibles:
                        return True
                    a_voir.append((cible[0], f.attr, niveau + 1))
    return False


def _est_une_route(fonction) -> bool:
    """Décorée par `@<routeur>.get|post|put|patch|delete(…)`."""
    return any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and d.func.attr in _METHODES_HTTP
        for d in fonction.decorator_list
    )


def routes_qui_atteignent(cibles: set[str], *, modules=None) -> list[tuple[str, str]]:
    """(module relatif à `app/`, fonction) des routes DÉCORÉES qui atteignent une cible."""
    index = _index(modules)
    return sorted(
        (module.rel, noeud.name)
        for module in index.values()
        for noeud in module.arbre.body
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _est_une_route(noeud)
        and atteint(module.rel, noeud.name, cibles, modules=index)
    )
