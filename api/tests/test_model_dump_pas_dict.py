"""🔒 Un schéma se vide par `model_dump()`, jamais par `.dict()` (#2956).

`.dict()` est la forme de Pydantic v1, dépréciée en v2 : elle marche encore, avec
un avertissement, jusqu'à la version qui la retirera — et ce jour-là la route
tombe en 500. La skill `api-scaffold` l'écrivait (« `model_dump()`, pas
`.dict()` »), et rien ne le refusait : l'audit du 23/11/2026 en a trouvé une,
dans `routers/patrimoine.py` (`PATCH /perimetres/{perimetre_id}`).

Ruff ne la connaît pas : le relevé lit l'arbre syntaxique de `app/` et refuse tout
appel de méthode nommé `dict` (`x.dict(…)`). Un dictionnaire Python n'a pas de
méthode `.dict` : aucun faux positif à déclarer, et l'appel nu `dict(…)` (le
constructeur) n'est pas un attribut, il n'est donc pas visé.
"""

from __future__ import annotations

import ast

from tests.aides_sources import modules_app


def _appels_de_methode(nom: str) -> list[str]:
    return [
        f"{module.rel}:{n.lineno}"
        for module in modules_app()
        for n in ast.walk(module.arbre)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == nom
    ]


def test_aucun_appel_dict_sur_un_objet():
    trouves = _appels_de_methode("dict")
    assert not trouves, (
        "`.dict()` est la forme dépréciée de Pydantic v1 — écrire `.model_dump(…)`, "
        f"mêmes arguments (`exclude_unset=True`…) : {trouves}"
    )


def test_le_releve_voit_les_model_dump():
    """Cas zéro : si le relevé ne voyait aucun appel de méthode, le test ci-dessus
    passerait à vide. La forme correcte, elle, est partout dans `app/`."""
    assert len(_appels_de_methode("model_dump")) >= 20
