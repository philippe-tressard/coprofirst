"""Sauvegardes : un préfixe qui ne nomme pas la résidence, et la transition (#2653).

POURQUOI CE TEST — les archives s'appelaient `hostachy_backup_…` : une réplique
d'une autre copropriété nommait ses sauvegardes du nom de la nôtre. Le préfixe
écrit est neutre (`backup.PREFIXE_ARCHIVE`) ; l'ancien reste LU tant que des
archives le portent (rotation, santé, copie hors site), jusqu'à #2659.

Le piège de la transition : tout trie par NOM, et l'ordre des noms n'est plus
l'ordre du temps quand deux préfixes se mêlent — tout `hostachy_…` passe avant
tout `sauvegarde_…`. Un retour à l'image d'avant écrit de nouveau l'historique,
APRÈS des archives neuves : trier par les lettres effacerait alors la plus récente,
et la santé jugerait une ancienne. Ces tests posent ce dossier mêlé.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.config import get_settings
from app.models.core import ConfigSauvegarde, HistoriqueMaintenance, TachePlanifiee
from app.utils import backup, health_monitor, horloge
from app.utils.backup import (
    PREFIXE_ARCHIVE,
    PREFIXE_HISTORIQUE,
    archives,
    horodatage_archive,
    nom_archive,
)

LIB = Path(__file__).resolve().parents[2] / "scripts" / "lib" / "lib-export-hors-site.sh"


def historique(instant: datetime) -> str:
    """Le nom qu'écrivait la version d'avant pour `instant` — à l'heure de Paris."""
    return nom_archive(instant).replace(PREFIXE_ARCHIVE, PREFIXE_HISTORIQUE, 1)


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path))
    return tmp_path


def poser(dossier: Path, *noms: str) -> None:
    for nom in noms:
        (dossier / nom).write_bytes(b"contenu")


# ── Le préfixe écrit ─────────────────────────────────────────────────────────


def test_le_prefixe_ecrit_ne_nomme_pas_la_residence():
    """🔒 Ni le nom historique du projet, ni celui que la résidence s'est donné."""
    from app.utils.liens import nom_site

    assert "hostachy" not in PREFIXE_ARCHIVE.lower()
    assert "hostachy" not in nom_archive(horloge.maintenant()).lower()
    assert nom_site().lower() not in PREFIXE_ARCHIVE.lower()
    assert PREFIXE_ARCHIVE != PREFIXE_HISTORIQUE


def test_une_archive_neuve_porte_le_prefixe_ecrit():
    assert nom_archive(datetime(2026, 11, 10, 3, 0)) == (
        f"{PREFIXE_ARCHIVE}20261110_040000_paris.tar.gz"
    )


def test_les_deux_prefixes_se_lisent_le_registre_ne_lit_que_le_sien():
    instant = datetime(2026, 11, 10, 3, 0)
    assert horodatage_archive(nom_archive(instant)) == instant
    assert horodatage_archive(historique(instant)) == instant
    #  Un préfixe nommé ne lit que lui : la série du registre ne prend pas la résidence.
    assert horodatage_archive(historique(instant), "plateforme_backup_") is None
    assert horodatage_archive(f"x_{nom_archive(instant)}") is None


def test_les_prefixes_sont_les_memes_cote_shell():
    lib = LIB.read_text(encoding="utf-8")
    assert f'PREFIXE_RESIDENCE="{PREFIXE_ARCHIVE}"' in lib
    assert f'PREFIXE_RESIDENCE_HISTORIQUE="{PREFIXE_HISTORIQUE}"' in lib


# ── L'ordre d'un dossier mêlé ────────────────────────────────────────────────


def test_un_dossier_mele_se_lit_dans_l_ordre_du_temps(dossier):
    """Historique, neuves, puis l'historique d'un retour arrière : l'ordre du temps."""
    t = datetime(2026, 11, 1, 3, 0)
    noms = [
        historique(t),
        nom_archive(t + timedelta(days=1)),
        historique(t + timedelta(days=2)),  # écrit par l'image d'avant, après un retour
        nom_archive(t + timedelta(days=3)),
    ]
    poser(dossier, *reversed(noms))
    (dossier / "export_copropriete_20261105_040000_paris.tar.gz").write_bytes(b"x")
    assert [os.path.basename(c) for c in archives(dossier)] == noms
    #  Le garde-fou se vérifie : l'ordre des LETTRES est faux sur ce dossier.
    assert sorted(noms) != noms


