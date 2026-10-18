"""Les avis sur l'application — une table neuve (#2075).

Un avis par compte : note de 1 à 5, titre, description, remarque sous 3 étoiles,
accord de l'auteur pour coprofirst.fr, validation et réponse du gestionnaire du
site, retrait daté. Le modèle et ses règles : `app/models/avis.py`,
`app/utils/avis.py`.

Une table neuve seulement : l'image précédente ne la lit pas et n'en souffre pas
(#1757). La retirer est le seul geste du `downgrade`.
"""

import sqlalchemy as sa
from alembic import op

revision = "0299"
down_revision = "0298"
branch_labels = None
depends_on = None

#  Un IDENTIFIANT s'interpole depuis une constante du fichier.
AVIS = "avis"
UTILISATEUR_ID = "utilisateur.id"


def upgrade():
    if sa.inspect(op.get_bind()).has_table(AVIS):
        return
    op.create_table(
        AVIS,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("auteur_id", sa.Integer, sa.ForeignKey(UTILISATEUR_ID), nullable=False, unique=True),
        sa.Column("note", sa.Integer, nullable=False),
        sa.Column("titre", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=False),
        sa.Column("remarque", sa.String, nullable=True),
        sa.Column("consentement_publication", sa.Boolean, nullable=True),
        sa.Column("publication_validee_le", sa.DateTime, nullable=True),
        sa.Column("reponse", sa.String, nullable=True),
        sa.Column("reponse_par_id", sa.Integer, sa.ForeignKey(UTILISATEUR_ID), nullable=True),
        sa.Column("reponse_le", sa.DateTime, nullable=True),
        sa.Column("archive_le", sa.DateTime, nullable=True),
        sa.Column("archive_par_id", sa.Integer, sa.ForeignKey(UTILISATEUR_ID), nullable=True),
        sa.Column("cree_le", sa.DateTime, nullable=False),
        sa.Column("mis_a_jour_le", sa.DateTime, nullable=True),
    )


def downgrade():
    if sa.inspect(op.get_bind()).has_table(AVIS):
        op.drop_table(AVIS)
