"""Chacun peut éteindre pour lui le décor des jours de fête (#2312, 30/10/2026).

L'administration allume le décor pour la copropriété (Admin › Services) ; le
résident le garde ou l'éteint dans son Profil, pour tous ses appareils. Le choix
vit sur le compte, pas dans un cookie : aucun cookie de plus à déclarer.

Colonne additive, vraie par défaut (`server_default`) : rien ne change pour
personne tant qu'il n'y touche pas, et l'image précédente l'ignore (#1757).

Revision ID: 0320
Revises: 0319
"""

import sqlalchemy as sa
from alembic import op

revision = "0320"
down_revision = "0319"
branch_labels = None
depends_on = None


TABLE = "utilisateur"  # identifiant : constante du fichier
COLONNE = "decor_fetes"  # identifiant : constante du fichier


def _presente() -> bool:
    return COLONNE in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if not _presente():
        op.add_column(
            TABLE, sa.Column(COLONNE, sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    if _presente():
        op.drop_column(TABLE, COLONNE)
