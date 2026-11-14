"""Un message de l'affaire retient l'entrée d'Historique qu'il a inscrite (#2722).

Modifier ou supprimer sa réponse doit suivre son miroir dans l'Historique : sans
renvoi, on le chercherait par la date, que le message et son entrée ne partagent pas
à la microseconde.

Colonne additive et nullable : un message d'avant ce lot n'a pas de renvoi, et l'image
précédente l'ignore (#1757).

Revision ID: 0337
Revises: 0336
"""

import sqlalchemy as sa
from alembic import op

revision = "0337"
down_revision = "0336"
branch_labels = None
depends_on = None


TABLE = "message_ticket"  # identifiant : constante du fichier


def _presentes() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if "evolution_id" not in _presentes():
        op.add_column(
            TABLE,
            sa.Column(
                "evolution_id", sa.Integer(), sa.ForeignKey("ticket_evolution.id"), nullable=True
            ),
        )


def downgrade() -> None:
    pass  # additive : revenir en arrière est un changement d'image (#1757)
