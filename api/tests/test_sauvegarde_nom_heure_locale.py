"""Le nom d'une archive de sauvegarde dit l'heure de PARIS, et le dit (#1611).

## Le défaut (audit du 02/10/2026)

`hostachy_backup_20261002_020000.tar.gz` avait été prise à **04:00** — l'heure que
le planificateur règle, à Paris. Le nom portait l'horloge UTC (`horloge.maintenant`)
sans le dire : un opérateur qui restaure « celle de 02:00 » ne prenait pas ce qu'il
croyait, et une sauvegarde prise entre 00:00 et 02:00 se nommait du JOUR D'AVANT.

## Ce que ce test fige

- le nom est à l'heure de Paris (été comme hiver) et **écrit son fuseau** : le suffixe
  `_paris` distingue une archive nouvelle d'une ancienne (UTC, sans suffixe) — sans
  lui, rien ne dirait laquelle des deux on lit pendant la rétention ;
- `horodatage_archive` rend toujours de l'**UTC naïf** (ce que comparent la santé et
  l'export) pour l'un comme pour l'autre format ;
- le tri alphabétique reste le tri chronologique, sur lequel reposent la rotation
  (`_rotate_backups`) et l'export hors site (`archives_a_supprimer`,
  `archives_a_rattraper`) — anciennes et nouvelles archives mêlées ;
- une archive prise à 00:30 à Paris porte la date de Paris, pas celle de la veille.
"""

from datetime import datetime

from app.utils import horloge
from app.utils.backup import PREFIXE_ARCHIVE, horodatage_archive, nom_archive


def test_une_archive_d_ete_porte_l_heure_de_paris():
    #  02:00 UTC le 5 octobre = 04:00 à Paris (CEST, UTC+2).
    assert nom_archive(datetime(2026, 10, 5, 2, 0, 0)) == (
        f"{PREFIXE_ARCHIVE}20261005_040000_paris.tar.gz"
    )


def test_une_archive_d_hiver_porte_l_heure_de_paris():
    #  03:00 UTC le 5 décembre = 04:00 à Paris (CET, UTC+1).
    assert nom_archive(datetime(2026, 12, 5, 3, 0, 0)) == (
        f"{PREFIXE_ARCHIVE}20261205_040000_paris.tar.gz"
    )


def test_une_archive_de_minuit_porte_le_jour_de_paris():
    """Le défaut d'origine : 22:30 UTC la veille, c'est 00:30 le lendemain à Paris."""
    assert nom_archive(datetime(2026, 10, 4, 22, 30, 0)) == (
        f"{PREFIXE_ARCHIVE}20261005_003000_paris.tar.gz"
    )


def test_l_horodatage_se_relit_en_utc_naif():
    instant = datetime(2026, 10, 5, 2, 0, 0)
    relu = horodatage_archive(nom_archive(instant))
    assert relu == instant and relu.tzinfo is None


def test_l_aller_retour_tient_a_la_bascule_d_heure():
    #  Autour du passage à l'heure d'hiver (25/10/2026, 03:00 → 02:00) : avant et après.
    for instant in (datetime(2026, 10, 24, 22, 0, 0), datetime(2026, 10, 25, 4, 0, 0)):
        assert horodatage_archive(nom_archive(instant)) == instant


def test_une_ancienne_archive_se_lit_toujours_en_utc():
    """Sans suffixe : le format d'avant #1611, dont l'heure est UTC."""
    assert horodatage_archive(f"{PREFIXE_ARCHIVE}20261002_020000.tar.gz") == datetime(
        2026, 10, 2, 2, 0, 0
    )


def test_un_suffixe_de_fuseau_inconnu_est_refuse():
    for nom in (
        f"{PREFIXE_ARCHIVE}20261005_040000_londres.tar.gz",
        f"{PREFIXE_ARCHIVE}20261005_040000_.tar.gz",
        f"{PREFIXE_ARCHIVE}20261005_paris.tar.gz",
    ):
        assert horodatage_archive(nom) is None, nom


def test_le_tri_alphabetique_reste_chronologique_anciennes_et_nouvelles_melees():
    """La rotation et l'export trient les NOMS : l'ordre des noms est l'ordre du temps."""
    instants = [
        datetime(2026, 10, 2, 2, 0, 0),  # ancienne (UTC) — nommée sans suffixe
        datetime(2026, 10, 4, 2, 0, 0),  # ancienne (UTC)
        datetime(2026, 10, 5, 2, 0, 0),  # nouvelle (Paris, 04:00)
        datetime(2026, 10, 6, 2, 0, 0),  # nouvelle
    ]
    noms = [
        f"{PREFIXE_ARCHIVE}{i:%Y%m%d_%H%M%S}.tar.gz"
        if i < datetime(2026, 10, 5)
        else nom_archive(i)
        for i in instants
    ]
    assert sorted(noms) == noms
    assert [horodatage_archive(n) for n in noms] == instants


def test_le_nom_est_accepte_par_les_lecteurs_shell():
    """`lib-export-hors-site.sh` valide le nom par un motif : le suffixe y passe."""
    import re

    nom = nom_archive(horloge.maintenant())
    assert re.fullmatch(r"hostachy_backup_[A-Za-z0-9._-]+\.tar\.gz", nom), nom


def test_run_backup_ecrit_le_nom_a_l_heure_de_paris(tmp_path, monkeypatch):
    """Bout en bout : l'archive posée sur le disque porte le nom à l'heure de Paris."""
    from sqlmodel import SQLModel

    from app.config import get_settings
    from app.database import engine
    from app.utils import backup

    SQLModel.metadata.create_all(engine)
    #  Le dossier se lit par le contexte (`contexte.dossier_des_sauvegardes`, #2053).
    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path))
    monkeypatch.setattr(horloge, "maintenant", lambda: datetime(2026, 10, 5, 2, 0, 0))

    backup.run_backup()

    archives = sorted(p.name for p in tmp_path.glob(backup.MOTIF_ARCHIVE))
    assert archives == [f"{PREFIXE_ARCHIVE}20261005_040000_paris.tar.gz"], archives
