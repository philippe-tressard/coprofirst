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


def test_une_affaire_sans_le_prestataire_exige_la_confirmation_de_l_ajout(session):
    from app.routers.prestataires_notations import NotationCreate

    cs = _compte(session, role=CS)
    p, q = _prestataire(session), _prestataire(session)
    affaire = _creer(session, cs, categorie="panne", prestataire_id=q.id)
    with pytest.raises(HTTPException) as e:
        _noter(session, cs, p, affaire)
    assert e.value.status_code == 409
    assert e.value.detail["code"] == "ajout_intervenant"
    #  Confirmé : l'avis part et le prestataire rejoint l'affaire, avec une trace au suivi.
    create_notation(
        body=NotationCreate(
            prestataire_id=p.id, etat="neutre", ticket_id=affaire.id, confirmer_ajout=True
        ),
        session=session,
        user=cs,
    )
    from app.utils.prestataires_affaire import prestataires_de as _pdd
    from app.models.tickets import Ticket as T

    assert p.id in _pdd(session, session.get(T, affaire.id))
    from app.models.tickets import TicketEvolution
    from sqlmodel import select

    journal = session.exec(
        select(TicketEvolution).where(TicketEvolution.ticket_id == affaire.id)
    ).all()
    assert any(p.nom in e.contenu for e in journal)


def test_un_membre_ne_modifie_pas_l_avis_d_un_collegue(session):
    from app.routers.prestataires_notations import NotationUpdate, update_notation

    cs, autre = _compte(session, role=CS), _compte(session, role=CS)
    p = _prestataire(session)
    affaire = _creer(session, cs, categorie="panne", prestataire_id=p.id)
    avis = _noter(session, cs, p, affaire)
    with pytest.raises(HTTPException) as e:
        update_notation(avis.id, NotationUpdate(etat="excellent"), session=session, user=autre)
    assert e.value.status_code == 403


def test_l_auteur_modifie_son_avis_et_le_mauvais_reste_justifie(session):
    from app.routers.prestataires_notations import NotationUpdate, update_notation

    cs = _compte(session, role=CS)
    p = _prestataire(session)
    affaire = _creer(session, cs, categorie="panne", prestataire_id=p.id)
    avis = _noter(session, cs, p, affaire, etat="excellent")
    maj = update_notation(avis.id, NotationUpdate(etat="neutre"), session=session, user=cs)
    assert maj.etat == "neutre"
    with pytest.raises(HTTPException) as e:
        update_notation(avis.id, NotationUpdate(etat="mauvais"), session=session, user=cs)
    assert e.value.status_code == 422


def test_les_affaires_a_noter_marquent_celles_ou_le_prestataire_intervient(session):
    from app.routers.prestataires_notations import lire_affaires_a_noter

    cs = _compte(session, role=CS)
    p, q = _prestataire(session), _prestataire(session)
    a = _creer(session, cs, categorie="panne", prestataire_id=p.id)
    b = _creer(session, cs, categorie="panne", prestataire_id=q.id)
    lues = {x.id: x for x in lire_affaires_a_noter(prestataire_id=p.id, session=session, _=cs)}
    assert lues[a.id].intervient is True
    assert lues[b.id].intervient is False
    assert b.id in lues  # toutes les affaires se proposent


def test_les_affaires_proposees_sont_celles_du_prestataire(session):
    cs = _compte(session, role=CS)
    p, q = _prestataire(session), _prestataire(session)
    a = _creer(session, cs, categorie="panne", prestataire_id=p.id)
    b = _creer(session, cs, categorie="panne", prestataire_id=q.id)
    ids = [x.id for x in lire_affaires_du_prestataire(p_id=p.id, session=session, _=cs)]
    assert a.id in ids
    assert b.id not in ids
