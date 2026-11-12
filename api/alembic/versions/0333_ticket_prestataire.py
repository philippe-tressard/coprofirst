"""La table `ticket_prestataire` : une affaire porte plusieurs prestataires (#2704).

Demandé par l'app iOS (coprofirst-ios#181) : l'intervenant d'une affaire devient
une LISTE ordonnée. Chaque affaire qui a un intervenant (`ticket.prestataire_id`
non nul) reçoit une ligne de rang 0 : la liste reprend ce qui existe.

Une table NEUVE, et une reprise : rien n'est retiré ni renommé. La colonne
`ticket.prestataire_id` reste, tenue égale au premier de la liste à chaque
écriture : la version précédente du code la lit toujours, et revenir à son
image ne demande aucune restauration (#1757). Les affaires dont l'intervenant
n'existe plus (aucune ligne `prestataire`) ne sont pas reprises : la clé
étrangère les refuserait, et leur lecture garde la colonne.

Revision ID: 0333
Revises: 0332
"""

import sqlalchemy as sa
from alembic import op

revision = "0333"
down_revision = "0332"
branch_labels = None
depends_on = None

TABLE = "ticket_prestataire"  # identifiant : constante du fichier
INDEX = ("ticket_id", "prestataire_id")  # identifiants : constantes

#  Aucune valeur interpolée : la requête est entièrement littérale.
REPRISE = sa.text(
    "INSERT INTO ticket_prestataire (ticket_id, prestataire_id, rang) "
    "SELECT t.id, t.prestataire_id, 0 FROM ticket t "
    "JOIN prestataire p ON p.id = t.prestataire_id "
    "WHERE t.prestataire_id IS NOT NULL "
    "AND NOT EXISTS (SELECT 1 FROM ticket_prestataire tp WHERE tp.ticket_id = t.id)"
)


def upgrade() -> None:
    #  Rejouable : un redémarrage après une migration interrompue la relance (0312).
    if TABLE not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("ticket.id"), nullable=False),
            sa.Column(
                "prestataire_id", sa.Integer(), sa.ForeignKey("prestataire.id"), nullable=False
            ),
            sa.Column("rang", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("ticket_id", "prestataire_id", name="uq_ticket_prestataire"),
        )
        for colonne in INDEX:
            op.create_index(f"ix_{TABLE}_{colonne}", TABLE, [colonne])
    op.execute(REPRISE)


def downgrade() -> None:
    for colonne in INDEX:
        op.drop_index(f"ix_{TABLE}_{colonne}", table_name=TABLE)
    op.drop_table(TABLE)
