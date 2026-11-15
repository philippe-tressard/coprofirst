"""On note le couple prestataire / affaire (15/11/2026).

Un avis peut porter sur une affaire où le prestataire est intervenant désigné ; plusieurs
membres peuvent noter le même couple. Une affaire d'un autre prestataire est refusée.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.core import RoleUtilisateur
from app.routers.prestataires import NotationCreate, create_notation, list_notations
from app.routers.prestataires_metriques import lire_affaires_du_prestataire
from tests.aides_affaire import _compte, _creer, _prestataire, session  # noqa: F401

CS = RoleUtilisateur.conseil_syndical


def _noter(session, qui, p, affaire, etat="neutre"):
    return create_notation(
        body=NotationCreate(prestataire_id=p.id, etat=etat, ticket_id=affaire.id),
        session=session,
        user=qui,
    )


def test_deux_membres_notent_le_meme_couple_et_l_avis_porte_le_titre(session):
    cs, autre = _compte(session, role=CS), _compte(session, role=CS)
    p = _prestataire(session)
    affaire = _creer(session, cs, categorie="panne", prestataire_id=p.id)
    _noter(session, cs, p, affaire)
    _noter(session, autre, p, affaire, etat="excellent")
    lues = list_notations(prestataire_id=p.id, session=session, _=cs)
    assert sorted(n.etat for n in lues) == ["excellent", "neutre"]
    assert {(n.ticket_id, n.ticket_titre) for n in lues} == {(affaire.id, affaire.titre)}


def test_une_affaire_d_un_autre_prestataire_est_refusee(session):
    cs = _compte(session, role=CS)
    p, q = _prestataire(session), _prestataire(session)
    affaire = _creer(session, cs, categorie="panne", prestataire_id=q.id)
    with pytest.raises(HTTPException) as e:
        _noter(session, cs, p, affaire)
    assert e.value.status_code == 400


def test_les_affaires_proposees_sont_celles_du_prestataire(session):
    cs = _compte(session, role=CS)
    p, q = _prestataire(session), _prestataire(session)
    a = _creer(session, cs, categorie="panne", prestataire_id=p.id)
    b = _creer(session, cs, categorie="panne", prestataire_id=q.id)
    ids = [x.id for x in lire_affaires_du_prestataire(p_id=p.id, session=session, _=cs)]
    assert a.id in ids
    assert b.id not in ids
