"""« Conseil syndical ou admin » ne s'écrit qu'une fois : `deps.est_moderateur`.

## L'incident (#1028, audit du 19/09/2026)

Le module central `auth/deps.py` tient — `test_autorisation.py` refuse tout
`Depends` local, et il est vert. Mais la **notion** de modérateur n'avait pas de
nom appelé : `user.has_role(RoleUtilisateur.conseil_syndical,
RoleUtilisateur.admin)` était redérivé **en ligne**, dans vingt-trois fichiers de
`routers/` et `utils/`, plus trois écritures dans `deps.py` lui-même.

Aucune n'était fausse. C'est l'ensemble qui était ingouvernable : le jour où ce
prédicat doit apprendre quelque chose — un rôle de plus, un compte désactivé qui
cesse de modérer, une délégation — il faut le savoir vingt-six fois. C'est
exactement la chaîne du défaut voisin du même audit : « ce lot est le mien »
écrit deux fois, dont une sans `actif`, et un badge commandable par un ancien
occupant (#1028, point 1).

⚠️ `peut_commander` existait et disait déjà cela — mais son **nom parlait du
geste** (fixer les champs de commandement d'un ticket), pas du rôle. Un nom qui
décrit un usage particulier n'est appelé que par cet usage : les vingt-cinq
autres points ne pouvaient pas le reconnaître comme le leur. Il est donc
**renommé**, pas aliasé (`standards/02` §1.6 — un alias ferait croire à deux
notions), et son explication des champs de commandement descend au point d'usage,
dans `routers/tickets/crud.py`.

## Ce que ce test verrouille

Une seule écriture du prédicat dans tout `api/app`, et elle est dans
`est_moderateur`. Pas de liste d'exceptions : il n'y en a aucune à déclarer, et
c'est le but — une exception ici voudrait dire qu'un endroit a besoin d'une
définition *différente* de « modérateur », ce qui est précisément ce qu'il faut
rendre visible.

⚠️ Ce test lit l'**arbre syntaxique**, pas le texte : un appel réparti sur
plusieurs lignes, avec les rôles dans l'autre ordre ou importés sous un autre
nom, est vu exactement pareil. Les vingt-six occurrences d'origine s'écrivaient
de quatre façons différentes (`admin` d'abord, `conseil_syndical` d'abord, sur
une ligne ou sur trois) — un `grep` en aurait manqué la moitié.

Il ne voyait pourtant qu'UN appel qui nomme les deux rôles (#2940) : la même notion
écrite en deux appels, `u.has_role(CS) or u.has_role(admin)`, passait — et sa
négation, `not u.has_role(CS) and not u.has_role(admin)`, la forme d'un refus.
Les deux sont lues, sur un même receveur, parenthèses aplaties. Hors de portée :
deux receveurs différents, et `and` sans négation (« les deux à la fois »), qui
sont d'autres questions.
"""

import ast
from pathlib import Path

from tests.aides_sources import Module, modules_app

RACINE = Path(__file__).resolve().parents[1] / "app"

#: Le seul endroit où la question a le droit d'être posée.
SOURCE = ("auth/deps.py", "est_moderateur")

#: Les deux rôles qui, ensemble, font un modérateur.
ROLES = {"conseil_syndical", "admin"}


def _fonction_englobante(arbre: ast.Module, noeud: ast.AST) -> str | None:
    """Le nom de la fonction qui contient ce nœud, ou None au niveau module."""
    for fn in ast.walk(arbre):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(d is noeud for d in ast.walk(fn)):
            return fn.name
    return None


def _appel_has_role(noeud: ast.AST) -> ast.Call | None:
    if (
        isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Attribute)
        and noeud.func.attr == "has_role"
    ):
        return noeud
    return None


def _roles(appel: ast.Call) -> set:
    return {
        a.attr if isinstance(a, ast.Attribute) else a.value
        for a in appel.args
        if isinstance(a, (ast.Attribute, ast.Constant))
    }


def _termes(noeud: ast.BoolOp) -> list[ast.AST]:
    """Les termes d'un `or` (ou d'un `and`), parenthèses imbriquées aplaties."""
    termes = []
    for v in noeud.values:
        if isinstance(v, ast.BoolOp) and isinstance(v.op, type(noeud.op)):
            termes.extend(_termes(v))
        else:
            termes.append(v)
    return termes


def _paires(noeud: ast.BoolOp) -> list[ast.Call]:
    """Les appels qui, ENSEMBLE, disent « conseil ou admin » sur un même receveur (#2940).

    `u.has_role(CS) or u.has_role(admin)`, et sa négation
    `not u.has_role(CS) and not u.has_role(admin)` — « ni l'un ni l'autre », la forme
    naturelle d'un refus. Rend [] si aucun receveur ne réunit les deux rôles.
    """
    if isinstance(noeud.op, ast.Or):
        appels = [_appel_has_role(t) for t in _termes(noeud)]
    else:
        appels = [
            _appel_has_role(t.operand)
            for t in _termes(noeud)
            if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not)
        ]
    par_receveur: dict[str, list[ast.Call]] = {}
    for appel in appels:
        if appel is not None and _roles(appel) < ROLES and _roles(appel):
            par_receveur.setdefault(ast.dump(appel.func.value), []).append(appel)
    for groupe in par_receveur.values():
        if len(groupe) >= 2 and set().union(*map(_roles, groupe)) == ROLES:
            return groupe
    return []


