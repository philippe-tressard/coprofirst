"""Second temps du retrait de `config_sauvegarde.active` : la colonne part (#2182)

Le code a cessé d'en dépendre en v3.13.8 (premier temps, `CONTRACTIONS` de
`test_migrations_compatibles.py`), et la 0310 lui a donné un défaut. Cette migration,
d'une version ultérieure, la retire : `config_sauvegarde.active` n'est plus lue depuis
#2060 (« la sauvegarde ne se coupe PAS »), et aucun modèle ne la déclare plus.

Retrait accordé par Philippe le 23/10/2026 (« oui, retire la colonne définitivement »,
consigné sur #2182) : la valeur ne se retrouve plus que dans les sauvegardes d'avant.
L'image précédente (v3.13.8 et plus) ne lit ni n'écrit cette colonne : revenir en arrière
reste un changement d'image (#1757).

Une base neuve n'a pas cette colonne (le schéma courant vient des modèles) : la
migration ne retire que ce qui existe. L'appel est écrit en littéral : c'est ce que
`test_migrations_compatibles.py` sait lire.

Revision ID: 0311
Revises: 0310
"""

import sqlalchemy as sa

from alembic import op

revision = "0311"
down_revision = "0310"
branch_labels = None
depends_on = None


def _existe(table: str, colonne: str) -> bool:
    return colonne in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if _existe("config_sauvegarde", "active"):
        op.drop_column("config_sauvegarde", "active")


def downgrade() -> None:
    #  La colonne revient avec son défaut (vrai) : la valeur d'avant ne se recrée pas.
    if not _existe("config_sauvegarde", "active"):
        op.add_column(
            "config_sauvegarde",
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
