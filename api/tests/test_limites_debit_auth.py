"""Toute route qui éprouve un secret porte une limite de débit, et elle est nommée (#1027).

## Pourquoi ce contrôle

Deux routes d'authentification n'avaient **aucune** limitation de débit le
19/09/2026, et l'une des deux éprouvait un secret :

| Route | Ce qu'elle éprouve | Limite |
|---|---|---|
| `POST /auth/change-password` | un mot de passe, en `verify_password` | **aucune** |
| `GET /auth/verifier-email` | un jeton, passé en clair dans l'URL | **aucune** |

Rien ne disait laquelle manquait : la règle vivait dans `CLAUDE.md` et dans la
skill de sécurité, c'est-à-dire **nulle part où une machine la lise**.

## La portée : l'INTENTION, plus le nom de fichier (audit du 23/11/2026)

La portée était `routers/auth*.py` — un NOM DE FICHIER —, alors que `utils/limiter.py`
définit l'intention : une requête qui soumet un secret devinable. Des routes hors de
ces modules éprouvaient un mot de passe ou la clé partagée des tâches planifiées, sans
plafond. La portée est désormais relevée dans le code (`aides_sources.routes_qui_atteignent`) :

| Ce que la route ATTEINT | La limite exigée |
|---|---|
| `verify_password` (le mot de passe de qui agit) | `LIMITE_SECRET_EPROUVE` |
| `exiger_cle_maintenance` (la clé partagée des nœuds) | `LIMITE_CLE_PARTAGEE` |
| — toute route d'un module `routers/auth*.py` | une constante de `utils.limiter` |

Une route qui n'éprouve le secret que dans UN cas (le profil et la fiche d'un compte, au
changement d'adresse) peut compter la TENTATIVE au lieu de limiter la route :
`utils.limiter.compter_tentative_secret`, appelée avant le secret. Limiter la route entière
bloquait un administrateur qui corrige plusieurs fiches d'affilée (décision du 23/11/2026 :
aucune régression) ; `test_tentative_secret_comptee` le prouve dans les deux sens.

## Ce que le contrôle exige, sur chacune

1. **Une limite**, sans liste d'exceptions : le jour où une route légitime devra s'en
   passer, ce test échouera, et la raison s'écrira ici avec sa date.
2. **Une constante** de `utils.limiter`, jamais un littéral — et la BONNE pour une
   route qui éprouve un secret.
3. **Sous** `@router.<méthode>` : au-dessus, la limite ne s'applique pas, en silence.
4. **Une `request`** dans la signature : sans elle, slowapi lève au premier appel.
"""

from __future__ import annotations

import ast
import pathlib

from tests.aides_sources import Module, module_app, modules_app, routes_qui_atteignent

_LIMITER = pathlib.Path(__file__).resolve().parents[1] / "app" / "utils" / "limiter.py"

_METHODES = {"get", "post", "patch", "put", "delete"}

#: Ce qu'une route atteint → la constante de limite qu'elle doit porter.
INTENTIONS = {
    "verify_password": "LIMITE_SECRET_EPROUVE",
    "exiger_cle_maintenance": "LIMITE_CLE_PARTAGEE",
}

#: Planchers du relevé (cas zéro) : le 23/11/2026, quatre routes éprouvaient un mot de
#: passe et sept la clé partagée.
PLANCHERS = {"verify_password": 4, "exiger_cle_maintenance": 7}


def _constantes_de_limite() -> set[str]:
    """Les noms de constantes exportés par `utils.limiter` — lus, pas recopiés."""
    arbre = ast.parse(_LIMITER.read_text(encoding="utf-8"))
    return {
        cible.id
        for noeud in arbre.body
        if isinstance(noeud, ast.Assign)
        for cible in noeud.targets
        if isinstance(cible, ast.Name) and cible.id.startswith("LIMITE_")
    }


def _route(module: Module, nom: str):
    """(décorateurs, arguments) de la route `nom` du module."""
    for noeud in ast.walk(module.arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) and noeud.name == nom:
            decores = [ast.unparse(d) for d in noeud.decorator_list]
            arguments = [a.arg for a in noeud.args.args] + [a.arg for a in noeud.args.kwonlyargs]
            return decores, arguments
    raise AssertionError(f"{module.rel}::{nom} a disparu")


def _routes_auth() -> list[tuple[str, str]]:
    """Les routes des modules `routers/auth*.py`."""
    trouvees = []
    for module in modules_app("routers"):
        if not pathlib.PurePosixPath(module.rel).name.startswith("auth"):
            continue
        for noeud in ast.walk(module.arbre):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(
                ast.unparse(d).startswith("router.")
                and ast.unparse(d).split("(")[0].split(".")[-1] in _METHODES
                for d in noeud.decorator_list
            ):
                trouvees.append((module.rel, noeud.name))
    return trouvees


