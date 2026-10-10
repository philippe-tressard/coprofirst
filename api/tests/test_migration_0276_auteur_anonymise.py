"""La 0276 rend l'auteur facultatif sans toucher à une ligne (#1688).

Exécutée pour de vrai par le contexte d'Alembic, sur une base au schéma d'AVANT :
`auteur_id` obligatoire sur les quatre tables d'un fil, des lignes dedans, et une
politique qui porte le passage de conservation des comptes. Sous `TESTS_BASE_URL`,
la même chose sur PostgreSQL — le moteur de la production.
"""

from __future__ import annotations

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from app.seed.contenus_legaux import ANONYMISATION_AFFAIRES, CONSERVATION_COMPTES
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

_MIGRATION = "0276_auteur_anonymise"
_TABLES = ("ticket", "message_ticket", "ticket_evolution", "evenement_evolution")
_POLITIQUE = "<ul><li>" + CONSERVATION_COMPTES + "</li><li>Sauvegardes.</li></ul>"


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration(_MIGRATION), sens)()


def _moteur():
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        for table in _TABLES:
            conn.execute(
                text(
                    f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, "  # noqa: S608 — constantes du test
                    "auteur_id INTEGER NOT NULL, contenu VARCHAR)"
                )
            )
            conn.execute(text(f"INSERT INTO {table} VALUES (1, 7, 'texte')"))  # noqa: S608
        conn.execute(text("CREATE TABLE config_site (cle VARCHAR PRIMARY KEY, valeur TEXT)"))
        conn.execute(
            text("INSERT INTO config_site VALUES ('politique_confidentialite', :v)").bindparams(
                v=_POLITIQUE
            )
        )
    return m


def _facultatives(moteur) -> dict[str, bool]:
    with moteur.connect() as conn:
        return {
            t: next(c["nullable"] for c in inspect(conn).get_columns(t) if c["name"] == "auteur_id")
            for t in _TABLES
        }


def _politique(moteur) -> str:
    with moteur.connect() as conn:
        return conn.execute(text("SELECT valeur FROM config_site")).scalar()


def test_l_auteur_devient_facultatif_et_les_lignes_restent():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    assert all(_facultatives(moteur).values())
    with moteur.begin() as conn:
        for table in _TABLES:
            assert conn.execute(text(f"SELECT auteur_id FROM {table}")).scalar() == 7  # noqa: S608
            conn.execute(text(f"UPDATE {table} SET auteur_id = NULL"))  # noqa: S608
    #  La politique servie le dit, une fois — même rejouée.
    assert _politique(moteur).count(ANONYMISATION_AFFAIRES) == 1


def test_le_retour_arriere_n_invente_pas_d_auteur():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert not any(_facultatives(moteur).values())
    assert ANONYMISATION_AFFAIRES not in _politique(moteur)

    _jouer(moteur)
    with moteur.begin() as conn:
        conn.execute(text("UPDATE ticket SET auteur_id = NULL"))
    with pytest.raises(RuntimeError, match="sans auteur"):
        _jouer(moteur, "downgrade")
