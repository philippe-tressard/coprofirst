"""La phrase du journal des courriels, sous la forme qu'écrit l'éditeur (#2555, suite de 0326).

La 0326 remplaçait la phrase « jamais le texte du message » par celle qui dit ce que
garde un message À CLASSER — mais seulement si elle figurait telle que le gabarit
l'écrit (`<li>…\xa0…</li>`). Le texte servi par la référence avait été repris par
l'éditeur d'Admin › Pages légales, qui écrit `<li><p>…&nbsp;…</p></li>` : rien n'a
été remplacé (constaté au post-check de v3.69.0, le 05/11/2026), et la politique
servie taisait la conservation des messages à classer.

Cette migration reconnaît la forme de l'éditeur, caractère pour caractère comme en
base (0298), et y pose la phrase neuve sous la même forme. Un texte reformulé ne
change toujours pas. Données seules ; l'image précédente lit les mêmes clés (#1757).

Revision ID: 0327
Revises: 0326
"""

from alembic import op

from app.seed.contenus_legaux import CONSERVATION_RELEVES
from app.utils.textes_livres import remplacer_passage

revision = "0327"
down_revision = "0326"
branch_labels = None
depends_on = None

CLE = {"cle": "politique_confidentialite"}


def forme_editeur(phrase: str) -> str:
    """Une puce du gabarit (`<li>…</li>`, espaces insécables) telle que l'éditeur la
    réécrit : un paragraphe dans la puce, l'espace insécable en entité."""
    corps = phrase.removeprefix("<li>").removesuffix("</li>").replace("\xa0", "&nbsp;")
    return f"<li><p>{corps}</p></li>"


#: La phrase telle que la référence la servait jusqu'à v3.69.0, lue en base.
ANCIEN = (
    "<li><p>Journal des réponses reçues par courriel&nbsp;: adresse de l'expéditeur, objet, "
    "date et suite donnée — ajoutée à l'affaire, refusée ou écartée —, <strong>jamais le "
    "texte du message</strong>. Conservé <strong>90&nbsp;jours</strong> pour vérifier "
    "qu'une réponse a bien été reçue, puis <strong>supprimé automatiquement</strong>.</p></li>"
)


def upgrade() -> None:
    remplacer_passage(
        op.get_bind(), "config_site", CLE, "valeur", ANCIEN, forme_editeur(CONSERVATION_RELEVES)
    )


def downgrade() -> None:
    remplacer_passage(
        op.get_bind(), "config_site", CLE, "valeur", forme_editeur(CONSERVATION_RELEVES), ANCIEN
    )
