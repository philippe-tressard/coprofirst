"""Les rôles Opérateur et Admin s'accordent et se retirent dans Admin › Utilisateurs.

Les règles vivent dans `routers/admin/utilisateurs` (`_exiger_geste_operateur`,
`_exiger_un_autre_titulaire`) ; ce fichier les éprouve par la route, comme
l'écran les emploie :

- tout administrateur accorde ou retire Opérateur, à lui-même compris
  (15/10/2026 — #1750 le réservait à un opérateur) ;
- Opérateur ne s'accorde qu'à un administrateur, et Admin ne se retire pas à un
  opérateur : les écrans de l'opérateur vivent sous `/admin` ;
- Admin et Opérateur se retirent, à soi-même compris, sauf à leur dernier
  titulaire actif.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models.core import RoleUtilisateur, Utilisateur
from app.models.roles import ROLE_OPERATEUR
from tests.aides_base import compte
from tests.aides_http import base_http, client_http

OPERATEUR = f"admin,{ROLE_OPERATEUR}"


def _geste(http, cible_id: int, geste: str, role: str = ROLE_OPERATEUR):
    return http.post(f"/admin/utilisateurs/{cible_id}/{geste}", json={"role": role})


def _roles(moteur, ident: int) -> list[str]:
    with Session(moteur) as s:
        return s.get(Utilisateur, ident).roles


def _cible(moteur, roles: str) -> int:
    with Session(moteur) as s:
        return compte(s, prefixe="cible", roles_json=roles, role=RoleUtilisateur.admin).id


def test_un_operateur_accorde_puis_retire_le_role_a_un_admin():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=OPERATEUR)
        cible = _cible(moteur, "propriétaire,admin")
        r = _geste(http, cible, "ajouter-role")
        assert r.status_code == 200, r.text
        assert ROLE_OPERATEUR in r.json()["roles"]
        assert ROLE_OPERATEUR in _roles(moteur, cible)
        #  Jamais le rôle principal : la colonne `role` est un type énuméré.
        with Session(moteur) as s:
            assert s.get(Utilisateur, cible).role == RoleUtilisateur.admin

        r = _geste(http, cible, "retirer-role")
        assert r.status_code == 200, r.text
        assert _roles(moteur, cible) == ["propriétaire", "admin"]


def test_un_admin_qui_n_est_pas_operateur_l_accorde_a_lui_meme_et_a_un_autre():
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json="admin")
        cible = _cible(moteur, "admin")
        assert _geste(http, cible, "ajouter-role").status_code == 200
        assert ROLE_OPERATEUR in _roles(moteur, cible)
        assert _geste(http, moi, "ajouter-role").status_code == 200
        assert ROLE_OPERATEUR in _roles(moteur, moi)


def test_un_admin_qui_n_est_pas_operateur_le_retire_a_un_autre():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json="admin")
        cible = _cible(moteur, OPERATEUR)
        _cible(moteur, OPERATEUR)  # un autre opérateur reste
        assert _geste(http, cible, "retirer-role").status_code == 200
        assert ROLE_OPERATEUR not in _roles(moteur, cible)


def test_le_role_ne_s_accorde_qu_a_un_administrateur():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=OPERATEUR)
        cible = _cible(moteur, "propriétaire,conseil_syndical")
        r = _geste(http, cible, "ajouter-role")
        assert r.status_code == 400
        assert "Admin" in r.json()["detail"]
        assert ROLE_OPERATEUR not in _roles(moteur, cible)


def test_admin_ne_se_retire_pas_a_un_operateur():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=OPERATEUR)
        cible = _cible(moteur, OPERATEUR)
        r = _geste(http, cible, "retirer-role", role="admin")
        assert r.status_code == 400
        assert "Opérateur" in r.json()["detail"]
        assert "admin" in _roles(moteur, cible)
        #  Dans l'ordre inverse, le geste passe.
        assert _geste(http, cible, "retirer-role").status_code == 200
        assert _geste(http, cible, "retirer-role", role="admin").status_code == 200


def test_le_dernier_operateur_ne_se_retire_pas_le_role():
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json=OPERATEUR)
        r = _geste(http, moi, "retirer-role")
        assert r.status_code == 400
        assert "Opérateur" in r.json()["detail"]
        assert ROLE_OPERATEUR in _roles(moteur, moi)


def test_un_operateur_se_retire_le_role_s_il_en_reste_un_autre():
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json=OPERATEUR)
        _cible(moteur, OPERATEUR)
        assert _geste(http, moi, "retirer-role").status_code == 200
        assert ROLE_OPERATEUR not in _roles(moteur, moi)


def test_le_dernier_admin_ne_se_retire_pas_le_role():
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json="propriétaire,admin")
        r = _geste(http, moi, "retirer-role", role="admin")
        assert r.status_code == 400
        assert "admin" in _roles(moteur, moi)


def test_un_admin_inactif_ne_compte_pas_comme_titulaire():
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json="propriétaire,admin")
        with Session(moteur) as s:
            compte(s, prefixe="parti", roles_json="admin", role=RoleUtilisateur.admin, actif=False)
        assert _geste(http, moi, "retirer-role", role="admin").status_code == 400


def test_un_admin_se_retire_le_role_s_il_en_reste_un_autre():
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json="propriétaire,admin")
        _cible(moteur, "admin")
        assert _geste(http, moi, "retirer-role", role="admin").status_code == 200
        assert "admin" not in _roles(moteur, moi)


def test_un_role_inconnu_reste_refuse():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=OPERATEUR)
        cible = _cible(moteur, "admin")
        assert _geste(http, cible, "ajouter-role", role="superviseur").status_code == 400
