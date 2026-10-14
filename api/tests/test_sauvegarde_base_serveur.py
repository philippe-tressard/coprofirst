"""La sauvegarde d'une base SERVEUR porte son export vérifié (#1781, DI-7b).

Sans fichier à copier, `backup.run_backup` partait sans la base et se disait
« réussie ». Elle met désormais dans l'archive l'export vérifié (P2-7), réimporté
dans une base jetable AVANT d'être déclaré bon ; l'export hors site le relit sur
le poste. Le moteur de l'application est, ici, une base en mémoire — sans
fichier, donc la même branche qu'une base PostgreSQL.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import HistoriqueSauvegarde, StatutSauvegarde
from app.utils import backup, horloge

RACINE = Path(__file__).resolve().parents[2]
#: La relecture vit avec les GESTES de la copie hors site depuis #1896.
COPIE_HORS_SITE = RACINE / "scripts" / "lib" / "lib-export-hors-site-copie.sh"
LIB_HORS_SITE = RACINE / "scripts" / "lib" / "lib-export-hors-site.sh"


@pytest.fixture
def sauvegarde(tmp_path, monkeypatch):
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(backup.settings, "backup_dir", str(tmp_path))
    monkeypatch.setattr(horloge, "maintenant", lambda: datetime(2026, 10, 9, 1, 0, 0))
    return tmp_path


def _derniere() -> HistoriqueSauvegarde:
    with Session(engine) as s:
        return s.exec(select(HistoriqueSauvegarde).order_by(HistoriqueSauvegarde.id.desc())).first()


def test_l_archive_porte_l_export_et_se_dit_reussie(sauvegarde):
    backup.run_backup()
    assert _derniere().statut == StatutSauvegarde.reussie
    (archive,) = sauvegarde.glob(backup.MOTIF_ARCHIVE)
    with tarfile.open(archive) as tar:
        assert backup.NOM_EXPORT_BASE in tar.getnames()
        assert "app.db" not in tar.getnames()


def test_un_export_qui_ne_se_restaure_pas_fait_echouer_la_sauvegarde(sauvegarde, monkeypatch):
    from app.utils import import_copropriete

    def refuse(*_a, **_k):
        raise import_copropriete.ImportRefuse("table lot : 3 lignes, 4 annoncées")

    monkeypatch.setattr(import_copropriete, "importer", refuse)
    backup.run_backup()
    derniere = _derniere()
    assert derniere.statut == StatutSauvegarde.echouee
    assert "4 annoncées" in derniere.message_erreur


def test_une_base_abimee_n_est_pas_sauvegardee(sauvegarde, monkeypatch):
    monkeypatch.setattr(backup, "_integrite", lambda: "2 page(s) en échec de somme de contrôle")
    backup.run_backup()
    assert _derniere().statut == StatutSauvegarde.echouee
    assert not list(sauvegarde.glob(backup.MOTIF_ARCHIVE)), "aucune archive d'une base abîmée"


def test_le_poste_relit_l_export_avec_son_propre_code(sauvegarde):
    """Le Python que la copie hors site exécute (`relire_export`), sur l'export réellement produit."""
    backup.run_backup()
    (archive,) = sauvegarde.glob(backup.MOTIF_ARCHIVE)
    with tarfile.open(archive) as tar:
        export = sauvegarde / "base-export.tar.gz"
        export.write_bytes(tar.extractfile(backup.NOM_EXPORT_BASE).read())
    script = COPIE_HORS_SITE.read_text(encoding="utf-8")
    code = re.search(r"<<'PYTHON'\n(.*?)\nPYTHON\n", script, re.S)
    assert code, "le code de relecture n'est plus dans lib-export-hors-site-copie.sh"
    sortie = subprocess.run(
        [sys.executable, "-", str(export)], input=code.group(1), capture_output=True, text=True
    )
    assert sortie.returncode == 0, sortie.stderr
    lignes = [li.split() for li in io.StringIO(sortie.stdout) if li.strip()]
    assert lignes, "aucune table relue : le contrôle du poste ne mesurerait rien"
    assert all(lues == annoncees for _t, lues, annoncees in lignes)


def test_le_nom_de_l_export_est_le_meme_des_deux_cotes():
    lib = LIB_HORS_SITE.read_text(encoding="utf-8")
    assert f'NOM_EXPORT_BASE="{backup.NOM_EXPORT_BASE}"' in lib
