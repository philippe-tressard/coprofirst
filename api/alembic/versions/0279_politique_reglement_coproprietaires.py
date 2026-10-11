"""La politique servie dit que les copropriétaires interrogent le règlement (11/10/2026)

L'onglet Règlement quitte l'Espace CS pour Ma résidence et s'ouvre aux
copropriétaires quand l'administration le permet (#1833). Leur question est
gardée avec leur identité, lisible d'eux, du conseil et de l'administration : le
paragraphe `QUESTION_REGLEMENT` de la politique de confidentialité, posé par la
0256, ne parlait que du conseil syndical. Aucune table ne change.

Le paragraphe d'AVANT est porté ici, tel que la 0256 l'a servi : une migration ne
lit pas l'historique du seed. Remplacement EXACT (`utils/textes_livres`) : un texte
reformulé à la main n'est pas touché — l'administrateur le reprend alors depuis
Admin › Légal.

Idempotente : rien ne change si le nouveau paragraphe y est déjà.

⚠️ La clé de configuration est une CONSTANTE du fichier.

Revision ID: 0279
Revises: 0278
"""

import sqlalchemy as sa

from alembic import op

revision = "0279"
down_revision = "0278"
branch_labels = None
depends_on = None

POLITIQUE = "politique_confidentialite"  # identifiant : constante du fichier

#: Le paragraphe servi par la 0256, mot pour mot.
AVANT = (
    "Lorsqu'un membre du conseil syndical pose une <strong>question au règlement de "
    "copropriété</strong>, la question et le texte entier du règlement chargé par le "
    "conseil — qui peut nommer les parties aux actes notariés — sont transmis, jamais le "
    "nom de qui la pose ni de la personne qu'elle concerne. "
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
    from app.seed.contenus_legaux import QUESTION_REGLEMENT

    conn = op.get_bind()
    if "config_site" not in set(sa.inspect(conn).get_table_names()):
        return
    texte = _texte(conn)
    if texte is not None and QUESTION_REGLEMENT not in texte:
        _corriger(conn, AVANT, QUESTION_REGLEMENT)


def downgrade() -> None:
    from app.seed.contenus_legaux import QUESTION_REGLEMENT

    conn = op.get_bind()
    if "config_site" in set(sa.inspect(conn).get_table_names()):
        _corriger(conn, QUESTION_REGLEMENT, AVANT)
