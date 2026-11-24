"""Une règle d'appartenance ne s'écrit pas chez un routeur.

## Pourquoi (#1028, point 2)

`test_autorisation.py` refuse tout `Depends` local — et il est vert. Mais les
règles d'**appartenance** ne sont pas des `Depends` : ce sont des fonctions
ordinaires, appelées au début d'un geste, et il ne les voyait donc pas. Deux
d'entre elles vivaient chez des routeurs, `routers/bailleur/commun.py` et
`routers/acces/resident.py`.

Elles sont dans `auth/appartenance.py` depuis ce lot — **sans être fondues**, et
c'est le point : elles divergent sur trois axes (le champ de propriété, l'accès
du conseil syndical, le code de refus), et les réunir aurait demandé quatre
paramètres de variation. Ce qu'elles gagnent n'est pas une abstraction, c'est un
**lieu** : côte à côte, on voit que l'une répond 403 et l'autre 404, et pourquoi.

## Ce que ce test refuse

Une comparaison au **compte courant** (`==`, `!=`, `in`, `not in` sur `<compte>.id`)
qui **gouverne une levée HTTP**, écrite hors de `auth/`. C'est la conjonction qui
compte : comparer est banal, lever est banal ; décider d'un refus sur une
appartenance est une règle d'autorisation, et `standards/03` §1 dit où elle vit.

Le compte courant se reconnaît par ce qu'il EST, pas par son nom (#2940) : un
paramètre annoté `Utilisateur`, ou dont la valeur par défaut est `Depends(…)` d'une
fonction d'`auth/` qui rend un `Utilisateur`. Jusque-là, seule la chaîne `user.id`
était lue, avec `==` ou `!=` : le même compte s'appelle `admin` dans vingt-deux
routes, `lecteur` dans trente-sept fonctions, et `user.id not in (…)` passait.
Le nom `user` reste reconnu sans annotation (`NOM_HISTORIQUE`) : l'élargissement
ne retire rien de ce qui était vu.

⚠️ Ce qu'il ne voit PAS, et il faut le savoir : une règle qui ne compare pas au
compte courant — « seul l'aidant accepte une délégation » compare à `aidant_id`,
« un ticket non ouvert n'est modifiable que par l'admin » ne compare rien du tout.
Elles restent chez leurs routeurs, et le ticket les nomme. Les couvrir demanderait
de reconnaître « un champ qui désigne une personne », ce qu'aucun motif ne sait
faire sans se tromper (`standards/04` §12).
"""

import ast
from pathlib import Path

from tests.aides_sources import Module, modules_app

RACINE = Path(__file__).resolve().parents[1] / "app"

#: Le seul endroit où une règle d'appartenance peut s'écrire.
SOURCE = "auth/appartenance.py"

#: Le nom que portait le compte courant quand seul lui était lu : reconnu même sans
#: annotation, pour que reconnaître la notion n'oublie pas la graphie d'avant.
NOM_HISTORIQUE = "user"

#: Les levées gouvernées par le compte courant hors d'`auth/` qui ne sont PAS une règle
#: d'appartenance, et pourquoi — (module, fonction, condition telle que l'écrit
#: `ast.unparse`) : la condition fait partie de la clé, pour qu'une règle neuve écrite
#: dans la même fonction reste vue. Vérifiée dans les deux sens : une entrée qui ne lève
#: plus échoue (#2940 — vues dès que `admin.id` et `in` ont été lus).
GARDES_DECLAREES = {
    (
        "routers/acces/resident.py",
        "_declarer_acces",
        "existant and user.id in porteurs(session, existant)",
    ): "un DOUBLON (400) : le porteur redéclare un badge qu'il porte déjà. Rien n'est "
    "refusé à autrui, et « porter » se lit à sa source unique, `utils/porteurs_acces.porteurs`",
    ("routers/admin/utilisateurs.py", "supprimer_utilisateur", "admin.id == user_id"): "une "
    "garde contre SOI-MÊME (400) : l'administrateur ne supprime pas son propre compte — une "
    "identité, pas l'appartenance d'un objet",
    ("utils/demande_suppression.py", "traiter", "user_id == admin.id"): "une garde contre "
    "SOI-MÊME (400) : sa propre demande d'effacement se traite par un autre administrateur",
}

_FONCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_COMPARAISONS = (ast.Eq, ast.NotEq, ast.In, ast.NotIn)


