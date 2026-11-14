"""La mesure d'audience distingue le CANAL d'accès : site web, app iPhone, app Android.

Demandé le 14/11/2026 : savoir, pour une page consultée, si elle l'a été depuis le
site ou depuis l'application — « c'est important de comprendre comment l'appli est
consommée ». Règle et libellés : `app/utils/canaux_audience.py`.

- `telemetry_event.canal` : colonne additive, `'site'` par défaut (`server_default`) —
  l'image précédente insère sans la connaître (#1757), et chaque vue enregistrée
  jusqu'ici venait du site, seul client qui collectait.
- `audience_canal_jour` et `audience_canal_mois` : les vues par page, par canal et par
  série du gestionnaire. Tables À PART des agrégats `telemetry_daily|monthly`, que
  leurs lecteurs continuent de lire tels quels.
- Reprise de l'historique : les agrégats existants y sont recopiés en `'site'` — vrai
  pour la même raison. Sans elle, l'écran dirait « 0 % site » pour tout ce qui
  précède ce lot.

Rejouable : chaque étape vérifie ce qui est déjà là (0312).

Revision ID: 0335
Revises: 0334
"""

import sqlalchemy as sa
from alembic import op

revision = "0335"
down_revision = "0334"
branch_labels = None
depends_on = None

#  Identifiants : constantes du fichier.
EVENEMENTS = "telemetry_event"
COLONNE = "canal"
SITE = "site"
#: (table de répartition, colonne de période, agrégat d'où reprendre l'historique)
REPARTITIONS = (
    ("audience_canal_jour", "jour", "telemetry_daily"),
    ("audience_canal_mois", "mois", "telemetry_monthly"),
)
#: La ligne « total du jour » des agrégats (`telemetry_aggregation.PAGE_TOTAL`) : la
#: répartition n'en a pas, les vues s'y additionnent page par page.
PAGE_TOTAL = "__total__"


def _inspecteur():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    inspecteur = _inspecteur()
    if COLONNE not in {c["name"] for c in inspecteur.get_columns(EVENEMENTS)}:
        op.add_column(
            EVENEMENTS,
            sa.Column(COLONNE, sa.String(), nullable=False, server_default=SITE),
        )
    tables = set(inspecteur.get_table_names())
    for table, periode, source in REPARTITIONS:
        if table in tables:
            continue
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(periode, sa.String(), nullable=False),
            sa.Column("page", sa.String(), nullable=False),
            sa.Column("canal", sa.String(), nullable=False),
            sa.Column("gestionnaire", sa.Boolean(), nullable=True),
            sa.Column("vues", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index(f"ix_{table}_{periode}", table, [periode])
        _reprendre(table, periode, source)


def _reprendre(table: str, periode: str, source: str) -> None:
    """Recopie l'agrégat `source` en vues du site — composé par SQLAlchemy, sans f-string SQL."""
    src = sa.table(
        source,
        sa.column(periode),
        sa.column("page"),
        sa.column("gestionnaire"),
        sa.column("total"),
    )
    cible = sa.table(
        table,
        sa.column(periode),
        sa.column("page"),
        sa.column("canal"),
        sa.column("gestionnaire"),
        sa.column("vues"),
    )
    lignes = (
        sa.select(
            src.c[periode],
            src.c.page,
            sa.literal(SITE),
            src.c.gestionnaire,
            sa.func.sum(src.c.total),
        )
        .where(src.c.page != PAGE_TOTAL)
        .group_by(src.c[periode], src.c.page, src.c.gestionnaire)
    )
    op.get_bind().execute(
        sa.insert(cible).from_select([periode, "page", "canal", "gestionnaire", "vues"], lignes)
    )


def downgrade() -> None:
    inspecteur = _inspecteur()
    tables = set(inspecteur.get_table_names())
    for table, periode, _ in REPARTITIONS[::-1]:
        if table in tables:
            op.drop_index(f"ix_{table}_{periode}", table_name=table)
            op.drop_table(table)
    if COLONNE in {c["name"] for c in inspecteur.get_columns(EVENEMENTS)}:
        op.drop_column(EVENEMENTS, COLONNE)
