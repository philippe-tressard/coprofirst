"""La nature d'un lot se lit par `utils/designation_lot`, nulle part ailleurs (#2212).

`Lot.nature` (l'état descriptif du règlement) précise `Lot.type` sans le remplacer
encore : un lot qui n'est pas passé par l'import n'en a pas. Lire `lot.nature` en
direct, c'est décider que ce lot n'a pas de nature — une cave non importée cesserait
d'être une annexe, et ouvrirait son bâtiment (`mes_batiments`). La question se pose à
`nature_du_lot` ou `est_annexe`, qui répondent aussi pour elle.

Le relevé lit l'arbre syntaxique : une LECTURE de l'attribut `nature` sur un objet
nommé `lot` (ou `….lot`). L'écriture — l'application de l'état descriptif — n'est pas
une lecture.
"""

from __future__ import annotations

import ast

from tests.aides_sources import module_app, modules_app

_SOURCE = "utils/designation_lot.py"


def _est_un_lot(objet: ast.AST) -> bool:
    if isinstance(objet, ast.Name):
        return objet.id in ("lot", "Lot")
    return isinstance(objet, ast.Attribute) and objet.attr == "lot"


def _lectures(arbre: ast.AST) -> list[int]:
    return [
        n.lineno
        for n in ast.walk(arbre)
        if isinstance(n, ast.Attribute)
        and n.attr == "nature"
        and isinstance(n.ctx, ast.Load)
        and _est_un_lot(n.value)
    ]


def test_la_nature_d_un_lot_ne_se_lit_qu_a_sa_source():
    fautes = [
        f"app/{m.rel}:{ligne}"
        for m in modules_app("", minimum=100)
        if m.rel != _SOURCE
        for ligne in _lectures(m.arbre)
    ]
    assert not fautes, (
        "`lot.nature` lu en direct — passer par `designation_lot.nature_du_lot` ou "
        "`est_annexe` :\n" + "\n".join(fautes)
    )


def test_le_releve_voit_la_forme_refusee():
    """Le contrôle refuse ce qu'il doit refuser — sinon il est vert par construction."""
    assert _lectures(ast.parse("x = lot.nature\ny = ul.lot.nature\nlot.nature = 1")) == [1, 2]


def test_la_source_existe_et_repond():
    assert "def nature_du_lot" in module_app(_SOURCE).source
