"""Chaque processus de la suite a SA base d'application (#2223).

Le pourquoi : `tests/aides_processus.py`.
"""

from __future__ import annotations

import os

from tests.aides_processus import MARQUE, base_a_poser


def test_sans_adresse_le_processus_pose_la_sienne():
    assert base_a_poser({})


def test_un_worker_ne_reprend_pas_l_adresse_posee_par_le_maitre():
    herite = {"DATABASE_URL": "postgresql://maitre", MARQUE: "postgresql://maitre"}
    assert base_a_poser(herite)


def test_une_adresse_choisie_par_l_appelant_est_gardee():
    assert not base_a_poser({"DATABASE_URL": "postgresql://choisie"})
    assert not base_a_poser({"DATABASE_URL": "postgresql://choisie", MARQUE: "postgresql://autre"})


def test_ce_processus_ecrit_dans_le_schema_qu_il_a_pose():
    """Sur le vrai processus : la base de l'application est celle posée ici."""
    from tests import conftest

    if conftest._SCHEMA_DU_PROCESSUS is None:
        #  Adresse choisie par l'appelant, ou pas de serveur : rien n'est posé
        #  ici, et rien ne doit le prétendre.
        assert os.environ.get(MARQUE) != os.environ.get("DATABASE_URL")
        return
    assert conftest._SCHEMA_DU_PROCESSUS in os.environ["DATABASE_URL"]
    assert os.environ[MARQUE] == os.environ["DATABASE_URL"]


def test_chaque_fichier_trouve_la_base_remise_a_neuf():
    """Le crochet est branché : autouse, une fois par FICHIER."""
    from tests import conftest

    definition = conftest._base_du_processus_neuve._fixture_function_marker
    assert definition.autouse and definition.scope == "module"


def test_remettre_a_neuf_pose_les_tables_vide_les_lignes_et_remet_les_compteurs():
    """Sur un schéma jetable : ce qu'un fichier de tests trouve au départ."""
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.pool import NullPool
    from sqlmodel import Session, SQLModel, select

    import app.models.core  # noqa: F401
    from app.models.core import Batiment, Copropriete
    from tests.aides_base import adresse_de_test
    from tests.aides_purge import remettre_a_neuf

    adresse, retirer = adresse_de_test()
    moteur = create_engine(adresse, poolclass=NullPool)
    try:
        #  Une base sans tables : elles sont posées, et rien n'est à vider.
        assert remettre_a_neuf(adresse) == 0
        assert set(SQLModel.metadata.tables) <= set(inspect(moteur).get_table_names())

        with Session(moteur) as s:
            copro = Copropriete(nom="Test", adresse="1 rue Test")
            s.add(copro)
            s.commit()
            s.add(Batiment(copropriete_id=copro.id, numero="1"))
            s.commit()

        assert remettre_a_neuf(adresse) == 2
        with Session(moteur) as s:
            assert s.exec(select(Copropriete)).all() == []
            assert s.exec(select(Batiment)).all() == []
            neuve = Copropriete(nom="Test", adresse="1 rue Test")
            s.add(neuve)
            s.commit()
            assert neuve.id == 1, "les compteurs repartent à 1, comme une base neuve"
    finally:
        moteur.dispose()
        retirer()
