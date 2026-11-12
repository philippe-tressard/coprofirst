"""La 0333 pose `ticket_prestataire` et REPREND l'intervenant de chaque affaire (#2704).

La base est celle de la production d'avant : sans la table. Une affaire avec
intervenant reçoit une ligne de rang 0 ; une affaire sans n'en reçoit aucune ;
une affaire dont l'intervenant a disparu n'en reçoit pas non plus (la clé
étrangère la refuserait) — sa colonne reste, et la lecture se tait. Rejouée,
la migration n'écrit rien de plus ; défaite, la table part.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlmodel import Session

from app.models.core import Ticket
from app.models.prestataires import Prestataire

from tests import aides_migrations
from tests.aides_base import moteur_de_test


def _jouer(moteur, pas) -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            pas()


def _lignes(moteur) -> list[tuple]:
    with moteur.connect() as conn:
        return list(
            conn.execute(
                sa.text(
                    "SELECT t.numero, tp.prestataire_id, tp.rang FROM ticket_prestataire tp "
                    "JOIN ticket t ON t.id = tp.ticket_id ORDER BY t.numero"
                )
            ).all()
        )


def test_la_reprise_pose_une_ligne_de_rang_0_par_affaire_qui_a_un_intervenant():
    moteur = moteur_de_test(cles_etrangeres=True)
    with moteur.begin() as conn:
        conn.execute(sa.text("DROP TABLE ticket_prestataire"))
    with Session(moteur) as s:
        p = Prestataire(nom="Ascenseurs Témoin", specialite="ascenseur")
        s.add(p)
        s.commit()
        prestataire = p.id
        for numero, pid in (("TK-1", prestataire), ("TK-2", None), ("TK-3", 999_999)):
            s.add(Ticket(numero=numero, titre="t", description="d", prestataire_id=pid))
        s.commit()
    assert "ticket_prestataire" not in sa.inspect(moteur).get_table_names(), "cas zéro"

    migration = aides_migrations.charger_migration("0333")
    _jouer(moteur, migration.upgrade)
    assert _lignes(moteur) == [("TK-1", prestataire, 0)]
    _jouer(moteur, migration.upgrade)  # un redémarrage la rejoue : rien de plus
    assert _lignes(moteur) == [("TK-1", prestataire, 0)]

    _jouer(moteur, migration.downgrade)
    assert "ticket_prestataire" not in sa.inspect(moteur).get_table_names()
    moteur.dispose()
