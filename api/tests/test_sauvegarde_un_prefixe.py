"""Sauvegardes : un préfixe qui ne nomme pas la résidence, et lui seul (#2653, #2659).

POURQUOI CE TEST — les archives s'appelaient `hostachy_backup_…` : une réplique
d'une autre copropriété nommait ses sauvegardes du nom de la nôtre. Le préfixe
écrit est neutre (`backup.PREFIXE_ARCHIVE`). L'ancien est resté LU pendant la
rotation des archives qui le portaient, puis s'est retiré (#2659) : constaté le
25/11/2026, plus aucune archive ne le portait, ni sur les deux nœuds ni dans la
copie hors site du poste.

🔒 Ce qui suit refuse son retour : ni la date, ni la liste, ni la santé, ni la copie
hors site ne lisent plus un nom `hostachy_backup_…`. Les tests de la transition
(un dossier où les deux préfixes se mêlent) sont partis avec elle.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.config import get_settings
from app.utils import backup, health_monitor, horloge
from app.utils.backup import PREFIXE_ARCHIVE, archives, horodatage_archive, nom_archive

RACINE = Path(__file__).resolve().parents[2]
LIB = RACINE / "scripts" / "lib" / "lib-export-hors-site.sh"
#: L'ancien préfixe, écrit ici seulement pour vérifier qu'il n'est plus lu.
ANCIEN = "hostachy_backup_"


def ancien(instant: datetime) -> str:
    """Le nom qu'écrivait la version d'avant #2653 pour `instant`."""
    return nom_archive(instant).replace(PREFIXE_ARCHIVE, ANCIEN, 1)


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "backup_dir", str(tmp_path))
    return tmp_path


def poser(dossier: Path, *noms: str) -> None:
    for nom in noms:
        (dossier / nom).write_bytes(b"contenu")


def test_le_prefixe_ecrit_ne_nomme_pas_la_residence():
    """🔒 Ni le nom historique du projet, ni celui que la résidence s'est donné."""
    from app.utils.liens import nom_site

    assert "hostachy" not in PREFIXE_ARCHIVE.lower()
    assert "hostachy" not in nom_archive(horloge.maintenant()).lower()
    assert nom_site().lower() not in PREFIXE_ARCHIVE.lower()


def test_une_archive_neuve_porte_le_prefixe_ecrit():
    assert nom_archive(datetime(2026, 11, 10, 3, 0)) == (
        f"{PREFIXE_ARCHIVE}20261110_040000_paris.tar.gz"
    )


def test_l_ancien_prefixe_ne_se_date_plus():
    instant = datetime(2026, 11, 10, 3, 0)
    assert horodatage_archive(nom_archive(instant)) == instant
    assert horodatage_archive(ancien(instant)) is None
    assert horodatage_archive(f"x_{nom_archive(instant)}") is None


def test_le_module_ne_porte_plus_l_ancien_prefixe():
    """Ni constante ni tuple de lecture : un retour se verrait ici avant la rotation."""
    assert not hasattr(backup, "PREFIXE_HISTORIQUE")
    assert not hasattr(backup, "PREFIXES_LUS")


def test_la_liste_ignore_l_ancien_prefixe(dossier):
    neuve = nom_archive(horloge.maintenant())
    poser(dossier, ancien(horloge.maintenant() - timedelta(days=1)), neuve)
    assert [os.path.basename(c) for c in archives(dossier)] == [neuve]


def test_un_nom_illisible_va_en_fin(dossier):
    """Il reste jugé « non conforme » par la santé — INCONNU, jamais OK."""
    poser(dossier, f"{PREFIXE_ARCHIVE}corrompu.tar.gz", nom_archive(horloge.maintenant()))
    assert os.path.basename(archives(dossier)[-1]) == f"{PREFIXE_ARCHIVE}corrompu.tar.gz"


def test_la_sante_ne_prend_pas_une_ancienne_archive_pour_une_sauvegarde(dossier):
    """Un dossier qui n'aurait plus que l'ancien préfixe n'a AUCUNE sauvegarde lue :
    la santé le dit, au lieu de juger fraîche une archive qu'elle ne sait plus lire."""
    poser(dossier, ancien(horloge.maintenant() - timedelta(hours=3)))
    assert health_monitor._check_archive_locale() != []


def test_la_copie_hors_site_ne_lit_que_le_prefixe_ecrit():
    """Même valeur des deux côtés, et rien d'autre côté shell."""
    lib = LIB.read_text(encoding="utf-8")
    assert f'PREFIXE_RESIDENCE="{PREFIXE_ARCHIVE}"' in lib
    for chemin in (
        LIB,
        RACINE / "scripts" / "lib" / "lib-export-hors-site-copie.sh",
        RACINE / "scripts" / "poste" / "export-hors-site.sh",
    ):
        texte = chemin.read_text(encoding="utf-8")
        assert "PREFIXE_RESIDENCE_HISTORIQUE" not in texte, chemin.name
        assert ANCIEN not in texte, chemin.name
