"""« Modère-t-il ? » est SERVI avec le compte — `UserRead.est_moderateur` (#2633).

Le site décidait par `$isCS` (`aRole(u, 'conseil_syndical', 'admin')`) et l'app iOS
l'aurait recopié. Le serveur le sert, calculé par LE prédicat
(`auth/deps.est_moderateur`), et le store `estModerateur` LIT le champ.

NON-RÉGRESSION (condition de la coordination, 11/11/2026) : pour CHAQUE combinaison
de rôles, le champ servi égale le prédicat, et égale ce que `$isCS` ouvrait — un
rôle conseil syndical ou administrateur. L'aidant d'une délégation (lecture seule,
#1534) garde SES rôles : aider un membre du conseil ne fait pas modérer.
"""

from __future__ import annotations

from datetime import timedelta
from itertools import combinations

import pytest

from app.auth.deps import est_moderateur
from app.models.core import Delegation, StatutDelegation
from app.models.roles import RoleUtilisateur
from app.schemas import UserRead
from app.utils import horloge
from app.utils.lecture_utilisateur import construire_user_read
from tests.aides_base import compte

#: Tous les rôles d'un compte, l'opérateur de la plateforme compris (#1750).
ROLES = [r.value for r in RoleUtilisateur] + ["operateur"]
#: Ce que `$isCS` ouvrait — `aRole(u, 'conseil_syndical', 'admin')`, avant #2633.
OUVRAIT_IS_CS = {"conseil_syndical", "admin"}
#: TOUTES les combinaisons non vides — 63 pour six rôles.
COMBINAISONS = [c for n in range(1, len(ROLES) + 1) for c in combinations(ROLES, n)]


@pytest.mark.parametrize("roles", COMBINAISONS, ids=["+".join(c) for c in COMBINAISONS])
def test_le_champ_servi_est_le_predicat_pour_chaque_combinaison(session, roles):
    #  Le rôle PRINCIPAL est un `RoleUtilisateur` : l'opérateur n'en est pas un (#1750).
    principal = next((r for r in roles if r != "operateur"), RoleUtilisateur.résident.value)
    u = compte(session, role=principal, roles_json=",".join(roles))
    servi = UserRead.from_orm_with_roles(u).model_dump()["est_moderateur"]
    assert servi is est_moderateur(u)
    assert servi is bool(OUVRAIT_IS_CS & set(roles))


@pytest.mark.parametrize("role", [r.value for r in RoleUtilisateur])
def test_un_compte_a_role_unique_sans_liste(session, role):
    """`roles_json` vide : le rôle principal fait foi (`Utilisateur.roles`)."""
    u = compte(session, role=role)
    assert UserRead.from_orm_with_roles(u).est_moderateur is (role in OUVRAIT_IS_CS)


@pytest.mark.parametrize(
    ("aidant", "mandant", "attendu"),
    [
        ("propriétaire", "conseil_syndical", False),
        ("propriétaire", "admin", False),
        ("conseil_syndical", "propriétaire", True),
    ],
)
def test_l_aidant_garde_ses_propres_roles(session, aidant, mandant, attendu):
    """`/auth/me` d'un aidant : SON compte, jamais celui de la personne aidée."""
    a = compte(session, prefixe="aidant", role=aidant)
    m = compte(session, prefixe="mandant", role=mandant)
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
    assert lu.est_moderateur is attendu is est_moderateur(a)


def test_le_defaut_est_ferme():
    """Hors de `from_orm_with_roles`, le geste n'est pas offert (CLAUDE.md, défaut fermé)."""
    assert UserRead.model_fields["est_moderateur"].default is False
