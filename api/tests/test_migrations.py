"""Garde-fou préventif : intégrité de la chaîne de migrations Alembic.

Une migration avec un mauvais `down_revision` crée plusieurs *heads* : en prod,
`start.sh` lance `alembic upgrade head` avec `set -e` → le conteneur reste
bloqué au démarrage. Ce test attrape ces erreurs structurelles avant la MEP
(la cause des fix « migration 0094/0105 » de l'historique).

Une base neuve reçoit le schéma courant d'un coup (`utils/schema_initial`) ;
la chaîne ne décrit que ce qui change après sa migration de base. La
validation porte donc sur la cohérence du graphe de révisions.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from tests.aides_migrations import CHAINES, sources_des_chaines

_API_DIR = Path(__file__).resolve().parents[1]


def _script_dir() -> ScriptDirectory:
    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_un_seul_head():
    """Pas de divergence : un unique head (sinon upgrade head échoue en prod)."""
    heads = _script_dir().get_heads()
    assert len(heads) == 1, f"Plusieurs heads de migration : {heads} (down_revision incorrect ?)"


def test_un_seul_head_pour_la_chaine_plateforme():
    """La chaîne de la base `plateforme` aussi (#2948) : `migrer` la porte à `head`."""
    cfg = Config()
    cfg.set_main_option("script_location", str(CHAINES["plateforme"].parent))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert len(heads) == 1, f"Plusieurs heads dans alembic_plateforme : {heads}"


def test_une_seule_base():
    """Un unique point de départ dans le graphe de migrations."""
    bases = _script_dir().get_bases()
    assert len(bases) == 1, f"Plusieurs bases de migration : {bases}"


def test_revisions_uniques():
    """Aucun identifiant de révision dupliqué."""
    revs = [s.revision for s in _script_dir().walk_revisions()]
    doublons = sorted({r for r in revs if revs.count(r) > 1})
    assert not doublons, f"Identifiants de révision dupliqués : {doublons}"


def test_les_migrations_qui_lisent_le_seed_y_trouvent_leur_modele():
    """Un modèle retiré du seed ne doit pas bloquer le démarrage du conteneur.

    Plusieurs migrations vont chercher le corps d'un modèle dans
    `seed.EMAIL_TEMPLATES` plutôt que d'en garder une copie — c'est voulu, deux
    copies du même HTML divergent. Mais elles l'extraient par
    `next(t for t in EMAIL_TEMPLATES if t[0] == "<code>")` : le jour où ce code
    disparaît du seed, `next` lève `StopIteration`. Sur une base neuve, cela
    fait échouer `alembic upgrade head`, et `start.sh` a `set -e` — le conteneur
    ne démarre plus du tout.

    Le risque n'est pas théorique : l'audit du 05/08/2026 a retiré dix modèles
    du seed en une journée. Une migration est figée ; c'est au code d'aujourd'hui
    de rester compatible avec elle, et ce test le vérifie.
    """
    import re

    from app.seed import EMAIL_TEMPLATES

    codes = {row[0] for row in EMAIL_TEMPLATES}
    motif = re.compile(r"""t\[0\]\s*==\s*["']([a-z0-9_]+)["']""")
    manquants: list[str] = []
    for chemin in sorted((_API_DIR / "alembic" / "versions").glob("*.py")):
        source = chemin.read_text(encoding="utf-8")
        if "EMAIL_TEMPLATES" not in source:
            continue
        for code in motif.findall(source):
            if code not in codes:
                manquants.append(f"{chemin.name} cherche « {code} »")

    assert not manquants, (
        "Migrations qui cherchent dans seed.EMAIL_TEMPLATES un modèle qui n'y "
        "est plus :\n  "
        + "\n  ".join(manquants)
        + "\nSur une base neuve, `next(...)` lève StopIteration et le conteneur "
        "reste bloqué au démarrage. Garder une copie du contenu dans la "
        "migration concernée plutôt que de la laisser lire le seed."
    )


# ─────────────────────────────────────────────────────────────────────────────
#  🔴 Aucune valeur interpolée dans le SQL d'une migration (#1032, #2948)
#
#  ⚠️ Un `grep 'op.execute(f"'` en rend **zéro** : la f-string est presque
#  toujours à la ligne suivante de l'appel. C'est pourquoi ce contrôle lit
#  l'arbre syntaxique et non le texte.
#
#  | Ce qu'on interpole | Verdict |
#  |---|---|
#  | une **valeur** (contenu, identifiant de ligne, date) | jamais — `bindparams` |
#  | un **identifiant** (nom de table ou de colonne) depuis une CONSTANTE du fichier | toléré : un identifiant ne se lie pas |
#
#  🔴 Jusqu'au 23/11/2026 il ne voyait qu'une forme sur sept : une f-string DANS
#  l'appel, et le seul mot `bindparams` l'excusait. Passée par une variable, par
#  `%`, `.format()` ou `+`, à côté d'un `bindparams`, ou par `exec_driver_sql`, une
#  valeur passait (#2948). Il lit désormais ces formes, sur les DEUX chaînes ; une
#  interpolation n'est admise que d'un nom en capitales (une constante du
#  fichier), et ce qu'on passe À `bindparams` est lié, donc hors de cause.
#  Ruff S608 passe aussi sur les deux chaînes ; il ne lit pas le DDL.
# ─────────────────────────────────────────────────────────────────────────────

#: Les appels qui exécutent du SQL.
_EXECUTANTS = ("execute", "exec_driver_sql")


def _interpolees(e):
    """Ce que `e` interpole dans une chaîne — ou None si `e` n'en construit pas."""
    import ast

    def chaine(x) -> bool:
        return isinstance(x, ast.Constant) and isinstance(x.value, str)

    if isinstance(e, ast.JoinedStr):
        return [v.value for v in e.values if isinstance(v, ast.FormattedValue)]
    if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mod) and chaine(e.left):
        return list(e.right.elts) if isinstance(e.right, ast.Tuple) else [e.right]
    if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute) and e.func.attr == "format":
        if chaine(e.func.value):
            return [*e.args, *(k.value for k in e.keywords)]
    if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Add):
        termes, pile = [], [e]
        while pile:
            x = pile.pop()
            if isinstance(x, ast.BinOp) and isinstance(x.op, ast.Add):
                pile += [x.left, x.right]
            else:
                termes.append(x)
        if any(chaine(t) for t in termes):
            return [t for t in termes if not isinstance(t, ast.Constant)]
    return None


