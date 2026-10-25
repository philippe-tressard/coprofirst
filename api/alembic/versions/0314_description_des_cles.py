"""Ce que finance une clé de charges — sa description, tirée du règlement (#2251).

« Escalier A » et « Escalier A' » ne se distinguent pas par leur libellé : le règlement
les définit (l'escalier du rez-de-chaussée aux étages, celui des deux sous-sols). La
définition entre par l'atelier de l'état descriptif (feuille « Clés ») et se montre sous
la clé, dans « Mes lots ». Colonne additive, nullable : l'image précédente l'ignore
(#1757).

Revision ID: 0314
Revises: 0313
"""

import sqlalchemy as sa
from alembic import op

revision = "0314"
down_revision = "0313"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cle_de_charges", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("cle_de_charges", "description")
