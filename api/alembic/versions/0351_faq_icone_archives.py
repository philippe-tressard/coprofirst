"""La FAQ nomme l'onglet des archives comme l'écran : « 📁 Archives » (#3002).

L'onglet porte `TITRE_ARCHIVES` (`front/src/lib/archives.ts`), dont l'icône est 📁 ;
la réponse de `FAQ_COMPLEMENTAIRE` écrivait « 🗂️ Archives ». Elle n'est remplacée que
si elle porte EXACTEMENT la rédaction posée par 0348 : une réponse retouchée par le
conseil n'est pas touchée. Les deux textes sont RECOPIÉS ici, figés — une migration
ne dépend pas d'un seed qui bouge. Données seules ; l'image précédente lit les mêmes
colonnes (#1757).

Revision ID: 0351
Revises: 0350
"""

from alembic import op

from app.utils.textes_livres import remplacer_si_intact

revision = "0351"
down_revision = "0350"
branch_labels = None
depends_on = None

TABLE = "faq_item"  # identifiant : constante du fichier

QUESTION = "Pourquoi mes anciennes affaires n'apparaissent plus dans la liste principale ?"

_DEBUT = "Les affaires résolues ou annulées passent automatiquement dans l'onglet <strong>"
_FIN = (
    " Archives</strong> de la page Affaires, après un délai réglé par l'administrateur de "
    "la copropriété. Cela garde la liste principale centrée sur les demandes encore "
    "actives, sans rien perdre : tout reste consultable dans les archives."
)
ANCIENNE = _DEBUT + "🗂️" + _FIN
NOUVELLE = _DEBUT + "📁" + _FIN


def upgrade() -> None:
    remplacer_si_intact(
        op.get_bind(),
        TABLE,
        {"question": QUESTION, "reponse": ANCIENNE},
        {"reponse": NOUVELLE},
    )


def downgrade() -> None:
    remplacer_si_intact(
        op.get_bind(),
        TABLE,
        {"question": QUESTION, "reponse": NOUVELLE},
        {"reponse": ANCIENNE},
    )
