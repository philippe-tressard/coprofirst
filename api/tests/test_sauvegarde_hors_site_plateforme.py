"""La copie hors site du REGISTRE des installations (#1896, spec §4.9 et §4.11).

Depuis #1892, la référence range chaque nuit une archive vérifiée de la base
`plateforme` ; `export-hors-site.sh` ne copiait que celles de la résidence, et le
registre n'avait aucune copie hors des deux RPi. Le script la tire désormais et
rend compte dans le rapport de l'export ; le contrôle de la PLATEFORME
(`registre/sauvegarde.probleme_copie_hors_site`) la juge et prévient l'opérateur.

Ce fichier tient aussi les couplages que rien d'autre ne relie : les noms de la
série côté shell et côté Python, les clés du rapport, et la relecture du poste
exécutée sur une archive du registre réellement produite.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlmodel import Session

from app import contexte
from app.config import get_settings
from app.models.core import HistoriqueMaintenance, TachePlanifiee
from app.registre import migrer, sauvegarde
from app.utils import backup, health_monitor, horloge, sante_plateforme
from tests.aides_registre import registre_allume

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "poste" / "export-hors-site.sh"
LIB = RACINE / "scripts" / "lib" / "lib-export-hors-site.sh"
COPIE = RACINE / "scripts" / "lib" / "lib-export-hors-site-copie.sh"


def _rapport(session, *, archive_plateforme="", integrite_plateforme="ok", archive_quand=None):
    """Un rapport d'export comme le script le poste ; la résidence y est saine."""
    archive_quand = archive_quand or horloge.maintenant()
    details = {
        "archive": backup.nom_archive(horloge.maintenant()),
        "integrite": "ok",
        "archive_plateforme": archive_plateforme
        or backup.nom_archive(archive_quand, sauvegarde.PREFIXE),
        "integrite_plateforme": integrite_plateforme,
    }
    session.add(
        HistoriqueMaintenance(
            tache=TachePlanifiee.export_hors_site.value,
            noeud="rpi1",
            statut="succes",
            cree_le=horloge.maintenant(),
            details=json.dumps(details),
        )
    )
    session.commit()


@pytest.fixture
def base_copro(session, monkeypatch):
    """La base de la copropriété servie, celle où le rapport de l'export est rangé."""
    moteur = session.get_bind()
    monkeypatch.setattr(contexte, "nouvelle_session", lambda: Session(moteur))
    return session


@pytest.fixture
def registre(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path / "sauvegardes"))
    with registre_allume(monkeypatch) as moteur:
        with Session(moteur) as s:
            migrer.inscrire_reference(s)
        yield moteur


# ── Le contrôle de la plateforme ─────────────────────────────────────────────


def test_registre_eteint_rien_a_juger(base_copro):
    """Cas zéro : hors de la référence, aucune copie n'est attendue — et aucun rapport n'est lu."""
    assert sauvegarde.probleme_copie_hors_site() == []


def test_aucune_copie_rapportee_se_dit(registre, base_copro):
    (probleme,) = sauvegarde.probleme_copie_hors_site()
    assert "Aucune copie hors site" in probleme


def test_un_export_sans_le_registre_compte_comme_aucune_copie(registre, base_copro):
    """Un poste resté sur l'ancien script : le rapport de la résidence n'en dit rien."""
    base_copro.add(
        HistoriqueMaintenance(
            tache=TachePlanifiee.export_hors_site.value,
            noeud="rpi1",
            statut="succes",
            cree_le=horloge.maintenant(),
            details=json.dumps({"archive": backup.nom_archive(horloge.maintenant())}),
        )
    )
    base_copro.commit()
    assert len(sauvegarde.probleme_copie_hors_site()) == 1


def test_une_copie_saine_et_fraiche_ne_dit_rien(registre, base_copro):
    _rapport(base_copro, archive_quand=horloge.maintenant() - timedelta(hours=5))
    assert sauvegarde.probleme_copie_hors_site() == []


