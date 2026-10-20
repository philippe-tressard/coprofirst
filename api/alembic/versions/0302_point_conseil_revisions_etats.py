"""Le point CS / Syndic : liste initiale, révisions, état à la validation, PDF rangé, dérogation (#2082)

Additive (#1757) : chaque colonne est nullable ou porte un `server_default` —
l'image précédente insère sans les connaître.

Revision ID: 0302
Revises: 0301
"""

import sqlalchemy as sa

from alembic import op

revision = "0302"
down_revision = "0301"
branch_labels = None
depends_on = None

POINT = "point_conseil"  # identifiants : constantes du fichier
PRESENT = "point_conseil_present"
COMMENTAIRE = "point_conseil_commentaire"
CR = "point_conseil_cr"

COLONNES = (
    (POINT, sa.Column("affaires_initiales_json", sa.String, nullable=True)),
    (POINT, sa.Column("revision", sa.Integer, nullable=False, server_default="0")),
    (POINT, sa.Column("pdf_cle", sa.String, nullable=True)),
    (PRESENT, sa.Column("valide_par_id", sa.Integer, nullable=True)),
    (COMMENTAIRE, sa.Column("saisi_par_id", sa.Integer, nullable=True)),
    (CR, sa.Column("etat_cible", sa.String, nullable=True)),
    (CR, sa.Column("revision", sa.Integer, nullable=True)),
)


def upgrade():
    inspecteur = sa.inspect(op.get_bind())
    for table, colonne in COLONNES:
        if colonne.name not in {c["name"] for c in inspecteur.get_columns(table)}:
            op.add_column(table, colonne)


def downgrade():
    for table, colonne in reversed(COLONNES):
        op.drop_column(table, colonne.name)
