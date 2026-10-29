"""Aucune transaction de la suite ne tient la table des verrous de tout le serveur (#2279).

🔴 Un verrou se prend par table ET par index, et se garde jusqu'à la fin de la
TRANSACTION. Mesuré le 29/10/2026 sur le PostgreSQL du poste (94 tables) :
`create_all` dans une transaction tenait 1 465 verrous, `DROP SCHEMA … CASCADE`
1 655. La table des verrous est PARTAGÉE (`max_locks_per_transaction` × connexions =
64 × 100 = 6 400) : quatre workers qui posaient ou retiraient un schéma au même
instant l'épuisaient — « mémoire partagée épuisée, increase max_locks_per_transaction »,
deux rejeux sur quatre le soir du 28/10.

Le correctif découpe : la pose se fait en AUTOCOMMIT (chaque instruction sa
transaction), le retrait par lots de `TABLES_PAR_LOT` tables. Ce test garde la
FORME du correctif — ce qui est tenu à la fin d'une instruction, ce que pèse la plus
lourde — et non le hasard d'un passage : l'épuisement, lui, dépend de l'instant.
Le plafond de verrous par worker est celui que `mesure-postgresql.sh` retient pour
borner les workers : une seule valeur, lue dans le script.
"""

from __future__ import annotations

import pathlib
import re
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
from sqlmodel import Session

from app import dialecte
from tests.aides_base import adresse_de_test, creer_les_tables, moteur_de_test, url_des_tests

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "ci" / "mesure-postgresql.sh"

#: Verrous encore tenus APRÈS une instruction en AUTOCOMMIT : ceux de la requête de
#: mesure elle-même, rien d'autre. Dans une transaction unique, le compte monte à 1 465.
TENUS_APRES_INSTRUCTION = 20

COMPTE = "SELECT count(*) FROM pg_locks WHERE pid = pg_backend_pid()"


def _verrous_par_worker() -> int:
    """`VERROUS_PAR_WORKER` du script qui borne les workers — sa seule écriture."""
    trouve = re.search(r"^VERROUS_PAR_WORKER=(\d+)$", SCRIPT.read_text(encoding="utf-8"), re.M)
    assert trouve, "VERROUS_PAR_WORKER n'est plus écrit dans mesure-postgresql.sh"
    return int(trouve.group(1))


