"""Les CANAUX de distribution et les VAGUES de déploiement (R5 #1881, spec §4.11 règle 6).

- `canal_distribution` : un canal est un POINTEUR vers une version de `main` (D21) —
  sa version, celle d'avant, et quand il a avancé (ce qui ouvre les vagues).
- `installation.vague` : quand une installation reçoit la version de son canal
  (`registre/canaux.VAGUES`) ; `1`, la vague générale, pour les inscriptions déjà là.
- `installation.version_epinglee` : la version que l'opérateur lui impose — épinglage,
  ou ordre de revenir à une version plus ancienne.

Ajouts seulement, nullable ou avec `server_default` : l'image précédente insère sans
les connaître (`CLAUDE.md`, « Migrations Alembic »).
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

INSTALLATION = "installation"
CANAL = "canal_distribution"


def upgrade():
    op.add_column(INSTALLATION, sa.Column("vague", sa.Integer, nullable=False, server_default="1"))
    op.add_column(INSTALLATION, sa.Column("version_epinglee", sa.String(40), nullable=True))
    op.create_table(
        CANAL,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nom", sa.String(60), nullable=False, unique=True),
        sa.Column("version", sa.String(40), nullable=True),
        sa.Column("version_precedente", sa.String(40), nullable=True),
        sa.Column("avance_le", sa.DateTime, nullable=True),
        sa.Column("cree_le", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table(CANAL)
    op.drop_column(INSTALLATION, "version_epinglee")
    op.drop_column(INSTALLATION, "vague")
