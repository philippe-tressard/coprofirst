"""Le prix d'une petite annonce en centimes entiers — expansion (#3011).

`petite_annonce.prix` est la seule colonne monétaire en flottant (socle 06 §7 :
« montants en entiers, jamais en flottant »). Premier temps de deux (#1757) :

- une colonne `prix_centimes`, entière et nullable — la version précédente du
  code insère sans la connaître ;
- reprise : chaque prix posé y est recopié, arrondi au centime par
  `ROUND(prix::numeric * 100)` — `numeric` et non `double precision`, sur lequel
  19,99 × 100 vaut 1 998,999… ; la moitié s'éloigne de zéro, comme
  `utils/montants.en_centimes` ;
- `prix` reste, écrite et lue par `utils/prix_annonce` ; elle sortira par une
  contraction, dans une version ultérieure.

Rejouable : la colonne n'est ajoutée que si elle manque, et la reprise ne remplit
que les lignes encore vides.
"""

import sqlalchemy as sa
from alembic import op

from app.utils.colonnes_presentes import colonnes_presentes

revision = "0351"
down_revision = "0350"
branch_labels = None
depends_on = None

TABLE = "petite_annonce"  # identifiant, constante du fichier
COLONNE = "prix_centimes"


def upgrade():
    if COLONNE not in colonnes_presentes(op.get_bind(), TABLE):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer, nullable=True))
    op.execute(
        sa.text(
            "UPDATE petite_annonce SET prix_centimes = CAST(ROUND(CAST(prix AS numeric) * 100) AS integer) "
            "WHERE prix IS NOT NULL AND prix_centimes IS NULL"
        )
    )


def downgrade():
    if COLONNE in colonnes_presentes(op.get_bind(), TABLE):
        op.drop_column(TABLE, COLONNE)
