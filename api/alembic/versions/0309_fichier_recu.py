"""L'auteur d'un fichier téléversé : la table `fichier_recu` (#2154)

Un fichier qu'aucun objet ne cite encore — la photo d'un formulaire pas encore
enregistré — se lit par son auteur seul (arbitrage du 23/10/2026). Table neuve :
l'image précédente l'ignore, revenir en arrière reste un changement d'image
(#1757). Les fichiers déjà sur disque n'y ont pas de ligne : sans porteur, ils
ne se lisent que par le conseil et l'administration.

Revision ID: 0309
Revises: 0308
"""

import sqlalchemy as sa

from alembic import op

revision = "0309"
down_revision = "0308"
branch_labels = None
depends_on = None

TABLE = "fichier_recu"


def upgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cle", sa.String(), nullable=False),
        sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_fichier_recu_cle", TABLE, ["cle"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_fichier_recu_cle", table_name=TABLE)
    op.drop_table(TABLE)
