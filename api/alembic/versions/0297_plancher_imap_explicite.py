"""Le plancher de la relève des courriels devient une donnée, plus un défaut du code (#2060)

`imap_plancher` absent valait le 02/09/2026, date écrite dans le code — celle de
la mise en service de 5Hostachy. Le code pose désormais, à la première relève, la
date du jour. Pour qu'une installation qui RELEVAIT déjà sans plancher saisi ne
change pas de comportement, cette migration écrit chez elle la date qu'elle
appliquait sans le savoir.

Données seules, et seulement là où la relève est allumée sans plancher. L'image
précédente lit la même clé (règle #1757). Idempotente. Sans retour : la date
posée est celle que l'ancienne image appliquait déjà.

⚠️ Les noms de table et de clé sont des CONSTANTES du fichier.

Revision ID: 0297
Revises: 0296
"""

import sqlalchemy as sa

from alembic import op

revision = "0297"
down_revision = "0296"
branch_labels = None
depends_on = None

CONFIG = "config_site"  # identifiants : constantes du fichier
CLE_PLANCHER = "imap_plancher"
CLE_SERVICE = "imap_enabled"
ANCIEN_DEFAUT = "2026-09-02"  # `courriel_ingestion.PLANCHER_PAR_DEFAUT` au 17/10/2026

_CONFIG = sa.table(CONFIG, sa.column("cle", sa.String), sa.column("valeur", sa.String))


def _valeur(bind, cle: str):
    return bind.execute(sa.select(_CONFIG.c.valeur).where(_CONFIG.c.cle == cle)).scalar()


def upgrade():
    bind = op.get_bind()
    if (_valeur(bind, CLE_SERVICE) or "").strip() != "1":
        return
    actuel = _valeur(bind, CLE_PLANCHER)
    if actuel is None:
        bind.execute(sa.insert(_CONFIG).values(cle=CLE_PLANCHER, valeur=ANCIEN_DEFAUT))
    elif not actuel.strip():
        bind.execute(
            sa.update(_CONFIG).where(_CONFIG.c.cle == CLE_PLANCHER).values(valeur=ANCIEN_DEFAUT)
        )


def downgrade():
    pass
