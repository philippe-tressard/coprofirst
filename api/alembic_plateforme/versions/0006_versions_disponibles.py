"""Les VERSIONS PUBLIÉES, et le canal Urgence ou une version choisie (#2210).

- `version_disponible` : les versions dont le tag a sa release et l'archive de
  déploiement, relues chaque nuit (`registre/canaux.relire_versions`).
- Les installations passent au nouveau suivi (`registre/canaux.suivi_de`) : une
  version épinglée devient la version choisie, en vague Fixe (3) ; un canal-branche
  (`replica`, `special-…`) devient Urgence, en vague Standard (2) — une mineure de
  recul, rodée 7 jours ; jamais la vague Urgence par défaut. La référence (`main`) ne
  bouge pas.

Idempotente : rejouée, elle ne touche plus rien — une version épinglée a été
vidée, un canal déjà `urgence` ou `X.Y.Z` est laissé tel quel (le choix de
l'opérateur n'est jamais réécrit).

Compatible avec l'image précédente : elle ne connaît ni `urgence` ni un canal
`X.Y.Z`, n'y trouve aucun canal, et son bail ne porte alors aucune version — pas de
mise à jour pendant le retour arrière, jamais une mauvaise. `canal_distribution`
reste, plus lue : elle se retire dans un second temps.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

VERSION = "version_disponible"
INSTALLATION = "installation"
MOTIF = r"^[0-9]+\.[0-9]+\.[0-9]+$"

#: La reprise des installations — rejouable à vide (`test_registre_canaux_migration`).
REPRISES = (
    text(
        "UPDATE installation SET canal = version_epinglee, vague = 3, version_epinglee = NULL "
        "WHERE canal <> 'main' AND version_epinglee ~ :motif"
    ).bindparams(motif=MOTIF),
    text(
        "UPDATE installation SET canal = 'urgence', vague = 2, version_epinglee = NULL "
        "WHERE canal NOT IN ('main', 'urgence') AND canal !~ :motif"
    ).bindparams(motif=MOTIF),
)


def upgrade():
    op.create_table(
        VERSION,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("version", sa.String(40), nullable=False, unique=True),
        sa.Column("publiee_le", sa.DateTime, nullable=False),
        sa.Column("lue_le", sa.DateTime, nullable=False),
    )
    #  Une inscription neuve suit Standard (`canaux.VAGUE_DEFAUT`).
    op.alter_column(INSTALLATION, "vague", server_default="2")
    for reprise in REPRISES:
        op.execute(reprise)


def downgrade():
    op.alter_column(INSTALLATION, "vague", server_default="1")
    op.execute(text("UPDATE installation SET canal = 'replica', vague = 1 WHERE canal <> 'main'"))
    op.drop_table(VERSION)
