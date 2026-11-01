"""Les équipements s'administrent : une table, liée aux périmètres (#2442, 01/11/2026).

Les dix-huit valeurs de l'énumération `TypeEquipement` deviennent les lignes de
`equipement`, que l'administrateur complète dans Admin › Copropriété ›
Équipements. Les lignes de départ sont posées par le seed, sur une table vide
seulement (`seed.equipements_par_defaut`) : une migration n'écrit pas de
proposition qu'on peut ensuite supprimer.

`contrat_entretien.type_equipement` passe du type énuméré `typeequipement` au
texte : un équipement créé dans l'administration doit pouvoir s'y écrire.

## Compatibilité avec la version précédente (#1757)

Éprouvé sur PostgreSQL : l'ancien code (colonne déclarée `Enum`) insère, filtre
et lit une colonne texte sans erreur — le type `typeequipement` est GARDÉ pour
cela, il n'est pas retiré ici. Une seule limite, écrite plutôt que tue : un
équipement CRÉÉ après la mise à jour et posé sur un contrat ne se lit pas par
l'ancienne image (`LookupError` sur la liste des contrats). Le retour arrière par
changement d'image reste donc sûr tant que l'administration n'a rien ajouté ;
au-delà, repasser ces contrats en « autre » avant de revenir.

Revision ID: 0321
Revises: 0320
"""

import sqlalchemy as sa
from alembic import op

revision = "0321"
down_revision = "0320"
branch_labels = None
depends_on = None

EQUIPEMENT = "equipement"  # identifiant : constante du fichier
LIEN = "equipement_perimetre"  # identifiant : constante du fichier
CONTRAT = "contrat_entretien"  # identifiant : constante du fichier
COLONNE = "type_equipement"  # identifiant : constante du fichier


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _colonne_enumeree() -> bool:
    for c in sa.inspect(op.get_bind()).get_columns(CONTRAT):
        if c["name"] == COLONNE:
            return isinstance(c["type"], sa.Enum)
    return False


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    tables = _tables()
    if EQUIPEMENT not in tables:
        op.create_table(
            EQUIPEMENT,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("code", sa.String, nullable=False),
            sa.Column("libelle", sa.String, nullable=False),
            sa.Column("abreviation", sa.String, nullable=True),
            sa.Column("icone", sa.String, nullable=False, server_default="wrench"),
            sa.Column("description", sa.String, nullable=True),
            sa.Column("ordre", sa.Integer, nullable=False, server_default="0"),
            sa.Column("actif", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("cree_le", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("modifie_le", sa.DateTime, nullable=True),
        )
        op.create_index("ix_equipement_code", EQUIPEMENT, ["code"], unique=True)
    if LIEN not in tables:
        op.create_table(
            LIEN,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("equipement_id", sa.Integer, sa.ForeignKey("equipement.id"), nullable=False),
            sa.Column("perimetre_id", sa.Integer, sa.ForeignKey("perimetre.id"), nullable=False),
            sa.UniqueConstraint("equipement_id", "perimetre_id", name="uq_equipement_perimetre"),
        )
        op.create_index("ix_equipement_perimetre_equipement_id", LIEN, ["equipement_id"])
    if _colonne_enumeree():
        op.alter_column(
            CONTRAT,
            COLONNE,
            type_=sa.String(),
            existing_nullable=False,
            postgresql_using="type_equipement::text",
        )


def downgrade() -> None:
    #  La colonne reste du texte : y remettre l'énumération refuserait les codes
    #  créés depuis. Les deux tables, elles, se retirent.
    tables = _tables()
    if LIEN in tables:
        op.drop_table(LIEN)
    if EQUIPEMENT in tables:
        op.drop_table(EQUIPEMENT)
