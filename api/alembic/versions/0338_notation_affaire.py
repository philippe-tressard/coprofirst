"""Un avis sur un prestataire peut porter sur une affaire (15/11/2026).

On note le couple prestataire / affaire : l'intervention qu'on juge. Plusieurs membres
peuvent noter le même couple. Colonne additive et nullable : un avis d'avant ce lot
n'a pas d'affaire, et l'image précédente l'ignore (#1757).

Revision ID: 0338
Revises: 0337
"""

import sqlalchemy as sa
from alembic import op

revision = "0338"
down_revision = "0337"
branch_labels = None
depends_on = None


TABLE = "notation_prestataire"  # identifiant : constante du fichier


def _presentes() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if "ticket_id" not in _presentes():
        op.add_column(
            TABLE,
            sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("ticket.id"), nullable=True),
        )


def downgrade() -> None:
    pass  # additive : revenir en arrière est un changement d'image (#1757)
