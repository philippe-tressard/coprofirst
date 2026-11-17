"""La puce « Accès utilisé » dit aussi le type d'appareil (#2774, 17/11/2026).

La 0344 joint à chaque page vue la CLASSE d'appareil que son client déclare
(téléphone, tablette, ordinateur, télévision, montre) : la politique de confidentialité
le dit. La puce `TELEMETRIE_ACCES` est remplacée dans le texte servi, sous ses deux
formes (celle du gabarit, celle de l'éditeur d'Admin › Pages légales) ; un texte qui ne
la porte plus telle quelle ne change pas. L'ANCIENNE est recopiée ici, littérale : une
migration ne dépend pas d'un seed qui bouge. Ancre vérifiée sur le texte servi en
production le 17/11/2026 (forme de l'éditeur, une occurrence). Données seules ; l'image
précédente lit les mêmes clés (#1757).

Revision ID: 0345
Revises: 0344
"""

from alembic import op

from app.seed.contenus_legaux_canal import TELEMETRIE_ACCES
from app.utils.textes_livres import forme_editeur, remplacer_passage

revision = "0345"
down_revision = "0344"
branch_labels = None
depends_on = None

TABLE, COLONNE = "config_site", "valeur"
CLE = {"cle": "politique_confidentialite"}

ANCIENNE = (
    "<li><strong>Accès utilisé\xa0:</strong> pour chaque page consultée, si vous l'avez "
    "ouverte depuis le site web ou depuis l'application pour téléphone (iPhone, puis "
    "Android) — jamais le modèle de l'appareil ni un identifiant qui lui serait propre. "
    "Il est joint à la page consultée, comme le reste de la mesure d'audience rattachée à "
    "votre compte, et conservé avec elle. Il sert à savoir comment le site et "
    "l'application sont utilisés. Votre refus de la mesure d'audience le coupe aussi.</li>"
)


def upgrade() -> None:
    conn = op.get_bind()
    #  Les deux formes : celle de l'éditeur (servie en production), puis celle du gabarit.
    for forme in (forme_editeur, str):
        remplacer_passage(conn, TABLE, CLE, COLONNE, forme(ANCIENNE), forme(TELEMETRIE_ACCES))


def downgrade() -> None:
    conn = op.get_bind()
    for forme in (forme_editeur, str):
        remplacer_passage(conn, TABLE, CLE, COLONNE, forme(TELEMETRIE_ACCES), forme(ANCIENNE))
