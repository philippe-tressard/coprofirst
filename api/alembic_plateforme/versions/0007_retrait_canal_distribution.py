"""Le second temps de #3098 : la table `canal_distribution` quitte la base du registre.

Premier temps en v3.126.1 (#3120) : le modèle a quitté le registre, la contraction est
annoncée (`CONTRACTIONS`, version 3.125.9). Plus rien ne la lit depuis #2210, et le
workflow qui l'avançait est retiré depuis v3.125.1 (#3009).

Sans perte, lu sur la production le 28/11/2026 (`PREUVES_SANS_PERTE`) : une ligne,
`replica|3.11.7|3.6.1`, le canal-branche retiré, que rien ne reprend ni ne lit.

Compatible avec l'image précédente : depuis v3.126.1, son code ne déclare plus la table
et ne la lit pas. Les sauvegardes d'avant la portent : l'import l'écarte
(`import_copropriete.TABLES_RETIREES`, qui garde son entrée).

Le retour arrière recrée la table VIDE, à sa forme de la 0005 : sa ligne, que plus
aucun code ne lisait, n'est pas rendue.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

CANAL = "canal_distribution"


def upgrade():
    op.drop_table(CANAL)


def downgrade():
    op.create_table(
        CANAL,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nom", sa.String(60), nullable=False, unique=True),
        sa.Column("version", sa.String(40), nullable=True),
        sa.Column("version_precedente", sa.String(40), nullable=True),
        sa.Column("avance_le", sa.DateTime, nullable=True),
        sa.Column("cree_le", sa.DateTime, nullable=False),
    )
