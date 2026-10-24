"""Le code de test ne se recopie pas plus que le code de l'application (#1495).

## Le défaut (audit du 30/09/2026)

Six relectures de `api/tests/` ont trouvé les mêmes aides réécrites d'un fichier
à l'autre : le balayage de `app/` (68 fichiers), la base de test (34), la
fabrique de compte (48 — avec un champ qui n'existe pas), des aides importées
depuis un AUTRE fichier de tests (11), la portée des scripts shell refaite à la
main. Chaque copie avait déjà divergé : seuils de cas zéro différents, portée
qui ne voyait pas les hooks git, `__pycache__` exclu ou non.

## Ce que ce fichier refuse

Chaque motif de `MOTIFS` ne s'écrit que dans son aide. Ailleurs, il est une
copie. Une exception se DÉCLARE (`EXCEPTIONS`, avec sa raison) et le contrôle
échoue si elle cesse de servir.
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

TESTS = pathlib.Path(__file__).resolve().parent
CE_FICHIER = pathlib.Path(__file__).name


@dataclass(frozen=True)
class Motif:
    nom: str
    regex: re.Pattern
    aide: str | None  #: le seul fichier où il s'écrit — None : nulle part
    remede: str


MOTIFS = (
    Motif(
        "balayage de app/",
        re.compile(r"\.rglob\(\s*[\"']\*\.py[\"']\s*\)"),
        "aides_sources.py",
        "`aides_sources.modules_app(sous_dossier)` — cas zéro et cache compris",
    ),
    Motif(
        "schéma de test posé à la main",
        re.compile(r"\bschema_jetable\(|CREATE SCHEMA"),
        "aides_base.py",
        "la fixture `session` (conftest), ou `aides_base.moteur_de_test()`",
    ),
    Motif(
        "fixture session qui refait la base de test",
        #  Une fixture `session` locale qui ne dépend pas de celle du conftest et
        #  rouvre `Session(moteur_de_test(…))` : la même base, écrite à côté (#1604).
        re.compile(
            r"def session\((?![^)]*\bsession\b)[^)]*\):(?:(?!\n\S)[\s\S])*?Session\(moteur_de_test\("
        ),
        "conftest.py",
        "`def session(session): …` — la locale AJOUTE ses données à celle du conftest",
    ),
    Motif(
        "champ inexistant d'Utilisateur",
        re.compile(r"\bmot_de_passe_hash\b"),
        None,
        "`aides_base.compte(session, …)` — le champ réel est `hashed_password`",
    ),
    Motif(
        "aide importée depuis un fichier de tests",
        re.compile(
            r"^\s*(?:from\s+(?:tests\.|\.)?test_\w+\s+import|import\s+tests\.test_\w+)",
            re.MULTILINE,
        ),
        None,
        "une aide partagée vit dans un `tests/aides_*.py`, jamais dans un test",
    ),
    Motif(
        "migration chargée à la main",
        re.compile(r"\bspec_from_file_location\("),
        "aides_migrations.py",
        "`aides_migrations.charger_migration(motif)`",
    ),
    Motif(
        "horloge dépréciée",
        re.compile(r"\butcnow\("),
        None,
        "`app.utils.horloge.maintenant()` — l'UTC naïf de la base",
    ),
    Motif(
        "docstrings écartées à la main",
        #  Quatre copies jusqu'au 07/10/2026 (#1725), dont une qui écartait aussi
        #  la première chaîne d'un `if` ou d'un `for`.
        re.compile(r"isinstance\(\s*corps\[0\]\.value,\s*ast\.Constant\s*\)"),
        "aides_sources.py",
        "`aides_sources.docstrings(arbre)` ou `aides_sources.chaines_du_code(arbre)`",
    ),
    Motif(
        "patrimoine vidé à la main",
        #  Le défaut du 24/10/2026 (#2223) : une fixture ne supprimait que les
        #  copropriétés, et SQLAlchemy déliait les bâtiments qu'un test précédent
        #  avait laissés — six erreurs, sur le lot d'un autre. Vider UNE table du
        #  patrimoine, c'est laisser les autres incohérentes.
        re.compile(
            r"select\((?:Copropriete|Batiment|Perimetre)\)\)\.all\(\)[^\n]*:\s*\n\s*\w+\.delete\("
            r"|\bdelete\((?:Copropriete|Batiment|Perimetre)\)"
            r"|purger_referentiellement\(\s*\w+,\s*(?:Copropriete|Batiment|Perimetre)\b"
            r"|(?i:delete\s+from\s+\"?(?:copropriete|batiment|perimetre)\b)"
        ),
        "aides_purge.py",
        "`aides_purge.vider_patrimoine(session)` — l'arbre seul : `vider_perimetres(session)`",
    ),
    Motif(
        "session de test jamais fermée",
        #  `session = Session(moteur_de_test())` garde sa connexion ouverte : le
        #  retrait du schéma du test l'attendait 10 s, puis échouait et laissait le
        #  schéma derrière lui (#2223, cinq tests sur la suite parallèle).
        re.compile(r"=\s*Session\(\s*moteur_de_test\("),
        None,
        "la fixture `session` (conftest), ou `with Session(moteur_de_test()) as s:`",
    ),
    Motif(
        "portée des scripts shell",
        re.compile(r"glob\(\s*[\"'][^\"']*\*\.sh[\"']"),
        "conftest.py",
        "`conftest.scripts_shell_versionnes()`",
    ),
)

#: (motif, fichier) → pourquoi ce fichier a le droit d'écrire le motif.
EXCEPTIONS: dict[tuple[str, str], str] = {
    ("balayage de app/", "test_dependances_declarees.py"): (
        "son second `rglob` lit `alembic/`, que `aides_sources` ne couvre pas : "
        "une migration importe aussi des modules tiers"
    ),
    ("schéma de test posé à la main", "test_schemas_jetables_perimes.py"): (
        "il pose des schémas sous des NOMS choisis — périmé, sans heure lisible — "
        "pour éprouver la purge (#2223) : `moteur_de_test` rend toujours un nom neuf"
    ),
    ("balayage de app/", "test_python_sans_avertissement_de_syntaxe.py"): (
        "il COMPILE chaque fichier de `app/`, `tests/`, `alembic/` et `scripts/` : "
        "`aides_sources` ne lit que `app/`, et ne compile rien"
    ),
}


def _fichiers() -> list[pathlib.Path]:
    return sorted(p for p in TESTS.glob("*.py") if p.name != CE_FICHIER)


def _ecarts(motif: Motif, fichiers) -> list[str]:
    ecarts = []
    for chemin, texte in fichiers:
        if chemin == motif.aide or (motif.nom, chemin) in EXCEPTIONS:
            continue
        n = len(motif.regex.findall(texte))
        if n:
            ecarts.append(f"{chemin} ({n})")
    return ecarts


def _textes():
    return [(p.name, p.read_text(encoding="utf-8")) for p in _fichiers()]


def test_aucune_aide_n_est_recopiee():
    textes = _textes()
    fautes = [
        f"• {m.nom} — {', '.join(e)}\n    → {m.remede}" for m in MOTIFS if (e := _ecarts(m, textes))
    ]
    assert not fautes, "Aides de test recopiées hors de leur module :\n" + "\n".join(fautes)


def test_le_controle_voit_ses_motifs():
    """Cas zéro : chaque aide porte bien son propre motif, et la portée lit des fichiers."""
    textes = dict(_textes())
    assert len(textes) > 200, "la portée ne lit presque rien : le dossier des tests a bougé"
    muets = [m.nom for m in MOTIFS if m.aide and not m.regex.search(textes.get(m.aide, ""))]
    assert not muets, f"motif(s) qui ne reconnaissent plus leur propre aide : {muets}"


def test_le_controle_sait_REFUSER():
    forges = {
        "balayage de app/": 'for p in APP.rglob("*.py"):',
        "schéma de test posé à la main": "moteur, retirer = schema_jetable(url)",
        "fixture session qui refait la base de test": (
            "def session():\n    with Session(moteur_de_test()) as s:\n        yield s\n"
        ),
        "champ inexistant d'Utilisateur": 'Utilisateur(mot_de_passe_hash="x")',
        "aide importée depuis un fichier de tests": "from tests.test_autre import _aide",
        "migration chargée à la main": "spec = importlib.util.spec_from_file_location(n, c)",
        "horloge dépréciée": "t = datetime.utcnow()",
        "docstrings écartées à la main": "if isinstance(corps[0].value, ast.Constant):",
        "patrimoine vidé à la main": (
            "for ligne in session.exec(select(Copropriete)).all():\n    session.delete(ligne)\n"
        ),
        "session de test jamais fermée": "session = Session(moteur_de_test())",
        "portée des scripts shell": 'racine.rglob("*.sh")',
    }
    assert set(forges) == {m.nom for m in MOTIFS}, "un motif n'a pas son extrait forgé"
    muets = [m.nom for m in MOTIFS if not _ecarts(m, [("test_forge.py", forges[m.nom])])]
    assert not muets, f"motif(s) qui laissent passer leur copie : {muets}"


def test_chaque_exception_sert_encore():
    textes = dict(_textes())
    par_nom = {m.nom: m for m in MOTIFS}
    mortes = [
        f"{nom} / {fichier}"
        for (nom, fichier) in EXCEPTIONS
        if not par_nom[nom].regex.search(textes.get(fichier, ""))
    ]
    assert not mortes, f"exception(s) qui ne servent plus — à retirer : {mortes}"
