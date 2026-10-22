"""Second temps du retrait des réglages morts : les colonnes quittent la base (#2124)

Premier temps en v3.11.0 (#2059, 0307) : le code a cessé de déclarer ces colonnes,
et `CONTRACTIONS` (`tests/test_migrations_compatibles.py`) l'annonce. Elles sont
retirées ici, dans une version ultérieure, comme le veut « ajouter, puis retirer »
(#1757) : l'image précédente — la v3.11.x — ne les lit ni ne les écrit plus, un
retour arrière reste un simple changement d'image.

- `config_sauvegarde.frequence`, `jour_semaine`, `jour_mois`, et le type énuméré
  `frequencesauvegarde` qui ne servait qu'à la première ;
- `modele_email.corps_texte` ;
- `copropriete.assurance_compagnie`, `assurance_numero_police`, `assurance_echeance`.

Une base neuve n'a ni ces colonnes ni ce type (son schéma vient des modèles) : la
migration ne retire que ce qui existe. La 0307 reste telle quelle — une migration
appliquée ne se modifie pas.

Revision ID: 0308
Revises: 0307
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0308"
down_revision = "0307"
branch_labels = None
depends_on = None

#: Le type énuméré de `frequence` — identifiant : constante du fichier.
TYPE_FREQUENCE = "frequencesauvegarde"
VALEURS_FREQUENCE = ("quotidienne", "hebdomadaire", "mensuelle")

#: Ce que `downgrade` rend : (table, colonne, type, défaut SQL) — identifiants : constantes
#: du fichier. Le type et le défaut sont ceux de l'ancien modèle (0307 pour les défauts).
RETIREES = (
    ("config_sauvegarde", "frequence", postgresql.ENUM(*VALEURS_FREQUENCE, name=TYPE_FREQUENCE,
     create_type=False), "'quotidienne'"),
    ("config_sauvegarde", "jour_semaine", sa.Integer(), "6"),
    ("config_sauvegarde", "jour_mois", sa.Integer(), "1"),
    ("modele_email", "corps_texte", sa.String(), "''"),
    ("copropriete", "assurance_compagnie", sa.String(), None),
    ("copropriete", "assurance_numero_police", sa.String(), None),
    ("copropriete", "assurance_echeance", sa.Date(), None),
)


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    #  Une cible LITTÉRALE par retrait : c'est ce que `test_migrations_compatibles`
    #  confronte à `CONTRACTIONS` — une cible tirée d'une boucle ne s'y lit pas.
    sauvegarde = _colonnes("config_sauvegarde")
    if "frequence" in sauvegarde:
        op.drop_column("config_sauvegarde", "frequence")
    if "jour_semaine" in sauvegarde:
        op.drop_column("config_sauvegarde", "jour_semaine")
    if "jour_mois" in sauvegarde:
        op.drop_column("config_sauvegarde", "jour_mois")
    if "corps_texte" in _colonnes("modele_email"):
        op.drop_column("modele_email", "corps_texte")
    copropriete = _colonnes("copropriete")
    if "assurance_compagnie" in copropriete:
        op.drop_column("copropriete", "assurance_compagnie")
    if "assurance_numero_police" in copropriete:
        op.drop_column("copropriete", "assurance_numero_police")
    if "assurance_echeance" in copropriete:
        op.drop_column("copropriete", "assurance_echeance")
    postgresql.ENUM(name=TYPE_FREQUENCE).drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    #  Rend les colonnes NULLABLES avec leur défaut : l'image d'avant la v3.11.0 les
    #  écrivait, celle de la v3.11.x les ignore — les deux démarrent.
    postgresql.ENUM(*VALEURS_FREQUENCE, name=TYPE_FREQUENCE).create(op.get_bind(), checkfirst=True)
    for table, colonne, type_, defaut in RETIREES:
        if colonne not in _colonnes(table):
            op.add_column(
                table,
                sa.Column(
                    colonne,
                    type_,
                    nullable=True,
                    server_default=sa.text(defaut) if defaut else None,
                ),
            )
