"""Sauvegardes : le contrôle regarde-t-il le FICHIER, et la copie hors site ?

POURQUOI CE TEST — constat du 04/08/2026 sur la production :

`_check_backups()` déclarait les sauvegardes saines en lisant `historique_sauvegarde`.
Or cette table vit dans `app.db`, que `bascule.sh` réplique sur le peer — alors que
le volume Docker `backups`, lui, n'est jamais répliqué. La ligne « réussie » ne
prouvait donc pas qu'une archive existe : elle prouvait qu'une ligne avait été
écrite. Volume vidé, disque plein, archive tronquée : le contrôle restait vert.
C'est « vérifier l'artefact déclaré plutôt que le fait » de
standards/04-fiabilite-des-controles.md.

Deuxième trou, plus grave : 100 % des archives vivaient sur deux RPi posés au même
endroit. `export-hors-site.sh` produit désormais une copie hors des deux nœuds, et
ces tests verrouillent ce qui peut redevenir silencieux :

  • une absence d'archive locale doit se voir ;
  • ne PAS savoir dater une archive vaut anomalie, jamais OK ;
  • un export qui tourne fidèlement mais recopie chaque fois la même archive
    périmée est un FAUX VERT — c'est le cas que `test_export_fidele_mais_archive_perimee`
    interdit de réintroduire ;
  • le script shell et le contrôle Python se parlent par des clés JSON qu'aucun
    compilateur ne relie : un renommage silencieux les désaccorderait
    (même motif que test_email_contexte_appel.py).
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.core import HistoriqueMaintenance, TachePlanifiee
from app.utils import health_monitor, horloge
from app.utils.backup import PREFIXE_ARCHIVE, horodatage_archive

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "poste" / "export-hors-site.sh"
COPIE = RACINE / "scripts" / "lib" / "lib-export-hors-site-copie.sh"


def nom_archive(quand: datetime) -> str:
    return f"{PREFIXE_ARCHIVE}{quand.strftime('%Y%m%d_%H%M%S')}.tar.gz"


@pytest.fixture
def repertoire_sauvegardes(tmp_path, monkeypatch):
    """Redirige `settings.backup_dir` vers un répertoire jetable."""
    monkeypatch.setattr(
        health_monitor,
        "get_settings",
        lambda: SimpleNamespace(backup_dir=str(tmp_path)),
    )
    return tmp_path


# ── Horodatage lu dans le nom de l'archive ───────────────────────────────────


def test_horodatage_lu_dans_le_nom():
    """La convention de nommage est porteuse de sens : elle doit se relire."""
    quand = datetime(2026, 8, 4, 3, 0, 0)
    assert horodatage_archive(nom_archive(quand)) == quand


def test_horodatage_illisible_rend_none_sans_lever():
    """Un nom non conforme ne doit pas faire ÉCHOUER un contrôle de santé — il
    doit le faire répondre « je ne sais pas », que l'appelant traite en anomalie."""
    for nom in (
        "",
        "autre.tar.gz",
        "hostachy_backup_pasunedate.tar.gz",
        "hostachy_backup_20260804_030000.zip",
        None,
    ):
        assert horodatage_archive(nom) is None


# ── Le contrôle regarde le fichier, pas la ligne d'historique ────────────────


def test_archive_fraiche_ne_signale_rien(repertoire_sauvegardes):
    fichier = repertoire_sauvegardes / nom_archive(horloge.maintenant() - timedelta(hours=3))
    fichier.write_bytes(b"contenu")
    assert health_monitor._check_archive_locale() == []


def test_absence_de_fichier_est_signalee(repertoire_sauvegardes):
    """Le cas que l'ancien contrôle ne pouvait pas voir : l'historique annonce
    une sauvegarde réussie, et il n'y a aucun fichier sur ce nœud."""
    anomalies = health_monitor._check_archive_locale()
    assert len(anomalies) == 1
    assert "Aucun fichier de sauvegarde" in anomalies[0]


def test_archive_vide_est_signalee(repertoire_sauvegardes):
    (repertoire_sauvegardes / nom_archive(horloge.maintenant())).write_bytes(b"")
    anomalies = health_monitor._check_archive_locale()
    assert len(anomalies) == 1
    assert "VIDE" in anomalies[0]


def test_archive_perimee_est_signalee(repertoire_sauvegardes):
    vieille = horloge.maintenant() - timedelta(hours=50)
    (repertoire_sauvegardes / nom_archive(vieille)).write_bytes(b"contenu")
    anomalies = health_monitor._check_archive_locale()
    assert len(anomalies) == 1
    assert "50h" in anomalies[0]


def test_nom_non_datable_vaut_anomalie_pas_ok(repertoire_sauvegardes):
    """Ne pas savoir dater une archive n'est PAS un feu vert (standards/04 §1)."""
    (repertoire_sauvegardes / f"{PREFIXE_ARCHIVE}corrompu.tar.gz").write_bytes(b"x")
    anomalies = health_monitor._check_archive_locale()
    assert len(anomalies) == 1
    assert "non conforme" in anomalies[0]


# ── Copie hors site ──────────────────────────────────────────────────────────


