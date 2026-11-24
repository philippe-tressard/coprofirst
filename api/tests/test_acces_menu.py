"""Qui voit quelle page au menu est SERVI — `UserRead.acces_menu` (#2969, #2905).

La règle vit dans `app/utils/acces_menu.py` ; le site et les apps la lisent. Ce test
la fixe cas par cas, prouve qu'elle ne retire rien au site d'avant (la seule
différence est déclarée), et la noue aux deux tables du front qu'elle nomme : les
`acces` des pages (`tables-clients.json`, table `pages`) et `ROLES_DU_DROIT`.
"""

from __future__ import annotations

import json
import pathlib
from datetime import timedelta
from itertools import combinations

import pytest

from app.models.core import Delegation, StatutDelegation, Utilisateur
from app.models.roles import ROLE_OPERATEUR, RoleUtilisateur, StatutUtilisateur
from app.schemas import UserRead
from app.utils import horloge
from app.utils.acces_menu import ACCES_MENU, SANS_ADMIN_SEUL, acces_du_menu
from app.utils.lecture_utilisateur import construire_user_read
from app.utils.roles_du_statut import roles_du_statut
from tests.aides_base import compte

RACINE = pathlib.Path(__file__).resolve().parents[2]
TABLES = json.loads((RACINE / "front" / "tables-clients.json").read_text(encoding="utf-8"))
E2E = json.loads((RACINE / "front" / "e2e" / "acces-menu-servis.json").read_text(encoding="utf-8"))[
    "comptes"
]

S = StatutUtilisateur


def _u(statut: S | None, roles: list[str]) -> Utilisateur:
    principal = next((r for r in roles if r != ROLE_OPERATEUR), RoleUtilisateur.résident.value)
    return Utilisateur(
        email="x@exemple.test",
        hashed_password="x",
        prenom="P",
        nom="N",
        role=principal,
        roles_json=",".join(roles),
        statut=statut,
    )


def _servi(statut: S | None, roles: list[str] | None = None, aidant_actif: bool = False):
    roles = roles if roles is not None else [r.value for r in roles_du_statut(statut)]
    return acces_du_menu(_u(statut, roles), roles, aidant_actif)


# ── La règle, cas par cas ─────────────────────────────────────────────────────

TOUS_RESIDENT = ["tous", "resident"]


@pytest.mark.parametrize(
    ("statut", "roles", "aidant_actif", "attendu"),
    [
        (S.copropriétaire_résident, None, False, TOUS_RESIDENT),
        (S.copropriétaire_bailleur, None, False, TOUS_RESIDENT),
        (S.locataire, None, False, TOUS_RESIDENT),
        #  #2905 : le syndic et le mandataire n'avaient AUCUNE entrée sur le site.
        (S.syndic, None, False, TOUS_RESIDENT),
        (S.mandataire, None, False, TOUS_RESIDENT),
        (S.aidant, None, False, ["tous", "cs-ou-aidant"]),
        (S.locataire, None, True, ["tous", "resident", "cs-ou-aidant"]),
        (
            S.copropriétaire_résident,
            ["propriétaire", "résident", "conseil_syndical"],
            False,
            ["tous", "resident", "cs", "cs-ou-aidant"],
        ),
        (S.copropriétaire_résident, ["propriétaire", "admin"], False, list(ACCES_MENU)),
        #  Le compte technique : l'administration, et rien des résidents.
        (S.admin_technique, ["admin"], False, ["admin"]),
        (S.admin_technique, ["admin", ROLE_OPERATEUR], False, ["admin"]),
        (S.admin_technique, [ROLE_OPERATEUR], False, ["admin"]),
    ],
)
def test_les_publics_de_chaque_profil(statut, roles, aidant_actif, attendu):
    assert _servi(statut, roles, aidant_actif) == attendu


# ── Non-régression : rien de ce que le site montrait ne disparaît ────────────

ROLES = [r.value for r in RoleUtilisateur] + [ROLE_OPERATEUR]
COMBINAISONS = [list(c) for n in range(1, len(ROLES) + 1) for c in combinations(ROLES, n)]


def _site_d_avant(u: Utilisateur, roles: list[str], aidant_actif: bool) -> set[str]:
    """`Nav.svelte` avant #2969 (`allNav`, `hasResidentRole`, `isAdminOnly`), recopié
    ICI SEULEMENT, comme témoin de non-régression."""
    r, statut = set(roles), u.statut
    residentiel = bool(r & {"propriétaire", "résident"}) or statut == S.aidant
    admin_seul = "admin" in r and not (r & SANS_ADMIN_SEUL)
    cs = bool(r & {"conseil_syndical", "admin"}) and not admin_seul
    vus = set()
    if residentiel:
        vus.add("tous")
    if residentiel and statut not in (S.syndic, S.mandataire, S.aidant):
        vus.add("resident")
    if cs:
        vus.add("cs")
    if cs or aidant_actif or statut == S.aidant:
        vus.add("cs-ou-aidant")
    if r & {"admin", ROLE_OPERATEUR}:
        vus.add("admin")
    return vus


