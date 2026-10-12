"""Les migrations de la base `plateforme` (registre des installations, D17).

Une chaîne À PART de celle de la résidence (`alembic/`) : autre base, autres
métadonnées (`registre_plateforme`). Elle se joue par `python -m app.registre.migrer`
— jamais par `alembic upgrade head`, qui migrerait la résidence. Mêmes règles que
l'autre chaîne : numéros à 4 chiffres, jamais modifier une migration appliquée,
ajouter puis retirer (`CLAUDE.md`, « Migrations Alembic »).
"""

from alembic import context

import app.registre.modeles  # noqa: F401 — enregistre les tables de la plateforme
from app.registre.modeles import registre_plateforme

config = context.config
target_metadata = registre_plateforme.metadata


def _migrer(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


#  Toujours EN LIGNE, sur la connexion que `app.registre.migrer` transmet : elle vient
#  du moteur de la plateforme, jamais d'une URL lue ailleurs.
_migrer(config.attributes["connection"])
