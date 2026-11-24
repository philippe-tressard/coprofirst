"""La 0350 remplace « 🗂️ Archives » par « 📁 Archives » dans la FAQ livrée (#3002).

Ses deux textes sont recopiés (une migration ne lit pas un seed qui bouge) : ce test
les tient égaux à ce qu'ils copient — l'ancienne rédaction est celle que la 0348 a
posée, la nouvelle est celle du seed. Joué sur une base : la réponse intacte change,
une réponse retouchée par le conseil ne bouge pas, et la descente la rend.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.models.residence import FaqItem
from app.seed.faq import FAQ_COMPLEMENTAIRE
from tests import aides_migrations
from tests.aides_base import moteur_de_test

_0350 = aides_migrations.charger_migration("0350")


def test_les_textes_recopies_sont_ceux_qu_ils_copient():
    assert _0350.ANCIENNE == aides_migrations.charger_migration("0348").NOUVELLE
    assert [r for _c, q, r, _o in FAQ_COMPLEMENTAIRE if q == _0350.QUESTION] == [_0350.NOUVELLE]
    assert "🗂️" in _0350.ANCIENNE and "📁" in _0350.NOUVELLE


def _jouer(moteur, pas) -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            pas()


def _reponses(moteur) -> list[str]:
    with moteur.connect() as conn:
        return list(conn.execute(sa.text("SELECT reponse FROM faq_item ORDER BY id")).scalars())


def test_la_reponse_intacte_change_la_retouchee_reste():
    moteur = moteur_de_test()
    retouchee = _0350.ANCIENNE + " Retouchée par le conseil."
    with moteur.begin() as conn:
        for reponse in (_0350.ANCIENNE, retouchee):
            conn.execute(
                sa.insert(FaqItem.__table__).values(
                    question=_0350.QUESTION, reponse=reponse, categorie="Affaires", ordre=0
                )
            )
    _jouer(moteur, _0350.upgrade)
    assert _reponses(moteur) == [_0350.NOUVELLE, retouchee]
    _jouer(moteur, _0350.downgrade)
    assert _reponses(moteur) == [_0350.ANCIENNE, retouchee]
