"""La 0285 retire les anciens chemins de fichier sans toucher à une ligne (#1816).

Exécutée pour de vrai par le contexte d'Alembic, sur une base au schéma d'AVANT :
les trois tables portent encore leur chemin, à côté de la clé. Sous
`TESTS_BASE_URL`, la même chose sur PostgreSQL — le moteur de la production.

`start.sh` lance `alembic upgrade head` sous `set -e` : les colonnes PARTENT, les
lignes et leurs clés RESTENT, et la rejouer ne casse rien.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

_MIGRATION = "0285_retrait_chemins_de_fichier"

#: (table, colonne de chemin, colonne de clé)
_TABLES = (
    ("document", "fichier_chemin", "fichier_cle"),
    ("diagnostic_rapport", "fichier_chemin", "fichier_cle"),
    ("annonce_hall", "pdf_chemin", "pdf_cle"),
)


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration(_MIGRATION), sens)()


def _moteur(tables=_TABLES):
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        for table, chemin, cle in tables:
            # identifiants : constantes du test
            conn.execute(
                text(
                    f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, "
                    f"{chemin} VARCHAR NOT NULL DEFAULT '', {cle} VARCHAR)"
                )
            )
            conn.execute(
                text(f"INSERT INTO {table} (id, {chemin}, {cle}) VALUES (1, '/app/x', 'prive/x')")
            )
    return m


def _colonnes(moteur, table: str) -> set[str]:
    with moteur.connect() as conn:
        return {c["name"] for c in inspect(conn).get_columns(table)}


def test_les_chemins_partent_et_les_cles_restent():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    for table, chemin, cle in _TABLES:
        assert chemin not in _colonnes(moteur, table)
        with moteur.connect() as conn:
            assert conn.execute(text(f"SELECT {cle} FROM {table}")).scalar_one() == "prive/x"


def test_une_table_absente_est_ignoree():
    """Une base qui n'a jamais eu d'affiches ni de diagnostics."""
    moteur = _moteur(tables=_TABLES[:1])
    _jouer(moteur)
    assert "fichier_chemin" not in _colonnes(moteur, "document")


def test_le_retour_arriere_rend_les_colonnes_avec_leur_defaut():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    for table, chemin, cle in _TABLES:
        assert chemin in _colonnes(moteur, table)
        with moteur.begin() as conn:
            conn.execute(text(f"INSERT INTO {table} (id, {cle}) VALUES (2, 'prive/y')"))
            assert conn.execute(text(f"SELECT {chemin} FROM {table} WHERE id = 2")).scalar() == ""
