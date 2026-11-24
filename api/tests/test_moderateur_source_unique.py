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
"""

import ast
from pathlib import Path

from tests.aides_sources import modules_app

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


def _derivations() -> list[tuple[str, int, str | None]]:
    """Tout appel `…has_role(<CS>, <admin>)` du code applicatif."""
    trouves = []
    for m in modules_app():
        arbre = m.arbre
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            cible = noeud.func
            if not (isinstance(cible, ast.Attribute) and cible.attr == "has_role"):
                continue
            roles = {
                a.attr if isinstance(a, ast.Attribute) else a.value
                for a in noeud.args
                if isinstance(a, (ast.Attribute, ast.Constant))
            }
            if roles != ROLES:
                continue
            chemin = m.rel
            trouves.append((chemin, noeud.lineno, _fonction_englobante(arbre, noeud)))
    return trouves


def test_le_predicat_moderateur_ne_s_ecrit_qu_une_fois():
    """Une seule dérivation dans tout `app/`, et c'est la définition."""
    ailleurs = [
        f"app/{chemin}:{ligne}" + (f" (dans {fn})" if fn else "")
        for chemin, ligne, fn in _derivations()
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
    source = [d for d in _derivations() if (d[0], d[2]) == SOURCE]
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
