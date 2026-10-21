"""Premier temps du retrait des réglages morts : un défaut aux colonnes que le code n'écrit plus (#2059)

Le code cesse de déclarer `config_sauvegarde.frequence|jour_semaine|jour_mois` et
`modele_email.corps_texte` (aucune lecture : la sauvegarde est quotidienne depuis la
0139, le texte brut d'un modèle n'a jamais servi), ainsi que les colonnes
`copropriete.assurance_*` (la fiche lit le contrat depuis #490).

Les trois dernières sont nullables : rien à faire. Les quatre premières sont
`NOT NULL` sans défaut en base — le modèle les remplissait. Sans lui, la première
insertion d'une ligne (`ConfigSauvegarde()` quand la table est vide, un modèle
d'e-mail neuf du seed) échouerait. Cette migration leur pose un défaut, et c'est tout :
rien n'est retiré (« ajouter, puis retirer », #1757 — le retrait, un second temps
annoncé dans `CONTRACTIONS`, vient dans une version ultérieure). L'image précédente
écrit ces colonnes comme avant.

Une base neuve n'a pas ces colonnes (le schéma courant vient des modèles) : la
migration ne touche que ce qui existe.

Revision ID: 0306
Revises: 0305
"""

import sqlalchemy as sa

from alembic import op

revision = "0306"
down_revision = "0305"
branch_labels = None
depends_on = None

#: (table, colonne, défaut SQL) — identifiants : constantes du fichier.
DEFAUTS = (
    ("config_sauvegarde", "frequence", "'quotidienne'"),
    ("config_sauvegarde", "jour_semaine", "6"),
    ("config_sauvegarde", "jour_mois", "1"),
    ("modele_email", "corps_texte", "''"),
)


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
