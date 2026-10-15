"""La MIGRATION INITIALE : une base neuve reçoit le schéma courant d'un coup (#1747).

## Pourquoi

Spec multi-copropriétés §4.3 : une base neuve — celle d'une réplique qu'on
installe (`deploiement/standard/`), d'un test — reçoit le schéma actuel d'un
coup. La chaîne Alembic part d'une migration de base vide (`0286`) : elle ne
décrit que ce qui change APRÈS elle, jamais comment on y est arrivé.

## Ce que fait `poser_si_neuve`

| La base…                              | Réponse     | Geste                                   |
|---------------------------------------|-------------|-----------------------------------------|
| n'a AUCUNE table                      | `posee`     | `create_all`, puis marquée à la tête    |
| a déjà des tables                     | `existante` | rien : `alembic upgrade head` la suivra |
| ne se lit pas                         | `inconnu`   | rien — on ne devine pas                 |

« Marquée à la tête » : `alembic_version` reçoit la révision de tête, sans en
exécuter aucune. Les migrations SUIVANTES s'appliquent ensuite normalement.

⚠️ Une base qui a des tables sans `alembic_version` n'est PAS neuve : la
marquer à la tête lui ferait sauter des migrations dont elle a besoin.

Lancé par `start.sh`, avant `alembic upgrade head`, par le seul processus du
conteneur. 🔒 `tests/test_schema_initial.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

from app.utils.revision_base import ALEMBIC_INI, config_alembic


def poser_si_neuve(url: str | None = None, ini: Path = ALEMBIC_INI) -> str:
    """`posee` | `existante` | `inconnu` — voir la table du module."""
    try:
        config = config_alembic(ini)
        if url:
            config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        moteur = create_engine(config.get_main_option("sqlalchemy.url"))
        with moteur.connect() as connexion:
            tables = inspect(connexion).get_table_names()
    except Exception:  # noqa: BLE001 — une base illisible rend « inconnu », jamais un verdict
        return "inconnu"
    try:
        if tables:
            return "existante"
        import app.models.core  # noqa: F401 — enregistre TOUTES les tables (alembic/env.py fait de même)

        SQLModel.metadata.create_all(moteur)
        #  La connexion est TRANSMISE à Alembic (`alembic/env.py`) : sans elle,
        #  `DATABASE_URL` l'emporterait sur `url`, et la marque irait ailleurs.
        with moteur.begin() as connexion:
            config.attributes["connection"] = connexion
            command.stamp(config, "head")
    finally:
        moteur.dispose()
    return "posee"


if __name__ == "__main__":
    print(poser_si_neuve())
    sys.exit(0)
