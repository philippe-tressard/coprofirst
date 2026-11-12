"""La table `demande_suppression_compte` : une personne demande l'effacement de son compte (#2699).

Exigé par la revue de l'App Store (règle 5.1.1 v) : l'app qui ouvre des comptes
doit permettre d'en lancer la suppression. La demande est traitée par
l'administration (arbitrage du 12/11/2026), par la purge existante.
Une table NEUVE, rien d'autre : la version précédente du code ne la connaît pas et
ne la lit pas — revenir à son image ne demande aucune restauration (#1757).

Revision ID: 0331
Revises: 0330
"""

import sqlalchemy as sa
from alembic import op

revision = "0331"
down_revision = "0330"
branch_labels = None
depends_on = None

TABLE = "demande_suppression_compte"  # identifiant : constante du fichier
INDEX = ("utilisateur_id", "statut")  # identifiants : constantes


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "utilisateur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False
        ),
        sa.Column("motif", sa.String(), nullable=True),
        sa.Column("statut", sa.String(), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("traitee_le", sa.DateTime(), nullable=True),
        sa.Column(
            "traitee_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True
        ),
        sa.Column("retiree_le", sa.DateTime(), nullable=True),
    )
    for colonne in INDEX:
        op.create_index(f"ix_{TABLE}_{colonne}", TABLE, [colonne])


def downgrade() -> None:
    for colonne in INDEX:
        op.drop_index(f"ix_{TABLE}_{colonne}", table_name=TABLE)
    op.drop_table(TABLE)
