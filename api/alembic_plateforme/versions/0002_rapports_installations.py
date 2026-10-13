"""Les rapports nocturnes des installations (R3 #1879, spec §4.11).

Une table de plus dans la base `plateforme` ; la résidence n'en sait rien.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

RAPPORT = "rapport_installation"


def upgrade():
    op.create_table(
        RAPPORT,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("installation_id", sa.Integer, sa.ForeignKey("installation.id"), nullable=False),
        sa.Column("recu_le", sa.DateTime, nullable=False),
        sa.Column("version_logicielle", sa.String(40), nullable=True),
        sa.Column("corps", sa.Text, nullable=False),
    )
    op.create_index("ix_rapport_installation_installation_id", RAPPORT, ["installation_id"])
    op.create_index("ix_rapport_installation_recu_le", RAPPORT, ["recu_le"])


def downgrade():
    op.drop_table(RAPPORT)
