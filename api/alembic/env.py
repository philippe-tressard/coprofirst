import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from sqlmodel import SQLModel

# Import all models so Alembic can detect them
import app.models.core  # noqa: F401

config = context.config

#  `DATABASE_URL` l'emporte sur `alembic.ini` (#1747), comme pour l'API et
#  `app/utils/revision_base.config_alembic` : une installation sur PostgreSQL
#  n'a que cette variable.
if os.environ.get("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"].replace("%", "%%"))

if config.config_file_name is not None:
    #  `disable_existing_loggers=False` : appelé DANS un processus qui journalise
    #  déjà (`utils/schema_initial`, ses tests), le défaut éteignait tous les
    #  journaux de l'application — trois tests de l'alerte WhatsApp ne lisaient
    #  plus rien après lui (#1747).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _migrer(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    #  Une connexion transmise par l'appelant l'emporte (`utils/schema_initial`,
    #  #1747) : c'est SA base qu'il faut marquer.
    transmise = config.attributes.get("connection")
    if transmise is not None:
        _migrer(transmise)
        return
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _migrer(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
