"""La FAQ ne dit plus le délai d'archivage « fixé par le conseil syndical » (#2926).

`archivage_delai_jours` s'écrit par `PUT /config`, réservé à l'administrateur
(Admin › Copropriété › Fonctionnement, `utils/reglages.PAR_ONGLET`). La question de
`FAQ_COMPLEMENTAIRE`, posée sur toute installation, prêtait ce réglage au conseil
syndical. La réponse n'est remplacée que si elle porte EXACTEMENT l'ancienne rédaction :
une réponse retouchée par le conseil n'est pas touchée. Les deux textes sont RECOPIÉS
ici, figés — une migration ne dépend pas d'un seed qui bouge. Données seules ; l'image
précédente lit les mêmes colonnes (#1757).

Revision ID: 0348
Revises: 0347
"""

from alembic import op

from app.utils.textes_livres import remplacer_si_intact

revision = "0348"
down_revision = "0347"
branch_labels = None
depends_on = None

TABLE = "faq_item"  # identifiant : constante du fichier

QUESTION = "Pourquoi mes anciennes affaires n'apparaissent plus dans la liste principale ?"

_DEBUT = (
    "Les affaires résolues ou annulées passent automatiquement dans l'onglet "
    "<strong>🗂️ Archives</strong> de la page Affaires, après un délai "
)
_FIN = (
    ". Cela garde la liste principale centrée sur les demandes encore actives, sans rien "
    "perdre : tout reste consultable dans les archives."
)
ANCIENNE = _DEBUT + "fixé par le conseil syndical" + _FIN
NOUVELLE = _DEBUT + "réglé par l'administrateur de la copropriété" + _FIN


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