@contextmanager
def _verrous_tenus_apres_chaque_instruction():
    """Le nombre de verrous que la connexion tient APRÈS chacune de ses instructions.

    Écouté sur TOUS les moteurs : `remettre_a_neuf` ouvre le sien. La mesure passe par
    la connexion du pilote — dans une transaction ouverte elle voit tout ce qu'elle
    garde, en autocommit seulement ce qu'elle prend pour se mesurer.
    """
    mesures: list[int] = []

    def apres(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT COUNT(*) FROM PG_LOCKS"):
            return
        mesures.append(cursor.connection.execute(COMPTE).fetchone()[0])

    event.listen(Engine, "after_cursor_execute", apres)
    try:
        yield mesures
    finally:
        event.remove(Engine, "after_cursor_execute", apres)


# ── Les fonctions pures ──────────────────────────────────────────────────────────────


def test_par_lots_coupe_dans_l_ordre_sans_rien_perdre():
    assert dialecte.par_lots(range(7), 3) == [[0, 1, 2], [3, 4, 5], [6]]
    assert dialecte.par_lots([], 3) == []
    assert dialecte.par_lots(["a"], 10) == [["a"]]


def test_le_retrait_vide_les_tables_par_lots_puis_retire_le_schema():
    tables = [f"t{i:02d}" for i in range(23)]
    instructions = dialecte.instructions_de_retrait("t_x", tables)
    assert instructions[-1] == 'DROP SCHEMA IF EXISTS "t_x" CASCADE'
    lots = instructions[:-1]
    assert len(lots) == 3  # 10 + 10 + 3
    assert all(i.startswith("DROP TABLE IF EXISTS ") and i.endswith(" CASCADE") for i in lots)
    for lot in lots:
        assert lot.count('"t_x".') <= dialecte.TABLES_PAR_LOT
    #  Chaque table part, une seule fois.
    nommees = [m for i in lots for m in re.findall(r'"t_x"\."(\w+)"', i)]
    assert sorted(nommees) == tables


def test_un_schema_sans_table_ne_retire_que_le_schema():
    assert dialecte.instructions_de_retrait("t_x", []) == ['DROP SCHEMA IF EXISTS "t_x" CASCADE']


# ── Ce que le serveur voit ───────────────────────────────────────────────────────────


def test_poser_les_tables_ne_tient_aucun_verrou_d_une_instruction_a_l_autre():
    adresse, retirer = adresse_de_test()
    moteur = create_engine(adresse, poolclass=NullPool)
    try:
        with _verrous_tenus_apres_chaque_instruction() as tenus:
            creer_les_tables(moteur)
        assert len(tenus) > 50, "la pose n'a émis presque rien : la mesure ne voit plus les DDL"
        assert max(tenus) <= TENUS_APRES_INSTRUCTION, (
            f"{max(tenus)} verrous tenus entre deux instructions : la pose est redevenue "
            "une seule transaction (#2279)"
        )
    finally:
        moteur.dispose()
        retirer()


def test_le_cas_zero_la_mesure_voit_une_transaction_unique():
    """Sans AUTOCOMMIT, la même pose tient plus de verrous que n'en porte un worker."""
    adresse, retirer = adresse_de_test()
    moteur = create_engine(adresse, poolclass=NullPool)
    try:
        with _verrous_tenus_apres_chaque_instruction() as tenus:
            from sqlmodel import SQLModel

            SQLModel.metadata.create_all(moteur, checkfirst=False)
        assert max(tenus) > _verrous_par_worker()
    finally:
        moteur.dispose()
        retirer()


def test_chaque_instruction_du_retrait_pese_moins_que_le_budget_d_un_worker():
    budget = _verrous_par_worker()
    adresse, retirer = adresse_de_test()
    url = url_des_tests()
    moteur = create_engine(adresse, poolclass=NullPool)
    creer_les_tables(moteur)
    with moteur.connect() as c:
        nom = c.execute(text("SELECT current_schema()")).scalar()
    moteur.dispose()
    admin = create_engine(url, poolclass=NullPool)
    try:
        with admin.connect() as c:
            tables = (
                c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = :s"), {"s": nom})
                .scalars()
                .all()
            )
        assert len(tables) > 50, "le schéma d'essai est presque vide : la mesure ne prouve rien"
        pics = []
        for instruction in dialecte.instructions_de_retrait(nom, tables):
            with admin.connect() as c:
                c.execute(text(instruction))
                pics.append(c.execute(text(COMPTE)).scalar())
                c.commit()
        assert max(pics) <= budget, (
            f"une instruction de retrait tient {max(pics)} verrous (budget {budget}) : "
            "TABLES_PAR_LOT est trop grand (#2279)"
        )
    finally:
        admin.dispose()
        retirer()  # le schéma n'existe plus : le retrait le tolère


def test_remettre_a_neuf_ne_garde_pas_ses_verrous_d_une_instruction_a_l_autre():
    from app.models.core import Copropriete
    from tests.aides_purge import remettre_a_neuf

    adresse, retirer = adresse_de_test()
    moteur = create_engine(adresse, poolclass=NullPool)
    try:
        creer_les_tables(moteur)
        with Session(moteur) as s:
            s.add(Copropriete(nom="Essai", adresse="1 rue Essai"))
            s.commit()
        with _verrous_tenus_apres_chaque_instruction() as tenus:
            assert remettre_a_neuf(adresse) >= 1
        assert tenus, "la remise à neuf n'a rien émis"
        assert max(tenus) <= TENUS_APRES_INSTRUCTION, (
            f"{max(tenus)} verrous tenus entre deux instructions : la remise à neuf est "
            "revenue à une seule transaction (#2279)"
        )
    finally:
        moteur.dispose()
        retirer()


def test_un_test_qui_demande_son_moteur_reste_sous_le_budget():
    """Le chemin de TOUS les tests : `moteur_de_test` pose, la fixture retire."""
    with _verrous_tenus_apres_chaque_instruction() as tenus:
        moteur = moteur_de_test()
        with Session(moteur) as s:
            s.exec(text("SELECT 1"))
    assert max(tenus) <= TENUS_APRES_INSTRUCTION
