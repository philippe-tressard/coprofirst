"""La politique de confidentialité dit l'ACCÈS utilisé : site web ou application (14/11/2026).

La 0335 joint à chaque page vue le canal d'accès que son client déclare
(`utils/canaux_audience`). Une puce neuve le dit, LUE dans
`seed/contenus_legaux_canal.TELEMETRIE_ACCES`, posée juste après celle de la
notification qui amène (`TELEMETRIE_ARRIVEES`) — la puce voisine, qui joint elle
aussi un contexte à la page consultée.

Le texte servi existe sous deux formes — celle du gabarit et celle qu'écrit l'éditeur
d'Admin › Pages légales (`<li><p>…&nbsp;…</p></li>`, 0327) : la puce se pose dans la
forme de son voisinage. Ancre vérifiée sur le texte servi en production le 14/11/2026
(forme de l'éditeur, une occurrence). Une ancre reformulée depuis l'administration
laisse le texte tel quel. Données seules ; l'image précédente lit les mêmes clés (#1757).

Revision ID: 0336
Revises: 0335
"""

from alembic import op

from app.seed.contenus_legaux import TELEMETRIE_ARRIVEES
from app.seed.contenus_legaux_canal import TELEMETRIE_ACCES
from app.utils.textes_livres import forme_editeur, inserer_apres, remplacer_passage

revision = "0336"
down_revision = "0335"
branch_labels = None
depends_on = None

CLE = {"cle": "politique_confidentialite"}


def _formes():
    yield TELEMETRIE_ARRIVEES, TELEMETRIE_ACCES
    yield forme_editeur(TELEMETRIE_ARRIVEES), forme_editeur(TELEMETRIE_ACCES)


def upgrade() -> None:
    for ancre, ajout in _formes():
        inserer_apres(op.get_bind(), "config_site", CLE, "valeur", ancre, ajout)


def downgrade() -> None:
    for ancre, ajout in _formes():
        remplacer_passage(op.get_bind(), "config_site", CLE, "valeur", ancre + ajout, ancre)