def _nom(noeud: ast.AST) -> str | None:
    if isinstance(noeud, ast.Name):
        return noeud.id
    return noeud.attr if isinstance(noeud, ast.Attribute) else None


def _est_utilisateur(annotation: ast.AST | None) -> bool:
    """`Utilisateur`, `m.Utilisateur`, `"Utilisateur"`, `Optional[…]`, `… | None`.

    Une liste, un `Callable` ou `"RoleUtilisateur"` ne sont pas un compte.
    """
    if isinstance(annotation, (ast.Name, ast.Attribute)):
        return _nom(annotation) == "Utilisateur"
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            return _est_utilisateur(ast.parse(annotation.value, mode="eval").body)
        except SyntaxError:
            return False
    if isinstance(annotation, ast.Subscript) and _nom(annotation.value) == "Optional":
        return _est_utilisateur(annotation.slice)
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        cotes = (annotation.left, annotation.right)
        aucun = [c for c in cotes if not (isinstance(c, ast.Constant) and c.value is None)]
        return len(aucun) == 1 and _est_utilisateur(aucun[0])
    return False


def _dependances_d_auth() -> set[str]:
    """Les fonctions d'`auth/` qui RENDENT un compte — lues, jamais recopiées ici."""
    return {
        n.name
        for m in modules_app("auth", minimum=10)
        for n in m.arbre.body
        if isinstance(n, _FONCTIONS) and _est_utilisateur(n.returns)
    }


def _comptes(fonction: ast.FunctionDef, dependances: set[str]) -> set[str]:
    """Les paramètres de `fonction` qui portent le compte courant."""
    a = fonction.args
    positionnels = a.posonlyargs + a.args
    defauts = [None] * (len(positionnels) - len(a.defaults)) + a.defaults + a.kw_defaults
    comptes = {NOM_HISTORIQUE}
    for parametre, defaut in zip(positionnels + a.kwonlyargs, defauts):
        depend = (
            isinstance(defaut, ast.Call)
            and _nom(defaut.func) == "Depends"
            and bool(defaut.args)
            and _nom(defaut.args[0]) in dependances
        )
        if depend or _est_utilisateur(parametre.annotation):
            comptes.add(parametre.arg)
    return comptes


def _compare_le_compte(condition: ast.AST, comptes: set[str]) -> bool:
    """Une comparaison dont un terme contient `<compte>.id`."""
    for c in ast.walk(condition):
        if not (isinstance(c, ast.Compare) and any(isinstance(o, _COMPARAISONS) for o in c.ops)):
            continue
        for terme in (c.left, *c.comparators):
            for n in ast.walk(terme):
                if isinstance(n, ast.Attribute) and n.attr == "id" and _nom(n.value) in comptes:
                    return True
    return False


def _leve_http(noeud: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Raise) and "HTTPException" in ast.unparse(n) for n in ast.walk(noeud)
    )


def _levees_gouvernees(modules) -> dict[tuple[str, int], tuple[str | None, str]]:
    """{(module, ligne): (fonction, condition)} : chaque `if` qui compare le compte
    courant et lève.

    La fonction est la plus intérieure — `ast.walk` rend l'englobante d'abord.
    """
    dependances = _dependances_d_auth()
    trouvees: dict[tuple[str, int], tuple[str | None, str]] = {}
    for module in modules:
        if module.rel.startswith("auth/"):
            continue
        portees = [(module.arbre, {NOM_HISTORIQUE}, None)] + [
            (f, _comptes(f, dependances), f.name)
            for f in ast.walk(module.arbre)
            if isinstance(f, _FONCTIONS)
        ]
        for portee, comptes, fonction in portees:
            for noeud in ast.walk(portee):
                if (
                    isinstance(noeud, ast.If)
                    and _compare_le_compte(noeud.test, comptes)
                    and _leve_http(noeud)
                ):
                    trouvees[(module.rel, noeud.lineno)] = (fonction, ast.unparse(noeud.test))
    return trouvees


def test_aucune_regle_d_appartenance_hors_du_module_central():
    fautes = [
        f"app/{rel}:{ligne}" + (f" (dans {fn})" if fn else "") + f" — `{condition}`"
        for (rel, ligne), (fn, condition) in sorted(_levees_gouvernees(modules_app()).items())
        if (rel, fn, condition) not in GARDES_DECLAREES
    ]
    assert not fautes, (
        "Règle(s) d'appartenance écrite(s) hors de `auth/` :\n"
        + "\n".join(f"  {f}" for f in fautes)
        + f"\n\nElles vivent dans `app/{SOURCE}`, avec les autres : c'est là qu'on "
        f"compare leurs décisions — qui est admis, et si le refus dit « interdit » "
        f"ou « introuvable ». Une règle rangée chez celui qui l'applique est "
        f"invisible au suivant (`standards/03` §1). Une garde qui n'est pas une "
        f"appartenance (un doublon, soi-même) se déclare dans `GARDES_DECLAREES`."
    )


