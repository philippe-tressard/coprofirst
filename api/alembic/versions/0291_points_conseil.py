"""Le point conseil syndical / syndic et son compte rendu (#2041)

Trois tables neuves — le point (Quand, Où, état), ses présents (CS, syndic,
invités) et le compte rendu de chaque affaire abordée. Règles :
`app/models/points_conseil.py` et `app/utils/points_conseil`.

Additive : trois tables que l'image précédente ignore (règle #1757,
`test_migrations_compatibles.py`).

Idempotente : `start.sh` a `set -e`, et un redémarrage après une migration
interrompue la rejoue — une table déjà présente est laissée telle quelle.

⚠️ Les noms de table sont des CONSTANTES du fichier.

Revision ID: 0291
Revises: 0290
"""

import sqlalchemy as sa

from alembic import op

revision = "0291"
down_revision = "0290"
branch_labels = None
depends_on = None

POINT = "point_conseil"  # identifiants : constantes du fichier
PRESENT = "point_conseil_present"
CR = "point_conseil_cr"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade():
    presentes = _tables()
    if POINT not in presentes:
        op.create_table(
            POINT,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("mode", sa.String, nullable=False, server_default="affaires", index=True),
            sa.Column("etat", sa.String, nullable=False, server_default="en_cours", index=True),
            sa.Column("debut", sa.DateTime, nullable=False),
            sa.Column("fin", sa.DateTime, nullable=True),
            sa.Column("a_distance", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("lieu", sa.String, nullable=True),
            sa.Column("auteur_id", sa.Integer, sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("non_traitees_json", sa.String, nullable=False, server_default="[]"),
            sa.Column("cree_le", sa.DateTime, nullable=False),
            sa.Column("mis_a_jour_le", sa.DateTime, nullable=False),
            sa.Column("termine_le", sa.DateTime, nullable=True),
            sa.Column("valide_le", sa.DateTime, nullable=True),
            sa.Column("valide_par_id", sa.Integer, nullable=True),
        )
    if PRESENT not in presentes:
        op.create_table(
            PRESENT,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "point_id", sa.Integer, sa.ForeignKey("point_conseil.id"), nullable=False, index=True
            ),
            sa.Column("nature", sa.String, nullable=False),
            sa.Column("membre_cs_id", sa.Integer, nullable=True),
            sa.Column("membre_syndic_id", sa.Integer, nullable=True),
            sa.Column("prenom", sa.String, nullable=True),
            sa.Column("nom", sa.String, nullable=True),
            sa.Column("entreprise", sa.String, nullable=True),
            sa.Column("fonction", sa.String, nullable=True),
            sa.Column("telephone", sa.String, nullable=True),
            sa.Column("email", sa.String, nullable=True),
        )
    if CR not in presentes:
        op.create_table(
            CR,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "point_id", sa.Integer, sa.ForeignKey("point_conseil.id"), nullable=False, index=True
            ),
            sa.Column(
                "ticket_id", sa.Integer, sa.ForeignKey("ticket.id"), nullable=False, index=True
            ),
            sa.Column("contenu", sa.String, nullable=False, server_default=""),
            sa.Column("brouillon", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("conseil_seul", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("auteur_id", sa.Integer, sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("cree_le", sa.DateTime, nullable=False),
            sa.Column("mis_a_jour_le", sa.DateTime, nullable=False),
            sa.UniqueConstraint("point_id", "ticket_id", name="uq_point_conseil_cr_affaire"),
        )


def downgrade():
    presentes = _tables()
    for table in (CR, PRESENT, POINT):
        if table in presentes:
            op.drop_table(table)
