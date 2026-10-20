"""« Ne pas fusionner » deux affaires liées : la décision se garde sur le lien (#2083)

Additive (#1757) : deux colonnes nullables — l'image précédente les ignore.

Revision ID: 0304
Revises: 0303
"""

import sqlalchemy as sa

from alembic import op

revision = "0304"
down_revision = "0303"
branch_labels = None
depends_on = None

TABLE = "affaire_liee"  # identifiant : constante du fichier
COLONNES = (
    sa.Column("fusion_ecartee_le", sa.DateTime, nullable=True),
    sa.Column("fusion_ecartee_par_id", sa.Integer, nullable=True),
)


def upgrade():
    existantes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}
    for colonne in COLONNES:
        if colonne.name not in existantes:
            op.add_column(TABLE, colonne)


def downgrade():
    for colonne in reversed(COLONNES):
        op.drop_column(TABLE, colonne.name)