@pytest.mark.parametrize("statut", [None, *S], ids=lambda s: getattr(s, "value", "aucun"))
@pytest.mark.parametrize("aidant_actif", [False, True])
def test_rien_de_ce_que_le_site_montrait_ne_disparait(statut, aidant_actif):
    for roles in COMBINAISONS:
        u = _u(statut, roles)
        avant = _site_d_avant(u, roles, aidant_actif)
        apres = set(acces_du_menu(u, roles, aidant_actif))
        assert avant <= apres, (statut, roles, aidant_actif, avant - apres)


def test_ce_qui_s_ajoute_est_declare():
    """Seuls GAGNENT les pages générales et la Communauté (Avis) : le compte lié par son
    statut sans rôle d'habitant, et le syndic et le mandataire (rôle `externe`, #2905)."""
    for statut in [None, *S]:
        for roles in COMBINAISONS:
            u = _u(statut, roles)
            gagne = set(acces_du_menu(u, roles, False)) - _site_d_avant(u, roles, False)
            if gagne:
                assert gagne <= {"tous", "resident"}, (statut, roles, gagne)
                #  …soit parce qu'il n'avait aucun rôle d'habitant, soit parce que son
                #  statut de gestionnaire lui ouvre l'Avis de la Communauté (#2075).
                gestionnaire = statut in (S.syndic, S.mandataire)
                assert gestionnaire or not set(roles) & {"propriétaire", "résident"}, (
                    statut,
                    roles,
                )


# ── Concordance avec les tables du front ──────────────────────────────────────


def test_chaque_page_du_menu_declare_un_public_que_le_serveur_connait():
    pages = [p for p in TABLES["tables"]["pages"]["valeur"] if p.get("href")]
    assert len(pages) >= 10, "cas zéro : la table des pages n'a pas été lue"
    sans = [p["id"] for p in pages if "acces" not in p]
    assert not sans, f"pages du menu sans `acces` : {sans}"
    assert {p["acces"] for p in pages} == set(ACCES_MENU)


def test_l_admin_seul_est_celui_du_front():
    droit = TABLES["tables"]["rolesDuDroit"]["valeur"]
    assert droit["adminSeul"] == [RoleUtilisateur.admin.value]
    assert set(droit["sansAdminSeul"]) == SANS_ADMIN_SEUL


# ── Servi par /auth/me ────────────────────────────────────────────────────────


def test_le_champ_est_servi_et_ferme_par_defaut(session):
    u = compte(session, statut=S.syndic, role="externe", roles_json="externe")
    assert UserRead.from_orm_with_roles(u).acces_menu == TOUS_RESIDENT
    assert UserRead.model_fields["acces_menu"].default == []


def test_l_aidant_d_une_delegation_active_ouvre_les_delegations(session):
    a = compte(session, prefixe="aidant", statut=S.locataire, role="résident")
    m = compte(session, prefixe="mandant", role="propriétaire")
    session.add(
        Delegation(
            mandant_id=m.id,
            aidant_id=a.id,
            cree_par_id=m.id,
            statut=StatutDelegation.active,
            date_debut=horloge.aujourd_hui() - timedelta(days=1),
        )
    )
    session.commit()
    lu = construire_user_read(a, session)
    assert lu.delegations_aidant, "la délégation doit être active : sinon le test ne prouve rien"
    assert "cs-ou-aidant" in lu.acces_menu


# ── Les comptes que les e2e simulent (`front/e2e/acces-menu-servis.json`) ────


def test_cas_zero_e2e():
    assert E2E, "aucun compte simulé : les e2e liraient un menu vide"


@pytest.mark.parametrize("c", E2E, ids=[f"{c['statut']}:{'+'.join(c['roles'])}" for c in E2E])
def test_le_menu_simule_est_celui_du_serveur(c):
    """Le statut est une valeur que le serveur connaît, et un statut EXTERNE porte les
    rôles que `roles_du_statut` lui donne (#2905 : un syndic `résident` n'existe pas)."""
    statut = S(c["statut"]) if c["statut"] else None
    if statut in (S.syndic, S.mandataire, S.aidant):
        assert set(c["roles"]) & {"propriétaire", "résident", "externe"} == {"externe"}, c
    assert acces_du_menu(_u(statut, c["roles"]), c["roles"], c["aidant"]) == c["acces_menu"]
