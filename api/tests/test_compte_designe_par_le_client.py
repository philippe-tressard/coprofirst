"""Une route ouverte aux résidents qui lit le compte qu'un client DÉSIGNE pose une
question de visibilité, ou se déclare avec sa raison.

## La règle

Une route qui reçoit l'identifiant d'un compte (chemin, requête ou corps) et le
lit peut en rendre le nom. Ouverte à tout résident connecté, elle ne nomme que
qui ce lecteur connaît déjà : elle appelle une question nommée (le masquage :
`masquage.auteur_lu_par` ; le locataire d'un bail : `appartenance.est_locataire_designable`),
dans son corps ou dans une fonction du même module qu'elle appelle, ou se déclare dans
`ROUTES_DECLAREES`, avec sa raison.

## Ce que le balayage voit — et sa limite

Sur l'AST de `app/routers/` : toute route dont aucune dépendance n'est réservée à
la modération (`require_cs_or_admin`, `require_admin`, `require_operateur`), et
qui charge un `Utilisateur` (`ou_404`, `ou_rien`, `.get`) par une expression qui
dépend d'un de ses paramètres, directement ou par une variable locale qui en est
tirée sans appel (un objet LU par son identifiant désigne ensuite un compte choisi
par le serveur) — dans son corps, ou dans une fonction du même module qu'elle appelle en lui
passant ce paramètre (un niveau).

Les routes posées par une fabrique (`enregistrer_routes_reponses`) sont vues :
le balayage parcourt l'arbre entier.

⚠️ Il ne voit pas : un compte lu par une requête `select`, une aide d'un autre
module ou de second niveau, une dépendance posée sur le routeur entier (une route
ainsi protégée apparaîtrait ici, et se déclarerait). Il juge la LECTURE du compte,
pas le rendu de son nom : une route qui lit sans nommer se déclare aussi, et sa
raison le dit. La liste est vérifiée dans les deux sens.
"""

from __future__ import annotations

import ast

from tests.aides_sources import modules_app

_METHODES = {"get", "post", "put", "patch", "delete"}
_MODERATION = {"require_cs_or_admin", "require_admin", "require_operateur"}
_CHARGEURS = {"ou_404", "ou_rien", "get"}

#: « module::route » → la question de visibilité que la route appelle — dans son corps,
#: ou dans une fonction du même module qu'elle appelle (un niveau, la portée du relevé).
ROUTES_QUESTIONNEES = {
    "masquages.py::masquer": "auteur_lu_par",
    #  Le locataire d'un bail : un compte que la recherche ouverte au bailleur rendrait
    #  (`auth/appartenance.est_locataire_designable`, claude-config#656).
    "bailleur/baux.py::creer_bail_multi": "est_locataire_designable",
    "bailleur/baux.py::update_bail": "est_locataire_designable",
}

#: « module::route » → pourquoi elle lit le compte désigné sans autre question.
ROUTES_DECLAREES: dict[str, str] = {}

#: Route relevée → les fonctions du même module qu'elle appelle (un niveau).
_APPELEES: dict[ast.AST, list[ast.AST]] = {}


def _noms(noeud: ast.AST) -> set[str]:
    """Les noms dont la VALEUR passe dans l'expression — sans entrer dans un appel :
    `annonce.auteur_id`, où `annonce` est lue par son identifiant, désigne un compte
    choisi par le serveur, pas par le client."""
    if isinstance(noeud, ast.Name):
        return {noeud.id}
    if isinstance(noeud, ast.Call):
        return set()
    return set().union(*(_noms(e) for e in ast.iter_child_nodes(noeud)))


def _contamines(fonction: ast.AST, depart: set[str]) -> set[str]:
    """Les paramètres reçus, et toute variable locale affectée depuis l'un d'eux."""
    noms = set(depart)
    while True:
        avant = len(noms)
        for n in ast.walk(fonction):
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None:
                if _noms(n.value) & noms:
                    cibles = n.targets if isinstance(n, ast.Assign) else [n.target]
                    noms |= {c.id for c in cibles if isinstance(c, ast.Name)}
        if len(noms) == avant:
            return noms


