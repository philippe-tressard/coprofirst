"""La 0276 : auteurs facultatifs, fermeture d'un compte, politique servie (#1688, #1821, #1822).

Exécutée pour de vrai par le contexte d'Alembic, sur une base au schéma d'AVANT :
la référence au compte obligatoire sur chaque table gardée, des lignes dedans,
des comptes ouverts, en attente et fermés, et la politique telle que la
production la sert. Sous `TESTS_BASE_URL`, la même chose sur PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from app.seed.contenus_legaux import (
    ANONYMISATION_CONTENUS,
    COMPTES_FERMES,
    COMPTES_FERMES_ANCIEN,
    CONSERVATION_COMPTES,
)
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

_MIGRATION = "0276_comptes_supprimes_et_fermes"
#: Lues dans la migration : c'est SA liste qu'on éprouve, sur chaque table.
_COLONNES = charger_migration(_MIGRATION).COLONNES
#: La politique telle que la production la sert AVANT : l'ancienne phrase des
#: comptes fermés, et rien sur ce qui reste d'un compte supprimé.
_SERVIE = CONSERVATION_COMPTES.replace(COMPTES_FERMES, COMPTES_FERMES_ANCIEN)
_POLITIQUE = "<ul><li>" + _SERVIE + "</li><li>Sauvegardes.</li></ul>"
_DECIDE = datetime(2020, 1, 1)


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration(_MIGRATION), sens)()


def _moteur():
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        for table, colonne in _COLONNES:
            conn.execute(
                text(
                    f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, "  # noqa: S608 — constantes du test
                    f"{colonne} INTEGER NOT NULL, contenu VARCHAR)"
                )
            )
            conn.execute(text(f"INSERT INTO {table} VALUES (1, 7, 'texte')"))  # noqa: S608
        conn.execute(
            text(
                "CREATE TABLE utilisateur (id INTEGER PRIMARY KEY, actif BOOLEAN NOT NULL, "
                "decision_compte_le TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO utilisateur VALUES (1, :oui, :d), (2, :non, NULL), (3, :non, :d)"
            ).bindparams(oui=True, non=False, d=_DECIDE)
        )
        conn.execute(text("CREATE TABLE config_site (cle VARCHAR PRIMARY KEY, valeur TEXT)"))
        conn.execute(
            text("INSERT INTO config_site VALUES ('politique_confidentialite', :v)").bindparams(
                v=_POLITIQUE
            )
        )
    return m


def _facultatives(moteur) -> dict[str, bool]:
    with moteur.connect() as conn:
        return {
            t: next(c["nullable"] for c in inspect(conn).get_columns(t) if c["name"] == col)
            for t, col in _COLONNES
        }


def _politique(moteur) -> str:
    with moteur.connect() as conn:
        return conn.execute(text("SELECT valeur FROM config_site")).scalar()


def test_les_auteurs_deviennent_facultatifs_et_les_lignes_restent():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    assert all(_facultatives(moteur).values())
    with moteur.begin() as conn:
        for table, col in _COLONNES:
            assert conn.execute(text(f"SELECT {col} FROM {table}")).scalar() == 7  # noqa: S608
            conn.execute(text(f"UPDATE {table} SET {col} = NULL"))  # noqa: S608


def test_seuls_les_comptes_deja_fermes_sont_classes_desactives_et_dates_d_aujourd_hui():
    moteur = _moteur()
    avant = datetime.now()
    _jouer(moteur)
    with moteur.connect() as conn:
        lignes = {
            r.id: r
            for r in conn.execute(
                text("SELECT id, fermeture_compte, compte_ferme_le FROM utilisateur")
            )
        }
    assert lignes[1].fermeture_compte is None, "un compte ouvert n'est pas fermé"
    assert lignes[2].fermeture_compte is None, "un compte en attente n'est pas fermé"
    assert lignes[3].fermeture_compte == "desactivation"
    #  Jamais la date de la décision (2020) : la durée partirait trop tôt.
    ferme_le = lignes[3].compte_ferme_le
    ferme_le = datetime.fromisoformat(ferme_le) if isinstance(ferme_le, str) else ferme_le
    assert ferme_le.year >= avant.year and ferme_le > _DECIDE


def test_la_politique_servie_dit_les_durees_et_ce_qui_reste():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)
    servie = _politique(moteur)
    assert COMPTES_FERMES in servie and COMPTES_FERMES_ANCIEN not in servie
    assert servie.count(ANONYMISATION_CONTENUS) == 1


def test_le_retour_arriere_rend_l_etat_d_avant_et_n_invente_pas_d_auteur():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert not any(_facultatives(moteur).values())
    assert _politique(moteur) == _POLITIQUE
    with moteur.connect() as conn:
        assert "fermeture_compte" not in {
            c["name"] for c in inspect(conn).get_columns("utilisateur")
        }

    _jouer(moteur)
    with moteur.begin() as conn:
        conn.execute(text("UPDATE ticket SET auteur_id = NULL"))
    with pytest.raises(RuntimeError, match="sans auteur"):
        _jouer(moteur, "downgrade")