def test_une_copie_abimee_se_dit(registre, base_copro):
    _rapport(base_copro, integrite_plateforme="écarts : installation 0/1")
    (probleme,) = sauvegarde.probleme_copie_hors_site()
    assert "n'a pas passé sa vérification" in probleme and "0/1" in probleme


def test_une_copie_perimee_se_dit(registre, base_copro):
    seuil_h = health_monitor.seuil_copie_hors_site_h()
    _rapport(base_copro, archive_quand=horloge.maintenant() - timedelta(hours=seuil_h + 48))
    (probleme,) = sauvegarde.probleme_copie_hors_site()
    assert "date de" in probleme and f"seuil : {seuil_h // 24} jours" in probleme


def test_l_operateur_est_prevenu_par_la_tache_de_la_plateforme(registre, base_copro, monkeypatch):
    """Le branchement : avec UNE copropriété, la tâche ne juge pas le disque, mais la copie."""
    recues: list[list[str]] = []
    monkeypatch.setattr(sante_plateforme, "alerter", recues.append)
    monkeypatch.setattr(sante_plateforme, "probleme_disque", lambda: ["disque"])
    sante_plateforme.run_controle_plateforme()
    assert len(recues) == 1 and recues[0][0].startswith("Aucune copie hors site")


def test_la_copropriete_ne_voit_pas_le_registre(base_copro):
    """§4.11, règle 7 : une copie du registre abîmée ne s'écrit pas dans le courriel de la résidence."""
    _rapport(base_copro, integrite_plateforme="transfert interrompu")
    assert health_monitor._check_export_hors_site(base_copro) == []


# ── Les couplages shell ⇄ Python ─────────────────────────────────────────────


def test_la_serie_porte_le_meme_nom_des_deux_cotes(tmp_path, monkeypatch):
    lib = LIB.read_text(encoding="utf-8")
    assert f'PREFIXE_PLATEFORME="{sauvegarde.PREFIXE}"' in lib
    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path))
    assert f'DOSSIER_PLATEFORME="{sauvegarde.dossier().name}"' in lib
    assert f'PREFIXE_RESIDENCE="{backup.PREFIXE_ARCHIVE}"' in lib


def test_le_script_remonte_les_cles_que_le_controle_relit():
    """Renommées d'un côté seulement, le contrôle dirait « aucune copie » chaque jour."""
    script = SCRIPT.read_text(encoding="utf-8")
    controle = Path(sauvegarde.__file__).read_text(encoding="utf-8")
    for cle in ("archive_plateforme", "integrite_plateforme"):
        assert f'"{cle}":' in script, f"le script ne remonte plus {cle}"
        assert f'"{cle}"' in controle, f"le contrôle ne lit plus {cle}"


def test_le_poste_relit_l_archive_du_registre(registre):
    """Le Python de `relire_export`, sur une archive du registre réellement produite."""
    archive = sauvegarde.sauvegarder()
    code = re.search(r"<<'PYTHON'\n(.*?)\nPYTHON\n", COPIE.read_text(encoding="utf-8"), re.S)
    assert code, "le code de relecture n'est plus dans lib-export-hors-site-copie.sh"
    sortie = subprocess.run(
        [sys.executable, "-", str(archive)], input=code.group(1), capture_output=True, text=True
    )
    assert sortie.returncode == 0, sortie.stderr
    lignes = [li.split() for li in io.StringIO(sortie.stdout) if li.strip()]
    assert ["installation", "1", "1"] in lignes, lignes
    assert all(lues == annoncees for _t, lues, annoncees in lignes)


def test_le_nom_produit_passe_la_liste_blanche_du_poste():
    nom = backup.nom_archive(datetime(2026, 10, 14, 3, 30), sauvegarde.PREFIXE)
    assert re.fullmatch(rf"{sauvegarde.PREFIXE}[A-Za-z0-9._-]+\.tar\.gz", nom), nom