def _derivations(modules) -> list[tuple[str, int, str | None]]:
    """Toute dérivation de « conseil ou admin » : un appel `…has_role(<CS>, <admin>)`, ou
    deux appels joints sur le même receveur (`or`, ou `and` de leurs négations)."""
    trouves = []
    for m in modules:
        arbre = m.arbre
        comptes: set[int] = set()  # un `or` imbriqué dans un autre ne compte qu'une fois
        for noeud in ast.walk(arbre):
            appel = _appel_has_role(noeud)
            if appel is not None and _roles(appel) == ROLES:
                trouves.append((m.rel, noeud.lineno, _fonction_englobante(arbre, noeud)))
            elif isinstance(noeud, ast.BoolOp):
                paire = _paires(noeud)
                if paire and not {id(a) for a in paire} <= comptes:
                    comptes |= {id(a) for a in paire}
                    trouves.append((m.rel, noeud.lineno, _fonction_englobante(arbre, noeud)))
    return trouves


def test_le_predicat_moderateur_ne_s_ecrit_qu_une_fois():
    """Une seule dérivation dans tout `app/`, et c'est la définition."""
    ailleurs = [
        f"app/{chemin}:{ligne}" + (f" (dans {fn})" if fn else "")
        for chemin, ligne, fn in _derivations(modules_app())
        if (chemin, fn) != SOURCE
    ]
    assert not ailleurs, (
        "« conseil syndical ou admin » est redérivé en ligne :\n"
        + "\n".join(f"  {x}" for x in ailleurs)
        + "\n\nAppeler `auth.deps.est_moderateur(user)`. Ce prédicat porte la NOTION "
        "— qui modère —, là où `require_cs_or_admin` porte le REFUS (dépendance "
        "FastAPI qui lève un 403) : deux gestes, une seule définition."
    )


def test_la_source_existe_encore():
    """Le cas ZÉRO : un test qui ne trouve plus sa source passerait au vert.

    Si `est_moderateur` disparaissait ou changeait de forme, le test ci-dessus
    deviendrait vert **en ne mesurant plus rien** — il ne compte que ce qu'il
    trouve. C'est le faux vert par sortie vide (`standards/04` §1 et §27).
    """
    source = [d for d in _derivations(modules_app()) if (d[0], d[2]) == SOURCE]
    assert len(source) == 1, (
        f"`est_moderateur` de `auth/deps.py` ne contient plus exactement une "
        f"dérivation de {sorted(ROLES)} (trouvé : {source}). Si le prédicat a été "
        f"réécrit, ce contrôle ne mesure plus rien tant qu'il n'est pas repris."
    )


def test_le_refus_passe_par_le_predicat():
    """`require_cs_or_admin` doit APPELER `est_moderateur`, pas le redériver.

    Sans cela, il resterait une seconde écriture — celle qui refuse — et les deux
    pourraient diverger en silence : le prédicat dirait « oui », la dépendance
    lèverait un 403, et rien ne le signalerait avant un ticket d'utilisateur.
    """
    arbre = ast.parse((RACINE / "auth" / "deps.py").read_text(encoding="utf-8"))
    fn = next(
        (
            n
            for n in ast.walk(arbre)
            if isinstance(n, ast.FunctionDef) and n.name == "require_cs_or_admin"
        ),
        None,
    )
    assert fn is not None, "`require_cs_or_admin` a disparu de auth/deps.py"

    #  Depuis #2942, le refus s'écrit UNE fois, `exiger_moderateur(user, motif)`, que
    #  la dépendance appelle comme les gestes qui gardent leur message : la chaîne est
    #  suivie — la dépendance appelle la porte, la porte appelle le prédicat.
    def appels(nom: str) -> set[str]:
        f = next(n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == nom)
        return {
            n.func.id
            for n in ast.walk(f)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }

    assert "exiger_moderateur" in appels("require_cs_or_admin") and "est_moderateur" in appels(
        "exiger_moderateur"
    ), (
        "`require_cs_or_admin` n'atteint pas `est_moderateur` par `exiger_moderateur` : la "
        "règle « qui modère » serait écrite deux fois, une pour dire et une pour refuser"
    )


def test_le_detecteur_voit_CHAQUE_forme_de_la_notion():
    """Un extrait forgé par forme à refuser, et trois autres questions qu'il laisse (#2940)."""
    source = "\n".join(
        (
            "def a(u):",  # 1
            "    return u.has_role(R.conseil_syndical, R.admin)",  # 2 — un appel
            "def b(u):",  # 3
            "    return u.has_role(R.conseil_syndical) or u.has_role(R.admin)",  # 4 — deux
            "def c(u):",  # 5
            "    if not u.has_role(R.admin) and not u.has_role(R.conseil_syndical):",  # 6
            "        raise Refus()",  # 7
            "def d(u):",  # 8
            "    return (",  # 9
            "        u.has_role('admin')",  # 10 — sur trois lignes, un terme entre
            "        or est_x(u)",  # 11
            "        or u.has_role(R.conseil_syndical)",  # 12
            "    )",  # 13
            "def e(u):",  # 14
            "    return x or (u.has_role(R.conseil_syndical) or u.has_role(R.admin))",  # 15
            "def f(u, v):",  # 16
            "    return u.has_role(R.admin) or v.has_role(R.conseil_syndical)",  # deux comptes
            "def g(u):",  # 18
            "    return u.has_role(R.admin) or u.has_role(R.syndic)",  # autre paire
            "def h(u):",  # 20
            "    return u.has_role(R.admin) and u.has_role(R.conseil_syndical)",  # les deux
        )
    )
    forge = Module(chemin=RACINE / "utils" / "forge.py", rel="utils/forge.py", source=source)
    vues = sorted((ligne, fn) for _, ligne, fn in _derivations([forge]))
    attendues = [(2, "a"), (4, "b"), (6, "c"), (10, "d"), (15, "e")]
    assert vues == attendues, (
        f"le détecteur a vu {vues}, il devait voir {attendues} : une écriture de "
        "« conseil ou admin » lui échappe, ou une autre question passe pour elle"
    )