def test_chaque_garde_declaree_leve_encore():
    """L'autre sens : une entrée qui ne lève plus ne couvre plus rien, elle se retire."""
    vues = {(rel, fn, cond) for (rel, _), (fn, cond) in _levees_gouvernees(modules_app()).items()}
    perimees = sorted(set(GARDES_DECLAREES) - vues)
    assert not perimees, f"`GARDES_DECLAREES` déclare des gardes disparues : {perimees}"


def test_le_compte_courant_se_lit_dans_les_dependances_d_auth():
    """Cas zéro : un relevé vide ne reconnaîtrait plus que le nom historique."""
    dependances = _dependances_d_auth()
    attendues = {"get_current_user", "require_admin", "require_cs_or_admin", "lecteur_de_la_cloche"}
    assert attendues <= dependances, (
        f"les dépendances d'auth qui rendent un compte ne sont plus lues : {sorted(dependances)}"
    )


def test_le_detecteur_voit_CHAQUE_forme_du_compte_courant():
    """Un extrait forgé par forme à refuser, et trois qui ne doivent pas l'être (#2940)."""
    source = "\n".join(
        (
            "def a(o, admin: Utilisateur = Depends(require_admin)):",  # 1
            "    if o.auteur_id != admin.id:",  # 2 — un autre nom, annoté
            "        raise HTTPException(403)",
            "def b(o, lecteur: Optional[Utilisateur]):",  # 4
            "    if lecteur.id == o.auteur_id:",  # 5 — Optional
            "        raise HTTPException(404)",
            "def c(o, qui=Depends(get_current_user)):",  # 7
            "    if qui.id not in o.porteurs:",  # 8 — sans annotation, `not in`
            "        raise HTTPException(404)",
            "def d(o, user):",  # 10
            "    if o.auteur_id not in (user.id, o.saisi_pour_id):",  # 11 — dans un tuple
            "        raise HTTPException(403)",
            "def e(o, compte: 'Utilisateur | None'):",  # 13
            "    if compte.id in o.membres:",  # 14 — annotation en chaîne
            "        raise HTTPException(403)",
            "def f(o, cible_id: int):",  # 16
            "    if o.auteur_id != cible_id:",  # pas de compte courant
            "        raise HTTPException(403)",
            "def g(o, user: Utilisateur):",  # 19
            "    if o.auteur_id != user.id:",  # ne lève pas
            "        return None",
            "def h(o, roles: list[Utilisateur], v: Callable[[Any, Utilisateur], bool]):",
            "    if o.id in (roles.id, v.id):",  # ni une liste ni un Callable
            "        raise HTTPException(403)",
        )
    )
    forge = Module(chemin=RACINE / "routers" / "forge.py", rel="routers/forge.py", source=source)
    dans_auth = Module(chemin=RACINE / "auth" / "forge.py", rel="auth/forge.py", source=source)
    trouvees = _levees_gouvernees([forge, dans_auth]).items()
    vues = sorted((ligne, fn) for (_, ligne), (fn, _) in trouvees)
    attendues = [(2, "a"), (5, "b"), (8, "c"), (11, "d"), (14, "e")]
    assert vues == attendues, (
        f"le détecteur a vu {vues}, il devait voir {attendues} : une forme du compte "
        "courant lui échappe, ou un autre paramètre passe pour lui"
    )


def test_le_module_central_porte_bien_des_regles():
    """Cas zéro : un module vide rendrait le test précédent vert sans rien dire.

    Il suffirait de supprimer `auth/appartenance.py` et de ne plus rien comparer
    à `user.id` nulle part pour que tout passe — en ayant perdu les règles.
    """
    module = RACINE / SOURCE
    assert module.exists(), f"app/{SOURCE} a disparu : les règles n'ont plus de lieu."
    arbre = ast.parse(module.read_text(encoding="utf-8"))
    exigeantes = [
        n.name
        for n in ast.walk(arbre)
        if isinstance(n, ast.FunctionDef)
        and any(
            isinstance(x, ast.Raise) and "HTTPException" in (ast.unparse(x) or "")
            for x in ast.walk(n)
        )
    ]
    assert len(exigeantes) >= 2, (
        f"app/{SOURCE} ne porte plus que {exigeantes} : ce module existe pour qu'on "
        f"COMPARE des règles d'appartenance ; avec une seule, il n'y a rien à comparer "
        f"et le lieu a perdu sa raison d'être."
    )


