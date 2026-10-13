"""Les anciens chemins de fichier quittent le document, le rapport et l'affiche (#1816)

Second temps de la contraction (règle #1757, `test_migrations_compatibles.py`).
Le premier, v2.142.7, a retiré `fichier_chemin` et `pdf_chemin` du code ; la
0284 leur a donné le défaut sans lequel un dépôt aurait échoué. Plus rien ne
les lit ni ne les écrit : chaque fichier se situe par sa CLÉ dans le stockage
depuis la 0283. Revenir à v2.142.7 ne demande donc pas de restaurer la base —
ce code-là ne les déclare déjà plus.

## Comment elles partent

`op.drop_column`, un retrait en place, natif sous PostgreSQL comme sous SQLite ≥
3.35 — et PAS le mode `batch` d'Alembic, qui recopierait `document`, cible de
clés étrangères (même choix que la 0275). Aucune des trois colonnes n'est
indexée, clé ou contrainte.

Idempotente : `start.sh` a `set -e`, et un redémarrage après une migration
interrompue la rejoue. Table ou colonne absente → rien à faire. `downgrade` les
rétablit, vides avec leur défaut : les chemins d'origine ne reviennent pas, et
aucun code ne les lit.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0285
Revises: 0284
"""

import sqlalchemy as sa

from alembic import op

revision = "0285"
down_revision = "0284"
branch_labels = None
depends_on = None

#  Identifiants : constantes du fichier. Le contrôle de contraction lit la cible
#  de chaque `drop_column` dans ses arguments — un littéral ou une constante, d'où
#  trois appels écrits plutôt qu'une boucle.
DOCUMENT = "document"
DIAGNOSTIC = "diagnostic_rapport"
AFFICHE = "annonce_hall"
FICHIER = "fichier_chemin"
PDF = "pdf_chemin"
COLONNES = ((DOCUMENT, FICHIER), (DIAGNOSTIC, FICHIER), (AFFICHE, PDF))


def _colonnes(table: str) -> set[str] | None:
    """Les colonnes de la table, ou None si elle n'existe pas."""
    inspecteur = sa.inspect(op.get_bind())
    if table not in inspecteur.get_table_names():
        return None
    return {c["name"] for c in inspecteur.get_columns(table)}


def upgrade() -> None:
    if FICHIER in (_colonnes(DOCUMENT) or ()):
        op.drop_column(DOCUMENT, FICHIER)
    if FICHIER in (_colonnes(DIAGNOSTIC) or ()):
        op.drop_column(DIAGNOSTIC, FICHIER)
    if PDF in (_colonnes(AFFICHE) or ()):
        op.drop_column(AFFICHE, PDF)


def downgrade() -> None:
    for table, nom in COLONNES:
        presentes = _colonnes(table)
        if presentes is not None and nom not in presentes:
            op.add_column(table, sa.Column(nom, sa.String(), nullable=False, server_default=""))
