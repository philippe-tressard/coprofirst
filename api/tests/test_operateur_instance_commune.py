"""Sur une instance COMMUNE, l'opérateur est désigné par l'exploitant (31/10/2026).

Règle (`auth/operateur`, spec §4.7) : l'administrateur d'une copropriété hébergée
gère SA base, pas l'instance. Avant ce lot, tout administrateur pouvait s'accorder
le rôle Opérateur et superviser l'instance entière. Ce fichier tient :

- le drapeau `operateur` d'un compte ne compte pas sur une instance commune ;
- un compte déclaré par l'exploitant (`operateurs` de SA copropriété) est
  opérateur, dans sa copropriété seulement ;
- Admin › Utilisateurs refuse d'accorder ou de retirer le rôle (409) ;
- l'affichage (`UserRead.roles`) dit ce que la route admet ;
- cas zéro : une instance propre garde la règle du drapeau.
"""

from __future__ import annotations

import copy

import pytest

from app import contexte
from app.auth.operateur import est_operateur, roles_effectifs
from app.installation_commune.declaration import DeclarationInvalide, declaration
from app.models.core import RoleUtilisateur, Utilisateur
from app.models.roles import ROLE_OPERATEUR
from app.routers.admin import utilisateurs
from app.schemas import UserRead
from tests.aides_http import base_http, client_http
from tests.aides_installation_commune import COPROPRIETES, installation_commune

DECLARE = "exploitation@hebergeur.example"


def _avec_operateur(adresse: str = DECLARE) -> list[dict]:
    coproprietes = copy.deepcopy(COPROPRIETES)
    coproprietes[0]["operateurs"] = [adresse]  # « tilleuls »
    return coproprietes


def _compte(email: str, roles: str) -> Utilisateur:
    return Utilisateur(
        id=1,
        nom="Témoin",
        prenom="Compte",
        email=email,
        role=RoleUtilisateur.admin,
        roles_json=roles,
    )


def _entree(identifiant: str):
    return next(e for e in declaration().entrees if e.copropriete.identifiant == identifiant)


def test_le_drapeau_d_un_admin_ne_fait_pas_l_operateur_d_une_instance_commune(
    tmp_path, monkeypatch
):
    with installation_commune(tmp_path, monkeypatch, _avec_operateur()):
        admin_client = _compte("admin@residence-chenes.example", f"admin,{ROLE_OPERATEUR}")
        with contexte.dans(_entree("chenes").copropriete):
            assert not est_operateur(admin_client)
            assert ROLE_OPERATEUR not in roles_effectifs(admin_client)
            assert ROLE_OPERATEUR not in UserRead.from_orm_with_roles(admin_client).roles


def test_le_compte_declare_est_operateur_dans_sa_copropriete_seulement(tmp_path, monkeypatch):
    with installation_commune(
        tmp_path, monkeypatch, _avec_operateur(" Exploitation@Hebergeur.example ")
    ):
        declare = _compte(DECLARE, "admin")
        with contexte.dans(_entree("tilleuls").copropriete):
            assert est_operateur(declare)
            assert ROLE_OPERATEUR in UserRead.from_orm_with_roles(declare).roles
        #  Même adresse, autre copropriété : un autre compte, pas déclaré (D8).
        with contexte.dans(_entree("chenes").copropriete):
            assert not est_operateur(declare)


def test_une_adresse_d_operateur_invalide_refuse_la_declaration(tmp_path, monkeypatch):
    with installation_commune(tmp_path, monkeypatch, _avec_operateur("pas-une-adresse")):
        with pytest.raises(DeclarationInvalide, match="opérateur"):
            declaration()


@pytest.mark.parametrize("geste", ["ajouter-role", "retirer-role"])
def test_admin_utilisateurs_ne_donne_ni_ne_retire_l_operateur_d_une_commune(geste, monkeypatch):
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}")
        #  Le geste seul : la résolution de l'hôte d'une vraie commune n'est pas l'objet ici.
        monkeypatch.setattr(utilisateurs, "designe_par_l_exploitant", lambda: True)
        r = http.post(f"/admin/utilisateurs/{moi}/{geste}", json={"role": ROLE_OPERATEUR})
        assert r.status_code == 409, r.text
        assert "exploitant" in r.json()["detail"]


def test_cas_zero_une_instance_propre_lit_le_drapeau_du_compte():
    assert not contexte.est_commune()
    assert est_operateur(_compte("a@exemple.example", f"admin,{ROLE_OPERATEUR}"))
    assert not est_operateur(_compte("b@exemple.example", "admin"))


def test_l_ecran_apprend_qui_designe_l_operateur(monkeypatch):
    """`GET /config` publie la clé calculée que lit l'écran (`#lib/portee`) — jamais saisie."""
    with base_http() as moteur:
        http, _ = client_http(moteur, None)
        assert http.get("/config").json()["operateur_par_exploitant"] == "0"
        monkeypatch.setattr("app.auth.operateur.designe_par_l_exploitant", lambda: True)
        assert http.get("/config").json()["operateur_par_exploitant"] == "1"
