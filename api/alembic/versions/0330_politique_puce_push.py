"""La puce des notifications sur téléphone, là où la 0329 n'a pas pu la poser (#2495).

La 0329 posait la puce `NOTIFICATIONS_PUSH` juste après celle de la réception des
courriels, et passait l'intitulé à « Cinq fonctions ». La référence a RENSEIGNÉ sa
puce de réception (son prestataire y est nommé) : l'ancre n'a pas été trouvée, la puce
n'a pas été posée, et la politique servie annonçait cinq services tiers pour quatre
listés (constaté au post-check de v3.80.0, le 10/11/2026).

Cette migration ancre la puce sur la FIN de la liste des services tiers — la balise
qui la ferme, suivie du titre de la section 5 —, qu'aucune reformulation d'une puce ne
déplace. Elle la pose sous la forme de son voisinage (celle de l'éditeur si le texte
servi l'emploie, sinon celle du gabarit), et ne fait rien si elle y figure déjà, sous
l'une ou l'autre forme. Un texte dont la section 5 a été retitrée ne change pas.
Données seules ; l'image précédente lit les mêmes clés (#1757).

Revision ID: 0330
Revises: 0329
"""

from alembic import op

from app.seed.contenus_legaux_notifications import NOTIFICATIONS_PUSH
from app.utils.textes_livres import forme_editeur, lire_texte, remplacer_passage

revision = "0330"
down_revision = "0329"
branch_labels = None
depends_on = None

TABLE, COLONNE = "config_site", "valeur"
CLE = {"cle": "politique_confidentialite"}

#: La fin de la liste des services tiers, telle que le gabarit et l'éditeur l'écrivent.
FIN_DE_LISTE = "</ul><h2>5. Durée de conservation</h2>"


def _puce_du_voisinage(texte: str) -> str:
    """La puce sous la forme qu'emploie le texte servi."""
    return forme_editeur(NOTIFICATIONS_PUSH) if "<li><p>" in texte else NOTIFICATIONS_PUSH


def upgrade() -> None:
    conn = op.get_bind()
    texte = lire_texte(conn, TABLE, CLE, COLONNE)
    if not texte or FIN_DE_LISTE not in texte:
        return
    if NOTIFICATIONS_PUSH in texte or forme_editeur(NOTIFICATIONS_PUSH) in texte:
        return
    puce = _puce_du_voisinage(texte)
    remplacer_passage(conn, TABLE, CLE, COLONNE, FIN_DE_LISTE, puce + FIN_DE_LISTE)


def downgrade() -> None:
    conn = op.get_bind()
    for puce in (forme_editeur(NOTIFICATIONS_PUSH), NOTIFICATIONS_PUSH):
        remplacer_passage(conn, TABLE, CLE, COLONNE, puce + FIN_DE_LISTE, FIN_DE_LISTE)
