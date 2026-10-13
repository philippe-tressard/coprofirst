"""Un transfert de courriel versé se VALIDE : il sort de la liste des gestes

Demandé le 13/10/2026 : un transfert versé au bon endroit gardait ses boutons
« Annuler », « Déplacer », « En faire une nouvelle affaire » jusqu'à ce qu'une
Suite les éteigne. « Valider le transfert » le confirme : `valide_le` et
`valide_par_id` sur `versement_courriel`, et `utils/versement_transfert` ne le
propose plus au geste.

Additive : deux colonnes nullables, que l'image précédente ignore (règle #1757,
`test_migrations_compatibles.py`). Colonne simple, sans clé étrangère, comme
`transfere_par_id` (0239).

Idempotente : `start.sh` a `set -e`, et un redémarrage après une migration
interrompue la rejoue — une colonne déjà présente est laissée telle quelle.

⚠️ Le nom de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0286
Revises: 0285
"""

import sqlalchemy as sa

from alembic import op

revision = "0286"
down_revision = "0285"
branch_labels = None
depends_on = None

TABLE = "versement_courriel"  # identifiants : constantes du fichier
VALIDE_LE = "valide_le"
VALIDE_PAR = "valide_par_id"


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade():
    presentes = _colonnes(op.get_bind())
    if VALIDE_LE not in presentes:
        op.add_column(TABLE, sa.Column(VALIDE_LE, sa.DateTime, nullable=True))
    if VALIDE_PAR not in presentes:
        op.add_column(TABLE, sa.Column(VALIDE_PAR, sa.Integer, nullable=True))


def downgrade():
    presentes = _colonnes(op.get_bind())
    with op.batch_alter_table(TABLE) as batch:
        if VALIDE_PAR in presentes:
            batch.drop_column(VALIDE_PAR)
        if VALIDE_LE in presentes:
            batch.drop_column(VALIDE_LE)