def _ids_charges(fonction: ast.AST) -> list[ast.AST]:
    """Les expressions d'identifiant passées après `Utilisateur` à un chargeur."""
    trouves = []
    for appel in ast.walk(fonction):
        if not isinstance(appel, ast.Call):
            continue
        if ast.unparse(appel.func).split(".")[-1] not in _CHARGEURS:
            continue
        noms = [ast.unparse(a) for a in appel.args]
        if "Utilisateur" in noms and noms.index("Utilisateur") + 1 < len(appel.args):
            trouves.append(appel.args[noms.index("Utilisateur") + 1])
    return trouves


def _parametres(fonction) -> list[str]:
    return [a.arg for a in fonction.args.args + fonction.args.kwonlyargs]


def _dependances(fonction) -> dict[str, str]:
    """Paramètre → dépendance (`Depends(x)`), pour les paramètres qui en portent une."""
    args = fonction.args
    paires = list(zip(reversed(args.args), reversed(args.defaults)))
    paires += [(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]
    return {
        a.arg: ast.unparse(d.args[0])
        for a, d in paires
        if isinstance(d, ast.Call) and ast.unparse(d.func) == "Depends" and d.args
    }


def _est_route(fonction) -> bool:
    for d in fonction.decorator_list:
        cible = d.func if isinstance(d, ast.Call) else d
        if isinstance(cible, ast.Attribute) and cible.attr in _METHODES:
            return True
    return False


def _routes_qui_lisent_un_compte_designe(exclues=_MODERATION) -> dict[str, ast.AST]:
    trouvees = {}
    for module in modules_app("routers", minimum=25):
        arbre = module.arbre
        fonctions = [
            n for n in ast.walk(arbre) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        aides = {f.name: f for f in fonctions if not _est_route(f)}
        for route in (f for f in fonctions if _est_route(f)):
            dependances = _dependances(route)
            if set(dependances.values()) & exclues:
                continue
            fournis = _contamines(
                route, set(_parametres(route)) - set(dependances) - {"request", "response"}
            )
            lit = any(_noms(i) & fournis for i in _ids_charges(route))
            for appel in ast.walk(route):
                if lit:
                    break
                if not (isinstance(appel, ast.Call) and isinstance(appel.func, ast.Name)):
                    continue
                aide = aides.get(appel.func.id)
                if aide is None:
                    continue
                params = _parametres(aide)
                relayes = _contamines(
                    aide,
                    {
                        params[i]
                        for i, a in enumerate(appel.args)
                        if i < len(params) and _noms(a) & fournis
                    },
                )
                lit = any(_noms(i) & relayes for i in _ids_charges(aide))
            if lit:
                trouvees[f"{module.rel.removeprefix('routers/')}::{route.name}"] = route
                _APPELEES[route] = [
                    aides[n.func.id]
                    for n in ast.walk(route)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id in aides
                ]
    return trouvees


def test_le_balayage_voit_des_routes():
    """Le cas zéro : sans les dépendances de modération exclues, il voit les routes
    d'administration qui lisent le compte désigné — preuve qu'il lit bien le code."""
    trouvees = _routes_qui_lisent_un_compte_designe()
    assert trouvees, "le balayage ne voit plus rien : portée perdue"
    toutes = _routes_qui_lisent_un_compte_designe(exclues=set())
    assert "admin/utilisateurs.py::modifier_utilisateur" in toutes
    assert len(toutes) > len(trouvees) + 3


def test_chaque_route_pose_sa_question_ou_se_declare():
    trouvees = _routes_qui_lisent_un_compte_designe()
    sans = sorted(set(trouvees) - set(ROUTES_QUESTIONNEES) - set(ROUTES_DECLAREES))
    assert not sans, (
        "Ces routes ouvertes aux résidents lisent le compte qu'un client désigne sans "
        "question de visibilité :\n  " + "\n  ".join(sans)
    )
    perimees = sorted((set(ROUTES_QUESTIONNEES) | set(ROUTES_DECLAREES)) - set(trouvees))
    assert not perimees, f"Entrées qui ne correspondent plus à aucune route : {perimees}"


def test_la_question_declaree_est_appelee():
    trouvees = _routes_qui_lisent_un_compte_designe()
    muettes = []
    for cle, question in ROUTES_QUESTIONNEES.items():
        route = trouvees.get(cle) or ast.Module(body=[], type_ignores=[])
        appels = {
            ast.unparse(n.func).split(".")[-1]
            for f in [route, *_APPELEES.get(route, [])]
            for n in ast.walk(f)
            if isinstance(n, ast.Call)
        }
        if question not in appels:
            muettes.append(f"{cle} n'appelle pas {question}")
    assert not muettes, "\n".join(muettes)
