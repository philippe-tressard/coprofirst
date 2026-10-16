"""Une colonne d'énumération ne se compare qu'à l'une de SES valeurs (DI-7c, 10/10/2026).

Le fil d'accueil filtrait `PetiteAnnonce.statut != "archive"` — or `archive`
n'est PAS une valeur de `StatutAnnonce` (l'archivage se calcule). L'énumération
est un TYPE, qui refuse la valeur : `GET /flux` est tombé en 500, et l'accueil
de tous les résidents avec lui.

Ce contrôle lit `app/` sur l'AST : une comparaison (`==`, `!=`, `in_`,
`notin_`) entre `Modele.colonne` d'énumération et un littéral hors de ses
valeurs est refusée — elle ne peut pas être juste.
"""

from __future__ import annotations

import ast

from sqlalchemy import Enum as SAEnum
from sqlmodel import SQLModel

import app.models.core  # noqa: F401 — enregistre toutes les tables (#1157)
from tests.aides_sources import modules_app


def _colonnes_enumerees() -> dict[str, dict[str, set[str]]]:
    """Modèle → colonne d'énumération → ses valeurs en base."""
    carte: dict[str, dict[str, set[str]]] = {}
    for mapper in SQLModel._sa_registry.mappers:
        table = getattr(mapper.class_, "__table__", None)
        if table is None:
            continue
        cols = {c.name: set(c.type.enums) for c in table.columns if isinstance(c.type, SAEnum)}
        if cols:
            carte[mapper.class_.__name__] = cols
    return carte


def _colonne(noeud, carte) -> tuple[str, str] | None:
    if (
        isinstance(noeud, ast.Attribute)
        and isinstance(noeud.value, ast.Name)
        and noeud.attr in carte.get(noeud.value.id, {})
    ):
        return noeud.value.id, noeud.attr
    return None


def _litteraux(noeuds) -> list[str]:
    return [n.value for n in noeuds if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def comparaisons_hors_valeurs(arbre: ast.AST, carte) -> list[tuple[int, str]]:
    """PURE. `(ligne, « Modele.colonne vs 'valeur' »)` pour chaque valeur hors de l'énumération."""
    fautes = []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Compare):
            membres = [n.left, *n.comparators]
            for m in membres:
                if (col := _colonne(m, carte)) is None:
                    continue
                for v in _litteraux(membres):
                    if v not in carte[col[0]][col[1]]:
                        fautes.append((n.lineno, f"{col[0]}.{col[1]} vs {v!r}"))
        elif (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in ("in_", "notin_")
            and (col := _colonne(n.func.value, carte)) is not None
            and n.args
            and isinstance(n.args[0], (ast.List, ast.Tuple, ast.Set))
        ):
            for v in _litteraux(n.args[0].elts):
                if v not in carte[col[0]][col[1]]:
                    fautes.append((n.lineno, f"{col[0]}.{col[1]}.{n.func.attr} {v!r}"))
    return fautes


def test_le_releve_connait_les_enumerations():
    carte = _colonnes_enumerees()
    assert "archive" not in carte["PetiteAnnonce"]["statut"]
    assert len(carte) >= 10, f"cas zéro : {len(carte)} modèle(s) à énumération lus"


def test_le_releve_voit_la_panne_du_10_10():
    carte = _colonnes_enumerees()
    code = 'select(PetiteAnnonce).where(PetiteAnnonce.statut != "archive")'
    assert comparaisons_hors_valeurs(ast.parse(code), carte) == [
        (1, "PetiteAnnonce.statut vs 'archive'")
    ]
    code = 'q.where(PetiteAnnonce.statut.in_(["en_cours", "archive"]))'
    assert len(comparaisons_hors_valeurs(ast.parse(code), carte)) == 1
    assert comparaisons_hors_valeurs(ast.parse('PetiteAnnonce.statut == "vendu"'), carte) == []


def test_aucune_enumeration_comparee_a_une_valeur_qui_n_en_est_pas():
    carte = _colonnes_enumerees()
    fautes = [
        f"app/{m.rel}:{ligne} {quoi}"
        for m in modules_app()
        for ligne, quoi in comparaisons_hors_valeurs(m.arbre, carte)
    ]
    assert not fautes, (
        "une colonne d'énumération comparée à une valeur qui n'en fait pas partie — "
        "refusé par la base (500) :\n" + "\n".join(fautes)
    )
