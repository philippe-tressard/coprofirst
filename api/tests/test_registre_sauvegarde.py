"""La sauvegarde nocturne de la base `plateforme` (#1892, spec §4.9 et §4.11).

La base de chaque test est posée par SA chaîne de migrations (`registre.migrer`),
comme dans `test_registre_inscription.py` : l'archive est celle que la production
produira, et sa vérification par réimport est réellement jouée.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app.config import get_settings
from app.registre import base, migrer, sauvegarde
from app.registre.modeles import IDENTIFIANT_REFERENCE, Installation
from app.utils import backup, sante_plateforme
from app.utils.import_copropriete import ImportRefuse
from tests.aides_base import adresse_de_test, moteur_de_test
from tests.aides_registre import registre_allume


@pytest.fixture
def registre(monkeypatch, tmp_path):
    """Une base `plateforme` migrée qui porte la référence, et le registre allumé."""
    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path / "sauvegardes"))
    with registre_allume(monkeypatch) as moteur:
        with Session(moteur) as session:
            migrer.inscrire_reference(session)
        yield moteur


@pytest.fixture
def alertes(monkeypatch) -> list[list[str]]:
    recues: list[list[str]] = []
    monkeypatch.setattr(sante_plateforme, "alerter", recues.append)
    return recues


def _manifeste(archive) -> dict:
    with tarfile.open(archive, "r:gz") as tar:
        return json.loads(tar.extractfile("manifeste.json").read())


def test_l_archive_porte_le_registre_et_rien_de_la_residence(registre, alertes):
    sauvegarde.run_sauvegarde_plateforme()
    (archive,) = sauvegarde.dossier().glob("plateforme_backup_*.tar.gz")
    tables = _manifeste(archive)["tables"]
    assert tables["installation"]["lignes"] == 1  # la référence, CF-000000
    assert "utilisateur" not in tables and "ticket" not in tables
    assert backup.horodatage_archive(archive.name, sauvegarde.PREFIXE) is not None
    assert not alertes


def test_les_archives_de_la_residence_ne_sont_pas_melees(registre, alertes):
    """Rotation, fraîcheur et copie hors site de la résidence lisent `hostachy_backup_*`
    à la racine : celles du registre vivent dans un sous-dossier, sous un autre nom."""
    sauvegarde.run_sauvegarde_plateforme()
    racine = sauvegarde.dossier().parent
    assert not list(racine.glob(backup.MOTIF_ARCHIVE))


def test_on_garde_les_dernieres(registre, monkeypatch):
    monkeypatch.setattr(get_settings(), "backup_keep_versions", 2)
    dossier = sauvegarde.dossier()
    dossier.mkdir(parents=True)
    for jour in ("20260101", "20260102", "20260103"):
        (dossier / f"plateforme_backup_{jour}_030000_paris.tar.gz").write_bytes(b"ancienne")
    sauvegarde.sauvegarder()
    restantes = sorted(p.name for p in dossier.glob("plateforme_backup_*.tar.gz"))
    assert len(restantes) == 2 and "plateforme_backup_20260103_030000_paris.tar.gz" in restantes


def test_une_archive_qui_ne_se_restaure_pas_n_est_pas_gardee_et_l_operateur_le_sait(
    registre, alertes, monkeypatch
):
    def refus(*_a, **_k):
        raise ImportRefuse("installation : contenu différent de l'archive (empreinte)")

    import app.utils.import_copropriete as import_copropriete

    monkeypatch.setattr(import_copropriete, "verifier_archive", refus)
    sauvegarde.run_sauvegarde_plateforme()
    assert not list(sauvegarde.dossier().glob("plateforme_backup_*.tar.gz"))
    assert len(alertes) == 1 and "empreinte" in alertes[0][0]


def test_eteinte_hors_de_la_reference(registre, alertes, monkeypatch):
    monkeypatch.setattr(base, "est_reference", lambda: False)
    sauvegarde.run_sauvegarde_plateforme()
    assert not sauvegarde.dossier().exists() and not alertes


def test_la_restauration_rend_le_registre(registre):
    """L'archive se réimporte dans une base NEUVE, marquée à la tête de sa chaîne (#1972)."""
    archive = sauvegarde.sauvegarder()
    cible = moteur_de_test(schema=False)
    bilan = sauvegarde.restaurer(archive, cible)
    assert bilan.lignes >= 1
    with Session(cible) as session:
        assert session.get(Installation, 1).identifiant == IDENTIFIANT_REFERENCE
        tete = session.exec(text("select version_num from alembic_version")).one()
        assert tete[0], "la base restaurée n'est pas marquée par sa chaîne de migrations"


def test_une_base_qui_n_est_pas_neuve_est_refusee_avant_tout_geste(registre):
    """La base du registre DÉJÀ démarrée porte la référence : y importer doublerait les
    lignes, et l'erreur d'intégrité ne dirait pas pourquoi. Refus, base intacte."""
    archive = sauvegarde.sauvegarder()
    with pytest.raises(ImportRefuse, match="pas neuve"):
        sauvegarde.restaurer(archive, registre)
    with Session(registre) as session:
        assert len(session.exec(select(Installation)).all()) == 1


def test_ni_l_epreuve_ni_la_restauration_ne_different_les_cles(registre, alertes):
    """Le rôle du registre ne peut pas différer les clés (refus simulé par `registre_allume`) :
    la sauvegarde nocturne ET la restauration passent sans. C'est l'épreuve qui
    échouait en production (17/10/2026) — `run_sauvegarde_plateforme` alertait."""
    sauvegarde.run_sauvegarde_plateforme()
    assert not alertes
    (archive,) = sauvegarde.dossier().glob("plateforme_backup_*.tar.gz")
    bilan = sauvegarde.restaurer(archive, moteur_de_test(schema=False))
    assert bilan.lignes >= 1


def test_une_archive_de_la_residence_n_est_pas_un_registre(registre, tmp_path, monkeypatch):
    """Les deux archives voisinent dans la copie hors site : l'erreur de fichier se refuse."""
    from app.utils import export_copropriete

    archive_residence = tmp_path / "residence.tar.gz"
    export_copropriete.exporter(moteur_de_test(), archive_residence)
    with pytest.raises(ImportRefuse, match="tables absentes"):
        sauvegarde.restaurer(archive_residence, moteur_de_test(schema=False))


def _commande(archive: Path, url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "app.registre.sauvegarde", "restaurer", str(archive), url],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )


def test_la_commande_restaure_une_base_neuve_puis_refuse_de_recommencer(registre):
    """`python -m app.registre.sauvegarde restaurer` — le geste de la procédure (#1972)."""
    archive = sauvegarde.sauvegarder()
    base_neuve, retirer = adresse_de_test()  # une base JETABLE du test
    try:
        sortie = _commande(archive, base_neuve)
        assert sortie.returncode == 0, sortie.stderr[-600:]
        assert "Importé et vérifié" in sortie.stdout
        relance = _commande(archive, base_neuve)
        assert relance.returncode != 0 and "RESTAURATION REFUSÉE" in relance.stderr
    finally:
        retirer()
