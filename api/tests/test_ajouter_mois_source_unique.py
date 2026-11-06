"""Une date plus N mois : une seule écriture, `echeance_contrat.ajouter_mois` (#2561).

## Pourquoi ce contrôle

« Une date plus N mois » était écrit QUATRE fois dans `api/` :
`echeance_contrat.ajouter_mois` (jour ramené au dernier du mois), une copie dans
`prochaine_visite` qui bornait le jour à 28 dans TOUS les cas — une visite du 30
glissait au 28 du mois suivant et y restait —, `recidive.il_y_a_mois` et
`telemetrie_lecture.mois_il_y_a` (plus le même calcul recopié dans un test).
`scripts/ci/clones_python.py` n'en voyait aucune : les corps différaient.

## Ce qu'il refuse

Sur l'AST de `app/` et de `tests/`, hors de `ajouter_mois` : un mois additionné ou
soustrait d'une valeur variable (`d.month + n`), une année multipliée par 12, un
`divmod(…, 12)`. Ces trois formes SONT l'arithmétique des mois ; un index de liste
(`MOIS[d.month - 1]`) n'est pas visé.

Une écriture qui pose une AUTRE question se déclare dans `EXCEPTIONS`, avec sa
raison — et le contrôle échoue si elle cesse de servir.
"""

from __future__ import annotations

import ast
from pathlib import Path

API = Path(__file__).resolve().parents[1]

#: La seule écriture admise : (fichier, fonction).
LIEU = ("app/utils/echeance_contrat.py", "ajouter_mois")

#: (fichier, fonction) → raison. Une autre question que « une date plus N mois ».
EXCEPTIONS = {
    ("app/utils/dates_fr.py", "mois_ecoules"): (
        "l'ÉCART en mois entre deux dates (ancienneté), pas une date déplacée"
    ),
}


def _constante(n: ast.AST) -> bool:
    return isinstance(n, ast.Constant)


def _forme(n: ast.AST) -> str | None:
    """La forme d'arithmétique des mois que porte le nœud, ou `None`."""
    if isinstance(n, ast.BinOp):
        for a, b in ((n.left, n.right), (n.right, n.left)):
            if not isinstance(a, ast.Attribute):
                continue
            if a.attr == "month" and isinstance(n.op, (ast.Add, ast.Sub)) and not _constante(b):
                return "mois ± valeur variable"
            if a.attr == "year" and isinstance(n.op, ast.Mult) and _constante(b) and b.value == 12:
                return "année × 12"
    if (
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "divmod"
        and len(n.args) == 2
        and _constante(n.args[1])
        and n.args[1].value == 12
    ):
        return "divmod(…, 12)"
    return None


def _ecritures(racine: Path, relatif: str, source: str) -> list[tuple[tuple[str, str], int, str]]:
    """Chaque forme trouvée, rattachée à la fonction qui la porte."""
    trouvees = []

    def visiter(noeud: ast.AST, fonction: str) -> None:
        for enfant in ast.iter_child_nodes(noeud):
            nom = fonction
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nom = enfant.name
            forme = _forme(enfant)
            if forme:
                trouvees.append(((relatif, nom), enfant.lineno, forme))
            visiter(enfant, nom)

    visiter(ast.parse(source), "<module>")
    return trouvees


def _toutes() -> list[tuple[tuple[str, str], int, str]]:
    toutes = []
    for dossier in ("app", "tests"):
        for f in sorted((API / dossier).rglob("*.py")):
            relatif = f.relative_to(API).as_posix()
            toutes += _ecritures(API, relatif, f.read_text(encoding="utf-8"))
    return toutes


def test_aucune_autre_ecriture_d_une_date_plus_n_mois():
    hors_lieu = [
        f"{lieu[0]}:{ligne} ({lieu[1]}) — {forme}"
        for lieu, ligne, forme in _toutes()
        if lieu != LIEU and lieu not in EXCEPTIONS
    ]
    assert not hors_lieu, (
        "« une date plus N mois » s'écrit par `echeance_contrat.ajouter_mois`, jamais "
        "recopié (#2561) — ou se déclare dans EXCEPTIONS avec sa raison :\n" + "\n".join(hors_lieu)
    )


def test_le_lieu_et_chaque_exception_servent():
    """Cas zéro : un motif qui ne trouve plus rien ne prouve plus rien."""
    lieux = {lieu for lieu, _, _ in _toutes()}
    assert LIEU in lieux, f"{LIEU} ne porte plus l'arithmétique des mois : le contrôle est aveugle"
    mortes = sorted(set(EXCEPTIONS) - lieux)
    assert not mortes, f"exceptions qui ne servent plus, à retirer : {mortes}"


def test_le_controle_voit_chaque_forme():
    """Le contrôle refuse les écritures qu'il a trouvées le 06/11/2026."""
    fautives = {
        "borne_28": "def f(d, n):\n    m = d.month + n\n",
        "annee_12": "def f(d, n):\n    t = d.year * 12 + d.month - 1 - n\n",
        "divmod": "def f(t):\n    return divmod(t, 12)\n",
    }
    for nom, source in fautives.items():
        assert _ecritures(API, "x.py", source), f"forme non vue : {nom}"
    #  Un index de liste n'est pas une arithmétique des mois.
    assert not _ecritures(API, "x.py", "def f(d):\n    return MOIS[d.month - 1]\n")
