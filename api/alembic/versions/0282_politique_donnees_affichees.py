"""La politique servie dit que l'affichage des données d'un écran est mesuré (#1846)

La mesure des durées d'affichage (0252) s'arrêtait à l'écran prêt. Elle compte
désormais aussi le temps jusqu'à ses données affichées (`donnees`,
`utils/mesures_affichage`) : même table, même absence de rattachement au compte,
même conservation. Le paragraphe `TELEMETRIE_PERFORMANCE` le nomme ; aucune table
ne change.

Le paragraphe d'AVANT est porté ici, tel que la 0252 l'a servi : une migration ne
lit pas l'historique du seed. Remplacement EXACT (`utils/textes_livres`) : un texte
reformulé à la main n'est pas touché — l'administrateur le reprend alors depuis
Admin › Légal.

Idempotente : rien ne change si le nouveau paragraphe y est déjà.

⚠️ La clé de configuration est une CONSTANTE du fichier.

Revision ID: 0282
Revises: 0281
"""

import sqlalchemy as sa

from alembic import op

revision = "0282"
down_revision = "0281"
branch_labels = None
depends_on = None

POLITIQUE = "politique_confidentialite"  # identifiant : constante du fichier

#: Le paragraphe servi par la 0252, mot pour mot.
AVANT = (
    "<li><strong>Durées d'affichage des écrans\xa0:</strong> le temps d'ouverture du site et "
    "de passage d'un écran à l'autre, par page, mesurés dans votre navigateur "
    "<strong>sans rattachement à votre compte</strong> et conservés 30\xa0jours. Elles servent "
    "à savoir quels écrans sont lents. Votre refus de la mesure d'audience les coupe aussi.</li>"
)


def _texte(conn) -> str | None:
    ligne = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :c").bindparams(c=POLITIQUE)
    ).fetchone()
    return (ligne[0] or "") if ligne else None


def _corriger(conn, avant: str, apres: str) -> int:
    from app.utils.textes_livres import remplacer_passage

    return remplacer_passage(conn, "config_site", {"cle": POLITIQUE}, "valeur", avant, apres)


def upgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_PERFORMANCE

    conn = op.get_bind()
    if "config_site" not in set(sa.inspect(conn).get_table_names()):
        return
    texte = _texte(conn)
    if texte is not None and TELEMETRIE_PERFORMANCE not in texte:
        _corriger(conn, AVANT, TELEMETRIE_PERFORMANCE)


def downgrade() -> None:
    from app.seed.contenus_legaux import TELEMETRIE_PERFORMANCE

    conn = op.get_bind()
    if "config_site" in set(sa.inspect(conn).get_table_names()):
        _corriger(conn, TELEMETRIE_PERFORMANCE, AVANT)
