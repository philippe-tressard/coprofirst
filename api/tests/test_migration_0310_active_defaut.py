"""La 0310 donne un défaut à `config_sauvegarde.active`, que le modèle ne remplit plus (#2182).

Premier temps du retrait : le champ a quitté `ConfigSauvegarde`, mais la colonne de
la production est `NOT NULL` sans défaut. Sans la migration, `ConfigSauvegarde()` —
l'insertion d'une ligne quand la table est vide — échoue. Le test recrée la colonne
telle que la production la porte, joue la migration, puis insère sans `active`.
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


def test_une_ligne_s_insere_sans_active_une_fois_la_migration_jouee():
    moteur = moteur_de_test()
    with moteur.begin() as conn:
        conn.execute(
            sa.text("ALTER TABLE config_sauvegarde ADD COLUMN active boolean NOT NULL DEFAULT true")
        )
        conn.execute(sa.text("ALTER TABLE config_sauvegarde ALTER COLUMN active DROP DEFAULT"))

    avant = sa.inspect(moteur).get_columns("config_sauvegarde")
    assert next(c for c in avant if c["name"] == "active")["default"] is None, (
        "cas zéro : la colonne de la production n'a pas de défaut"
    )
    with Session(moteur) as session:
        session.add(ConfigSauvegarde())
        try:
            session.commit()
            raise AssertionError("sans la migration, l'insertion doit échouer")
        except sa.exc.IntegrityError:
            session.rollback()

    migration = aides_migrations.charger_migration("0310")
    _jouer(moteur, migration.upgrade)
    _jouer(moteur, migration.upgrade)  # idempotente : un redémarrage la rejoue

    with Session(moteur) as session:
        session.add(ConfigSauvegarde(heure_execution=4))
        session.commit()
        active = session.exec(sa.text("SELECT active FROM config_sauvegarde")).scalar()
    assert active is True, "le défaut est vrai, comme celui du modèle"
    moteur.dispose()


def test_la_migration_ne_touche_pas_une_base_neuve():
    """Une base neuve n'a pas la colonne : rien à faire, et rien ne lève."""
    moteur = moteur_de_test()
    migration = aides_migrations.charger_migration("0310")
    _jouer(moteur, migration.upgrade)
    _jouer(moteur, migration.downgrade)
