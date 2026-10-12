"""La 0283 donne à chaque document, rapport et affiche la CLÉ de son fichier (#1816).

Exécutée pour de vrai par le contexte d'Alembic, sur une base au schéma d'AVANT :
les trois tables avec leur seul chemin absolu, tel qu'il est en production
(`/app/uploads/prive/…`, `/app/uploads/annonces-hall/…`). Sous `TESTS_BASE_URL`,
la même chose sur PostgreSQL.
"""

from __future__ import annotations

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

_MIGRATION = "0283_cle_des_fichiers"


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration(_MIGRATION), sens)()


def _moteur():
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(text("CREATE TABLE document (id INTEGER PRIMARY KEY, fichier_chemin VARCHAR)"))
        conn.execute(
            text("CREATE TABLE diagnostic_rapport (id INTEGER PRIMARY KEY, fichier_chemin VARCHAR)")
        )
        conn.execute(text("CREATE TABLE annonce_hall (id INTEGER PRIMARY KEY, pdf_chemin VARCHAR)"))
        conn.execute(
            text(
                "INSERT INTO document (id, fichier_chemin) VALUES "
                "(1, '/app/uploads/prive/0a1b_reglement.pdf'), (2, '/ailleurs/x.pdf'), (3, '')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO diagnostic_rapport (id, fichier_chemin) "
                "VALUES (1, '/app/uploads/prive/9f_dpe.pdf')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO annonce_hall (id, pdf_chemin) "
                "VALUES (1, '/app/uploads/annonces-hall/c3.pdf'), (2, '')"
            )
        )
    return m


def _lire(moteur, sql: str) -> list:
    with moteur.connect() as conn:
        return [tuple(r) for r in conn.execute(text(sql))]


def test_les_cles_se_deduisent_des_chemins_de_production():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    assert _lire(moteur, "SELECT id, fichier_cle FROM document ORDER BY id") == [
        (1, "prive/0a1b_reglement.pdf"),
        #  Hors des dossiers connus, ou vide : pas de clé, donc pas de fichier
        #  depuis le second temps (0284). Aucune en production (relevé du 12/10).
        (2, None),
        (3, None),
    ]
    assert _lire(moteur, "SELECT fichier_cle FROM diagnostic_rapport") == [("prive/9f_dpe.pdf",)]
    assert _lire(moteur, "SELECT pdf_cle FROM annonce_hall ORDER BY id") == [
        ("annonces-hall/c3.pdf",),
        (None,),
    ]
    #  Le chemin reste : la version précédente le relit (#1757).
    assert _lire(moteur, "SELECT fichier_chemin FROM document WHERE id = 1") == [
        ("/app/uploads/prive/0a1b_reglement.pdf",)
    ]


def test_le_retour_arriere_retire_les_trois_colonnes():
    moteur = _moteur()
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    with moteur.connect() as conn:
        noms = {
            t: {c["name"] for c in inspect(conn).get_columns(t)}
            for t in ("document", "diagnostic_rapport", "annonce_hall")
        }
    assert "fichier_cle" not in noms["document"] | noms["diagnostic_rapport"]
    assert "pdf_cle" not in noms["annonce_hall"]


@pytest.mark.parametrize(
    "chemin, cle",
    [
        ("/app/uploads/prive/a.pdf", "prive/a.pdf"),
        ("/app/uploads/essai-b/prive/a.pdf", "prive/a.pdf"),
        ("C:\\uploads\\prive\\a.pdf", "prive/a.pdf"),
        ("/app/uploads/photos/a.jpg", None),
        ("/app/uploads/prive/..", None),
        ("a.pdf", None),
        ("", None),
        (None, None),
    ],
)
def test_la_cle_ne_se_deduit_que_d_un_dossier_connu(chemin, cle):
    assert charger_migration(_MIGRATION).cle_du_chemin(chemin) == cle
