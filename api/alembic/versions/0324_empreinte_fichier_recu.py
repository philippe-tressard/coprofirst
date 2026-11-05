"""Une pièce jointe d'un courriel ne se verse pas deux fois dans une affaire (#2515, 04/11/2026).

La trace d'un fichier reçu (`fichier_recu`) garde l'empreinte SHA-256 des octets
REÇUS — une image est réencodée à l'écriture, l'empreinte du fichier stocké ne
dit donc rien de ce qui a été reçu. La relève des courriels la pose, et ne verse
pas une pièce que le fil de l'affaire porte déjà.

Colonne additive et nullable : une trace d'avant ce lot n'a pas d'empreinte, et
l'image précédente l'ignore (#1757).

Revision ID: 0324
Revises: 0323
"""

import sqlalchemy as sa
from alembic import op

revision = "0324"
down_revision = "0323"
branch_labels = None
depends_on = None


TABLE = "fichier_recu"  # identifiant : constante du fichier
COLONNE = "empreinte"  # identifiant : constante du fichier
INDEX = "ix_fichier_recu_empreinte"  # identifiant : constante du fichier


def _presente() -> bool:
    return COLONNE in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if not _presente():
        op.add_column(TABLE, sa.Column(COLONNE, sa.String(), nullable=True))
        op.create_index(INDEX, TABLE, [COLONNE])


def downgrade() -> None:
    if _presente():
        op.drop_index(INDEX, table_name=TABLE)
        op.drop_column(TABLE, COLONNE)
