"""Retirer un badge ou une télécommande : ce qui se délie, et l'ordre des DELETE (#1569, #546).

`utils/acces_detachement` n'était nommé par aucun test. Il porte une règle que ni le
schéma ni SQLAlchemy ne devinent : la ligne d'import d'un badge supprimé RESTE, et
repasse à l'état d'avant l'appariement. Vigik et télécommande sont jumeaux ; la
divergence d'origine (la télécommande déliait son import, le badge non) se tient donc
sur les DEUX types.

1. la ligne d'import est déliée du badge ;
2. son statut revient à « propriétaire lié » si le propriétaire était reconnu, à
   « en attente » sinon — la ligne n'est jamais effacée ;
3. sans ligne d'import, rien ne se passe ;
4. une autre ligne d'import n'est jamais touchée ;
5. **l'ordre** : avec les clés vérifiées, supprimer le badge APRÈS le détachement
   réussit, alors que sans lui la clé étrangère refuse — le témoin sans lequel le
   « réussit » ne prouverait rien.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.models.core import StatutImport
from app.utils.acces_detachement import detacher_acces
from tests.aides_badges import TYPES, _badge, _compte, _ligne, _lot
from tests.aides_base import moteur_de_test


def _lier(session, type_acces, ligne, badge) -> None:
    """La ligne d'import résolue vers ce badge — l'état d'AVANT le détachement."""
    setattr(ligne, type_acces.colonne_import, badge.id)
    ligne.statut = StatutImport.resolu
    session.add(ligne)
    session.commit()


def _detacher(session, type_acces, badge) -> None:
    detacher_acces(session, badge.id, type_acces.modele_import, type_acces.colonne_import)
    session.commit()


@pytest.mark.parametrize("type_acces", TYPES)
def test_la_ligne_d_import_est_deliee_du_badge(session, type_acces):
    lot = _lot(session, type_acces)
    badge = _badge(session, type_acces, lot=lot)
    ligne = _ligne(session, type_acces, lot=lot)
    _lier(session, type_acces, ligne, badge)

    _detacher(session, type_acces, badge)

    session.refresh(ligne)
    assert getattr(ligne, type_acces.colonne_import) is None
    assert ligne.id is not None, "la ligne d'import reste : elle décrit ce que le fichier contenait"


@pytest.mark.parametrize("type_acces", TYPES)
def test_sans_proprietaire_reconnu_la_ligne_repart_en_attente(session, type_acces):
    lot = _lot(session, type_acces)
    badge = _badge(session, type_acces, lot=lot)
    ligne = _ligne(session, type_acces, lot=lot)
    _lier(session, type_acces, ligne, badge)

    _detacher(session, type_acces, badge)

    session.refresh(ligne)
    assert ligne.statut == StatutImport.en_attente


@pytest.mark.parametrize("type_acces", TYPES)
def test_avec_proprietaire_reconnu_la_ligne_reste_proprietaire_lie(session, type_acces):
    lot = _lot(session, type_acces)
    proprietaire = _compte(session, "Proprio")
    badge = _badge(session, type_acces, lot=lot)
    ligne = _ligne(session, type_acces, lot=lot, user_proprietaire_id=proprietaire.id)
    _lier(session, type_acces, ligne, badge)

    _detacher(session, type_acces, badge)

    session.refresh(ligne)
    assert ligne.statut == StatutImport.proprietaire_lie
    assert ligne.user_proprietaire_id == proprietaire.id, "la reconnaissance du propriétaire survit"


@pytest.mark.parametrize("type_acces", TYPES)
def test_sans_ligne_d_import_il_n_y_a_rien_a_faire(session, type_acces):
    badge = _badge(session, type_acces, lot=_lot(session, type_acces))

    _detacher(session, type_acces, badge)  # ne lève pas

    assert session.get(type_acces.modele, badge.id) is not None


@pytest.mark.parametrize("type_acces", TYPES)
def test_la_ligne_d_un_autre_badge_n_est_pas_touchee(session, type_acces):
    lot = _lot(session, type_acces)
    badge = _badge(session, type_acces, code="A", lot=lot)
    autre = _badge(session, type_acces, code="B", lot=lot)
    ligne_autre = _ligne(session, type_acces, code="B", lot=lot)
    _lier(session, type_acces, ligne_autre, autre)

    _detacher(session, type_acces, badge)

    session.refresh(ligne_autre)
    assert getattr(ligne_autre, type_acces.colonne_import) == autre.id
    assert ligne_autre.statut == StatutImport.resolu


# ── L'ordre des DELETE, sous clés étrangères actives ────────────────────────


@pytest.fixture()
def session_fk():
    """La règle de l'APPLICATION : clés étrangères actives, comme en production."""
    with Session(moteur_de_test(cles_etrangeres=True)) as s:
        yield s


def _badge_et_ligne(session, type_acces):
    lot = _lot(session, type_acces)
    badge = _badge(session, type_acces, lot=lot)
    ligne = _ligne(session, type_acces, lot=lot)
    _lier(session, type_acces, ligne, badge)
    return badge, ligne


@pytest.mark.parametrize("type_acces", TYPES)
def test_temoin_sans_detachement_la_cle_etrangere_refuse_la_suppression(session_fk, type_acces):
    badge, _ = _badge_et_ligne(session_fk, type_acces)

    session_fk.delete(badge)
    with pytest.raises(IntegrityError):
        session_fk.commit()


@pytest.mark.parametrize("type_acces", TYPES)
def test_apres_le_detachement_le_badge_se_supprime_sous_cles_etrangeres(session_fk, type_acces):
    badge, ligne = _badge_et_ligne(session_fk, type_acces)
    badge_id = badge.id

    detacher_acces(session_fk, badge_id, type_acces.modele_import, type_acces.colonne_import)
    session_fk.delete(badge)
    session_fk.commit()

    assert session_fk.get(type_acces.modele, badge_id) is None
    session_fk.refresh(ligne)
    assert getattr(ligne, type_acces.colonne_import) is None
