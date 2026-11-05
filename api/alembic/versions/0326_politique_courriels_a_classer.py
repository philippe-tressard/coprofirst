"""La politique de confidentialité dit ce que garde un message à classer (#2555).

Le paragraphe du journal des réponses reçues par courriel disait « jamais le texte
du message ». Depuis #2555, le message authentifié d'un correspondant connu
qu'aucune affaire ne désigne est gardé ENTIER jusqu'à son classement : la phrase
servie deviendrait fausse. La neuve est LUE dans `seed/contenus_legaux`
(`CONSERVATION_RELEVES`) ; l'ancienne est écrite ici, seul endroit où elle doit
encore être reconnue.

Remplacé seulement s'il figure TEL QUEL (`remplacer_passage`) : un texte retouché
depuis Admin › Pages légales ne change pas. Données seules ; l'image précédente lit
les mêmes clés (#1757).

Revision ID: 0326
Revises: 0325
"""

from alembic import op

from app.seed.contenus_legaux import CONSERVATION_RELEVES
from app.utils.textes_livres import remplacer_passage

revision = "0326"
down_revision = "0325"
branch_labels = None
depends_on = None

CLE = {"cle": "politique_confidentialite"}

#: Le paragraphe tel que le gabarit l'écrivait jusqu'à la v3.68.
ANCIEN = (
    "<li>Journal des réponses reçues par courriel\xa0: adresse de l'expéditeur, objet, date "
    "et suite donnée — ajoutée à l'affaire, refusée ou écartée —, <strong>jamais le texte du "
    "message</strong>. Conservé <strong>90\xa0jours</strong> pour "
    "vérifier qu'une réponse a bien été reçue, puis <strong>supprimé automatiquement</strong>."
    "</li>"
)


def upgrade() -> None:
    remplacer_passage(op.get_bind(), "config_site", CLE, "valeur", ANCIEN, CONSERVATION_RELEVES)


def downgrade() -> None:
    remplacer_passage(op.get_bind(), "config_site", CLE, "valeur", CONSERVATION_RELEVES, ANCIEN)
