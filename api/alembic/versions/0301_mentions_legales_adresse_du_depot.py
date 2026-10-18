"""Les mentions légales lient le nom du logiciel et son code source (demande de l'auteur, 18/10/2026).

Le paragraphe « Propriété intellectuelle » nommait CoproFirst sans lien et finissait par
« Le code source de la version en service est accessible depuis le pied de chaque page. »
sans dire où se trouve le dépôt. Désormais le NOM renvoie au site de présentation
(`SITE_PLATEFORME`) et « code source » au dépôt (`DEPOT_SOURCE`) : aucune adresse écrite
en clair, aucune mention de plus. Les phrases viennent du gabarit
(`seed.contenus_legaux_licence.PHRASE_SERVI_PAR`, `PHRASE_CODE_SOURCE`), qui les lit de
`utils/plateforme`.

Donnée seule, sur le modèle de la 0298 : un passage n'est remplacé que s'il figure TEL
QUEL (`remplacer_passage`). Une installation qui ne l'a jamais eu, ou dont les mentions
ont été retouchées depuis Admin › Pages légales, ne change pas. Le texte modifié
redevient « à relire » : son empreinte a changé. L'image précédente lit la même clé (#1757).

Revision ID: 0301
Revises: 0300
"""

from alembic import op

from app.seed.contenus_legaux_licence import PHRASE_CODE_SOURCE, PHRASE_SERVI_PAR
from app.utils.plateforme import NOM_PLATEFORME
from app.utils.textes_livres import remplacer_passage

revision = "0301"
down_revision = "0300"
branch_labels = None
depends_on = None

#: (clé de `config_site`, avant, après) — tels qu'en base, caractère pour caractère.
REMPLACEMENTS: list[tuple[str, str, str]] = [
    ("mentions_legales", f"Ce site est servi par {NOM_PLATEFORME},", PHRASE_SERVI_PAR),
    (
        "mentions_legales",
        "Le code source de la version en service est accessible depuis le pied de chaque page.",
        PHRASE_CODE_SOURCE,
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for cle, ancien, nouveau in REMPLACEMENTS:
        remplacer_passage(conn, "config_site", {"cle": cle}, "valeur", ancien, nouveau)


def downgrade() -> None:
    conn = op.get_bind()
    for cle, ancien, nouveau in REMPLACEMENTS:
        remplacer_passage(conn, "config_site", {"cle": cle}, "valeur", nouveau, ancien)
