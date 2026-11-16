"""La table `jeton_montre` : le jeton d'une montre, lecture de la cloche seule (#2771, 16/11/2026).

Une table NEUVE, rien d'autre : la version précédente du code ne la connaît pas et ne
la lit pas — revenir à son image ne demande aucune restauration (#1757).

Revision ID: 0339
Revises: 0338
"""

import sqlalchemy as sa
from alembic import op

revision = "0339"
down_revision = "0338"
branch_labels = None
depends_on = None

TABLE = "jeton_montre"  # identifiant : constante du fichier


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("utilisateur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("empreinte", sa.String(), nullable=False),
        sa.Column("plateforme", sa.String(), nullable=False),
        sa.Column("empreinte_compte", sa.String(), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("expire_le", sa.DateTime(), nullable=False),
        sa.Column("vu_le", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("empreinte", name="uq_jeton_montre_empreinte"),
    )
    op.create_index("ix_jeton_montre_utilisateur_id", TABLE, ["utilisateur_id"])


def downgrade() -> None:
    op.drop_index("ix_jeton_montre_utilisateur_id", table_name=TABLE)
    op.drop_table(TABLE)
