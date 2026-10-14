"""Les services qu'une installation a le droit d'allumer (#1880, spec §4.11).

La référence les accorde un par un depuis l'onglet « Installations » ; le bail les
porte. Une colonne neuve AVEC `server_default` : l'image précédente insère sans la
connaître (`CLAUDE.md`, « Migrations Alembic »), et les inscriptions déjà là
n'ont aucun service — ce que le bail disait déjà.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

INSTALLATION = "installation"


def upgrade():
    op.add_column(
        INSTALLATION,
        sa.Column("services_autorises", sa.Text, nullable=False, server_default="[]"),
    )


def downgrade():
    op.drop_column(INSTALLATION, "services_autorises")
