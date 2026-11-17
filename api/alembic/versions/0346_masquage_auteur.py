"""Les masques par auteur (#2861) : « masquer ce que publie X », pour soi seul.

Une table neuve, sans reprise : la version précédente du code ne la lit pas et ne
s'en aperçoit pas (#1757).
"""

import sqlalchemy as sa
from alembic import op

revision = "0346"
down_revision = "0345"
branch_labels = None
depends_on = None

TABLE = "masquage_auteur"  # identifiant, constante du fichier


def upgrade():
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("masque_par_id", sa.Integer, sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("auteur_id", sa.Integer, sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("cree_le", sa.DateTime, nullable=False),
        sa.UniqueConstraint("masque_par_id", "auteur_id", name="uq_masquage_auteur"),
    )
    op.create_index("ix_masquage_auteur_masque_par_id", TABLE, ["masque_par_id"])


def downgrade():
    op.drop_index("ix_masquage_auteur_masque_par_id", table_name=TABLE)
    op.drop_table(TABLE)