def _hors_bindparams(noeud):
    """Les nœuds sous `noeud`, sauf ce qu'on passe à `bindparams`/`bindparam` (c'est lié)."""
    import ast

    pile = [noeud]
    while pile:
        x = pile.pop()
        yield x
        if isinstance(x, ast.Call) and ast.unparse(x.func).split(".")[-1] in (
            "bindparams",
            "bindparam",
        ):
            pile.append(x.func)
            continue
        pile.extend(ast.iter_child_nodes(x))


def _fstrings_sans_bindparams(sources: dict[str, str] | None = None) -> set[str]:
    """Les appels qui exécutent du SQL où une VALEUR est interpolée, par AST."""
    import ast

    if sources is None:
        sources = sources_des_chaines()
    trouves = set()
    for nom, source in sources.items():
        arbre = ast.parse(source)
        #  Une variable se suit jusqu'à ce qu'on lui affecte : `sql = f"…"`, puis
        #  `op.execute(sql)`.
        affectations: dict[str, list] = {}
        for n in ast.walk(arbre):
            if isinstance(n, ast.Assign):
                for cible in n.targets:
                    if isinstance(cible, ast.Name):
                        affectations.setdefault(cible.id, []).append(n.value)
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            if ast.unparse(noeud.func).split(".")[-1] not in _EXECUTANTS:
                continue
            vus = list(_hors_bindparams(noeud))
            for x in list(vus):
                if isinstance(x, ast.Name) and x.id in affectations:
                    vus += [y for v in affectations[x.id] for y in _hors_bindparams(v)]
            for x in vus:
                valeurs = _interpolees(x) or []
                if any(not (isinstance(v, ast.Name) and v.id.isupper()) for v in valeurs):
                    trouves.add(f"{nom}:{noeud.lineno}")
    return trouves


def test_le_controle_voit_bien_les_migrations():
    """Cas zéro de la portée, PAR chaîne : un glob vide se lirait comme « aucun écart »."""
    sources = sources_des_chaines()
    for chaine in CHAINES:
        assert any(n.startswith(f"{chaine}/") for n in sources), f"chaîne `{chaine}` non lue"


FORMES_FAUTIVES = {
    "directe": 'op.execute(\n    f"DELETE FROM t WHERE id = {x}"\n)',
    "variable": 'sql = f"DELETE FROM t WHERE id = {x}"\nop.execute(sql)',
    "pourcent": 'op.execute("DELETE FROM t WHERE id = %s" % x)',
    "format": 'op.execute("DELETE FROM t WHERE id = {}".format(x))',
    "concaténation": 'op.execute("DELETE FROM t WHERE id = " + str(x))',
    "à côté d'un bindparams": 'op.execute(text(f"DELETE FROM t WHERE a = {x} AND b = :b").bindparams(b=1))',
    "exec_driver_sql": 'bind.exec_driver_sql(f"DELETE FROM t WHERE id = {x}")',
}


def test_le_controle_sait_REFUSER():
    """Les témoins : sept formes forgées, chacune vue — dont six que l'ancien relevé ne voyait pas."""
    for forme, code in FORMES_FAUTIVES.items():
        assert _fstrings_sans_bindparams({f"{forme}.py": code}), f"forme « {forme} » non vue"


def test_le_controle_admet_ce_qui_est_lie_ou_constant():
    admis = {
        "identifiant constant": 'op.execute(text(f"DELETE FROM {TABLE} WHERE id = :x").bindparams(x=1))',
        "valeur liée": 'op.execute(text("UPDATE t SET a = :m").bindparams(m=f"bat:%/{suffixe}"))',
        "sans interpolation": 'op.execute("DELETE FROM t")',
    }
    for cas, code in admis.items():
        assert _fstrings_sans_bindparams({f"{cas}.py": code}) == set(), f"« {cas} » refusé à tort"


def test_aucune_fstring_sans_bindparams():
    fautives = sorted(_fstrings_sans_bindparams())
    saut = chr(10) + "  "
    assert not fautives, (
        "Ces `execute()` interpolent une f-string sans lier de paramètre :"
        + saut
        + saut.join(fautives)
        + chr(10) * 2
        + "Une VALEUR se lie : text('... :x ...').bindparams(x=valeur)."
        + chr(10)
        + "Un IDENTIFIANT (nom de table ou de colonne) ne se lie pas : le prendre "
        + "dans une constante du fichier, et écrire en commentaire que c'est un "
        + "identifiant."
    )
