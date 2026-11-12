"""La politique de confidentialité dit qu'on DEMANDE la suppression de son compte depuis son profil (#2699).

La phrase du point 6 sur ce qu'un compte fait depuis son profil devient celle de
`seed/contenus_legaux_suppression.DROITS_DEPUIS_LE_PROFIL` : on y demande aussi la
suppression de son compte, traitée sous le délai que l'API sert. Remplacée
seulement si elle figure telle quel dans le texte servi — une phrase reformulée
depuis Admin › Pages légales reste comme l'a écrite l'administration. L'espace
insécable prend la forme de son voisinage (`&nbsp;` sous l'éditeur, 0327).
Données seules ; l'image précédente lit les mêmes clés (#1757).

Revision ID: 0332
Revises: 0331
"""

from alembic import op

from app.seed.contenus_legaux_suppression import (
    DROITS_DEPUIS_LE_PROFIL,
    DROITS_DEPUIS_LE_PROFIL_ANCIEN,
)
from app.utils.textes_livres import lire_texte, remplacer_passage

revision = "0332"
down_revision = "0331"
branch_labels = None
depends_on = None

TABLE, COLONNE = "config_site", "valeur"
CLE = {"cle": "politique_confidentialite"}


def _formes(texte: str) -> list[str]:
    """La phrase neuve sous ses deux formes, celle du voisinage d'abord."""
    editeur = DROITS_DEPUIS_LE_PROFIL.replace("\xa0", "&nbsp;")
    return [editeur, DROITS_DEPUIS_LE_PROFIL] if "&nbsp;" in texte else [DROITS_DEPUIS_LE_PROFIL]


def upgrade() -> None:
    conn = op.get_bind()
    texte = lire_texte(conn, TABLE, CLE, COLONNE)
    if not texte:
        return
    remplacer_passage(
        conn, TABLE, CLE, COLONNE, DROITS_DEPUIS_LE_PROFIL_ANCIEN, _formes(texte)[0]
    )


def downgrade() -> None:
    conn = op.get_bind()
    for forme in (DROITS_DEPUIS_LE_PROFIL.replace("\xa0", "&nbsp;"), DROITS_DEPUIS_LE_PROFIL):
        remplacer_passage(conn, TABLE, CLE, COLONNE, forme, DROITS_DEPUIS_LE_PROFIL_ANCIEN)
