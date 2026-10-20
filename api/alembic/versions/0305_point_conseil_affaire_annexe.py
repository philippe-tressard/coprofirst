"""Le point CS / Syndic retient son affaire « Points annexes » (#2084)

Additive (#1757) : une colonne nullable, sans clé étrangère — comme les fiches
des présents, la ligne du point survit à l'affaire.

Revision ID: 0305
Revises: 0304
"""

import sqlalchemy as sa

from alembic import op

revision = "0305"
down_revision = "0304"
branch_labels = None
depends_on = None

TABLE = "point_conseil"  # identifiant : constante du fichier
COLONNE = "affaire_annexe_id"


def upgrade():
    if COLONNE not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}:
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer, nullable=True))


def downgrade():
    op.drop_column(TABLE, COLONNE)
