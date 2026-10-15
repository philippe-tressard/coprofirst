"""Le schéma initial — la base de la chaîne.

Une base NEUVE reçoit le schéma courant d'un coup, par `utils/schema_initial`
(`start.sh`), et se marque à cette révision ou à la tête de la chaîne. Une base
en service est déjà à cette révision. Cette migration n'a donc rien à poser :
elle est le point de départ des suivantes.

Toute migration suivante reste compatible avec la version précédente du code
(« ajouter, puis retirer », `test_migrations_compatibles.py`).

Revision ID: 0286
Revises:
"""

revision = "0286"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
