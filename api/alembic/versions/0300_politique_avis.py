"""La politique de confidentialité nomme les avis sur l'application (#2075).

Un avis consenti peut paraître sur le site de présentation du logiciel : le texte
servi par chaque copropriété le dit désormais, dans « Finalités et bases
légales », juste après les e-mails transactionnels. Le paragraphe est LU dans
`seed/contenus_legaux_avis` — le gabarit et cette migration n'en ont qu'une
rédaction.

Inséré seulement si l'entrée qui le précède figure TELLE QUELLE
(`remplacer_passage`) : un texte retouché depuis Admin › Pages légales ne change
pas, et son administrateur ajoutera la mention lui-même. Le texte modifié
redevient « à relire » : son empreinte a changé. Données seules ; l'image
précédente lit les mêmes clés (#1757).

Revision ID: 0300
Revises: 0299
"""

import sqlalchemy as sa
from alembic import op

from app.seed.contenus_legaux_avis import APRES_EMAILS_TRANSACTIONNELS, AVIS_SITE_PRESENTATION
from app.utils.textes_livres import remplacer_passage

revision = "0300"
down_revision = "0299"
branch_labels = None
depends_on = None

CLE = {"cle": "politique_confidentialite"}


def _texte_servi() -> str:
    t = sa.table("config_site", sa.column("cle"), sa.column("valeur"))
    return op.get_bind().execute(sa.select(t.c.valeur).where(t.c.cle == CLE["cle"])).scalar() or ""


def upgrade() -> None:
    #  Déjà présent — une base neuve reçoit le gabarit à jour : rien à insérer.
    if AVIS_SITE_PRESENTATION in _texte_servi():
        return
    ancre = APRES_EMAILS_TRANSACTIONNELS
    remplacer_passage(
        op.get_bind(), "config_site", CLE, "valeur", ancre, ancre + AVIS_SITE_PRESENTATION
    )


def downgrade() -> None:
    remplacer_passage(op.get_bind(), "config_site", CLE, "valeur", AVIS_SITE_PRESENTATION, "")
