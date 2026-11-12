"""Un contrat peut être résilié et remplacé par un autre : `resilie_le`, `remplace_par_id`.

Demandé à l'écran (12/11/2026) : « Pour un contrat / prestataire : comment préciser
qu'un prestataire est remplacé par un autre — après vérification, la résiliation de
SPEM est effective au 17 novembre, lancez votre contrat au 18 novembre (BOUVIER). »

Deux colonnes sur l'ANCIEN contrat, jamais sur le nouveau : la date et le renvoi se
saisissent au même endroit, et le sens inverse (« remplace SPEM ») se déduit à la
lecture — une seule vérité, pas deux colonnes libres de se contredire.

Colonnes additives et nullables : un contrat d'avant ce lot n'est ni résilié ni
remplacé, et l'image précédente les ignore (#1757).

Revision ID: 0334
Revises: 0333
"""

import sqlalchemy as sa
from alembic import op

revision = "0334"
down_revision = "0333"
branch_labels = None
depends_on = None


TABLE = "contrat_entretien"  # identifiant : constante du fichier
COLONNES = ("resilie_le", "remplace_par_id")  # identifiants : constantes du fichier


def _presentes() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    presentes = _presentes()
    if "resilie_le" not in presentes:
        op.add_column(TABLE, sa.Column("resilie_le", sa.Date(), nullable=True))
    if "remplace_par_id" not in presentes:
        op.add_column(
            TABLE,
            sa.Column(
                "remplace_par_id",
                sa.Integer(),
                sa.ForeignKey("contrat_entretien.id"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    presentes = _presentes()
    for colonne in COLONNES[::-1]:
        if colonne in presentes:
            op.drop_column(TABLE, colonne)
