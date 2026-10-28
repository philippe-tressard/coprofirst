"""Un locataire rattaché automatiquement à son bailleur, par le seul nom (#1136).

Arbitré le 24/09/2026. Le risque des homonymes est accepté, et borné : un seul
bailleur de ce nom, un seul bail libre ou un seul logement, aucun lien déjà posé.
"""

from __future__ import annotations

from datetime import date

from sqlmodel import select

from app.models.copropriete import TypeLot
from app.models.core import LocationBail, Lot, StatutUtilisateur, TypeLien, UserLot
from app.utils.rattachement_bailleur import rattacher_au_bailleur
from tests.aides_base import compte


def _logement(session, proprio, numero="12", type_=TypeLot.appartement):
    lot = Lot(numero=numero, type=type_)
    session.add(lot)
    session.commit()
    session.refresh(lot)
    session.add(UserLot(user_id=proprio.id, lot_id=lot.id, type_lien=TypeLien.bailleur, actif=True))
    session.commit()
    return lot


def _locataire(session, nom_proprietaire="Durandal"):
    return compte(
        session, nom="Loc", statut=StatutUtilisateur.locataire, nom_proprietaire=nom_proprietaire
    )


def _liens(session, user):
    return session.exec(select(UserLot).where(UserLot.user_id == user.id)).all()


def test_le_locataire_est_rattache_au_logement_de_son_bailleur(session):
    b = compte(session, nom="DURANDAL", statut=StatutUtilisateur.copropriétaire_bailleur)
    lot = _logement(session, b)
    _logement(session, b, numero="C3", type_=TypeLot.cave)  # une cave ne compte pas
    loc = _locataire(session)
    assert rattacher_au_bailleur(loc, session) == 1
    session.commit()
    assert [(ul.lot_id, ul.type_lien) for ul in _liens(session, loc)] == [
        (lot.id, TypeLien.locataire)
    ]


def test_un_bail_libre_passe_avant_le_logement(session):
    b = compte(session, nom="DURANDAL", statut=StatutUtilisateur.copropriétaire_bailleur)
    lot = _logement(session, b)
    bail = LocationBail(lot_id=lot.id, bailleur_id=b.id, date_entree=date(2026, 9, 1))
    session.add(bail)
    session.commit()
    loc = _locataire(session)
    assert rattacher_au_bailleur(loc, session) == 1
    session.commit()
    session.refresh(bail)
    assert bail.locataire_id == loc.id and _liens(session, loc) == []


def test_deux_bailleurs_homonymes_et_rien_n_est_fait(session):
    for _ in range(2):
        _logement(
            session,
            compte(session, nom="DURANDAL", statut=StatutUtilisateur.copropriétaire_bailleur),
        )
    assert rattacher_au_bailleur(_locataire(session), session) == 0


def test_deux_logements_et_rien_n_est_fait(session):
    b = compte(session, nom="DURANDAL", statut=StatutUtilisateur.copropriétaire_bailleur)
    _logement(session, b, "12")
    _logement(session, b, "14")
    assert rattacher_au_bailleur(_locataire(session), session) == 0


def test_un_lien_deja_pose_n_est_pas_touche(session):
    b = compte(session, nom="DURANDAL", statut=StatutUtilisateur.copropriétaire_bailleur)
    _logement(session, b)
    autre = _logement(
        session, compte(session, nom="MARTINEAU", statut=StatutUtilisateur.copropriétaire_bailleur)
    )
    loc = _locataire(session)
    session.add(UserLot(user_id=loc.id, lot_id=autre.id, type_lien=TypeLien.locataire, actif=True))
    session.commit()
    assert rattacher_au_bailleur(loc, session) == 0


def test_seul_un_locataire_est_rattache(session):
    _logement(
        session, compte(session, nom="DURANDAL", statut=StatutUtilisateur.copropriétaire_bailleur)
    )
    proprio = compte(
        session,
        nom="Autre",
        statut=StatutUtilisateur.copropriétaire_résident,
        nom_proprietaire="Durandal",
    )
    assert rattacher_au_bailleur(proprio, session) == 0


def test_le_rapprochement_d_un_compte_rattache_le_locataire(session):
    """Par la porte d'entrée réelle : la validation du compte appelle ce rapprochement."""
    from app.utils.auto_match_service import auto_match_pour_utilisateur

    _logement(
        session, compte(session, nom="DURANDAL", statut=StatutUtilisateur.copropriétaire_bailleur)
    )
    loc = _locataire(session)
    assert auto_match_pour_utilisateur(loc, session)["rattache"] == 1


def test_le_logement_du_bailleur_remet_ses_badges_au_locataire(session):
    """Le lien seul laissait le Vigik chez le propriétaire (#2267)."""
    from app.models.core import Vigik

    b = compte(session, nom="DURANDAL", statut=StatutUtilisateur.copropriétaire_bailleur)
    lot = _logement(session, b)
    vigik = Vigik(code="V-2267", lot_id=lot.id)
    session.add(vigik)
    session.commit()
    loc = _locataire(session)
    assert rattacher_au_bailleur(loc, session) == 1
    session.commit()
    session.refresh(vigik)
    assert (vigik.chez_locataire, vigik.user_id) == (True, loc.id)
