"""La 0282 met à jour le paragraphe des durées d'affichage dans la politique servie (#1846).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire qui porte
la politique telle que la 0252 l'a laissée.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.seed.contenus_legaux import DEFAULT_LEGAL, TELEMETRIE_PERFORMANCE
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

MIGRATION = charger_migration("0282_politique_donnees_affichees")
#: La politique servie avant la 0282 : le gabarit, avec l'ancien paragraphe.
SERVIE = DEFAULT_LEGAL["politique_confidentialite"].replace(TELEMETRIE_PERFORMANCE, MIGRATION.AVANT)


def _moteur(page: str):
    m = moteur_memoire()
    with m.begin() as conn:
        conn.execute(
            text("INSERT INTO config_site (cle, valeur) VALUES ('politique_confidentialite', :v)"),
            {"v": page},
        )
    return m


def _jouer(moteur, sens: str = "upgrade") -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(MIGRATION, sens)()


def _politique(moteur) -> str:
    with moteur.connect() as conn:
        return conn.execute(
            text("SELECT valeur FROM config_site WHERE cle = 'politique_confidentialite'")
        ).scalar()


def test_le_gabarit_porte_le_nouveau_paragraphe_et_plus_l_ancien():
    gabarit = DEFAULT_LEGAL["politique_confidentialite"]
    assert gabarit.count(TELEMETRIE_PERFORMANCE) == 1
    assert MIGRATION.AVANT not in gabarit
    #  Cas zéro : la politique servie porte bien l'ancien, sinon rien n'est éprouvé.
    assert SERVIE.count(MIGRATION.AVANT) == 1


def test_la_politique_servie_nomme_l_affichage_des_donnees():
    moteur = _moteur(SERVIE)
    _jouer(moteur)
    _jouer(moteur)  # idempotente : `start.sh` rejoue après un arrêt
    politique = _politique(moteur)
    assert politique.count(TELEMETRIE_PERFORMANCE) == 1
    assert MIGRATION.AVANT not in politique


def test_un_texte_reformule_a_la_main_n_est_pas_touche():
    reformule = SERVIE.replace(MIGRATION.AVANT, "<li>Mes propres mots.</li>")
    moteur = _moteur(reformule)
    _jouer(moteur)
    assert _politique(moteur) == reformule


def test_le_retour_arriere_rend_l_ancien_paragraphe():
    moteur = _moteur(SERVIE)
    _jouer(moteur)
    _jouer(moteur, "downgrade")
    assert _politique(moteur) == SERVIE
