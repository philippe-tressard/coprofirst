"""La plateforme d'un appareil : `apns` (iPhone) ou `fcm` (Android) — #2789, 16/11/2026.

Colonne ADDITIVE, `server_default 'apns'` : tout appareil enregistré avant ce lot est un
iPhone, et l'image précédente ignore la colonne (#1757).

Revision ID: 0340
Revises: 0339
"""

import sqlalchemy as sa
from alembic import op

revision = "0340"
down_revision = "0339"
branch_labels = None
depends_on = None

TABLE = "appareil"  # identifiant : constante du fichier


def _presentes() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if "plateforme" not in _presentes():
        op.add_column(
            TABLE,
            sa.Column("plateforme", sa.String(), nullable=False, server_default="apns"),
        )


def downgrade() -> None:
    pass  # additive : revenir en arrière est un changement d'image (#1757)
