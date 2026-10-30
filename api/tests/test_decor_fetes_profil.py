"""Chacun garde ou éteint pour lui le décor des jours de fête (#2312, 30/10/2026).

L'administration allume le décor pour la copropriété (Admin › Services) ; le
résident le garde ou l'éteint dans son Profil. Le choix vit sur le COMPTE
(`Utilisateur.decor_fetes`), vrai tant qu'il n'y a pas touché : la migration
0320 pose la colonne avec `server_default` vrai, rien ne change pour personne.
"""

from __future__ import annotations

from fastapi import BackgroundTasks
from sqlmodel import Session

from app.routers.auth_profil import MeUpdate, update_me
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


def test_le_decor_est_garde_tant_qu_on_n_y_touche_pas(session: Session):
    user = aides_base.compte(session, prefixe="decor")
    assert user.decor_fetes is True
    assert _modifier(session, user, prenom="Alix").decor_fetes is True


def test_l_eteindre_puis_le_rallumer_s_enregistre_et_se_relit(session: Session):
    user = aides_base.compte(session, prefixe="decor")

    lu = _modifier(session, user, decor_fetes=False)
    session.refresh(user)
    assert user.decor_fetes is False and lu.decor_fetes is False

    lu = _modifier(session, user, decor_fetes=True)
    session.refresh(user)
    assert user.decor_fetes is True and lu.decor_fetes is True


def test_un_autre_reglage_ne_le_rallume_pas(session: Session):
    """Un PATCH partiel : enregistrer ses notifications ne touche pas au décor."""
    user = aides_base.compte(session, prefixe="decor", decor_fetes=False)
    _modifier(session, user, restreindre_a_mes_batiments=True)
    session.refresh(user)
    assert user.decor_fetes is False
