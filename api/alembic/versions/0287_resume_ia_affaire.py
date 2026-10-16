"""Le RÉSUMÉ d'une affaire par l'assistant, gardé sur l'affaire (#2035)

Le Suivi des affaires et la relance du syndic montrent, sous le titre de chaque
affaire, un résumé de cinq lignes au plus rédigé par l'usage
`synthese_affaires_en_cours` — au lieu du descriptif coupé à dix lignes. Il est
GARDÉ : il resservirait sinon à chaque ouverture de l'écran un appel facturé, et
le courriel de relance doit pouvoir le lire au serveur.

Additive : deux colonnes nullables sur `ticket`, que l'image précédente ignore
(règle #1757, `test_migrations_compatibles.py`).

Idempotente : `start.sh` a `set -e`, et un redémarrage après une migration
interrompue la rejoue — une colonne déjà présente est laissée telle quelle.

⚠️ Le nom de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0287
Revises: 0286
"""

import sqlalchemy as sa

from alembic import op

revision = "0287"
down_revision = "0286"
branch_labels = None
depends_on = None

TABLE = "ticket"  # identifiants : constantes du fichier
RESUME = "resume_ia"
RESUME_LE = "resume_ia_le"


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade():
    presentes = _colonnes(op.get_bind())
    if RESUME not in presentes:
        op.add_column(TABLE, sa.Column(RESUME, sa.String, nullable=True))
    if RESUME_LE not in presentes:
        op.add_column(TABLE, sa.Column(RESUME_LE, sa.DateTime, nullable=True))


def downgrade():
    presentes = _colonnes(op.get_bind())
    with op.batch_alter_table(TABLE) as batch:
        if RESUME_LE in presentes:
            batch.drop_column(RESUME_LE)
        if RESUME in presentes:
            batch.drop_column(RESUME)
