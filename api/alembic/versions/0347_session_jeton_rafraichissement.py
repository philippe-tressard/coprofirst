"""La session d'un jeton de rafraîchissement (23/11/2026).

La déconnexion ferme la SESSION présentée, jetons d'accès compris : le jeton
d'accès porte l'identifiant de sa session, que portent aussi les jetons de
rafraîchissement de la même session, d'une rotation à la suivante
(`app/auth/jetons_rafraichissement.py`).

Colonne additive et NULLABLE : `NULL` = un jeton émis avant ce lot, qui ne porte
pas de session. L'image précédente insère sans la connaître (#1757) ; il n'y a
rien à reprendre — la rotation suivante en pose une neuve.

Rejouable : la colonne et l'index ne sont créés que s'ils manquent (0312).

Revision ID: 0347
Revises: 0346
"""

import sqlalchemy as sa
from alembic import op

revision = "0347"
down_revision = "0346"
branch_labels = None
depends_on = None

#  Identifiants : constantes du fichier.
TABLE = "refresh_token"
COLONNE = "session_id"
INDEX = "ix_refresh_token_session_id"


def upgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    if COLONNE not in {c["name"] for c in inspecteur.get_columns(TABLE)}:
        op.add_column(TABLE, sa.Column(COLONNE, sa.String(), nullable=True))
    if INDEX not in {i["name"] for i in inspecteur.get_indexes(TABLE)}:
        op.create_index(INDEX, TABLE, [COLONNE])


def downgrade() -> None:
    pass  # additive : revenir en arrière est un changement d'image (#1757)
