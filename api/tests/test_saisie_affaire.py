"""La saisie d'une affaire, Essentielle ou Complète (#2595, 08/11/2026).

Le choix vit sur le COMPTE ; `NULL` veut dire « rien choisi », et le défaut se
calcule à la lecture : Essentielle, pour tous les rôles.
"""

from __future__ import annotations

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session

from app.models.core import RoleUtilisateur
from app.routers.auth_profil import MeUpdate, update_me
from app.routers.tickets.referentiels import referentiels_pour
from app.utils.saisie_affaire import (
    COMPLETE,
    ESSENTIELLE,
    SECTIONS_DE_BASE,
    SECTIONS_ESSENTIELLES_PAR_CATEGORIE,
    choix_a_enregistrer,
    mode_effectif,
)
from tests import aides_base
from tests.conftest import requete_de_test


def _modifier(session: Session, user, **champs):
    return update_me(
        requete_de_test("/auth/me", "PATCH"),
        MeUpdate(**champs),
        BackgroundTasks(),
        session=session,
        user=user,
    )


def _conseil(session: Session, **champs):
    return aides_base.compte(
        session, prefixe="saisie-cs", role=RoleUtilisateur.conseil_syndical, **champs
    )


def test_sans_choix_le_defaut_est_essentielle_pour_tous_les_roles(session: Session):
    resident = aides_base.compte(session, prefixe="saisie-res")
    assert resident.saisie_affaire is None
    assert mode_effectif(resident) == ESSENTIELLE
    assert mode_effectif(_conseil(session)) == ESSENTIELLE


def test_le_choix_prime_sur_le_defaut(session: Session):
    assert mode_effectif(_conseil(session, saisie_affaire=COMPLETE)) == COMPLETE
    resident = aides_base.compte(session, prefixe="saisie-res", saisie_affaire=COMPLETE)
    assert mode_effectif(resident) == COMPLETE


def test_une_valeur_inconnue_en_base_retombe_sur_le_defaut(session: Session):
    """Une colonne altérée à la main ne doit pas produire un mode que l'écran ignore."""
    resident = aides_base.compte(session, prefixe="saisie-res", saisie_affaire="bizarre")
    assert mode_effectif(resident) == ESSENTIELLE


def test_le_profil_enregistre_le_choix_et_le_sert_relu(session: Session):
    user = aides_base.compte(session, prefixe="saisie-res")

    lu = _modifier(session, user, saisie_affaire="complete")
    session.refresh(user)
    assert user.saisie_affaire == COMPLETE
    assert lu.saisie_affaire == COMPLETE and lu.saisie_affaire_effective == COMPLETE


def test_selon_mon_role_n_existe_plus(session: Session):
    """Retiré du Profil le 08/11/2026 : un client resté sur l'ancien écran est refusé."""
    user = aides_base.compte(session, prefixe="saisie-res", saisie_affaire=COMPLETE)

    with pytest.raises(HTTPException) as e:
        _modifier(session, user, saisie_affaire="role")
    assert e.value.status_code == 400
    session.refresh(user)
    assert user.saisie_affaire == COMPLETE


def test_un_autre_reglage_ne_touche_pas_au_choix(session: Session):
    """Un PATCH partiel : enregistrer ses notifications laisse la saisie où elle est."""
    user = aides_base.compte(session, prefixe="saisie-res", saisie_affaire=COMPLETE)
    _modifier(session, user, restreindre_a_mes_batiments=True)
    session.refresh(user)
    assert user.saisie_affaire == COMPLETE


def test_un_mot_inconnu_est_refuse_en_400(session: Session):
    user = aides_base.compte(session, prefixe="saisie-res")
    with pytest.raises(HTTPException) as e:
        _modifier(session, user, saisie_affaire="simplifiee")
    assert e.value.status_code == 400
    session.refresh(user)
    assert user.saisie_affaire is None


def test_choix_a_enregistrer_cas_zero():
    """Cas zéro : les deux mots valides rendent chacun leur valeur."""
    assert choix_a_enregistrer("essentielle") == ESSENTIELLE
    assert choix_a_enregistrer("complete") == COMPLETE


def test_le_referentiel_sert_les_sections_essentielles_de_chaque_categorie(session: Session):
    user = aides_base.compte(session, prefixe="saisie-res")
    servies = {c.code: c.sections_essentielles for c in referentiels_pour(user).categories}

    assert servies, "aucune catégorie servie : le test ne mesurerait rien"
    for code, sections in servies.items():
        assert sections[: len(SECTIONS_DE_BASE)] == list(SECTIONS_DE_BASE), code
    assert "pieces_jointes" in servies["panne"]
    assert servies["question"] == list(SECTIONS_DE_BASE)


def test_la_table_ne_cite_que_des_categories_et_des_sections_du_cadre():
    from app.models.tickets import CategorieTicket

    categories = {c.value for c in CategorieTicket}
    assert set(SECTIONS_ESSENTIELLES_PAR_CATEGORIE) <= categories