#  ── Une appartenance qui FILTRE au lieu de lever (#1551) ──────────────────────
#
#  Le test du haut ne voit qu'une comparaison qui gouverne une LEVÉE. La liste des
#  transferts d'une affaire filtrait par `continue` sur la règle même de
#  `exiger_auteur_du_versement` (`v.transfere_par_id != user.id`) : invisible, et
#  libre de diverger le jour où la règle apprend quelque chose — la liste
#  proposerait alors un geste refusé, ou tairait un geste permis.
#
#  On ne cherche pas « toute comparaison à user.id » : la plupart excluent
#  l'auteur d'une notification (« ne pas se prévenir soi-même »), ce qui n'est
#  pas une appartenance. On cherche les champs que le module central compare
#  LUI-MÊME à un utilisateur — lus dans `auth/appartenance.py`, jamais recopiés
#  ici : une règle neuve y étend aussitôt ce contrôle.
#
#  ⚠️ Hors portée, délibérément : la colonne d'une CLASSE dans un `select()`
#  (`LocationBail.bailleur_id == user.id`). C'est la liste « des miens », une
#  autre question que « puis-je agir dessus » — le bail admet le conseil
#  syndical, « mes baux » non. Même arbitrage que `test_regle_acces_source_unique`.


def _comparaisons_a_un_utilisateur(arbre: ast.AST):
    """(champ, ligne) pour chaque `objet.champ ==/!= x.id`, `objet` une instance."""
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Compare) or len(n.ops) != 1:
            continue
        if not isinstance(n.ops[0], (ast.Eq, ast.NotEq)):
            continue
        for a, b in ((n.left, n.comparators[0]), (n.comparators[0], n.left)):
            if not (isinstance(b, ast.Attribute) and b.attr == "id"):
                continue
            if (
                isinstance(a, ast.Attribute)
                and isinstance(a.value, ast.Name)
                and not a.value.id[:1].isupper()  # une instance, pas une colonne de classe
                and a.attr != "id"
            ):
                yield a.attr, n.lineno


def _champs_d_appartenance() -> set[str]:
    """Les champs que le module central compare à un utilisateur."""
    arbre = ast.parse((RACINE / SOURCE).read_text(encoding="utf-8"))
    return {champ for champ, _ in _comparaisons_a_un_utilisateur(arbre)}


def test_les_champs_d_appartenance_se_lisent_dans_le_module_central():
    """Cas zéro : un relevé vide rendrait le test suivant vert sur rien."""
    champs = _champs_d_appartenance()
    assert {"transfere_par_id", "bailleur_id"} <= champs, (
        f"le module central ne compare plus que {sorted(champs)} à un utilisateur : "
        "le relevé a perdu sa portée, ou les règles ont changé de forme"
    )
    #  Le compte comparé n'a pas de nom imposé ici (#2940) : `user`, `lecteur`, `admin`.
    for compte in ("user", "lecteur", "admin"):
        copie = f"for v in vs:\n    if v.transfere_par_id != {compte}.id:\n        continue\n"
        assert list(_comparaisons_a_un_utilisateur(ast.parse(copie))), (
            f"la forme « filtre » n'est plus reconnue sur `{compte}.id`"
        )


def test_aucune_appartenance_ne_se_recompare_hors_du_module_central():
    """🔴 Le défaut de #1551 : le filtre des transferts recopiait la règle du geste."""
    champs = _champs_d_appartenance()
    fautes = []
    for module in modules_app():
        if module.rel.startswith("auth/"):
            continue
        if not any(c in module.source for c in champs):
            continue
        for champ, ligne in _comparaisons_a_un_utilisateur(module.arbre):
            if champ in champs:
                fautes.append(f"  app/{module.rel}:{ligne} — `{champ}`")
    assert not fautes, (
        "Une règle d'appartenance du module central est recomparée ailleurs :\n"
        + "\n".join(fautes)
        + f"\n\nAppeler le prédicat de `app/{SOURCE}` — celui que le geste appelle "
        "pour refuser. Une liste qui filtre sur sa propre copie propose ce que le "
        "geste refusera, ou tait ce qu'il permet."
    )
