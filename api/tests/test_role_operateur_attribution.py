"""Le rôle Opérateur s'accorde et se retire dans Admin › Utilisateurs (#1750).

Les règles vivent dans `routers/admin/utilisateurs._exiger_geste_operateur` ;
ce fichier les éprouve par la route, comme l'écran les emploie :

- seul un opérateur accorde ou retire le rôle — l'administrateur de la
  copropriété ne se donne pas la supervision de la plateforme ;
- il ne s'accorde qu'à un administrateur, et Admin ne se retire pas à un
  opérateur : les écrans de l'opérateur vivent sous `/admin` ;
- on ne se le retire pas soi-même, ce qui garde au moins un opérateur.
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


def test_un_admin_qui_n_est_pas_operateur_ne_l_accorde_pas():
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json="admin")
        cible = _cible(moteur, "admin")
        assert _geste(http, cible, "ajouter-role").status_code == 403
        #  …ni à lui-même : c'est l'élévation que la règle empêche.
        assert _geste(http, moi, "ajouter-role").status_code == 403
        assert ROLE_OPERATEUR not in _roles(moteur, moi)


def test_un_admin_qui_n_est_pas_operateur_ne_le_retire_pas():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json="admin")
        cible = _cible(moteur, OPERATEUR)
        assert _geste(http, cible, "retirer-role").status_code == 403
        assert ROLE_OPERATEUR in _roles(moteur, cible)


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


def test_on_ne_se_retire_pas_le_role_soi_meme():
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json=OPERATEUR)
        r = _geste(http, moi, "retirer-role")
        assert r.status_code == 400
        assert ROLE_OPERATEUR in _roles(moteur, moi)


def test_un_role_inconnu_reste_refuse():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=OPERATEUR)
        cible = _cible(moteur, "admin")
        assert _geste(http, cible, "ajouter-role", role="superviseur").status_code == 400
