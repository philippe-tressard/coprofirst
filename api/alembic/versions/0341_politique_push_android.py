"""La puce des notifications sur téléphone nomme Google et FCM pour Android (#2789, 16/11/2026).

L'app Android avertit par Firebase Cloud Messaging de Google : la politique de
confidentialité ne nommait qu'Apple et APNs. La puce `NOTIFICATIONS_PUSH` est remplacée
dans le texte servi, sous ses deux formes (celle du gabarit, celle de l'éditeur
d'Admin › Pages légales) ; un texte qui ne la porte plus telle quelle ne change pas.
L'ANCIENNE est recopiée ici, littérale : une migration ne dépend pas d'un seed qui bouge.
Données seules ; l'image précédente lit les mêmes clés (#1757).

Revision ID: 0341
Revises: 0340
"""

from alembic import op

from app.seed.contenus_legaux_notifications import NOTIFICATIONS_PUSH
from app.utils.textes_livres import forme_editeur, remplacer_passage

revision = "0341"
down_revision = "0340"
branch_labels = None
depends_on = None

TABLE, COLONNE = "config_site", "valeur"
CLE = {"cle": "politique_confidentialite"}

ANCIENNE = (
    "<li><strong>Notifications sur téléphone (application iOS)</strong> — service coupé "
    "par défaut, que l'administration peut activer. Si vous utilisez l'application et "
    "autorisez ses notifications, votre téléphone est enregistré auprès de ce site par le "
    "<strong>jeton</strong> qu'Apple lui attribue et par un identifiant tiré au hasard par "
    "l'application. Pour vous prévenir, ce site transmet ce jeton, cet identifiant et le "
    "niveau de l'avis au <strong>relais de notifications de CoproFirst</strong>, qui les "
    "transmet au service de notifications d'Apple (APNs) avec un texte fixe —\xa0«\xa0Vous "
    "avez une nouvelle notification\xa0»\xa0— et <strong>rien d'autre</strong>\xa0: ni votre "
    "nom, ni la résidence, ni le contenu de l'avis, que l'application lit ensuite sur ce "
    "site. Pour un avis urgent (fuite, ascenseur bloqué), l'envoi porte en plus le niveau "
    "«\xa0urgent\xa0» d'Apple, qui apprend à Apple qu'un avis est urgent, sans dire lequel. "
    "Vous pouvez couper ces notifications dans les réglages du téléphone.</li>"
)


def upgrade() -> None:
    conn = op.get_bind()
    #  Les deux formes : celle de l'éditeur (servie en production), puis celle du gabarit.
    for forme in (forme_editeur, str):
        remplacer_passage(conn, TABLE, CLE, COLONNE, forme(ANCIENNE), forme(NOTIFICATIONS_PUSH))


def downgrade() -> None:
    conn = op.get_bind()
    for forme in (forme_editeur, str):
        remplacer_passage(conn, TABLE, CLE, COLONNE, forme(NOTIFICATIONS_PUSH), forme(ANCIENNE))
