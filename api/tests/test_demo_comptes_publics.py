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


# ── Les comptes techniques : fixes si le .env le donne (14/10/2026, #1985) ───

#: Adresse du compte → réglage du `.env` qui fixe son mot de passe.
TECHNIQUES = {
    "admin@localhost": "demo_admin_mot_de_passe",
    "operateur@localhost": "demo_operateur_mot_de_passe",
}


@pytest.mark.parametrize("adresse,reglage", sorted(TECHNIQUES.items()))
def test_sans_mot_de_passe_du_env_le_compte_garde_celui_du_seed(
    session, monkeypatch, adresse, reglage
):
    from app.demo import administrateur
    from tests.aides_base import compte

    monkeypatch.setattr(get_settings(), reglage, "")
    technique = compte(session, email=adresse, role="admin", roles_json="admin")
    avant = technique.hashed_password
    assert administrateur.fixer_mot_de_passe(session, technique) is False
    assert technique.hashed_password == avant


@pytest.mark.parametrize("adresse,reglage", sorted(TECHNIQUES.items()))
def test_le_mot_de_passe_du_env_est_pose_sur_son_compte(session, monkeypatch, adresse, reglage):
    """Chacun le sien : celui de l'administrateur ne déverrouille pas l'opérateur."""
    from app.auth.jwt import verify_password
    from app.demo import administrateur
    from tests.aides_base import compte

    for autre in TECHNIQUES.values():
        monkeypatch.setattr(get_settings(), autre, "")
    monkeypatch.setattr(get_settings(), reglage, "Secret-Demo-42")
    comptes = {a: compte(session, email=a, role="admin", roles_json="admin") for a in TECHNIQUES}
    poses = {a: administrateur.fixer_mot_de_passe(session, c) for a, c in comptes.items()}
    assert poses == {a: a == adresse for a in TECHNIQUES}
    assert verify_password("Secret-Demo-42", comptes[adresse].hashed_password)


@pytest.mark.parametrize("reglage", sorted(TECHNIQUES.values()))
def test_un_mot_de_passe_faible_arrete_avant_toute_ecriture(monkeypatch, reglage):
    """Refusé par la règle du produit AVANT la base : la remise à zéro laisse l'API
    arrêtée plutôt que de servir une démo à moitié chargée (code 4)."""
    monkeypatch.setattr(get_settings(), "mode_demo", "oui")
    monkeypatch.setattr(get_settings(), reglage, "faible")
    assert charger.main() == 4


@pytest.mark.parametrize("reglage", sorted(TECHNIQUES.values()))
def test_aucun_mot_de_passe_technique_dans_le_depot(reglage):
    """Fixés par le .env du serveur seulement : aucun défaut écrit dans le code."""
    from app.config import Settings

    assert Settings.model_fields[reglage].default == ""