def test_un_nom_illisible_va_en_fin_comme_avant(dossier):
    """Il reste jugé « non conforme » par la santé — INCONNU, jamais OK."""
    poser(dossier, f"{PREFIXE_ARCHIVE}corrompu.tar.gz", nom_archive(horloge.maintenant()))
    assert os.path.basename(archives(dossier)[-1]) == f"{PREFIXE_ARCHIVE}corrompu.tar.gz"


# ── La rotation compte les deux préfixes ─────────────────────────────────────


def test_la_rotation_compte_les_deux_et_garde_les_plus_recentes(dossier, session):
    session.add(ConfigSauvegarde(nb_versions_conservees=2))
    session.commit()
    t = datetime(2026, 11, 1, 3, 0)
    anciennes = [historique(t), historique(t + timedelta(days=1))]
    recentes = [historique(t + timedelta(days=3)), nom_archive(t + timedelta(days=2))]
    poser(dossier, *anciennes, *recentes)

    backup._rotate_backups(session)

    assert sorted(p.name for p in dossier.iterdir()) == sorted(recentes)


def test_la_rotation_n_efface_pas_le_neuf_pour_un_historique_plus_ancien(dossier, session):
    session.add(ConfigSauvegarde(nb_versions_conservees=1))
    session.commit()
    t = datetime(2026, 11, 1, 3, 0)
    poser(dossier, historique(t), nom_archive(t + timedelta(days=1)))

    backup._rotate_backups(session)

    assert [p.name for p in dossier.iterdir()] == [nom_archive(t + timedelta(days=1))]


def test_apres_un_retour_arriere_la_rotation_garde_l_historique_le_plus_recent(dossier, session):
    """L'image d'avant a réécrit l'historique APRÈS une neuve : par les lettres, la
    rotation l'aurait effacé — la plus récente des sauvegardes."""
    session.add(ConfigSauvegarde(nb_versions_conservees=1))
    session.commit()
    t = datetime(2026, 11, 1, 3, 0)
    poser(dossier, nom_archive(t), historique(t + timedelta(days=1)))

    backup._rotate_backups(session)

    assert [p.name for p in dossier.iterdir()] == [historique(t + timedelta(days=1))]


# ── La santé lit la plus récente, quel que soit son préfixe ──────────────────


def test_la_sante_juge_l_archive_neuve_quand_l_historique_est_plus_vieux(dossier):
    poser(
        dossier,
        historique(horloge.maintenant() - timedelta(days=5)),
        nom_archive(horloge.maintenant() - timedelta(hours=3)),
    )
    assert health_monitor._check_archive_locale() == []


def test_la_sante_lit_encore_un_dossier_d_historique_seul(dossier):
    poser(dossier, historique(horloge.maintenant() - timedelta(hours=3)))
    assert health_monitor._check_archive_locale() == []


def test_la_sante_dit_perimee_une_neuve_vieille_meme_avec_un_historique_plus_vieux(dossier):
    poser(
        dossier,
        historique(horloge.maintenant() - timedelta(days=9)),
        nom_archive(horloge.maintenant() - timedelta(hours=50)),
    )
    (anomalie,) = health_monitor._check_archive_locale()
    assert "50h" in anomalie and PREFIXE_ARCHIVE in anomalie


def test_apres_un_retour_arriere_la_sante_juge_l_historique_le_plus_recent(dossier):
    poser(
        dossier,
        nom_archive(horloge.maintenant() - timedelta(hours=50)),
        historique(horloge.maintenant() - timedelta(hours=3)),
    )
    assert health_monitor._check_archive_locale() == []


def test_la_copie_hors_site_d_une_archive_historique_se_date(session):
    """Le lendemain de la MEP, le rapport du poste nomme encore l'historique."""
    session.add(
        HistoriqueMaintenance(
            tache=TachePlanifiee.export_hors_site.value,
            noeud="rpi1",
            statut="succes",
            cree_le=horloge.maintenant(),
            details=json.dumps(
                {
                    "archive": historique(horloge.maintenant() - timedelta(hours=3)),
                    "integrite": "ok",
                }
            ),
        )
    )
    session.commit()
    assert health_monitor._check_export_hors_site(session) == []
