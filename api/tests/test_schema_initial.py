"""La migration initiale : une base neuve reçoit le schéma courant, marqué à la tête (#1747).

`app/utils/schema_initial.py` est lancé par `start.sh` avant `alembic upgrade
head`. Ces tests le jouent sur une base PostgreSQL neuve — un schéma vide, seul visible
(`url_neuve`) : c'est la migration initiale de la spec §4.3.
"""

from __future__ import annotations

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

import app.models.core  # noqa: F401 — toutes les tables, comme le module testé
from app.utils.revision_base import config_alembic
from app.utils.schema_initial import poser_si_neuve
from tests.aides_base import adresse_de_test
from tests.aides_processus import SERVEUR_INJOIGNABLE


def _tete() -> str:
    return ScriptDirectory.from_config(config_alembic()).get_current_head()


@pytest.fixture
def url_neuve():
    """L'adresse d'une base VIDE, telle que l'application la voit : un schéma neuf, retiré à la fin.

    C'était une BASE créée puis détruite. Sous Windows, `DROP DATABASE` force un
    point de contrôle du serveur entier : 60 à 140 s par test pendant que la suite
    parallèle écrit (#2223), la plus longue attente de toute la suite. Un schéma
    seul visible (`search_path`) est, pour le module testé comme pour Alembic,
    une base qui ne contient rien.
    """
    adresse, retirer = adresse_de_test()
    try:
        yield adresse
    finally:
        retirer()


def _lire(url: str) -> tuple[set[str], list[str]]:
    moteur = create_engine(url, poolclass=NullPool)
    try:
        with moteur.connect() as c:
            tables = set(inspect(c).get_table_names())
            versions = (
                [r[0] for r in c.execute(text("SELECT version_num FROM alembic_version"))]
                if "alembic_version" in tables
                else []
            )
    finally:
        moteur.dispose()
    return tables, versions


def test_une_base_neuve_recoit_tout_le_schema_marque_a_la_tete(url_neuve):
    assert poser_si_neuve(url_neuve) == "posee"
    tables, versions = _lire(url_neuve)
    assert set(SQLModel.metadata.tables) <= tables
    assert versions == [_tete()]


def test_alembic_n_a_plus_rien_a_faire_ensuite(url_neuve):
    """`start.sh` enchaîne `alembic upgrade head` : sur une base marquée, il ne rejoue rien."""
    poser_si_neuve(url_neuve)
    moteur = create_engine(url_neuve, poolclass=NullPool)
    try:
        config = config_alembic()
        with moteur.begin() as connexion:
            config.attributes["connection"] = connexion
            command.upgrade(config, "head")
    finally:
        moteur.dispose()
    assert _lire(url_neuve)[1] == [_tete()]


def test_une_base_deja_posee_n_est_pas_touchee(url_neuve):
    poser_si_neuve(url_neuve)
    assert poser_si_neuve(url_neuve) == "existante"


def test_des_tables_sans_version_ne_font_pas_une_base_neuve(url_neuve):
    """La marquer à la tête lui ferait sauter les migrations dont elle a besoin."""
    moteur = create_engine(url_neuve, poolclass=NullPool)
    try:
        with moteur.begin() as c:
            c.execute(text("CREATE TABLE lot (id INTEGER PRIMARY KEY)"))
    finally:
        moteur.dispose()
    assert poser_si_neuve(url_neuve) == "existante"
    assert _lire(url_neuve) == ({"lot"}, [])


def test_une_base_injoignable_rend_inconnu():
    """Jamais « posée » ni « existante » sur ce qu'on n'a pas pu lire."""
    assert (
        poser_si_neuve(f"postgresql+psycopg://personne:x@{SERVEUR_INJOIGNABLE}/aucune") == "inconnu"
    )


#  L'ordre que `start.sh` suivait (attendre, en avance, schéma initial, migrer) vit
#  dans `app/utils/preparer_bases` depuis #2053, et s'éprouve sur son COMPORTEMENT :
#  `tests/test_preparer_bases.py`.
