"""Une aide de tests qui REND une liste lue en base la rend dans un ordre écrit (#2175).

PostgreSQL ne garantit aucun ordre sans `ORDER BY`. `_evolutions` (`aides_courriel`)
rendait `session.exec(select(...)).all()` sans tri, et un test en découpait la fin
(`_evolutions(...)[avant:]`) en supposant l'ordre d'insertion : une ligne mise à jour
entre les deux lectures repassait en fin de table, et la tranche prenait la mauvaise
entrée — une fois sur quatre passages, sans aucun changement.

La règle, lue sur l'AST de `tests/aides_*.py` : une fonction qui `return`
`<x>.exec(<requête>).all()` porte un `order_by` dans sa requête. Une aide dont les
appelants ne s'appuient pas sur l'ordre (ils comptent, ou comparent à `[]`) se
déclare dans `ENSEMBLES`, avec sa raison ; une déclaration qui ne sert plus échoue.
Itérer pour purger n'est pas rendre : seules les valeurs RENDUES sont jugées.
"""

from __future__ import annotations

import ast
import pathlib

TESTS = pathlib.Path(__file__).resolve().parent

#  `module.fonction` → pourquoi l'ordre n'importe à aucun appelant. Vide au 23/10/2026.
ENSEMBLES: dict[str, str] = {}


def _contient_order_by(noeud: ast.AST) -> bool:
    return any(isinstance(n, ast.Attribute) and n.attr == "order_by" for n in ast.walk(noeud))


def _lecture_rendue(valeur: ast.AST | None) -> ast.Call | None:
    """`<x>.exec(<requête>).all()` → l'appel `exec` ; sinon None."""
    if not (
        isinstance(valeur, ast.Call)
        and isinstance(valeur.func, ast.Attribute)
        and valeur.func.attr == "all"
    ):
        return None
    recepteur = valeur.func.value
    if (
        isinstance(recepteur, ast.Call)
        and isinstance(recepteur.func, ast.Attribute)
        and recepteur.func.attr == "exec"
    ):
        return recepteur
    return None


def lectures_sans_ordre(source: str, module: str) -> list[str]:
    """Les `module.fonction` qui rendent une lecture en base sans `order_by`."""
    fautives = []
    for fonction in ast.walk(ast.parse(source)):
        if not isinstance(fonction, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for n in ast.walk(fonction):
            if isinstance(n, ast.Return) and (lecture := _lecture_rendue(n.value)):
                if not _contient_order_by(lecture):
                    fautives.append(f"{module}.{fonction.name}")
    return sorted(set(fautives))


def _releve() -> tuple[list[str], int]:
    fautives, lectures = [], 0
    for chemin in sorted(TESTS.glob("aides_*.py")):
        source = chemin.read_text(encoding="utf-8")
        fautives += lectures_sans_ordre(source, chemin.stem)
        arbre = ast.parse(source)
        lectures += sum(
            isinstance(n, ast.Return) and _lecture_rendue(n.value) is not None
            for n in ast.walk(arbre)
        )
    return fautives, lectures


def test_cas_zero_le_releve_voit_les_lectures_rendues():
    _, lectures = _releve()
    assert lectures >= 3, f"le relevé ne voit plus que {lectures} lecture(s) rendue(s)"


def test_une_aide_rend_sa_lecture_dans_un_ordre_ecrit():
    fautives = [f for f in _releve()[0] if f not in ENSEMBLES]
    assert not fautives, (
        "Aides de tests qui rendent `session.exec(select(...)).all()` sans `order_by` — "
        "PostgreSQL ne garantit aucun ordre (#2175). Ajouter `.order_by(Modele.id)`, "
        "ou déclarer l'aide dans `ENSEMBLES` avec sa raison :\n  " + "\n  ".join(fautives)
    )


def test_une_declaration_qui_ne_sert_plus_echoue():
    perimees = sorted(set(ENSEMBLES) - set(_releve()[0]))
    assert not perimees, f"Déclarations d'`ENSEMBLES` qui ne servent plus : {perimees}"


def test_le_releve_sait_REFUSER():
    """Le cas fautif de #2175, et ses deux formes admises."""
    source = (
        "def _evolutions(session, t):\n"
        "    return session.exec(select(E).where(E.ticket_id == t.id)).all()\n"
        "def _triees(session, t):\n"
        "    return session.exec(select(E).where(E.ticket_id == t.id).order_by(E.id)).all()\n"
        "def _purge(session):\n"
        "    for x in session.exec(select(E)).all():\n"
        "        purger(x)\n"
    )
    assert lectures_sans_ordre(source, "aides_x") == ["aides_x._evolutions"]
