"""Une table retirée du modèle n'efface pas les sauvegardes faites avant (#3098).

POURQUOI (25/11/2026) — retirer `canal_distribution` du modèle du registre (premier
temps de sa contraction) aurait rendu irrestaurables TOUTES les sauvegardes du
registre déjà faites : l'import refuse une table absente des modèles (« tables
absentes des modèles de ce code »), et chaque archive la porte — lu sur la
production le 25/11, `plateforme_backup_20261125_033000` : `canal_distribution`,
1 ligne. Une COLONNE retirée était déjà écartée d'office (#1799) ; une table, non.

CE QUE CE TEST TIENT :

- une table inconnue NON déclarée reste refusée (témoin) : c'est ce qui arrête
  l'archive d'un code plus récent, qu'on ne sait pas relire ;
- une table DÉCLARÉE retirée (`import_copropriete.TABLES_RETIREES`) est écartée,
  nommée au bilan et dans le résumé ;
- la déclaration est tenue des deux côtés, dans `test_migrations_compatibles.py`
  qui détient `CONTRACTIONS` : chaque table annoncée y est, et chacune de ses
  entrées est annoncée et n'est plus un modèle.
"""

from __future__ import annotations

import pytest

from app.utils import export_copropriete as ex
from app.utils import import_copropriete as im
from tests.aides_base import moteur_de_test
from tests.aides_export import ajouter_table, base_peuplee

LIGNE_D_AVANT = {"id": 1, "nom": "replica", "version": "3.11.7"}


@pytest.fixture
def archive(tmp_path):
    chemin = tmp_path / "export.tar.gz"
    ex.exporter(base_peuplee(), chemin)
    return chemin


def test_une_table_inconnue_non_declaree_est_refusee(archive, tmp_path):
    """Témoin (`standards/04` §2) : la règle d'avant tient pour ce qui n'est pas déclaré."""
    inconnue = tmp_path / "inconnue.tar.gz"
    ajouter_table(archive, inconnue, "table_d_un_code_plus_recent", [LIGNE_D_AVANT])
    with pytest.raises(im.ImportRefuse, match="table_d_un_code_plus_recent"):
        im.importer(inconnue, moteur_de_test())


def test_une_table_declaree_retiree_est_ecartee_et_nommee(archive, tmp_path, monkeypatch):
    monkeypatch.setattr(im, "TABLES_RETIREES", {"table_fantome": "retirée pour l'essai"})
    ancienne = tmp_path / "ancienne.tar.gz"
    ajouter_table(archive, ancienne, "table_fantome", [LIGNE_D_AVANT])
    bilan = im.importer(ancienne, moteur_de_test())
    assert bilan.tables_ecartees == ["table_fantome"]
    assert bilan.ecarts == []
    assert any("table_fantome" in ligne for ligne in im.resume(bilan))


def test_canal_distribution_d_une_sauvegarde_d_avant_se_relit(archive, tmp_path):
    """Le cas du 25/11 : une sauvegarde du registre faite avant #3098 la porte."""
    ancienne = tmp_path / "registre-d-avant.tar.gz"
    ajouter_table(archive, ancienne, "canal_distribution", [LIGNE_D_AVANT])
    bilan = im.importer(ancienne, moteur_de_test())
    assert bilan.tables_ecartees == ["canal_distribution"]
