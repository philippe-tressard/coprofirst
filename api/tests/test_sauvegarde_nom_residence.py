"""Sauvegardes : le nom d'une archive dit à quelle résidence elle appartient (#2667).

POURQUOI CE TEST — sur une installation commune, les archives sont séparées par
DOSSIER (`contexte.dossier_des_sauvegardes`, #2053), pas par nom : une archive
sortie de son dossier (téléchargée, copiée hors site) ne disait plus de quelle
copropriété elle venait. Le nom porte désormais la résidence servie :
`sauvegarde_copropriete_<qui>_AAAAMMJJ_HHMMSS_paris.tar.gz`.

Ce que ces tests figent :
- `<qui>` vient de la BASE (`site_nom`, réduit en `[a-z0-9-]`) ou du CONTEXTE (son
  identifiant, `principale` sur une installation propre) — jamais du code : la garde
  de #2653 reste vraie ;
- trois formes se lisent pendant la rétention : l'historique, le neuf sans nom, le
  neuf avec ;
- le nom n'est ni un critère de tri ni de rotation : une résidence renommée voit ses
  anciennes archives tourner sous leur ancien nom ; et la rotation d'une copropriété
  ne touche jamais le dossier d'une autre.
"""

import os
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from app import contexte
from app.config import get_settings
from app.models.core import ConfigSauvegarde
from app.utils import backup, health_monitor, horloge
from app.utils.backup import (
    LONGUEUR_QUI,
    PREFIXE_ARCHIVE,
    PREFIXE_HISTORIQUE,
    archives,
    horodatage_archive,
    nom_archive,
    qui_nomme_l_archive,
)
from app.utils.config_site import ecrire_cle

INSTANT = datetime(2026, 11, 10, 3, 0)


def nommer(session, site_nom: str | None) -> str:
    if site_nom is not None:
        ecrire_cle(session, "site_nom", site_nom)
        session.commit()
    return qui_nomme_l_archive(session)


def copropriete(identifiant: str):
    """Une copropriété d'installation commune, posée dans le contexte."""
    return contexte.dans(replace(contexte.de_la_configuration(), identifiant=identifiant))


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path))
    return tmp_path


def poser(dossier, *noms: str) -> None:
    for nom in noms:
        (dossier / nom).write_bytes(b"contenu")


# ── D'où vient le nom ────────────────────────────────────────────────────────


def test_le_nom_vient_de_site_nom_reduit(session):
    assert nommer(session, "Résidence « Les Tilleuls » — Bât. A") == "residence-les-tilleuls-bat-a"


def test_sans_site_nom_le_nom_vient_du_contexte(session):
    """Installation propre : l'identifiant de l'unique copropriété, `principale`."""
    assert nommer(session, None) == contexte.IDENTIFIANT_UNIQUE
    assert nommer(session, "") == contexte.IDENTIFIANT_UNIQUE
    assert nommer(session, " — ! ") == contexte.IDENTIFIANT_UNIQUE


def test_sans_site_nom_une_copropriete_commune_donne_son_identifiant(session):
    with copropriete("tilleuls"):
        assert nommer(session, "") == "tilleuls"


def test_deux_coproprietes_communes_ont_deux_noms(session):
    with copropriete("tilleuls"):
        un = nom_archive(INSTANT, qui=nommer(session, ""))
    with copropriete("amandiers"):
        deux = nom_archive(INSTANT, qui=nommer(session, ""))
    assert un != deux
    assert horodatage_archive(un) == horodatage_archive(deux) == INSTANT


def test_un_long_nom_est_borne(session):
    qui = nommer(session, "Copropriété " + "très " * 20 + "longue")
    assert 0 < len(qui) <= LONGUEUR_QUI and not qui.endswith("-") and "_" not in qui


def test_le_nom_n_est_jamais_ecrit_en_dur(session):
    """🔒 Le nom de la résidence change avec la base : rien ne le fige dans le code."""
    assert nommer(session, "Les Amandiers") == "les-amandiers"
    assert nommer(session, "Le Parc") == "le-parc"
    assert "hostachy" not in PREFIXE_ARCHIVE


def test_un_qui_hors_forme_est_refuse_a_l_ecriture():
    for qui in ("a_b", "A", "-x", "a/b", "x" * (LONGUEUR_QUI + 1)):
        with pytest.raises(ValueError):
            nom_archive(INSTANT, qui=qui)


# ── Les trois formes se lisent ───────────────────────────────────────────────


def test_les_trois_formes_se_datent():
    avec = nom_archive(INSTANT, qui="les-tilleuls")
    assert avec == f"{PREFIXE_ARCHIVE}les-tilleuls_20261110_040000_paris.tar.gz"
    sans = nom_archive(INSTANT)
    ancien = sans.replace(PREFIXE_ARCHIVE, PREFIXE_HISTORIQUE, 1)
    assert horodatage_archive(avec) == horodatage_archive(sans) == INSTANT
    assert horodatage_archive(ancien) == INSTANT


def test_un_nom_illisible_au_milieu_rend_none():
    for nom in (
        f"{PREFIXE_ARCHIVE}Les_Tilleuls_20261110_040000_paris.tar.gz",
        f"{PREFIXE_ARCHIVE}A_20261110_040000_paris.tar.gz",
        f"{PREFIXE_ARCHIVE}x_y_20261110_040000_paris.tar.gz",
    ):
        assert horodatage_archive(nom) is None, nom


# ── Ni tri, ni rotation par le nom ───────────────────────────────────────────


def test_une_residence_renommee_tourne_avec_ses_anciennes_archives(dossier, session):
    """Les anciennes portent l'ancien nom — qui passe APRÈS le nouveau dans l'alphabet."""
    session.add(ConfigSauvegarde(nb_versions_conservees=2))
    session.commit()
    serie = [
        nom_archive(INSTANT, qui="les-tilleuls"),
        nom_archive(INSTANT + timedelta(days=1), qui="les-tilleuls"),
        nom_archive(INSTANT + timedelta(days=2), qui="les-amandiers"),
        nom_archive(INSTANT + timedelta(days=3), qui="les-amandiers"),
    ]
    poser(dossier, *serie)
    assert [os.path.basename(c) for c in archives(dossier)] == serie

    backup._rotate_backups(session)

    assert sorted(p.name for p in dossier.iterdir()) == sorted(serie[2:])


def test_la_rotation_ne_touche_pas_le_dossier_d_une_autre(tmp_path, monkeypatch, session):
    session.add(ConfigSauvegarde(nb_versions_conservees=1))
    session.commit()
    a, b = tmp_path / "tilleuls", tmp_path / "amandiers"
    a.mkdir(), b.mkdir()
    chez_b = [nom_archive(INSTANT + timedelta(days=j), qui="amandiers") for j in range(3)]
    poser(b, *chez_b)
    poser(a, *(nom_archive(INSTANT + timedelta(days=j), qui="tilleuls") for j in range(3)))
    monkeypatch.setattr(contexte, "dossier_des_sauvegardes", lambda: a)

    backup._rotate_backups(session)

    assert len(list(a.iterdir())) == 1
    assert sorted(p.name for p in b.iterdir()) == sorted(chez_b)


def test_la_sante_lit_une_archive_nommee(dossier):
    poser(dossier, nom_archive(horloge.maintenant() - timedelta(hours=3), qui="les-tilleuls"))
    assert health_monitor._check_archive_locale() == []
