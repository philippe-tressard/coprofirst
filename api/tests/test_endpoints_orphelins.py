"""Garde-fou : aucun endpoint ne doit rester exposé sans consommateur.

Le 03/08/2026, la bascule des pièces jointes vers `POST /uploads/fichier` a laissé
`POST /uploads/ticket/{id}` et `POST /uploads/evenement/{id}` sans un seul
appelant — repérés à l'œil, pas par un contrôle. Un endpoint orphelin n'est pas
qu'un déchet :

  - il reste une **surface d'attaque** authentifiée que plus personne ne teste ;
  - il **ment** sur le fonctionnement réel du produit à qui lit le code ;
  - il fige un schéma (`photos_urls` alimenté après création) que la nouvelle
    logique ne respecte plus, donc il diverge en silence.

Le contrôle est statique : il lit les décorateurs `@router.<méthode>("…")` sans
importer l'application (pas de base, pas d'effet de bord), puis cherche un
consommateur dans le front **et** dans les scripts d'infra — `maintenance.sh` et
`check-reliability.sh` sont des clients aussi légitimes qu'une page Svelte.

Les deux sens sont vérifiés, conformément au principe « un contrôle qui ne peut
pas s'exécuter renvoie INCONNU » :
  - une route orpheline non déclarée fait échouer le test ;
  - une entrée de la liste d'exceptions qui a retrouvé un consommateur le fait aussi,
    sinon la liste se remplit et ne protège plus rien.
"""

import ast
import pathlib
import re

import pytest
from tests.aides_sources import modules_app
from tests.conftest import scripts_shell_versionnes

RACINE = pathlib.Path(__file__).resolve().parents[2]
ROUTEURS = RACINE / "api" / "app" / "routers"

#: Routes légitimement absentes du front, avec la raison. Toute entrée ajoutée
#: ici est une décision consciente : si la raison ne tient pas en une ligne,
#: c'est probablement que la route doit être supprimée.
SANS_CONSOMMATEUR_FRONT = {
    "/admin/db/checkpoint": "voie in-process obligatoire contre la corruption SQLite (CLAUDE.md, "
    "règle d'or) — appelée à la main pendant un incident, jamais par le front",
    "/acces/admin/imports/{import_id}/refuser-locataire": "pendant de `resoudre` documenté dans specs/architecture/api.md, "
    "conservé pour l'exploitation manuelle des imports Vigik",
    "/prestataires/releves/{r_id}/photo/{nom}": "idem, pour `releve_compteur.photo_url` — le GET passait auparavant par "
    "coïncidence, le POST d'upload partageant son chemin (cf. limite de "
    "`_motif`) ; les chemins diffèrent depuis la 0126, il est donc vu",
}


def _prefixe_declare(chemin: pathlib.Path) -> str:
    """Le `prefix=` passé à `APIRouter(...)` dans ce fichier, ou "" s'il n'y en a pas."""
    prefixe = ""
    for noeud in ast.walk(ast.parse(chemin.read_text(encoding="utf-8"))):
        if isinstance(noeud, ast.Call) and getattr(noeud.func, "id", "") == "APIRouter":
            for kw in noeud.keywords:
                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                    prefixe = kw.value.value
    return prefixe


def _routes() -> list[tuple[str, str, str]]:
    """(fichier, méthode, chemin complet) de chaque endpoint déclaré.

    Parcourt les **sous-paquets** (`rglob`), et pas seulement `routers/*.py`. Sans
    cela, découper un router en paquet fait disparaître ses endpoints du champ du
    contrôle : c'est arrivé le 06/08/2026 avec `admin.py` (2057 lignes) devenu le
    paquet `admin/`, et ses 45 routes se sont évaporées d'un coup.

    Le préfixe **s'hérite du paquet**. Dans un paquet découpé, les sous-modules
    déclarent `APIRouter()` nu et c'est l'`__init__.py` qui porte
    `APIRouter(prefix="/admin")` — le montage réel donne donc `/admin/...`. Un
    détecteur qui lit chaque fichier isolément reconstruirait `/db/checkpoint` et
    conclurait que `/admin/db/checkpoint` n'existe plus. C'est exactement le
    message d'erreur qu'a produit ce test au moment du découpage.
    """
    trouvees: list[tuple[str, str, str]] = []
    for module in modules_app("routers"):
        fichier, arbre = module.chemin, module.arbre
        prefixe = _prefixe_declare(fichier)
        if not prefixe and fichier.parent != ROUTEURS:
            #  Sous-module d'un paquet : le préfixe est celui de son `__init__.py`.
            init = fichier.parent / "__init__.py"
            if init.exists():
                prefixe = _prefixe_declare(init)
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in noeud.decorator_list:
                if (
                    isinstance(deco, ast.Call)
                    and isinstance(deco.func, ast.Attribute)
                    and deco.func.attr in {"get", "post", "patch", "put", "delete"}
                    and deco.args
                    and isinstance(deco.args[0], ast.Constant)
                ):
                    trouvees.append(
                        (
                            fichier.name,
                            deco.func.attr.upper(),
                            (prefixe + deco.args[0].value) or "/",
                        )
                    )
    return trouvees


