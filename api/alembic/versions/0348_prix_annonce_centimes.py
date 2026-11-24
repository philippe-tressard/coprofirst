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

revision = "0348"
down_revision = "0347"
branch_labels = None
depends_on = None

TABLE = "petite_annonce"  # identifiant, constante du fichier
COLONNE = "prix_centimes"


def _colonnes() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade():
    if COLONNE not in _colonnes():
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer, nullable=True))
    op.execute(
        sa.text(
            "UPDATE petite_annonce SET prix_centimes = CAST(ROUND(CAST(prix AS numeric) * 100) AS integer) "
            "WHERE prix IS NOT NULL AND prix_centimes IS NULL"
        )
    )


def downgrade():
    if COLONNE in _colonnes():
        op.drop_column(TABLE, COLONNE)
