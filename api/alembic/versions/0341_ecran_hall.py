"""Les tables `ecran` et `appairage_ecran` : l'écran de hall appairé (#2770, 16/11/2026).

Deux tables NEUVES, rien d'autre : la version précédente du code ne les connaît pas et
ne les lit pas — revenir à son image ne demande aucune restauration (#1757). Aucune
donnée personnelle : un écran n'a pas de compte derrière lui.

Revision ID: 0341
Revises: 0340
"""

import sqlalchemy as sa
from alembic import op

revision = "0341"
down_revision = "0340"
branch_labels = None
depends_on = None

ECRAN = "ecran"  # identifiant : constante du fichier
APPAIRAGE = "appairage_ecran"  # identifiant : constante du fichier


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    presentes = sa.inspect(op.get_bind()).get_table_names()
    if ECRAN not in presentes:
        op.create_table(
            ECRAN,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nom", sa.String(), nullable=False),
            sa.Column("perimetre", sa.String(), nullable=False),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
            sa.Column("empreinte", sa.String(), nullable=False),
            sa.Column("expire_le", sa.DateTime(), nullable=False),
            sa.Column("vu_le", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("empreinte", name="uq_ecran_empreinte"),
        )
    if APPAIRAGE not in presentes:
        op.create_table(
            APPAIRAGE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("empreinte_code_appareil", sa.String(), nullable=False),
            sa.Column("empreinte_code_court", sa.String(), nullable=False),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
            sa.Column("expire_le", sa.DateTime(), nullable=False),
            sa.Column("intervalle", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("interroge_le", sa.DateTime(), nullable=True),
            sa.Column("nom", sa.String(), nullable=True),
            sa.Column("perimetre", sa.String(), nullable=True),
            sa.Column("confirme_le", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "empreinte_code_appareil", name="uq_appairage_ecran_empreinte_code_appareil"
            ),
            sa.UniqueConstraint(
                "empreinte_code_court", name="uq_appairage_ecran_empreinte_code_court"
            ),
        )


def downgrade() -> None:
    op.drop_table(APPAIRAGE)
    op.drop_table(ECRAN)
