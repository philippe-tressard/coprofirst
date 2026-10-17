"""Le MOYEN d'un point conseil syndical / syndic (#2041)

`point_conseil.moyen` : sur place, visioconférence, téléphone, ou sur place et à
distance (arbitré le 17/10/2026, liste « A »). Il remplace à l'écran la bascule
« Sur place | À distance » ; `a_distance` s'en déduit à l'écriture et reste lu
pour les points saisis avant.

Additive : une colonne nullable que l'image précédente ignore (règle #1757,
`test_migrations_compatibles.py`). Idempotente : une colonne déjà présente est
laissée telle quelle.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0293
Revises: 0292
"""

import sqlalchemy as sa

from alembic import op

revision = "0293"
down_revision = "0292"
branch_labels = None
depends_on = None

POINT = "point_conseil"  # identifiants : constantes du fichier
COLONNE = "moyen"


def _colonnes() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(POINT)}


def upgrade():
    if COLONNE not in _colonnes():
        op.add_column(POINT, sa.Column(COLONNE, sa.String, nullable=True))


def downgrade():
    if COLONNE in _colonnes():
        with op.batch_alter_table(POINT) as batch:
            batch.drop_column(COLONNE)
