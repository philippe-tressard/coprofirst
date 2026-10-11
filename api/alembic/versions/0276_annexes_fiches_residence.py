"""Les fiches de « Ma résidence » portent des annexes

Un plan, un règlement, un CR d'AG, un rapport de diagnostic n'étaient qu'UN
fichier, et une règle n'en portait aucun : l'édition de ces fiches n'offrait
donc pas la section « Pièces jointes » du cadre. Une annexe est un `document`
rattaché à sa fiche par l'une de ces trois colonnes — la forme des pièces
jointes d'affaire et d'événement (`ticket_id`, `evenement_id`, #390).

Additive : trois colonnes nullables, que l'image précédente ignore (règle
#1757, `test_migrations_compatibles.py`). Sans clé étrangère : SQLite refuse
d'en poser une dans un `add_column` (`test_migrations.py`).

Idempotente : `start.sh` a `set -e`, et un redémarrage après une migration
interrompue la rejoue — une colonne déjà présente est laissée telle quelle.

⚠️ Le nom de table et de colonnes sont des CONSTANTES du fichier.

Revision ID: 0276
Revises: 0275
"""

import sqlalchemy as sa

from alembic import op

revision = "0276"
down_revision = "0275"
branch_labels = None
depends_on = None

TABLE = "document"  # identifiants : constantes du fichier
COLONNES = ("document_parent_id", "diagnostic_rapport_id", "regle_residence_id")


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade():
    presentes = _colonnes(op.get_bind())
    for colonne in COLONNES:
        if colonne not in presentes:
            op.add_column(TABLE, sa.Column(colonne, sa.Integer, nullable=True))


def downgrade():
    presentes = _colonnes(op.get_bind())
    with op.batch_alter_table(TABLE) as batch:
        for colonne in COLONNES:
            if colonne in presentes:
                batch.drop_column(colonne)
