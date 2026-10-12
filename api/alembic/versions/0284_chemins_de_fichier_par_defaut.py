"""Les anciens chemins de fichier reçoivent un défaut : le code cesse de les déclarer (#1816)

Second temps de #1816, premier temps d'une contraction (règle #1757,
`test_migrations_compatibles.py`). Depuis la 0283, le document, le rapport de
diagnostic et l'affiche de hall gardent la CLÉ de leur fichier ; ce lot cesse
de lire et d'écrire le chemin absolu, et retire `fichier_chemin` et
`pdf_chemin` des modèles. Les colonnes, elles, restent jusqu'à une version
ULTÉRIEURE : la version précédente les écrit encore, et revenir à son image ne
doit pas demander de restaurer la base.

## Pourquoi un défaut

Le modèle cessant de les déclarer, l'application insère des lignes SANS ces
colonnes. Elles sont `NOT NULL`, et une base née du schéma courant
(`utils/schema_initial`, `create_all`) n'y porte AUCUN défaut — c'est le cas de
la production depuis le passage sous PostgreSQL : tout dépôt de document, de
rapport ou d'affiche y échouerait. La migration pose `''` là où il manque, et
seulement là. Sous SQLite, `batch_alter_table` recrée la table : réservé aux
bases qui en ont besoin.

La version précédente relit une ligne neuve par sa clé (`stockage().cle_de`
préfère `…_cle`) : un chemin vide ne la gêne pas.

Idempotente : rejouée, elle trouve le défaut posé ; une colonne déjà retirée
est ignorée.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0284
Revises: 0283
"""

import sqlalchemy as sa

from alembic import op

revision = "0284"
down_revision = "0283"
branch_labels = None
depends_on = None

#: (table, colonne) — identifiants : constantes du fichier.
COLONNES = (
    ("document", "fichier_chemin"),
    ("diagnostic_rapport", "fichier_chemin"),
    ("annonce_hall", "pdf_chemin"),
)


def _colonne(conn, table: str, nom: str) -> dict | None:
    inspecteur = sa.inspect(conn)
    if table not in inspecteur.get_table_names():
        return None
    for c in inspecteur.get_columns(table):
        if c["name"] == nom:
            return c
    return None


def upgrade():
    conn = op.get_bind()
    for table, nom in COLONNES:
        colonne = _colonne(conn, table, nom)
        if colonne is None or colonne.get("default") is not None:
            continue
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                nom,
                existing_type=sa.String(),
                existing_nullable=colonne["nullable"],
                server_default="",
            )


def downgrade():
    #  Rien à défaire : un défaut ne gêne aucune version du code, et la version
    #  précédente écrit la colonne elle-même.
    pass
