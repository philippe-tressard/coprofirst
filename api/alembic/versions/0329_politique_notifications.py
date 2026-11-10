"""La politique de confidentialité dit ce que deviennent les notifications (#2495, #2535).

Deux puces neuves, LUES dans `seed/contenus_legaux_notifications` :

- `NOTIFICATIONS_PUSH`, posée après la puce de la réception des courriels (services
  tiers) : ce qui part chez Apple quand les notifications sur téléphone sont actives ;
- `CONSERVATION_NOTIFICATIONS`, posée après celle du journal des réponses reçues
  (durées de conservation) : une notification lue est gardée douze mois (#2535).

L'intitulé des services tiers compte ses puces en toutes lettres (#1585) : « Quatre
fonctions » devient « Cinq fonctions » (`FONCTIONS_TIERS`), l'ancien mot écrit ici
seulement.

Le texte servi existe sous deux formes — celle du gabarit et celle qu'écrit l'éditeur
d'Admin › Pages légales (`<li><p>…&nbsp;…</p></li>`, 0327) : chaque puce se pose dans la
forme de son voisinage. Une ancre reformulée depuis l'administration laisse le texte
tel quel. Données seules ; l'image précédente lit les mêmes clés (#1757).

Revision ID: 0329
Revises: 0328
"""

from alembic import op

from app.seed.contenus_legaux import CONSERVATION_RELEVES, FONCTIONS_TIERS, RECEPTION_COURRIELS
from app.seed.contenus_legaux_notifications import (
    CONSERVATION_NOTIFICATIONS,
    NOTIFICATIONS_PUSH,
)
from app.utils.textes_livres import forme_editeur, inserer_apres, remplacer_passage

revision = "0329"
down_revision = "0328"
branch_labels = None
depends_on = None

CLE = {"cle": "politique_confidentialite"}

#: L'intitulé des services tiers tel que le gabarit l'écrivait jusqu'à la v3.78.
FONCTIONS_TIERS_QUATRE = (
    "Quatre fonctions font passer des informations par un service tiers lorsqu'elles sont activées"
)

#: (ancre, puce posée après elle), sous la forme du gabarit.
INSERTIONS = [
    (RECEPTION_COURRIELS, NOTIFICATIONS_PUSH),
    (CONSERVATION_RELEVES, CONSERVATION_NOTIFICATIONS),
]


def _formes():
    for ancre, ajout in INSERTIONS:
        yield ancre, ajout
        yield forme_editeur(ancre), forme_editeur(ajout)


def upgrade() -> None:
    remplacer_passage(
        op.get_bind(), "config_site", CLE, "valeur", FONCTIONS_TIERS_QUATRE, FONCTIONS_TIERS
    )
    for ancre, ajout in _formes():
        inserer_apres(op.get_bind(), "config_site", CLE, "valeur", ancre, ajout)


def downgrade() -> None:
    for ancre, ajout in _formes():
        remplacer_passage(op.get_bind(), "config_site", CLE, "valeur", ancre + ajout, ancre)
    remplacer_passage(
        op.get_bind(), "config_site", CLE, "valeur", FONCTIONS_TIERS, FONCTIONS_TIERS_QUATRE
    )
