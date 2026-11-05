"""La table `courriel_a_classer` : les messages qu'aucune affaire ne désigne (#2555, 05/11/2026).

Un message authentifié d'un correspondant connu, sans affaire désignée, était
refusé et perdu pour le site. Il attend désormais d'être classé par le conseil.
Une table NEUVE, rien d'autre : la version précédente du code ne la connaît pas et
ne la lit pas — revenir à son image ne demande aucune restauration (#1757).

Revision ID: 0325
Revises: 0324
"""

import sqlalchemy as sa
from alembic import op

revision = "0325"
down_revision = "0324"
branch_labels = None
depends_on = None

TABLE = "courriel_a_classer"  # identifiant : constante du fichier
INDEX = ("releve_id", "cree_le", "statut", "ticket_id")  # identifiants : constantes


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("releve_id", sa.Integer(), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("envoye_le", sa.DateTime(), nullable=True),
        sa.Column("expediteur", sa.String(), nullable=False),
        sa.Column("objet", sa.String(), nullable=False),
        sa.Column("brut", sa.LargeBinary(), nullable=True),
        sa.Column("statut", sa.String(), nullable=False),
        sa.Column("classe_le", sa.DateTime(), nullable=True),
        sa.Column("classe_par_id", sa.Integer(), nullable=True),
        sa.Column("ticket_id", sa.Integer(), nullable=True),
    )
    for colonne in INDEX:
        op.create_index(f"ix_{TABLE}_{colonne}", TABLE, [colonne])


def downgrade() -> None:
    for colonne in INDEX:
        op.drop_index(f"ix_{TABLE}_{colonne}", table_name=TABLE)
    op.drop_table(TABLE)
