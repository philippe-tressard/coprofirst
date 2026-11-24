"""Le mot de passe temporaire d'un compte initial se change à la première connexion (#3019).

Le seed crée l'administrateur et l'opérateur d'une installation neuve avec un mot de
passe tiré au sort, écrit au journal du conteneur (#2973) ; rien n'imposait de le
changer. Décision du 23/11/2026 : tant que ce drapeau tient, le compte ne peut que lire
son profil, changer son mot de passe et se déconnecter (`app/auth/mot_de_passe_a_changer`).
Le seed le pose ; `utils/mots_de_passe.poser_mot_de_passe` le retire.

Colonne additive, FAUSSE par défaut (`server_default`) : aucun compte existant n'est
touché — seule une installation neuve la voit vraie, sur ses deux comptes initiaux —,
et l'image précédente l'ignore (#1757).

Revision ID: 0350
Revises: 0349
"""

import sqlalchemy as sa
from alembic import op

revision = "0350"
down_revision = "0349"
branch_labels = None
depends_on = None


TABLE = "utilisateur"  # identifiant : constante du fichier
COLONNE = "mot_de_passe_a_changer"  # identifiant : constante du fichier


def _presente() -> bool:
    return COLONNE in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if not _presente():
        op.add_column(
            TABLE, sa.Column(COLONNE, sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    if _presente():
        op.drop_column(TABLE, COLONNE)
