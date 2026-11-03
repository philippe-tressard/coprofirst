"""La table `appareil` : les téléphones qui sonnent pour une personne (#2493, 03/11/2026).

Lot P2 des notifications push (`specs/architecture/notifications-push.md` §6.1).
Une table NEUVE, rien d'autre : la version précédente du code ne la connaît pas et
ne la lit pas — revenir à son image ne demande aucune restauration (#1757).

Revision ID: 0323
Revises: 0322
"""

import sqlalchemy as sa
from alembic import op

revision = "0323"
down_revision = "0322"
branch_labels = None
depends_on = None

TABLE = "appareil"  # identifiant : constante du fichier


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("utilisateur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("jeton", sa.String(), nullable=False),
        sa.Column("environnement", sa.String(), nullable=False),
        sa.Column("abonnement", sa.String(), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("vu_le", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("jeton", name="uq_appareil_jeton"),
        sa.UniqueConstraint("abonnement", name="uq_appareil_abonnement"),
    )
    op.create_index("ix_appareil_utilisateur_id", TABLE, ["utilisateur_id"])


def downgrade() -> None:
    op.drop_index("ix_appareil_utilisateur_id", table_name=TABLE)
    op.drop_table(TABLE)
