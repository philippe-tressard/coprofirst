"""La 0315 remplace la consigne de `lecture_etat_descriptif` — seulement si elle est intacte (#2251).

La consigne d'origine demande désormais l'« objet » de chaque clé. Une installation qui
l'a ENREGISTRÉE telle quelle reçoit la nouvelle ; une consigne retouchée par
l'administrateur (Admin › Assistant IA) n'est jamais écrasée, et le retour arrière rend
l'ancienne. Données seules : rien d'autre ne bouge.

Test d'une migration appliquée : il part avec elle, une fois la MEP passée
(mémoire « tests de migrations appliquées »).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.utils.etat_descriptif_ia import CONSIGNE
from tests.aides_base import moteur_de_test
from tests.aides_migrations import charger_migration

M = charger_migration("0315")


@pytest.fixture()
def conn(monkeypatch):
    moteur = moteur_de_test(schema=False)
    with moteur.begin() as connexion:
        connexion.execute(sa.text("CREATE TABLE config_site (cle TEXT, valeur TEXT)"))
        monkeypatch.setattr(M, "op", SimpleNamespace(get_bind=lambda: connexion))
        yield connexion


def _valeur(conn) -> str | None:
    return conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :c"), {"c": M.CLE}
    ).scalar()


def _poser(conn, valeur: str) -> None:
    conn.execute(sa.text("INSERT INTO config_site VALUES (:c, :v)"), {"c": M.CLE, "v": valeur})


def test_la_nouvelle_consigne_est_celle_du_code():
    assert M.NOUVELLE == CONSIGNE
    assert "objet" in M.NOUVELLE and "objet" not in M.ANCIENNE


def test_une_consigne_intacte_est_remplacee_et_le_retour_arriere_la_rend(conn):
    _poser(conn, M.ANCIENNE)
    M.upgrade()
    assert _valeur(conn) == M.NOUVELLE
    M.downgrade()
    assert _valeur(conn) == M.ANCIENNE


def test_une_consigne_retouchee_par_l_administrateur_n_est_jamais_ecrasee(conn):
    retouchee = M.ANCIENNE + "\n- Ajout de l'administrateur : lis aussi l'annexe."
    _poser(conn, retouchee)
    M.upgrade()
    assert _valeur(conn) == retouchee


def test_sans_valeur_en_base_rien_n_est_ecrit(conn):
    M.upgrade()
    assert _valeur(conn) is None
