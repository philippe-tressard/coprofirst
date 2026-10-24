"""La 0311 retire `config_sauvegarde.active`, dont plus rien ne dépend (#2182).

Second temps du retrait : la colonne que la 0310 avait dotée d'un défaut part. Le test
la recrée telle que la production la porte, joue la migration, et vérifie qu'elle a
disparu, que la table sert toujours (insertion d'une ligne du modèle), et que le
retour arrière la rend avec son défaut.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlmodel import Session

from app.models.core import ConfigSauvegarde
from tests import aides_migrations
from tests.aides_base import moteur_de_test


def _jouer(moteur, pas) -> None:
    """Un pas de migration dans sa transaction, sur CE moteur (un appel de
    `moteur_de_test()` ouvre un schéma neuf : la base d'un test n'est qu'à un moteur)."""
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            pas()


def _colonnes(moteur) -> dict[str, dict]:
    return {c["name"]: c for c in sa.inspect(moteur).get_columns("config_sauvegarde")}


def test_la_colonne_part_la_table_sert_toujours_et_le_retour_la_rend():
    moteur = moteur_de_test()
    with moteur.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE config_sauvegarde ADD COLUMN active boolean NOT NULL DEFAULT true")
        )
    assert "active" in _colonnes(moteur), "cas zéro : la colonne de la production est là"

    migration = aides_migrations.charger_migration("0311")
    _jouer(moteur, migration.upgrade)
    _jouer(moteur, migration.upgrade)  # idempotente : un redémarrage la rejoue
    assert "active" not in _colonnes(moteur), "la colonne n'a pas été retirée"

    with Session(moteur) as session:
        session.add(ConfigSauvegarde(heure_execution=4))
        session.commit()

    _jouer(moteur, migration.downgrade)
    revenue = _colonnes(moteur)["active"]
    assert revenue["nullable"] is False and revenue["default"] == "true"
    moteur.dispose()


def test_la_migration_ne_touche_pas_une_base_neuve():
    """Une base neuve n'a pas la colonne : rien à retirer, et rien ne lève."""
    moteur = moteur_de_test()
    migration = aides_migrations.charger_migration("0311")
    _jouer(moteur, migration.upgrade)
    assert "active" not in _colonnes(moteur)