def _sources_consommatrices() -> str:
    """Tout ce qui peut appeler l'API.

    Trois familles de clients, et en oublier une fait déclarer morte une route
    bien vivante — c'est « la portée du contrôle fait partie du contrôle »
    (`standards/05` §9) :

    - le **front**, client évident ;
    - les **scripts d'infra** (`maintenance.sh`, `check-reliability.sh`), qui
      appellent par `curl` ;
    - le **reverse proxy** : depuis le 03/08/2026, `forward_auth` fait interroger
      `/auth/verifier-acces` par Caddy avant de servir un fichier. Cette route
      n'est appelée ni par le front ni par un script — le contrôle l'a signalée
      comme orpheline, à raison de son point de vue, à tort en réalité.
    """
    morceaux = [
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (RACINE / "front" / "src").rglob("*")
        if p.suffix in {".ts", ".js", ".svelte"}
    ]
    morceaux += [p.read_text(encoding="utf-8", errors="ignore") for p in scripts_shell_versionnes()]
    morceaux.append((RACINE / "Caddyfile").read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(morceaux)


def _motif(chemin: str) -> re.Pattern:
    """`/tickets/{id}/evolutions` → motif tolérant à `${…}` et aux concaténations.

    ⚠️ Limite connue : la comparaison porte sur le CHEMIN, pas sur le couple
    (méthode, chemin). Un `GET /x/{id}/photo` sans appelant passe donc au vert si
    un `POST /x/{id}/photo` est appelé quelque part — constaté le 03/08/2026 sur
    les photos de relevés. Distinguer les méthodes produirait beaucoup de bruit
    (une même route porte souvent GET, PATCH et DELETE) ; on préfère l'assumer et
    l'écrire, plutôt qu'un faux vert silencieux.
    """
    segments = [re.escape(s) for s in re.split(r"\{[^}]+\}", chemin)]
    return re.compile(r"[^\s'\"`]*".join(segments))


@pytest.fixture(scope="module")
def orphelines() -> set[str]:
    sources = _sources_consommatrices()
    assert len(sources) > 100_000, (
        "sources consommatrices introuvables ou quasi vides : le contrôle ne peut "
        "pas s'exécuter, il ne doit donc pas passer au vert"
    )
    return {chemin for _, _, chemin in _routes() if not _motif(chemin).search(sources)}


def test_aucun_endpoint_orphelin_non_declare(orphelines):
    """Une route sans appelant doit être supprimée — ou justifiée explicitement."""
    inattendues = sorted(orphelines - set(SANS_CONSOMMATEUR_FRONT))
    assert not inattendues, (
        "Endpoints sans aucun consommateur (front ni script d'infra) :\n  "
        + "\n  ".join(inattendues)
        + "\n\nSupprimer l'endpoint ET son client TypeScript, ou l'inscrire dans "
        "SANS_CONSOMMATEUR_FRONT avec sa raison."
    )


def test_la_liste_dexceptions_ne_pourrit_pas(orphelines):
    """Une exception qui n'a plus lieu d'être doit disparaître de la liste.

    Sans ce sens-là, la liste grossit à chaque cas particulier et finit par
    couvrir des routes redevenues normales : le contrôle reste vert en ne
    contrôlant plus rien.

    Les deux causes sont distinguées, parce qu'elles n'appellent pas la même
    correction — un message qui les confond envoie chercher au mauvais endroit.
    """
    declarees = {chemin for _, _, chemin in _routes()}

    supprimees = sorted(set(SANS_CONSOMMATEUR_FRONT) - declarees)
    assert not supprimees, (
        "Ces routes n'existent plus : retirer leur entrée de "
        "SANS_CONSOMMATEUR_FRONT :\n  " + "\n  ".join(supprimees)
    )

    reutilisees = sorted(set(SANS_CONSOMMATEUR_FRONT) - orphelines - set(supprimees))
    assert not reutilisees, (
        "Ces routes ont désormais un consommateur : elles n'ont plus besoin "
        "d'exception :\n  " + "\n  ".join(reutilisees)
    )


def test_les_routes_sont_bien_detectees():
    """Le détecteur lui-même : s'il ne trouve plus rien, tout paraît consommé."""
    routes = _routes()
    assert len(routes) > 200, f"seulement {len(routes)} routes détectées — parseur cassé ?"
