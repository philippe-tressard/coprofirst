"""La politique de confidentialité nomme la lecture de l'état descriptif par l'assistant (#2218).

Le texte du règlement part aussi quand le conseil demande à l'assistant de lire
l'état descriptif de division : le texte servi par chaque copropriété le dit
désormais, juste après la phrase des questions au règlement. La phrase est LUE dans
`seed/contenus_legaux_etat_descriptif` — le gabarit et cette migration n'en ont
qu'une rédaction.

Insérée seulement si la phrase qui la précède figure TELLE QUELLE
(`remplacer_passage`) : un texte retouché depuis Admin › Pages légales ne change
pas, et son administrateur ajoutera la mention lui-même. Le texte modifié redevient
« à relire » : son empreinte a changé. Données seules ; l'image précédente lit les
mêmes clés (#1757).

Revision ID: 0313
Revises: 0312
"""

import sqlalchemy as sa
from alembic import op

from app.seed.contenus_legaux import QUESTION_REGLEMENT
from app.seed.contenus_legaux_etat_descriptif import LECTURE_ETAT_DESCRIPTIF
from app.utils.textes_livres import remplacer_passage

revision = "0313"
down_revision = "0312"
branch_labels = None
depends_on = None

CLE = {"cle": "politique_confidentialite"}


def _texte_servi() -> str:
    t = sa.table("config_site", sa.column("cle"), sa.column("valeur"))
    return op.get_bind().execute(sa.select(t.c.valeur).where(t.c.cle == CLE["cle"])).scalar() or ""


def upgrade() -> None:
    #  Déjà présente — une base neuve reçoit le gabarit à jour : rien à insérer.
    if LECTURE_ETAT_DESCRIPTIF in _texte_servi():
        return
    ancre = QUESTION_REGLEMENT
    remplacer_passage(
        op.get_bind(), "config_site", CLE, "valeur", ancre, ancre + LECTURE_ETAT_DESCRIPTIF
    )


def downgrade() -> None:
    remplacer_passage(op.get_bind(), "config_site", CLE, "valeur", LECTURE_ETAT_DESCRIPTIF, "")
