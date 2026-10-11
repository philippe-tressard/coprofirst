"""La date d'un document de « Ma résidence » — celle du document, pas de son dépôt

La gouttière d'une fiche dit QUAND (arbitré le 11/10/2026) : la date de l'AG
pour un compte-rendu (`date_ag`), celle du document pour un règlement. Elle ne
peut pas être `publie_le` : un règlement de 1998 déposé ce mois-ci afficherait
la date du dépôt, sous la même colonne qui donne ailleurs la date de l'AG.

Additive : une colonne nullable, que l'image précédente ignore (règle #1757,
`test_migrations_compatibles.py`). Les documents existants n'ont pas de date :
le formulaire de correction propose la date d'ajout, modifiable.

Idempotente : `start.sh` a `set -e`, et un redémarrage après une migration
interrompue la rejoue — une colonne déjà présente est laissée telle quelle.

⚠️ Le nom de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0280
Revises: 0279
"""

import sqlalchemy as sa

from alembic import op

revision = "0280"
down_revision = "0279"
branch_labels = None
depends_on = None

TABLE = "document"  # identifiants : constantes du fichier
COLONNE = "date_document"


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade():
    if COLONNE not in _colonnes(op.get_bind()):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Date, nullable=True))


def downgrade():
    if COLONNE in _colonnes(op.get_bind()):
        with op.batch_alter_table(TABLE) as batch:
            batch.drop_column(COLONNE)
