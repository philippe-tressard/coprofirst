"""Les comptes PUBLICS de la démo (spec `mode-demo.md` §5, lot D8 #1932).

Arbitré le 13/10/2026 : on entre par le formulaire, avec trois identifiants publiés
sur la page « Démo » du site vitrine. Leurs mots de passe sont publics et versionnés
— c'est voulu, mais seulement en démo : le générateur refuse ailleurs.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.demo import charger
from app.demo.personnages import DOMAINE, PERSONNAGES
from app.utils.mots_de_passe import verifier_robustesse


def test_trois_comptes_publics_et_aucun_administrateur():
    assert set(PERSONNAGES) == {"user-cs", "user-copro", "user-loc"}
    assert all("admin" not in p.roles_json.split(",") for p in PERSONNAGES.values())


def test_les_roles_publies():
    assert "conseil_syndical" in PERSONNAGES["user-cs"].roles_json.split(",")
    assert "propriétaire" in PERSONNAGES["user-copro"].roles_json.split(",")
    assert "propriétaire" not in PERSONNAGES["user-loc"].roles_json.split(",")


def test_les_identifiants_publies():
    assert [p.adresse for p in PERSONNAGES.values()] == [
        f"{code}@{DOMAINE}" for code in PERSONNAGES
    ]
    assert DOMAINE == "demo.coprofirst.fr"


@pytest.mark.parametrize("code", sorted(PERSONNAGES))
def test_chaque_mot_de_passe_publie_passe_la_regle_du_produit(code):
    verifier_robustesse(PERSONNAGES[code].mot_de_passe)


def test_la_regle_refuserait_un_mot_de_passe_sans_chiffre():
    """Témoin : les mots de passe d'abord donnés n'avaient pas de chiffre."""
    with pytest.raises(HTTPException):
        verifier_robustesse("PSWD-user-cs")


def test_le_generateur_refuse_hors_demo(monkeypatch):
    """Les mots de passe publiés ne se posent JAMAIS sur une vraie installation."""
    monkeypatch.setattr(get_settings(), "mode_demo", "")
    assert charger.main() == 2


# ── L'administrateur : fixe et SECRET, si le .env le donne (14/10/2026) ───────


def test_sans_mot_de_passe_du_env_l_administrateur_garde_celui_du_seed(session, monkeypatch):
    from app.demo import administrateur
    from tests.aides_base import compte

    monkeypatch.setattr(get_settings(), "demo_admin_mot_de_passe", "")
    admin = compte(session, role="admin", roles_json="admin")
    avant = admin.hashed_password
    assert administrateur.fixer_mot_de_passe(session, admin) is False
    assert admin.hashed_password == avant


def test_le_mot_de_passe_du_env_est_pose_sur_l_administrateur(session, monkeypatch):
    from app.auth.jwt import verify_password
    from app.demo import administrateur
    from tests.aides_base import compte

    monkeypatch.setattr(get_settings(), "demo_admin_mot_de_passe", "Secret-Demo-42")
    admin = compte(session, role="admin", roles_json="admin")
    assert administrateur.fixer_mot_de_passe(session, admin) is True
    assert verify_password("Secret-Demo-42", admin.hashed_password)


def test_un_mot_de_passe_faible_arrete_avant_toute_ecriture(monkeypatch):
    """Refusé par la règle du produit AVANT la base : la remise à zéro laisse l'API
    arrêtée plutôt que de servir une démo à moitié chargée (code 4)."""
    monkeypatch.setattr(get_settings(), "mode_demo", "oui")
    monkeypatch.setattr(get_settings(), "demo_admin_mot_de_passe", "faible")
    assert charger.main() == 4


def test_le_mot_de_passe_de_l_administrateur_n_est_pas_dans_le_depot():
    """Il est secret : aucun défaut écrit dans le code (les publics, eux, le sont)."""
    from app.config import Settings

    assert Settings.model_fields["demo_admin_mot_de_passe"].default == ""
