"""Un jeton de rafraîchissement rejoué invalide aussi les jetons d'accès (#2481, 03/11/2026).

Le jeton d'accès porte l'empreinte du compte (#1063) : celle du condensé du mot
de passe, et désormais de `generation_sessions`, que la détection d'un rejeu
incrémente. Tous les jetons d'accès du compte tombent alors au geste suivant —
celui du voleur compris —, comme après un mot de passe changé.

Colonne additive, nulle par défaut (`server_default`) : une génération 0 donne
l'empreinte d'avant ce lot (`jwt.empreinte_du_compte`), donc aucun jeton en
cours ne tombe à la mise en production ; l'image précédente l'ignore (#1757).

Revision ID: 0322
Revises: 0321
"""

import sqlalchemy as sa
from alembic import op

revision = "0322"
down_revision = "0321"
branch_labels = None
depends_on = None


TABLE = "utilisateur"  # identifiant : constante du fichier
COLONNE = "generation_sessions"  # identifiant : constante du fichier


def _presente() -> bool:
    return COLONNE in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if not _presente():
        op.add_column(
            TABLE, sa.Column(COLONNE, sa.Integer(), nullable=False, server_default=sa.text("0"))
        )


def downgrade() -> None:
    if _presente():
        op.drop_column(TABLE, COLONNE)
