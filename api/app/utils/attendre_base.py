"""Attendre que la base RÉPONDE avant de la migrer — lu par `start.sh` (#1759, DI-7).

## Pourquoi

Le serveur de base (conteneur voisin) peut démarrer après l'API. Sans attente,
`utils/schema_initial` la trouvait illisible (« inconnu », il ne pose rien),
puis `alembic upgrade head` l'atteignait une seconde plus tard — VIDE — sans
qu'aucun schéma initial y soit posé : une base « existante » cassée.

## Ce que fait `attendre`

Il essaie de se connecter jusqu'à ce que la base réponde, ou jusqu'au délai.
Délai dépassé : code 1, et `start.sh` (`set -e`) s'arrête — Docker relance le
conteneur. On ne migre JAMAIS une base qu'on n'a pas pu lire.

Lancé par le seul processus du conteneur, avant uvicorn. 🔒 `tests/test_attendre_base.py`.
"""

from __future__ import annotations

import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.utils.revision_base import config_alembic

#: Le temps laissé à une base serveur pour démarrer à côté de l'API.
DELAI_SECONDES = 90
PAS_SECONDES = 2


def attendre(
    url: str | None = None, delai: float = DELAI_SECONDES, pas: float = PAS_SECONDES
) -> bool:
    """`True` dès que la base répond à `SELECT 1` ; `False` au bout du délai."""
    adresse = url or config_alembic().get_main_option("sqlalchemy.url")
    fin = time.monotonic() + delai
    moteur = create_engine(adresse, poolclass=NullPool)
    try:
        while True:
            try:
                with moteur.connect() as connexion:
                    connexion.execute(text("SELECT 1"))
                return True
            except Exception:  # noqa: BLE001 — toute erreur de connexion : on réessaie
                if time.monotonic() >= fin:
                    return False
                time.sleep(pas)
    finally:
        moteur.dispose()


if __name__ == "__main__":
    if attendre():
        print("joignable")
        sys.exit(0)
    print(f"injoignable après {DELAI_SECONDES} s")
    sys.exit(1)
