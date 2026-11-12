"""Un module de `tests/` porte un nom qui dit ce qu'il est (#1604).

Trois noms seulement : `test_*.py` (des tests), `aides_*.py` (une aide partagée —
skill `api-scaffold` §9, « le code de test ne se recopie pas »), `conftest.py`. Le reste est
refusé : `purge_test.py` était collecté par le motif par défaut de pytest
(`*_test.py`) comme s'il portait des tests, alors qu'il n'en portait aucun, et
`contrats_email.py`, `lib_variables_jinja.py`… ne disaient pas qu'ils étaient des
aides. La config (`api/pytest.ini`) restreint en plus la COLLECTE à `test_*.py`.
"""

from __future__ import annotations

import fnmatch
import pathlib
import re

TESTS = pathlib.Path(__file__).resolve().parent
NOMS_ADMIS = (r"test_\w+", r"aides_\w+", r"conftest", r"__init__")


def _refuses(noms: list[str]) -> list[str]:
    """Les modules (sans extension) dont le nom n'est ni de test, ni d'aide, ni de conftest."""
    return [n for n in noms if not any(re.fullmatch(motif, n) for motif in NOMS_ADMIS)]


def _modules() -> list[str]:
    return sorted(p.stem for p in TESTS.glob("*.py"))


def test_cas_zero_le_releve_voit_les_tests_et_les_aides():
    noms = _modules()
    assert sum(n.startswith("test_") for n in noms) > 100, "le relevé ne voit plus les tests"
    assert sum(n.startswith("aides_") for n in noms) >= 5, "le relevé ne voit plus les aides"


def test_aucun_module_de_tests_sans_nom_de_test_ni_d_aide():
    refuses = _refuses(_modules())
    assert not refuses, (
        "Modules de `tests/` qui ne sont ni `test_*`, ni `aides_*`, ni `conftest` — "
        "les renommer (`git mv`) :\n  " + "\n  ".join(f"{n}.py" for n in refuses)
    )


def test_le_releve_sait_REFUSER():
    """Le cas fautif : les cinq noms qui existaient avant #1604, et un `*_test.py`."""
    anciens = [
        "purge_test",
        "contrats_email",
        "lib_variables_jinja",
        "roles_libelles_lecture",
        "tables_supprimees",
    ]
    assert _refuses([*anciens, "test_ok", "aides_ok", "conftest"]) == anciens


def test_la_collecte_ne_prend_que_les_fichiers_test(pytestconfig):
    """Le comportement, pas le fichier : la config EFFECTIVE de cette session."""
    motifs = pytestconfig.getini("python_files")
    assert motifs == ["test_*.py"], f"`python_files` vaut {motifs} — `api/pytest.ini` a bougé"
    #  Le défaut de pytest (`*_test.py`) aurait pris l'ancien `purge_test.py`.
    assert not any(fnmatch.fnmatch("purge_test.py", m) for m in motifs)
    assert any(fnmatch.fnmatch("test_x.py", m) for m in motifs)
