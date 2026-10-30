"""La politique de confidentialité nomme les décisions d'AG lues par l'assistant (29/10/2026).

Les questions au règlement transmettent aussi les décisions d'assemblée générale
validées, et l'assistant transcrit un procès-verbal d'AG entier : le texte servi
par chaque copropriété le dit désormais, juste après la phrase des questions au
règlement. La phrase est LUE dans `seed/contenus_legaux_decisions_ag` — le gabarit
et cette migration n'en ont qu'une rédaction.

Insérée seulement si la phrase qui la précède figure TELLE QUELLE
(`remplacer_passage`) : un texte retouché depuis Admin › Pages légales ne change
pas, et son administrateur ajoutera la mention lui-même. Le texte modifié redevient
« à relire » : son empreinte a changé. Données seules ; l'image précédente lit les
mêmes clés (#1757).

Revision ID: 0318
Revises: 0317
"""

import sqlalchemy as sa
from alembic import op

from app.seed.contenus_legaux import QUESTION_REGLEMENT
from app.seed.contenus_legaux_decisions_ag import DECISIONS_AG
from app.utils.textes_livres import remplacer_passage

revision = "0318"
down_revision = "0317"
branch_labels = None
depends_on = None

CLE = {"cle": "politique_confidentialite"}


def _texte_servi() -> str:
    t = sa.table("config_site", sa.column("cle"), sa.column("valeur"))
    return op.get_bind().execute(sa.select(t.c.valeur).where(t.c.cle == CLE["cle"])).scalar() or ""


def upgrade() -> None:
    #  Déjà présente — une base neuve reçoit le gabarit à jour : rien à insérer.
    if DECISIONS_AG in _texte_servi():
        return
    ancre = QUESTION_REGLEMENT
    remplacer_passage(op.get_bind(), "config_site", CLE, "valeur", ancre, ancre + DECISIONS_AG)


def downgrade() -> None:
    remplacer_passage(op.get_bind(), "config_site", CLE, "valeur", DECISIONS_AG, "")
