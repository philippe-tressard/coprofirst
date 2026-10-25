"""Une clé de charges appelée ou non par le syndic, et son libellé sur l'appel de fonds (#2252).

Le règlement prévoit des clés que le syndic n'appelle pas toujours (un escalier sans
budget ce trimestre). « Mes lots » les montait au même rang que les autres, et le
copropriétaire cherchait en vain la ligne sur son appel de fonds. Le conseil dit, clé
par clé, si elle est appelée et sous quel libellé ; rien ne change tant qu'il n'y
touche pas (`appelee` vrai par défaut).

Colonnes additives — `server_default` pour l'une, nullable pour l'autre : l'image
précédente les ignore (#1757).

Revision ID: 0316
Revises: 0315
"""

import sqlalchemy as sa
from alembic import op

revision = "0316"
down_revision = "0315"
branch_labels = None
depends_on = None


TABLE = "cle_de_charges"  # identifiant : constante du fichier


def _colonnes() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    presentes = _colonnes()
    if "appelee" not in presentes:
        op.add_column(
            TABLE, sa.Column("appelee", sa.Boolean(), nullable=False, server_default=sa.true())
        )
    if "libelle_syndic" not in presentes:
        op.add_column(TABLE, sa.Column("libelle_syndic", sa.String(), nullable=True))


def downgrade() -> None:
    presentes = _colonnes()
    for colonne in ("libelle_syndic", "appelee"):
        if colonne in presentes:
            op.drop_column(TABLE, colonne)
