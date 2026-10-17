"""La CONSERVATION des affaires, lot L2 (#2014)

- `ticket.conservee_le` : le jour où l'affaire échue a perdu ses pièces jointes
  et ses auteurs ; elle n'est jamais retraitée.
- `auteur_qualite` sur `ticket`, `message_ticket` et `ticket_evolution` : ce que
  l'auteur détaché était à l'échéance (« resident », « conseil »).
- la table `archive_affaires` : une archive par exercice et par type, suivie
  jusqu'à sa copie sur le PC et son retrait du serveur.

Additive : des colonnes nullables et une table neuve, que l'image précédente
ignore (règle #1757, `test_migrations_compatibles.py`). Idempotente.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0295
Revises: 0294
"""

import sqlalchemy as sa

from alembic import op

revision = "0295"
down_revision = "0294"
branch_labels = None
depends_on = None

TICKET = "ticket"  # identifiants : constantes du fichier
CONSERVEE_LE = "conservee_le"
QUALITE = "auteur_qualite"
TABLES_QUALITE = ("ticket", "message_ticket", "ticket_evolution")
ARCHIVE = "archive_affaires"


def _inspecteur():
    return sa.inspect(op.get_bind())


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in _inspecteur().get_columns(table)}


def upgrade():
    if CONSERVEE_LE not in _colonnes(TICKET):
        op.add_column(TICKET, sa.Column(CONSERVEE_LE, sa.DateTime, nullable=True))
    for table in TABLES_QUALITE:
        if QUALITE not in _colonnes(table):
            op.add_column(table, sa.Column(QUALITE, sa.String, nullable=True))
    if not _inspecteur().has_table(ARCHIVE):
        op.create_table(
            ARCHIVE,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("nom", sa.String, nullable=False, unique=True, index=True),
            sa.Column("cle", sa.String, nullable=False),
            sa.Column("exercice", sa.String, nullable=False),
            sa.Column("type", sa.String, nullable=False),
            sa.Column("empreinte", sa.String, nullable=False),
            sa.Column("octets", sa.Integer, nullable=False, server_default="0"),
            sa.Column("affaires", sa.Integer, nullable=False, server_default="0"),
            sa.Column("fichiers", sa.Integer, nullable=False, server_default="0"),
            sa.Column("cree_le", sa.DateTime, nullable=False),
            sa.Column("copiee_le", sa.DateTime, nullable=True),
            sa.Column("retiree_le", sa.DateTime, nullable=True),
        )


def downgrade():
    if _inspecteur().has_table(ARCHIVE):
        op.drop_table(ARCHIVE)
    for table in TABLES_QUALITE:
        if QUALITE in _colonnes(table):
            with op.batch_alter_table(table) as batch:
                batch.drop_column(QUALITE)
    if CONSERVEE_LE in _colonnes(TICKET):
        with op.batch_alter_table(TICKET) as batch:
            batch.drop_column(CONSERVEE_LE)
