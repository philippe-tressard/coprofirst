"""Une requête `text()` dont les dates se comparent comme la base les stocke — `requete_liee` (#1569, #1298).

Un seuil lié tel quel en `datetime.isoformat()` part en TEXTE, comparé à un
horodatage : le jour du seuil, une purge avait effacé des jetons de session encore
valides. Le module n'était nommé par aucun test ; `test_purge_dates_liees.py` ne
tient que les appelants.

Ici, sur une base réelle : le verdict correct, puis les paramètres qui ne sont pas
des dates.
"""

from __future__ import annotations

from datetime import datetime


from app.utils.requete_liee import requete_liee
from tests.aides_base import compte

SEUIL = datetime(2026, 9, 25, 12, 0, 0)


def _ids(session, requete) -> set[int]:
    return {r[0] for r in session.execute(requete).all()}


def _comptes_crees_a(session, *heures: datetime) -> list[int]:
    ids = []
    for h in heures:
        u = compte(session, prefixe="rl")
        u.cree_le = h
        session.add(u)
        session.commit()
        ids.append(u.id)
    return ids


def test_un_datetime_se_compare_comme_la_base_le_stocke(session):
    avant_le_seuil, apres_le_seuil, la_veille, le_lendemain = _comptes_crees_a(
        session,
        datetime(2026, 9, 25, 8, 0),
        datetime(2026, 9, 25, 18, 0),
        datetime(2026, 9, 24, 23, 59),
        datetime(2026, 9, 26, 0, 1),
    )

    anterieurs = _ids(
        session, requete_liee("SELECT id FROM utilisateur WHERE cree_le < :s", s=SEUIL)
    )
    posterieurs = _ids(
        session, requete_liee("SELECT id FROM utilisateur WHERE cree_le >= :s", s=SEUIL)
    )

    assert anterieurs == {avant_le_seuil, la_veille}
    assert posterieurs == {apres_le_seuil, le_lendemain}
    assert anterieurs.isdisjoint(posterieurs)


def test_a_l_instant_du_seuil_la_ligne_n_est_pas_anterieure(session):
    [pile] = _comptes_crees_a(session, SEUIL)

    assert pile not in _ids(
        session, requete_liee("SELECT id FROM utilisateur WHERE cree_le < :s", s=SEUIL)
    )
    assert pile in _ids(
        session, requete_liee("SELECT id FROM utilisateur WHERE cree_le <= :s", s=SEUIL)
    )


def test_les_autres_parametres_sont_lies_tels_quels(session):
    u = compte(session, prefixe="rl")

    trouve = _ids(session, requete_liee("SELECT id FROM utilisateur WHERE id = :i", i=u.id))
    absent = _ids(
        session, requete_liee("SELECT id FROM utilisateur WHERE email = :e", e="nul@exemple.test")
    )

    assert trouve == {u.id}
    assert absent == set()


def test_plusieurs_parametres_se_melangent(session):
    ancien, recent = _comptes_crees_a(session, datetime(2026, 9, 1), datetime(2026, 10, 1))

    ids = _ids(
        session,
        requete_liee(
            "SELECT id FROM utilisateur WHERE cree_le < :s AND id IN (:a, :b)",
            s=SEUIL,
            a=ancien,
            b=recent,
        ),
    )

    assert ids == {ancien}


def test_sans_parametre_la_requete_est_un_text_ordinaire(session):
    requete = requete_liee("SELECT 1")
    assert session.execute(requete).scalar() == 1
