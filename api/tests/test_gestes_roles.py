"""Les gestes de rôle SERVIS par la liste des comptes sont ceux que la route accepte (#2618).

`UtilisateurAdminRead.gestes_roles` dit, par compte, quels rôles Admin › Utilisateurs
offre d'ajouter ou de retirer ; le site et l'app iOS le LISENT au lieu de recomposer
la règle. Ce fichier confronte chaque geste servi à la réponse réelle de
`POST /admin/utilisateurs/{id}/ajouter-role|retirer-role`, dans une base neuve à
chaque fois :

- un geste servi aboutit toujours (200) ;
- un geste que la ROUTE refuse n'est jamais servi (dernier titulaire, Opérateur à un
  non-administrateur) ;
- la seule différence permise va dans l'autre sens, et elle est déclarée : « + CS »
  et « + Admin » ne s'offrent qu'à un copropriétaire, que la route n'exige pas
  (`utils/gestes_roles`, l'écran offre MOINS que la route).

Et `communaute_banni` : jugé à l'heure du serveur, jamais à celle du téléphone.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur, Utilisateur
from app.models.roles import ROLE_OPERATEUR
from app.utils import horloge
from tests.aides_base import compte
from tests.aides_http import base_http, client_http

ROLES = ("conseil_syndical", "admin", ROLE_OPERATEUR)

#: Les comptes du jeu : (préfixe, roles_json, statut, actif). « moi » est l'appelant,
#: seul opérateur — donc jamais retirable de ce rôle — mais pas seul administrateur.
COMPTES = {
    "copro": ("copro", "propriétaire,résident", "copropriétaire_résident", True),
    "loc": ("loc", "résident", "locataire", True),
    "cs": ("cs", "propriétaire,conseil_syndical", "copropriétaire_bailleur", True),
    "adm": ("adm", "propriétaire,admin", "copropriétaire_résident", True),
    "inactif": ("inactif", "propriétaire,admin", "copropriétaire_résident", False),
}


def _jeu(moteur) -> dict[str, int]:
    with Session(moteur) as s:
        return {
            nom: compte(
                s,
                prefixe=p,
                roles_json=r,
                statut=statut,
                actif=actif,
                role=RoleUtilisateur.résident,
            ).id
            for nom, (p, r, statut, actif) in COMPTES.items()
        }


def _servis(http) -> dict[int, dict]:
    r = http.get("/admin/utilisateurs")
    assert r.status_code == 200, r.text
    return {u["id"]: u["gestes_roles"] for u in r.json()}


def _cas() -> list[tuple[str, str]]:
    """Chaque (compte, rôle) du jeu — l'appelant compris."""
    return [(nom, role) for nom in [*COMPTES, "moi"] for role in ROLES]


@pytest.mark.parametrize(("nom", "role"), _cas())
def test_le_geste_servi_est_celui_que_la_route_admet(nom, role):
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}")
        ids = {**_jeu(moteur), "moi": moi}
        geste = _servis(http)[ids[nom]][role]

        if geste is None:
            #  Ce que l'écran n'offre pas : la route refuse, OU c'est la restriction
            #  déclarée « copropriétaire seulement » (l'écran offre moins).
            avec = "retirer-role" if _porte(moteur, ids[nom], role) else "ajouter-role"
            r = http.post(f"/admin/utilisateurs/{ids[nom]}/{avec}", json={"role": role})
            restriction_declaree = (
                avec == "ajouter-role" and role in ("conseil_syndical", "admin") and nom == "loc"
            )
            assert r.status_code != 200 or restriction_declaree or nom == "inactif", (
                f"{nom}/{role} : la route accepte « {avec} » que la liste ne sert pas"
            )
        else:
            r = http.post(f"/admin/utilisateurs/{ids[nom]}/{geste}-role", json={"role": role})
            assert r.status_code == 200, f"{nom}/{role} : « {geste} » servi, refusé — {r.text}"


def _porte(moteur, ident: int, role: str) -> bool:
    with Session(moteur) as s:
        return s.get(Utilisateur, ident).has_role(role)


def test_les_gestes_attendus_du_jeu():
    """Le relevé lui-même, pour qu'une règle qui ne servirait plus rien échoue aussi."""
    with base_http() as moteur:
        http, moi = client_http(moteur, RoleUtilisateur.admin, roles_json=f"admin,{ROLE_OPERATEUR}")
        ids = {**_jeu(moteur), "moi": moi}
        servis = _servis(http)
    assert servis[ids["copro"]] == {
        "conseil_syndical": "ajouter",
        "admin": "ajouter",
        "operateur": None,
    }
    assert servis[ids["loc"]] == {"conseil_syndical": None, "admin": None, "operateur": None}
    assert servis[ids["cs"]]["conseil_syndical"] == "retirer"
    assert servis[ids["adm"]] == {
        "conseil_syndical": "ajouter",
        "admin": "retirer",
        "operateur": "ajouter",
    }
    assert servis[ids["inactif"]] == {"conseil_syndical": None, "admin": None, "operateur": None}
    #  L'appelant est le SEUL opérateur : il ne se le retire pas.
    assert servis[moi]["operateur"] is None and servis[moi]["admin"] == "retirer"


def test_le_conseil_syndical_ne_recoit_aucun_geste():
    """Les routes prennent `require_admin` : le CS lit la liste, il n'y a pas de geste."""
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        _jeu(moteur)
        for gestes in _servis(http).values():
            assert gestes == {"conseil_syndical": None, "admin": None, "operateur": None}


@pytest.mark.parametrize(
    ("interdit", "jusqu_au", "banni"),
    [
        (False, None, False),
        (True, None, True),
        (False, timedelta(days=3), True),
        (False, -timedelta(days=1), False),
    ],
)
def test_le_bannissement_est_juge_a_l_heure_du_serveur(interdit, jusqu_au, banni):
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        with Session(moteur) as s:
            cible = compte(
                s,
                prefixe="ban",
                communaute_interdit=interdit,
                communaute_ban_jusqu_au=horloge.maintenant() + jusqu_au if jusqu_au else None,
            ).id
        lignes = {u["id"]: u for u in http.get("/admin/utilisateurs").json()}
    assert lignes[cible]["communaute_banni"] is banni
