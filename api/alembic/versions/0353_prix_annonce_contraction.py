"""Le prix d'une petite annonce, contraction — premier temps (#3011).

L'expansion (0352, v3.125.0) a posé `prix_centimes` à côté de `prix` (euros, en
flottant). Le code ne lit et n'écrit plus que `prix_centimes` ; la colonne `prix`
reste en base jusqu'au second temps (`drop_column`, une version ultérieure,
`CONTRACTIONS`). Cette migration la VIDE, en deux gestes :

1. elle applique d'abord la règle de lecture de la version précédente
   (`utils/prix_annonce` de la v3.125) : là où `prix` est posé et que les centimes
   manquent ou disent autre chose, c'est `prix` qui porte la dernière saisie — les
   centimes la reprennent, arrondis par `numeric` comme dans la 0352 ;
2. puis elle met `prix` à NULL. Une annonce corrigée après cette version ne change
   que ses centimes : sans ce vidage, un retour arrière vers la v3.125 lirait l'ancien
   prix, resté dans `prix`, et le préférerait aux centimes.

Rejouable, et sans effet sur un schéma neuf (né des modèles, donc sans `prix`).
Retour : `prix` se recompose depuis les centimes.
"""

import sqlalchemy as sa
from alembic import op

from app.utils.colonnes_presentes import colonnes_presentes

revision = "0353"
down_revision = "0352"
branch_labels = None
depends_on = None

TABLE = "petite_annonce"  # identifiant, constante du fichier
ANCIENNE = "prix"


def upgrade():
    if ANCIENNE not in colonnes_presentes(op.get_bind(), TABLE):
        return
    op.execute(
        sa.text(
            "UPDATE petite_annonce "
            "SET prix_centimes = CAST(ROUND(CAST(prix AS numeric) * 100) AS integer) "
            "WHERE prix IS NOT NULL AND (prix_centimes IS NULL "
            "OR prix_centimes <> CAST(ROUND(CAST(prix AS numeric) * 100) AS integer))"
        )
    )
    op.execute(sa.text("UPDATE petite_annonce SET prix = NULL WHERE prix IS NOT NULL"))


def downgrade():
    if ANCIENNE not in colonnes_presentes(op.get_bind(), TABLE):
        return
    op.execute(
        sa.text(
            "UPDATE petite_annonce SET prix = prix_centimes / 100.0 "
            "WHERE prix IS NULL AND prix_centimes IS NOT NULL"
        )
    )
