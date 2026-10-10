"""La 0276 fait des administrateurs d'alors des opérateurs, et de personne d'autre (#1750).

Exécutée pour de vrai par le contexte d'Alembic, sur une base en mémoire.
"""

from __future__ import annotations

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration

COMPTES = {
    1: ("admin", "propriétaire,résident,admin,conseil_syndical"),
    2: ("admin", ""),  # rôle principal seul, liste vide
    3: ("conseil_syndical", "résident,conseil_syndical"),
    4: ("admin", "admin,operateur"),  # déjà opérateur
}


def _jouer(sens: str, comptes=COMPTES) -> dict[int, str]:
    m = moteur_memoire(schema=False)
    with m.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE utilisateur (id INTEGER PRIMARY KEY, role VARCHAR, roles_json VARCHAR)"
            )
        )
        for ident, (role, roles) in comptes.items():
            conn.execute(
                text("INSERT INTO utilisateur VALUES (:i, :r, :j)"),
                {"i": ident, "r": role, "j": roles},
            )
    with m.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(charger_migration("0276_operateur_de_plateforme"), sens)()
    with m.connect() as conn:
        return dict(conn.execute(text("SELECT id, roles_json FROM utilisateur")).all())


def test_chaque_administrateur_devient_operateur_et_lui_seul():
    apres = _jouer("upgrade")
    assert apres[1] == "propriétaire,résident,admin,conseil_syndical,operateur"
    assert apres[2] == "admin,operateur"
    assert apres[3] == "résident,conseil_syndical"
    assert apres[4] == "admin,operateur"


def test_rejouee_elle_ne_double_rien():
    une_fois = _jouer("upgrade")
    deux_fois = _jouer(
        "upgrade", {i: ("admin" if "admin" in r else "x", r) for i, r in une_fois.items()}
    )
    assert deux_fois == une_fois


def test_downgrade_retire_le_role_partout():
    apres = _jouer("downgrade")
    assert "operateur" not in ",".join(apres.values())
    assert apres[1] == "propriétaire,résident,admin,conseil_syndical"
