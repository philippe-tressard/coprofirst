"""Les tests sautés se consignent pour le rejeu local de la CI (#1734).

Le rejeu rendait « Run pytest — OK » sur un lot que la CI a vu échouer : les
tests de rendu PDF, sautés faute de WeasyPrint sur le poste, n'avaient pas
tourné, et rien ne le disait. Le pourquoi : `tests/aides_rejeu.py`.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests import conftest
from tests.aides_rejeu import VARIABLE, consigner_saut, ligne_de_saut


def _rapport(skipped: bool, longrepr=None, nodeid="tests/test_x.py::test_y"):
    return SimpleNamespace(skipped=skipped, longrepr=longrepr, nodeid=nodeid)


def test_un_saut_donne_son_noeud_et_sa_raison():
    r = _rapport(True, ("tests/test_x.py", 12, "Skipped: WeasyPrint absent\t(système)"))
    assert ligne_de_saut(r) == "tests/test_x.py::test_y\tWeasyPrint absent (système)"


def test_un_saut_relaye_par_le_maitre_xdist_ne_compte_pas_deux_fois():
    relaye = _rapport(True, ("f", 1, "Skipped: WeasyPrint absent"))
    relaye.node = object()  # le worker d'origine, posé par xdist chez le maître
    assert ligne_de_saut(relaye) is None


def test_un_test_joue_ne_donne_rien():
    assert ligne_de_saut(_rapport(False)) is None


def test_hors_rejeu_rien_n_est_ecrit(tmp_path, monkeypatch):
    monkeypatch.delenv(VARIABLE, raising=False)
    consigner_saut(_rapport(True, ("f", 1, "Skipped: x")))
    assert list(tmp_path.iterdir()) == []


def test_dans_le_rejeu_chaque_saut_s_ajoute(tmp_path, monkeypatch):
    fichier = tmp_path / "sauts"
    monkeypatch.setenv(VARIABLE, str(fichier))
    consigner_saut(_rapport(True, ("f", 1, "Skipped: a"), nodeid="t::un"))
    consigner_saut(_rapport(False))
    consigner_saut(_rapport(True, ("f", 2, "Skipped: b"), nodeid="t::deux"))
    assert fichier.read_text(encoding="utf-8") == "t::un\ta\nt::deux\tb\n"


def test_le_crochet_est_branche():
    #  Écrit dans un module qu'aucun crochet n'appelle, le relevé serait muet.
    assert callable(getattr(conftest, "pytest_runtest_logreport", None))
