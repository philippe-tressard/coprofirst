"""Toute route d'authentification porte une limite de débit, et elle est nommée (#1027).

## Pourquoi ce contrôle

Deux routes d'authentification n'avaient **aucune** limitation de débit le
19/09/2026, et l'une des deux éprouvait un secret :

| Route | Ce qu'elle éprouve | Limite |
|---|---|---|
| `POST /auth/change-password` | un mot de passe, en `verify_password` | **aucune** |
| `GET /auth/verifier-email` | un jeton, passé en clair dans l'URL | **aucune** |

Les onze autres en portaient une. Rien ne disait laquelle manquait : la règle
« limiter les routes d'authentification » vivait dans `CLAUDE.md` et dans la
skill de sécurité, c'est-à-dire **nulle part où une machine la lise**. Poser une
douzième route sans limite n'aurait rien fait échouer non plus.

## Ce que le contrôle exige

1. **La portée** : toute route d'un module `auth*.py` porte un `@limiter.limit`.
   Pas de liste d'exceptions — il n'y en a aucune, et une exception posée à vide
   ferait croire à une décision. Le jour où une route légitime devra s'en
   passer, ce test échouera, et la raison s'écrira ici avec sa date. Hors de
   l'authentification, une route s'y ajoute par `ROUTES_LIMITEES_HORS_AUTH`.
2. **La forme** : la valeur vient d'une **constante** de `utils.limiter`, jamais
   d'une chaîne littérale. Un littéral ne dit pas pourquoi il vaut cinq, et onze
   littéraux ne disent pas si deux routes de même nature partagent un plafond
   par décision ou par hasard.
3. **L'ordre des décorateurs** : `@limiter.limit` doit être **sous**
   `@router.<méthode>`, sinon la route est enregistrée avant d'être décorée et la
   limite ne s'applique pas. L'erreur est silencieuse — la route répond
   normalement, sans plafond.
4. **La signature** : slowapi lit l'adresse du client dans une `Request`. Une
   route décorée sans paramètre `request` lève une erreur **à l'appel**, pas au
   démarrage : sans ce contrôle, la panne attend le premier visiteur.
"""

from __future__ import annotations

import ast
import pathlib

_ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"

#: Les modules qui portent des routes d'authentification.
MODULES_AUTH = sorted(p.name for p in _ROUTERS.glob("auth*.py"))

#: Hors de l'authentification, les routes dont la limite est EXIGÉE — et pourquoi.
#: Elles passent les mêmes contrôles (constante, ordre, `request`) ; une entrée
#: qui ne correspond plus à aucune route échoue.
ROUTES_LIMITEES_HORS_AUTH = {
    ("masquages.py", "masquer"): "elle répond sur un compte désigné par le client (#2861)",
}

_METHODES = {"get", "post", "patch", "put", "delete"}


def _constantes_de_limite() -> set[str]:
    """Les noms de constantes exportés par `utils.limiter` — lus, pas recopiés."""
    source = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "utils" / "limiter.py"
    ).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    return {
        cible.id
        for noeud in arbre.body
        if isinstance(noeud, ast.Assign)
        for cible in noeud.targets
        if isinstance(cible, ast.Name) and cible.id.startswith("LIMITE_")
    }


