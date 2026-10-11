"""La provenance du texte lu par l'assistant, gardée avec chaque question au règlement

L'avis se termine par « d'après {provenance} » — la phrase saisie par
l'administration (`utils/question_reglement/provenance`), et non plus la date de
chargement des fichiers. Chaque question garde celle du moment où elle a été
posée ; une question plus ancienne lit la provenance actuelle.

Additive : une colonne nullable, que l'image précédente ignore (règle #1757,
`test_migrations_compatibles.py`).

Idempotente : `start.sh` a `set -e`, et un redémarrage après une migration
interrompue la rejoue — une colonne déjà présente est laissée telle quelle.

⚠️ Le nom de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0281
Revises: 0280
"""

import sqlalchemy as sa

from alembic import op

revision = "0281"
down_revision = "0280"
branch_labels = None
depends_on = None

TABLE = "question_reglement"  # identifiants : constantes du fichier
COLONNE = "provenance"


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade():
    if COLONNE not in _colonnes(op.get_bind()):
        op.add_column(TABLE, sa.Column(COLONNE, sa.String, nullable=True))


def downgrade():
    if COLONNE in _colonnes(op.get_bind()):
        with op.batch_alter_table(TABLE) as batch:
            batch.drop_column(COLONNE)
