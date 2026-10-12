"""La 0284 donne un défaut aux anciens chemins de fichier, que le code ne déclare plus (#1816).

Exécutée pour de vrai par le contexte d'Alembic, sur une base au schéma de la
production sous PostgreSQL : née du schéma courant (`create_all`), donc des
colonnes `NOT NULL` SANS défaut. Sans la migration, une insertion qui ne les
nomme pas — celle du code de ce lot — échoue. Sous `TESTS_BASE_URL`, la même
chose sur PostgreSQL.
"""

from __future__ import annotations

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

_MIGRATION = "0284_chemins_de_fichier_par_defaut"

_TABLES = (
    ("document", "fichier_chemin"),
    ("diagnostic_rapport", "fichier_chemin"),
    ("annonce_hall", "pdf_chemin"),
)


def _jouer(moteur) -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            charger_migration(_MIGRATION).upgrade()


def _moteur(tables=_TABLES):
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        for table, colonne in tables:
            # identifiants : constantes du test
            conn.execute(
                text(
                    f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, "
                    f"{colonne} VARCHAR NOT NULL, cle VARCHAR)"
                )
            )
    return m


def _inserer_sans_chemin(moteur, table: str) -> None:
    with moteur.begin() as conn:
        conn.execute(text(f"INSERT INTO {table} (id, cle) VALUES (1, 'prive/a.pdf')"))


def test_sans_la_migration_une_ligne_sans_chemin_est_refusee():
    """Le cas fautif : ce que ferait le code de ce lot sur la base de production."""
    moteur = _moteur()
    with pytest.raises(IntegrityError):
        _inserer_sans_chemin(moteur, "document")


def test_apres_la_migration_chaque_table_accepte_une_ligne_sans_chemin():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    for table, colonne in _TABLES:
        _inserer_sans_chemin(moteur, table)
        with moteur.connect() as conn:
            assert conn.execute(text(f"SELECT {colonne} FROM {table}")).scalar_one() == ""


def test_une_table_ou_une_colonne_absente_est_ignoree():
    """Une base où le second temps est passé, ou qui n'a jamais eu d'affiches."""
    moteur = _moteur(tables=(("document", "fichier_chemin"),))
    _jouer(moteur)
    _inserer_sans_chemin(moteur, "document")
