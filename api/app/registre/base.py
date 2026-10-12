"""La base `plateforme` — où le registre des installations se lit et s'écrit (D17).

Le registre n'existe que chez le MAÎTRE, et seulement quand sa base est déclarée
(`PLATEFORME_DATABASE_URL`) avec le nom sous lequel il répond (`HOTE_REGISTRE`).
Partout ailleurs — une réplique, le poste, un test qui ne le demande pas —, il est
éteint, et ses routes répondent 404 comme si elles n'existaient pas.

🔴 Le registre ne doit JAMAIS arrêter la résidence : sa base est une autre base,
migrée à part et sans `set -e` (`api/start.sh`), et une panne de la sienne ne
touche que ses routes.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import TYPE_CHECKING

from sqlmodel import Session

from app.config import get_settings
from app.utils.installation import est_reference

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def registre_actif() -> bool:
    """Le registre est-il servi par CETTE installation ? Référence, base et nom déclarés."""
    s = get_settings()
    return (
        est_reference()
        and bool(s.plateforme_database_url.strip())
        and bool(s.hote_registre.strip())
    )


#: Le moteur de la base `plateforme`, par URL — un seul par processus. Il ne porte
#: aucune donnée de copropriété : c'est la base de la PLATEFORME (déclaré dans
#: `test_etat_module_par_copropriete.DU_PROCESSUS`).
_moteurs: dict[str, Engine] = {}
_verrou = threading.Lock()


def moteur() -> Engine:
    """Le moteur de la base `plateforme`, construit par la recette commune (`creer_moteur`)."""
    from app.database import creer_moteur

    url = get_settings().plateforme_database_url.strip()
    with _verrou:
        if url not in _moteurs:
            _moteurs[url] = creer_moteur(url)
        return _moteurs[url]


def get_session_plateforme() -> Iterator[Session]:
    """Dépendance FastAPI : une session sur la base `plateforme`."""
    with Session(moteur()) as session:
        yield session
