"""La base est-elle EN AVANCE sur le code ? — lu par `start.sh` avant `alembic` (#1756).

## Pourquoi

Revenir à la version précédente doit n'être qu'un changement d'image : les
migrations sont compatibles d'une version à l'autre (on ajoute, puis on retire à
la version suivante — `tests/test_migrations_compatibles.py`, #1757). Mais
l'ancienne image ne CONNAÎT pas la révision que la nouvelle a posée : son
`alembic upgrade head` échoue sur « Can't locate revision », et `start.sh`, sous
`set -e`, arrête le conteneur. L'API redémarre alors en boucle, et la promesse du
retour arrière ne tient pas — sur une réplique (D15, un seul serveur), c'est le
seul filet.

## Ce que ce module répond

| La table `alembic_version` porte… | Réponse    | `start.sh`                       |
|-----------------------------------|------------|----------------------------------|
| une révision que ce code connaît  | `connue`   | `alembic upgrade head`, comme avant |
| aucune ligne, ou pas de table     | `vide`     | idem : la base est neuve          |
| une révision INCONNUE de ce code  | `en_avance`| saute les migrations, et le DIT   |
| (la lecture échoue)               | `inconnu`  | `alembic upgrade head` : on ne devine pas |

« Inconnue » veut dire « posée par une version plus récente » : une migration
appliquée ne disparaît jamais d'une version à la suivante, sauf retour arrière.

⚠️ La base est ouverte AVANT uvicorn, par le seul processus du conteneur : ce
n'est pas l'ouverture par un tiers que la règle d'or interdit (CLAUDE.md).
🔒 `tests/test_revision_base.py`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def config_alembic(ini: Path = ALEMBIC_INI) -> Config:
    """La configuration d'Alembic, pointée sur LA base de l'application.

    `DATABASE_URL` l'emporte sur `alembic.ini` (#1747) : c'est la variable que
    lit l'API, et une installation sur PostgreSQL n'a que celle-là. L'écrire une
    fois ici garde Alembic, `start.sh` et l'API sur la même base.
    """
    config = Config(str(ini))
    config.set_main_option("script_location", str(ini.parent / "alembic"))
    url = os.environ.get("DATABASE_URL")
    if url:
        #  `%` est l'interpolation d'`alembic.ini` : un mot de passe qui en porte
        #  se double, sinon la configuration lève.
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def _lire(url: str | None, ini: Path) -> tuple[set[str], set[str], list[str] | None]:
    """(révisions connues de ce code, ses têtes, révisions posées en base — `None` sans
    table). Lève si la base ne se lit pas : chaque appelant dit ce que l'échec veut dire."""
    config = config_alembic(ini)
    script = ScriptDirectory.from_config(config)
    connues = {r.revision for r in script.walk_revisions()}
    moteur = create_engine(url or config.get_main_option("sqlalchemy.url"))
    try:
        with moteur.connect() as connexion:
            if "alembic_version" not in inspect(connexion).get_table_names():
                return connues, set(script.get_heads()), None
            posees = [
                r[0] for r in connexion.execute(text("SELECT version_num FROM alembic_version"))
            ]
    finally:
        moteur.dispose()
    return connues, set(script.get_heads()), posees


def etat_revision(url: str | None = None, ini: Path = ALEMBIC_INI) -> str:
    """`connue` | `vide` | `en_avance` | `inconnu` — voir la table du module."""
    try:
        connues, _tetes, posees = _lire(url, ini)
    except Exception:  # noqa: BLE001 — toute erreur de lecture rend « inconnu », jamais un verdict
        return "inconnu"
    if not posees:
        return "vide"
    return "connue" if all(p in connues for p in posees) else "en_avance"


def servable(url: str, ini: Path = ALEMBIC_INI) -> bool:
    """Ce code peut-il servir cette base ? À la tête de sa chaîne, ou EN AVANCE (un
    retour arrière, que les migrations compatibles permettent, #1757) — jamais une base
    neuve, en retard ou illisible : la servir rendrait 500 à la première colonne neuve
    (`installation_commune/bases_pretes`, #2053)."""
    try:
        connues, tetes, posees = _lire(url, ini)
    except Exception:  # noqa: BLE001 — illisible : on ne sert pas
        return False
    if not posees:
        return False
    return set(posees) == tetes or not all(p in connues for p in posees)


if __name__ == "__main__":
    print(etat_revision())
    sys.exit(0)
