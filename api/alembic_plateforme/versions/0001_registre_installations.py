"""Le registre des installations : installations, contact, décisions, contrats acceptés.

R1 (#1877), spec §4.11. Première migration de la base `plateforme` — une base neuve,
distincte de celle de la résidence.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

INSTALLATION = "installation"
CONTACT = "contact_installation"
DECISION = "decision_registre"
ACCEPTATION = "acceptation_conditions"


def upgrade():
    op.create_table(
        INSTALLATION,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("identifiant", sa.String(20), nullable=False, unique=True),
        sa.Column("cle_publique", sa.String(60), nullable=True, unique=True),
        sa.Column("empreinte_cle", sa.String(16), nullable=True),
        sa.Column(
            "etat",
            sa.Enum("en_attente", "active", "suspendue", "resiliee", name="etatinscription"),
            nullable=False,
        ),
        sa.Column("canal", sa.String(60), nullable=False),
        sa.Column("version_logicielle", sa.String(40), nullable=True),
        sa.Column("conditions_acceptees", sa.Integer, nullable=True),
        sa.Column("cree_le", sa.DateTime, nullable=False),
        sa.Column("mis_a_jour_le", sa.DateTime, nullable=True),
        sa.Column("vue_le", sa.DateTime, nullable=True),
    )
    op.create_table(
        CONTACT,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "installation_id",
            sa.Integer,
            sa.ForeignKey("installation.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("prenom", sa.String(80), nullable=False),
        sa.Column("nom", sa.String(80), nullable=False),
        sa.Column("courriel", sa.String(254), nullable=False),
        sa.Column("telephone", sa.String(30), nullable=True),
        sa.Column("mis_a_jour_le", sa.DateTime, nullable=False),
    )
    op.create_table(
        DECISION,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("installation_id", sa.Integer, sa.ForeignKey("installation.id"), nullable=False),
        sa.Column("geste", sa.String(40), nullable=False),
        sa.Column("motif", sa.String(500), nullable=False),
        sa.Column("auteur", sa.String(60), nullable=False),
        sa.Column("cree_le", sa.DateTime, nullable=False),
    )
    op.create_index("ix_decision_registre_installation_id", DECISION, ["installation_id"])
    op.create_table(
        ACCEPTATION,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("installation_id", sa.Integer, sa.ForeignKey("installation.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("empreinte", sa.String(64), nullable=False),
        sa.Column("texte", sa.Text, nullable=False),
        sa.Column("accepte_par", sa.String(300), nullable=False),
        sa.Column("accepte_le", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_acceptation_conditions_installation_id", ACCEPTATION, ["installation_id"]
    )


def downgrade():
    op.drop_table(ACCEPTATION)
    op.drop_table(DECISION)
    op.drop_table(CONTACT)
    op.drop_table(INSTALLATION)
    sa.Enum(name="etatinscription").drop(op.get_bind(), checkfirst=True)
