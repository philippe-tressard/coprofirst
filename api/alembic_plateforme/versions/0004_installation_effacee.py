"""Une installation résiliée peut être SUPPRIMÉE par l'opérateur (`registre/conservation`).

La ligne reste — son numéro fait l'identifiant `CF-…`, qui ne se réattribue jamais ;
une colonne datée dit qu'elle a quitté la liste. Nullable : l'image précédente
insère sans la connaître (`CLAUDE.md`, « Migrations Alembic »).
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

INSTALLATION = "installation"


def upgrade():
    op.add_column(INSTALLATION, sa.Column("effacee_le", sa.DateTime, nullable=True))


def downgrade():
    op.drop_column(INSTALLATION, "effacee_le")
