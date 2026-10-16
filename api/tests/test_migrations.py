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

_API_DIR = Path(__file__).resolve().parents[1]


def _script_dir() -> ScriptDirectory:
    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_un_seul_head():
    """Pas de divergence : un unique head (sinon upgrade head échoue en prod)."""
    heads = _script_dir().get_heads()
    assert len(heads) == 1, f"Plusieurs heads de migration : {heads} (down_revision incorrect ?)"


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
#  🔴 Aucune f-string dans un `execute()` de migration (#1032)
#
#  ⚠️ Un `grep 'op.execute(f"'` en rend **zéro** : la f-string est presque
#  toujours à la ligne suivante de l'appel. C'est pourquoi ce contrôle lit
#  l'arbre syntaxique et non le texte.
#
#  | Ce qu'on interpole | Verdict |
#  |---|---|
#  | une **valeur** (contenu, identifiant de ligne, date) | jamais — `bindparams` |
#  | un **identifiant** (nom de table ou de colonne) depuis une constante du fichier | toléré : un identifiant ne se lie pas |
# ─────────────────────────────────────────────────────────────────────────────


def _fstrings_sans_bindparams(sources: dict[str, str] | None = None) -> set[str]:
    """Les `execute(...)` de migration qui interpolent sans lier, par AST."""
    import ast

    if sources is None:
        sources = {
            f.name: f.read_text(encoding="utf-8")
            for f in sorted((_API_DIR / "alembic" / "versions").glob("*.py"))
        }
    trouves = set()
    for nom, source in sources.items():
        arbre = ast.parse(source)
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            if not ast.unparse(noeud.func).endswith("execute"):
                continue
            if not any(isinstance(x, ast.JoinedStr) for x in ast.walk(noeud)):
                continue
            if "bindparams" in ast.unparse(noeud):
                continue
            trouves.add(f"{nom}:{noeud.lineno}")
    return trouves


def test_le_controle_voit_bien_les_migrations():
    """Cas zéro de la portée : un glob vide se lirait comme « aucun écart »."""
    versions = list((_API_DIR / "alembic" / "versions").glob("*.py"))
    assert versions, "aucune migration vue — le contrôle a perdu sa portée"


def test_le_controle_sait_REFUSER():
    """Le témoin : une f-string non liée, forgée, est vue — même à la ligne suivante."""
    forge = 'from alembic import op\nop.execute(\n    f"DELETE FROM t WHERE id = {x}"\n)\n'
    assert _fstrings_sans_bindparams({"forge.py": forge}) == {"forge.py:2"}
    lie = 'op.execute(text(f"DELETE FROM {TABLE} WHERE id = :x").bindparams(x=1))\n'
    assert _fstrings_sans_bindparams({"lie.py": lie}) == set()


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