def enregistrer_export(
    session, *, quand=None, archive_quand=None, statut="succes", integrite="ok", erreur=None
):
    quand = quand or horloge.maintenant()
    archive_quand = archive_quand or horloge.maintenant()
    ligne = HistoriqueMaintenance(
        tache=TachePlanifiee.export_hors_site.value,
        noeud="rpi1",
        statut=statut,
        erreur=erreur,
        cree_le=quand,
        details=json.dumps(
            {
                "archive": nom_archive(archive_quand),
                "taille_octets": 1024,
                "integrite": integrite,
            }
        ),
    )
    session.add(ligne)
    session.commit()
    return ligne


def test_aucun_export_jamais_enregistre(session):
    anomalies = health_monitor._check_export_hors_site(session)
    assert len(anomalies) == 1
    assert "Aucune copie hors site" in anomalies[0]


def test_export_recent_et_archive_fraiche_ne_signale_rien(session):
    enregistrer_export(session)
    assert health_monitor._check_export_hors_site(session) == []


def test_export_ancien_est_signale(session):
    enregistrer_export(
        session,
        quand=horloge.maintenant() - timedelta(days=20),
        archive_quand=horloge.maintenant() - timedelta(days=20),
    )
    anomalies = health_monitor._check_export_hors_site(session)
    assert any("Aucun export hors site depuis" in a for a in anomalies)


def test_export_fidele_mais_archive_perimee(session):
    """LE faux vert que ce lot existe pour empêcher.

    L'export tourne tous les jours, réussit, et recopie fidèlement… la même
    archive vieille de trois semaines (sauvegarde bloquée en amont). Vérifier
    seulement que « l'export a tourné » déclarerait la situation saine.
    """
    enregistrer_export(
        session, quand=horloge.maintenant(), archive_quand=horloge.maintenant() - timedelta(days=21)
    )
    anomalies = health_monitor._check_export_hors_site(session)
    assert any("recopie une archive périmée" in a for a in anomalies)


def test_export_en_echec_est_signale(session):
    enregistrer_export(session, statut="erreur", erreur="Empreinte SHA-256 différente")
    anomalies = health_monitor._check_export_hors_site(session)
    assert any("ÉCHOUÉ" in a for a in anomalies)


def test_integrite_non_ok_est_signalee(session):
    enregistrer_export(session, integrite="malformed database")
    anomalies = health_monitor._check_export_hors_site(session)
    assert any("intégrité" in a for a in anomalies)


def test_integrite_non_verifiee_est_signalee(session):
    """Le script rend « inconnue » quand ni sqlite3 ni python n'ont pu vérifier.
    Ce n'est pas « ok » : ça doit remonter."""
    enregistrer_export(session, integrite="inconnue")
    anomalies = health_monitor._check_export_hors_site(session)
    assert any("intégrité" in a for a in anomalies)


# ── Couplage implicite script shell ⇄ contrôle Python ────────────────────────


def test_le_script_existe_et_expose_un_selftest():
    contenu = SCRIPT.read_text(encoding="utf-8")
    assert "--selftest" in contenu, "le job CI test-scripts exige un self-test"


def test_le_script_declare_la_meme_tache_que_l_enum():
    """Le script poste `tache=export_hors_site` ; l'API interroge l'énumération.
    Rien ne relie ces deux chaînes — sauf ce test."""
    contenu = SCRIPT.read_text(encoding="utf-8")
    nom = TachePlanifiee.export_hors_site.value
    assert f"rapport_payload {nom} " in contenu or f'"tache":"{nom}"' in contenu


def test_le_script_remonte_les_cles_que_le_controle_relit():
    """`archive` et `integrite` sont lues par `_check_export_hors_site`.

    Les renommer côté script ne casserait RIEN de visible : le contrôle
    cesserait simplement de vérifier la fraîcheur, en silence, et resterait
    vert. C'est exactement le motif du bug `'destinataire' is undefined`
    (cf. test_email_contexte_appel.py) transposé à l'infra.
    """
    contenu = SCRIPT.read_text(encoding="utf-8")
    for cle in ("archive", "integrite"):
        assert f'"{cle}":' in contenu, f"le script ne remonte plus la clé {cle}"


def test_le_script_ne_touche_jamais_la_base_de_production():
    """Règle d'or anti-corruption : aucun accès à app.db sur un RPi.

    Le script n'a le droit de lire que des archives closes. Une commande
    `sqlite3` visant app.db, ou un `docker exec … PRAGMA`, réintroduirait le
    motif qui a coûté trois incidents (05+17/06 et 17/07/2026).
    """
    #  Les gestes partagés vivent à côté depuis #1896 : la règle les couvre aussi.
    contenu = SCRIPT.read_text(encoding="utf-8") + COPIE.read_text(encoding="utf-8")
    lignes_actives = [
        ligne
        for ligne in contenu.splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    ]
    # On ne cherche pas le MOT « sqlite3 » (il apparaît légitimement dans un
    # message et dans un `command -v`), mais une INVOCATION sur un fichier .db :
    # c'est cela, et cela seul, qui ouvrirait une base.
    ouverture_base = re.compile(r'sqlite3\s+"?\$?[^\s"]*\.db')
    for ligne in lignes_actives:
        assert "app.db-wal" not in ligne
        assert "docker exec" not in ligne, "aucun docker exec sur les nœuds"
        for invocation in ouverture_base.finditer(ligne):
            assert "$TMP" in invocation.group(0), (
                f"sqlite3 ouvre une base hors de la copie locale : {ligne.strip()}"
            )
