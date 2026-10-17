"""La validation du CR d'un point conseil syndical / syndic (#2042)

- `point_conseil.envoye_le` : le dernier envoi aux présents, qui fait courir
  les 7 jours de l'auto-validation ;
- `point_conseil_present.jeton_empreinte` et `.valide_le` : le lien de chaque
  présent (par son empreinte, jamais en clair) et le moment de son « Je valide » ;
- `point_conseil_commentaire` : ce qu'un présent répond.

Additive : deux colonnes nullables et une table que l'image précédente ignore
(règle #1757, `test_migrations_compatibles.py`). Idempotente : une colonne ou
une table déjà présente est laissée telle quelle.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0292
Revises: 0291
"""

import sqlalchemy as sa

from alembic import op

revision = "0292"
down_revision = "0291"
branch_labels = None
depends_on = None

POINT = "point_conseil"  # identifiants : constantes du fichier
PRESENT = "point_conseil_present"
COMMENTAIRE = "point_conseil_commentaire"
INDEX_JETON = "ix_point_conseil_present_jeton_empreinte"


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if "envoye_le" not in _colonnes(POINT):
        op.add_column(POINT, sa.Column("envoye_le", sa.DateTime, nullable=True))
    presentes = _colonnes(PRESENT)
    if "jeton_empreinte" not in presentes:
        op.add_column(PRESENT, sa.Column("jeton_empreinte", sa.String, nullable=True))
        op.create_index(INDEX_JETON, PRESENT, ["jeton_empreinte"])
    if "valide_le" not in presentes:
        op.add_column(PRESENT, sa.Column("valide_le", sa.DateTime, nullable=True))
    if COMMENTAIRE not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            COMMENTAIRE,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "point_id", sa.Integer, sa.ForeignKey("point_conseil.id"), nullable=False, index=True
            ),
            sa.Column("present_id", sa.Integer, nullable=True),
            sa.Column("contenu", sa.String, nullable=False, server_default=""),
            sa.Column("cree_le", sa.DateTime, nullable=False),
        )


def downgrade():
    if COMMENTAIRE in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(COMMENTAIRE)
    presentes = _colonnes(PRESENT)
    with op.batch_alter_table(PRESENT) as batch:
        if "jeton_empreinte" in presentes:
            batch.drop_index(INDEX_JETON)
            batch.drop_column("jeton_empreinte")
        if "valide_le" in presentes:
            batch.drop_column("valide_le")
    if "envoye_le" in _colonnes(POINT):
        with op.batch_alter_table(POINT) as batch:
            batch.drop_column("envoye_le")