def portee(modules=None) -> dict[tuple[str, str], str | None]:
    """Chaque route relevée → la constante EXIGÉE (None : une constante quelconque)."""
    exigences: dict[tuple[str, str], str | None] = dict.fromkeys(_routes_auth())
    for cible, constante in INTENTIONS.items():
        for route in routes_qui_atteignent({cible}, modules=modules):
            exigences[route] = constante
    return exigences


#: La porte qui compte la tentative d'un secret, et la limite qu'elle applique.
A_LA_TENTATIVE = ("compter_tentative_secret", "LIMITE_SECRET_EPROUVE")


def fautes_de_limite(
    module: Module, nom: str, exigee: str | None, connues: set[str], *, tentative: bool = False
) -> list[str]:
    """`tentative` : la route atteint `compter_tentative_secret` — la limite des secrets
    s'y applique à la tentative, la route garde la sienne (ou aucune)."""
    decores, arguments = _route(module, nom)
    limites = [d for d in decores if "limiter.limit" in d]
    ici = f"{module.rel}::{nom}"
    if tentative and exigee == A_LA_TENTATIVE[1]:
        exigee = None
        if not limites:
            return [] if "request" in arguments else [f"{ici} : compte la tentative sans `request`"]
    if not limites:
        return [f"{ici} : aucune limite de débit"]
    fautes = []
    for d in limites:
        argument = d.split("(", 1)[1].rsplit(")", 1)[0].strip()
        if argument not in connues:
            fautes.append(f"{ici} : `{argument}` n'est pas une constante de `utils.limiter`")
    if exigee and not any(exigee in d for d in limites):
        fautes.append(f"{ici} : éprouve un secret — limite attendue `{exigee}`")
    rangs_route = [i for i, d in enumerate(decores) if d.startswith("router.")]
    if rangs_route and min(i for i, d in enumerate(decores) if "limiter.limit" in d) < min(
        rangs_route
    ):
        fautes.append(f"{ici} : `@limiter.limit` AU-DESSUS de la route (sans effet)")
    if "request" not in arguments:
        fautes.append(f"{ici} : limitée sans paramètre `request` (slowapi lève à l'appel)")
    return fautes


def test_le_controle_voit_bien_des_routes():
    """Le cas zéro de la portée : une sortie vide se lirait comme un succès."""
    assert len(_routes_auth()) >= 10, "les modules auth*.py ont perdu leurs routes"
    for cible, plancher in PLANCHERS.items():
        vues = routes_qui_atteignent({cible})
        assert len(vues) >= plancher, f"{len(vues)} route(s) atteignent `{cible}` : portée perdue"
    assert set(INTENTIONS.values()) <= _constantes_de_limite(), "constante de limite disparue"


def test_toute_route_qui_eprouve_un_secret_porte_sa_limite():
    connues = _constantes_de_limite()
    comptees = set(routes_qui_atteignent({A_LA_TENTATIVE[0]}))
    fautes = [
        faute
        for (rel, nom), exigee in sorted(portee().items(), key=lambda x: x[0])
        for faute in fautes_de_limite(
            module_app(rel), nom, exigee, connues, tentative=(rel, nom) in comptees
        )
    ]
    assert not fautes, (
        "Limite de débit absente, mal nommée ou sans effet :\n  "
        + "\n  ".join(fautes)
        + "\n\nUne route qui éprouve un secret sans plafond s'éprouve au rythme du réseau."
    )


def test_temoin_une_route_hors_d_auth_qui_eprouve_un_secret_est_relevee():
    """Le défaut d'avant : une route d'un module quelconque qui atteint le mot de passe,
    par une aide, sans limite — le relevé la voit, le contrôle la refuse."""
    forge = Module(
        chemin=pathlib.Path("forge.py"),
        rel="routers/forge.py",
        source=(
            "from app.utils.forge_aide import changer\n"
            "@router.patch('/x')\n"
            "def modifier(body):\n"
            "    changer(body)\n"
        ),
    )
    aide = Module(
        chemin=pathlib.Path("forge_aide.py"),
        rel="utils/forge_aide.py",
        source="def changer(body):\n    verify_password(body.mdp, '')\n",
    )
    exigences = portee(modules=[forge, aide])
    assert exigences.get(("routers/forge.py", "modifier")) == "LIMITE_SECRET_EPROUVE"
    connues = _constantes_de_limite()
    assert fautes_de_limite(forge, "modifier", "LIMITE_SECRET_EPROUVE", connues) == [
        "routers/forge.py::modifier : aucune limite de débit"
    ]
    plafonnee = Module(
        chemin=pathlib.Path("forge.py"),
        rel="routers/forge.py",
        source=(
            "@router.patch('/x')\n@limiter.limit(LIMITE_PREFERENCE)\n"
            "def modifier(request, body):\n    pass\n"
        ),
    )
    assert fautes_de_limite(plafonnee, "modifier", "LIMITE_SECRET_EPROUVE", connues) == [
        "routers/forge.py::modifier : éprouve un secret — limite attendue `LIMITE_SECRET_EPROUVE`"
    ]