def _routes(module: str):
    """(nom de fonction, décorateurs, arguments) de chaque route du module."""
    arbre = ast.parse((_ROUTERS / module).read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decores = [ast.unparse(d) for d in noeud.decorator_list]
        if any(
            d.startswith("router.") and d.split("(")[0].split(".")[-1] in _METHODES for d in decores
        ):
            arguments = [a.arg for a in noeud.args.args] + [a.arg for a in noeud.args.kwonlyargs]
            yield noeud.name, decores, arguments


def _routes_controlees():
    """(module, nom, décorateurs, arguments) : toutes les routes d'auth, et celles
    déclarées hors de l'authentification."""
    for module in MODULES_AUTH:
        for route in _routes(module):
            yield (module, *route)
    for module in sorted({m for m, _ in ROUTES_LIMITEES_HORS_AUTH}):
        for nom, decores, arguments in _routes(module):
            if (module, nom) in ROUTES_LIMITEES_HORS_AUTH:
                yield module, nom, decores, arguments


def test_les_routes_declarees_hors_auth_existent():
    vues = {(m, n) for m, n, _, _ in _routes_controlees()}
    assert set(ROUTES_LIMITEES_HORS_AUTH) <= vues, set(ROUTES_LIMITEES_HORS_AUTH) - vues


def test_le_controle_voit_bien_des_routes():
    """Le cas zéro de la portée : une sortie vide se lirait comme un succès.

    C'est la panne la plus fréquente de ce genre de contrôle — un glob qui ne
    trouve plus rien après un rangement de fichiers, et un test vert qui ne
    vérifie plus rien (`standards/04` §2).
    """
    assert MODULES_AUTH, "aucun module auth*.py trouvé — le contrôle a perdu sa portée"
    total = sum(1 for module in MODULES_AUTH for _ in _routes(module))
    assert total >= 10, f"seulement {total} route(s) d'auth vue(s) : portée suspecte"
    assert _constantes_de_limite(), "utils/limiter.py n'exporte plus aucune constante"


def test_toute_route_d_auth_porte_une_limite():
    """Le défaut exact : `change-password` et `verifier-email` n'en avaient pas."""
    sans = [
        f"{module}::{nom}"
        for module, nom, decores, _ in _routes_controlees()
        if not any("limiter.limit" in d for d in decores)
    ]
    assert not sans, (
        "Ces routes d'authentification n'ont aucune limitation de débit :\n  "
        + "\n  ".join(sans)
        + "\n\nUne route d'auth sans plafond s'éprouve au rythme du réseau. Si "
        "l'une d'elles doit légitimement s'en passer, l'exception s'écrit dans "
        "ce test, avec sa raison et sa date."
    )


def test_la_limite_vient_d_une_constante_nommee():
    """Onze chaînes littérales ne disent pas pourquoi elles valent cinq."""
    connues = _constantes_de_limite()
    litterales = []
    for module, nom, decores, _ in _routes_controlees():
        for decore in decores:
            if "limiter.limit" not in decore:
                continue
            argument = decore.split("(", 1)[1].rsplit(")", 1)[0].strip()
            if argument not in connues:
                litterales.append(f"{module}::{nom} → {argument}")

    assert not litterales, (
        "Ces limites ne viennent pas d'une constante de `utils.limiter` :\n  "
        + "\n  ".join(litterales)
        + f"\n\nConstantes disponibles : {', '.join(sorted(connues))}"
    )


def test_la_limite_est_posee_SOUS_le_decorateur_de_route():
    """Au-dessus, elle décore une fonction déjà enregistrée : aucun effet.

    Et l'erreur ne se voit pas — la route répond normalement, sans plafond.
    """
    inversees = []
    for module, nom, decores, _ in _routes_controlees():
        rangs_route = [i for i, d in enumerate(decores) if d.startswith("router.")]
        rangs_limite = [i for i, d in enumerate(decores) if "limiter.limit" in d]
        if rangs_route and rangs_limite and min(rangs_limite) < min(rangs_route):
            inversees.append(f"{module}::{nom}")

    assert not inversees, (
        "`@limiter.limit` est posé AU-DESSUS de `@router.<méthode>` sur :\n  "
        + "\n  ".join(inversees)
        + "\n\nLa route est alors enregistrée avant d'être décorée : la limite "
        "n'existe pas, et rien ne le signale."
    )


def test_une_route_limitee_recoit_bien_une_requete():
    """slowapi lit l'adresse du client : sans `request`, la route lève à l'appel."""
    sans_requete = [
        f"{module}::{nom}"
        for module, nom, decores, arguments in _routes_controlees()
        if any("limiter.limit" in d for d in decores) and "request" not in arguments
    ]
    assert not sans_requete, (
        "Ces routes sont limitées sans recevoir de `request` :\n  "
        + "\n  ".join(sans_requete)
        + "\n\nslowapi lève alors une erreur au premier appel — au premier "
        "visiteur, pas au démarrage."
    )
