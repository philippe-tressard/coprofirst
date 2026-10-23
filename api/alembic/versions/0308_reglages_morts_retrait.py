"""Second temps du retrait des réglages morts : les colonnes partent (#2124, #2059)

Le code a cessé d'en dépendre en v3.11.0 (premier temps, `CONTRACTIONS` de
`test_migrations_compatibles.py`), et la 0307 leur a donné un défaut. Cette
migration, d'une version ultérieure, les retire :

- `config_sauvegarde.frequence`, `jour_semaine`, `jour_mois`, et le type
  `frequencesauvegarde` qui ne sert plus qu'à la première ;
- `modele_email.corps_texte` ;
- `copropriete.assurance_compagnie`, `assurance_numero_police`, `assurance_echeance`
  (la fiche lit l'assurance sur le contrat, `assurance_contrat_id`, qui reste).

Retrait accordé par Philippe le 23/10/2026 : les valeurs ne se retrouvent plus
que dans les sauvegardes d'avant. L'image précédente (v3.11.x et plus) ne lit ni
n'écrit ces colonnes : revenir en arrière reste un changement d'image (#1757).

Une base neuve n'a pas ces colonnes (le schéma courant vient des modèles) : la
migration ne retire que ce qui existe. Les appels sont écrits un par un, en
littéraux : c'est ce que `test_migrations_compatibles.py` sait lire.

Revision ID: 0308
Revises: 0307
"""

import sqlalchemy as sa

from alembic import op

revision = "0308"
down_revision = "0307"
branch_labels = None
depends_on = None


def _existe(table: str, colonne: str) -> bool:
    return colonne in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if _existe("config_sauvegarde", "frequence"):
        op.drop_column("config_sauvegarde", "frequence")
    if _existe("config_sauvegarde", "jour_semaine"):
        op.drop_column("config_sauvegarde", "jour_semaine")
    if _existe("config_sauvegarde", "jour_mois"):
        op.drop_column("config_sauvegarde", "jour_mois")
    if _existe("modele_email", "corps_texte"):
        op.drop_column("modele_email", "corps_texte")
    if _existe("copropriete", "assurance_compagnie"):
        op.drop_column("copropriete", "assurance_compagnie")
    if _existe("copropriete", "assurance_numero_police"):
        op.drop_column("copropriete", "assurance_numero_police")
    if _existe("copropriete", "assurance_echeance"):
        op.drop_column("copropriete", "assurance_echeance")
    #  Le type ne portait que `frequence` : sans elle, plus rien ne le cite.
    sa.Enum(name="frequencesauvegarde").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    #  Les colonnes reviennent nullables et vides : les valeurs ne se recréent pas.
    op.add_column("copropriete", sa.Column("assurance_echeance", sa.Date(), nullable=True))
    op.add_column("copropriete", sa.Column("assurance_numero_police", sa.String(), nullable=True))
    op.add_column("copropriete", sa.Column("assurance_compagnie", sa.String(), nullable=True))
    op.add_column(
        "modele_email",
        sa.Column("corps_texte", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "config_sauvegarde",
        sa.Column("jour_mois", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "config_sauvegarde",
        sa.Column("jour_semaine", sa.Integer(), nullable=False, server_default="6"),
    )
    #  Le type et sa colonne, tels que la production les porte : c'est ce qui fait
    #  éprouver à `test_migration_de_tete` le retrait du type APRÈS celui de la colonne.
    frequence = sa.Enum("quotidienne", "hebdomadaire", "mensuelle", name="frequencesauvegarde")
    frequence.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "config_sauvegarde",
        sa.Column("frequence", frequence, nullable=False, server_default="quotidienne"),
    )
