"""La 0250 retire `evenement.archivee` sans toucher à une ligne (#1568, 02/10/2026).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire au
schéma d'AVANT : celui des modèles d'aujourd'hui, plus la colonne que la 0049 y
avait posée (`BOOLEAN NOT NULL DEFAULT 0`, en fin de table, comme en production),
des événements dont certains portent `archivee = 1`, et des lignes qui en
dépendent par clé étrangère — `PRAGMA foreign_keys` allumé comme l'API le fait.

`start.sh` lance `alembic upgrade head` sous `set -e` : une migration qui plante
bloque le conteneur. Ce fichier tient donc trois choses — la colonne PART, les
lignes (et leurs dépendantes) RESTENT, et la rejouer ne casse rien.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlmodel import Session

from app.models.documents import Document
from app.models.evenement import Evenement, EvenementEvolution
from tests.aides_base import compte, moteur_memoire
from tests.aides_migrations import charger_migration

_MIGRATION = "0250_evenement_sans_archivee.py"


def _module():
    return charger_migration(_MIGRATION)


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(_module(), sens)()


def _colonnes(moteur) -> list[str]:
    return [c["name"] for c in inspect(moteur).get_columns("evenement")]


@pytest.fixture()
def avant():
    """La base d'avant : schéma courant + `archivee`, trois événements, des dépendantes."""
    moteur = moteur_memoire(cles_etrangeres=True)
    with moteur.begin() as conn:
        conn.execute(text("ALTER TABLE evenement ADD COLUMN archivee BOOLEAN NOT NULL DEFAULT 0"))
    with Session(moteur) as session:
        auteur = compte(session)
        evenements = [
            Evenement(titre=titre, auteur_id=auteur.id, debut=debut)
            for titre, debut in (
                ("Visite de l'ascensoriste", datetime(2026, 3, 4, 9, 30)),
                ("Assemblée générale", datetime(2026, 5, 12, 18, 0)),
                ("Collecte des encombrants", datetime(2026, 6, 1, 8, 0)),
            )
        ]
        session.add_all(evenements)
        session.commit()
        ids = [e.id for e in evenements]
        session.add(
            EvenementEvolution(evenement_id=ids[0], type="commentaire", auteur_id=auteur.id)
        )
        session.add(
            Document(
                titre="Plan d'accès",
                fichier_nom="plan.pdf",
                evenement_id=ids[1],
                publie_par_id=auteur.id,
            )
        )
        session.commit()
    with moteur.begin() as conn:
        conn.execute(
            text("UPDATE evenement SET archivee = 1 WHERE id IN (:a, :b)"),
            {"a": ids[0], "b": ids[2]},
        )
    yield moteur, ids
    moteur.dispose()


def _lignes(moteur) -> list[tuple]:
    """Tout ce que la table porte, SAUF la colonne qui part — dans l'ordre des identifiants."""
    with moteur.connect() as conn:
        return [
            tuple(r)
            for r in conn.execute(
                text(
                    "SELECT id, titre, debut, auteur_id, perimetre, statut_kanban, epingle "
                    "FROM evenement ORDER BY id"
                )
            )
        ]


def _compte(moteur, table: str) -> int:
    with moteur.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()  # noqa: S608


def test_cas_zero_la_base_d_avant_porte_la_colonne_et_les_cles_etrangeres(avant):
    """Le témoin doit SERVIR : sans lui, la suite passerait sur une base qui n'a rien à retirer."""
    moteur, ids = avant
    assert "archivee" in _colonnes(moteur)
    with moteur.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        archives = conn.execute(text("SELECT COUNT(*) FROM evenement WHERE archivee = 1")).scalar()
    assert archives == 2
    assert _compte(moteur, "evenement_evolution") == 1
    assert _compte(moteur, "document") == 1


def test_la_colonne_part_et_le_reste_de_la_table_est_intact(avant):
    moteur, ids = avant
    lignes_avant = _lignes(moteur)
    colonnes_avant = [c for c in _colonnes(moteur) if c != "archivee"]

    _jouer(moteur)

    assert "archivee" not in _colonnes(moteur)
    assert _colonnes(moteur) == colonnes_avant, "une autre colonne a bougé, ou changé de place"
    assert _lignes(moteur) == lignes_avant
    assert [ligne[0] for ligne in lignes_avant] == ids


def test_les_lignes_qui_dependent_des_evenements_restent(avant):
    """`evenement` est la cible de clés étrangères : on ne la recopie ni ne la recrée."""
    moteur, _ = avant
    _jouer(moteur)
    assert _compte(moteur, "evenement_evolution") == 1
    assert _compte(moteur, "document") == 1
    with moteur.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_key_check")).fetchall() == []
        assert conn.execute(text("PRAGMA integrity_check")).scalar() == "ok"


def test_le_schema_migre_est_celui_du_modele(avant):
    """Base neuve et base migrée portent la même table (CLAUDE.md, « Migrations Alembic »)."""
    moteur, _ = avant
    _jouer(moteur)
    assert set(_colonnes(moteur)) == set(Evenement.__table__.c.keys())


def test_la_migration_est_idempotente(avant):
    moteur, _ = avant
    _jouer(moteur)
    une_fois = (_colonnes(moteur), _lignes(moteur))
    _jouer(moteur)
    assert (_colonnes(moteur), _lignes(moteur)) == une_fois


def test_une_table_absente_ne_plante_pas():
    """Une base sans la table : rien à faire, et surtout pas de crash au démarrage."""
    moteur = moteur_memoire(schema=False)
    _jouer(moteur)
    _jouer(moteur, "downgrade")


def test_le_retour_arriere_retablit_la_colonne_comme_la_0049_la_posait(avant):
    moteur, ids = avant
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    colonnes = {c["name"]: c for c in inspect(moteur).get_columns("evenement")}
    assert "archivee" in colonnes
    assert colonnes["archivee"]["nullable"] is False
    with moteur.connect() as conn:
        valeurs = conn.execute(text("SELECT DISTINCT archivee FROM evenement")).fetchall()
    assert [tuple(v) for v in valeurs] == [(0,)], "toutes les lignes reprennent le défaut"
    assert _compte(moteur, "evenement") == len(ids)
    _jouer(moteur, "downgrade")  # rejouable
    _jouer(moteur)
    assert "archivee" not in _colonnes(moteur)
