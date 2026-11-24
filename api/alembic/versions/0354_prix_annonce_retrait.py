"""Le prix d'une petite annonce, contraction — second temps : `prix` est retirée (#3011).

Premier temps (0353) : le code ne lit ni n'écrit plus que `prix_centimes`, et
`prix` a été vidée. Ce retrait vient dans une version ultérieure
(`CONTRACTIONS`), avec sa preuve sans perte lue sur la production
(`PREUVES_SANS_PERTE`).

Rejouable : la colonne n'est retirée que si elle est là. Retour : elle revient,
recomposée depuis les centimes — la version précédente ne la lit pas, mais la
v3.125 la lirait.
"""

import sqlalchemy as sa
from alembic import op

from app.utils.colonnes_presentes import colonnes_presentes

revision = "0354"
down_revision = "0353"
branch_labels = None
depends_on = None

TABLE = "petite_annonce"  # identifiant, constante du fichier
COLONNE = "prix"


def upgrade():
    if COLONNE in colonnes_presentes(op.get_bind(), TABLE):
        op.drop_column(TABLE, COLONNE)


def downgrade():
    if COLONNE not in colonnes_presentes(op.get_bind(), TABLE):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Float, nullable=True))
        op.execute(
            sa.text(
                "UPDATE petite_annonce SET prix = prix_centimes / 100.0 "
                "WHERE prix_centimes IS NOT NULL"
            )
        )
