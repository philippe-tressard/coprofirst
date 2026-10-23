"""Premier temps du retrait de `config_sauvegarde.active` : un défaut à la colonne (#2182)

La colonne n'est plus lue depuis #2060 (« la sauvegarde ne se coupe PAS »), et le
code cesse de la déclarer : le modèle `ConfigSauvegarde` n'a plus de champ `active`.
Elle est `NOT NULL` sans défaut en base — le modèle la remplissait. Sans lui, la
première insertion d'une ligne (`ConfigSauvegarde()` quand la table est vide) échoue.
Cette migration lui pose un défaut (vrai, comme le modèle), et c'est tout : rien n'est
retiré (« ajouter, puis retirer », #1757 — le retrait, un second temps annoncé dans
`CONTRACTIONS` de `test_migrations_compatibles.py`, vient dans une version
ultérieure). L'image précédente écrit la colonne comme avant.

Une base neuve n'a pas cette colonne (le schéma courant vient des modèles) : la
migration ne touche que ce qui existe.

Revision ID: 0310
Revises: 0309
"""

import sqlalchemy as sa

from alembic import op

revision = "0310"
down_revision = "0309"
branch_labels = None
depends_on = None

#: (table, colonne, défaut SQL) — identifiants : constantes du fichier.
DEFAUTS = (("config_sauvegarde", "active", "true"),)


def _colonnes(table: str) -> dict[str, dict]:
    return {c["name"]: c for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for table, colonne, defaut in DEFAUTS:
        existantes = _colonnes(table)
        if colonne in existantes and existantes[colonne].get("default") is None:
            op.alter_column(table, colonne, server_default=sa.text(defaut))


def downgrade() -> None:
    for table, colonne, _defaut in DEFAUTS:
        if colonne in _colonnes(table):
            op.alter_column(table, colonne, server_default=None)
