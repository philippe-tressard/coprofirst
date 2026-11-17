"""La mesure d'audience garde la CLASSE d'appareil, sous le canal (#2774, 15/11/2026).

« Pour la télémétrie, tu décomposeras en web, iOS et Android et si possible tu
éclateras pour l'OS concerné sur le matériel. » Règle et libellés :
`app/utils/canaux_audience.py` (`APPAREILS_PAR_CANAL`).

- `telemetry_event.appareil` : colonne additive et NULLABLE — `NULL` = « non précisé ».
  L'image précédente insère sans la connaître (#1757), et aucune vue d'avant ce lot ne
  disait son appareil : il n'y a rien à reprendre.
- `audience_canal_jour.appareil` et `audience_canal_mois.appareil` : la même dimension
  dans la répartition agrégée, NULLABLE pour la même raison.

Rejouable : chaque colonne n'est ajoutée que si elle manque (0312).

Revision ID: 0344
Revises: 0343
"""

import sqlalchemy as sa
from alembic import op

revision = "0344"
down_revision = "0343"
branch_labels = None
depends_on = None

#  Identifiants : constantes du fichier.
COLONNE = "appareil"
TABLES = ("telemetry_event", "audience_canal_jour", "audience_canal_mois")


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for table in TABLES:
        if COLONNE not in _colonnes(table):
            op.add_column(table, sa.Column(COLONNE, sa.String(), nullable=True))


def downgrade() -> None:
    for table in TABLES[::-1]:
        if COLONNE in _colonnes(table):
            op.drop_column(table, COLONNE)
