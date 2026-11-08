"""Chacun choisit sa saisie d'une affaire : Essentielle ou Complète (#2595, 08/11/2026).

La préférence vit sur le compte, pour tous les appareils. `NULL` = « selon mon
rôle » : le défaut se calcule à la lecture (`utils/saisie_affaire`), il ne s'écrit
pas — un résident élu au conseil change de défaut sans migration de données.

Colonne additive et nullable : rien ne change pour personne tant qu'il n'y touche
pas, et l'image précédente l'ignore (#1757).

Revision ID: 0328
Revises: 0327
"""

import sqlalchemy as sa
from alembic import op

revision = "0328"
down_revision = "0327"
branch_labels = None
depends_on = None


TABLE = "utilisateur"  # identifiant : constante du fichier
COLONNE = "saisie_affaire"  # identifiant : constante du fichier


def _presente() -> bool:
    return COLONNE in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if not _presente():
        op.add_column(TABLE, sa.Column(COLONNE, sa.String(), nullable=True))


def downgrade() -> None:
    if _presente():
        op.drop_column(TABLE, COLONNE)
