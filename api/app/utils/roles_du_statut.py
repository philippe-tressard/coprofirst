"""Les rôles qu'un STATUT confère — écrits une fois, pour l'inscription et le changement (#2161).

## 🔴 Pourquoi ce module existe

La règle « un copropriétaire est propriétaire, un locataire est résident, le syndic
est externe » n'était écrite qu'à l'inscription (`routers/auth.py`). Approuver une
demande de changement de statut (`admin/profils.py`) écrivait `statut`, jamais les
rôles. Or l'autorisation lit les RÔLES (`require_proprietaire` →
`has_role(propriétaire, …)`) : un copropriétaire qui avait vendu et était devenu
locataire gardait le carnet, la recherche de locataires, les questions au règlement.

## Ce qu'un changement de statut retire, et ce qu'il garde

Il remplace les rôles que le statut CONFÈRE (`ROLES_DERIVES`) et garde tous les
autres — conseil syndical, administration, opérateur : ceux-là se donnent un par un,
par l'administration, et ne dépendent pas de la nature du lien au lot.
"""

from __future__ import annotations

from app.models.core import RoleUtilisateur, StatutUtilisateur, Utilisateur
from app.models.roles import role_principal

#: Les statuts qui CONSULTENT seulement (#1911, arbitré le 13/10/2026).
STATUTS_EXTERNES = frozenset(
    {StatutUtilisateur.syndic, StatutUtilisateur.mandataire, StatutUtilisateur.aidant}
)

ROLES_DU_STATUT: dict[StatutUtilisateur, tuple[RoleUtilisateur, ...]] = {
    StatutUtilisateur.copropriétaire_résident: (
        RoleUtilisateur.propriétaire,
        RoleUtilisateur.résident,
    ),
    StatutUtilisateur.copropriétaire_bailleur: (RoleUtilisateur.propriétaire,),
    StatutUtilisateur.locataire: (RoleUtilisateur.résident,),
}

#: Les rôles qu'un statut confère — donc ceux qu'un changement de statut remplace.
ROLES_DERIVES = frozenset(
    {RoleUtilisateur.propriétaire, RoleUtilisateur.résident, RoleUtilisateur.externe}
)


def roles_du_statut(statut: StatutUtilisateur | None) -> tuple[RoleUtilisateur, ...]:
    """PURE. Les rôles que ce statut confère — `résident` pour un statut sans règle."""
    if statut in STATUTS_EXTERNES:
        return (RoleUtilisateur.externe,)
    return ROLES_DU_STATUT.get(statut, (RoleUtilisateur.résident,))


def poser_roles_du_statut(user: Utilisateur, statut: StatutUtilisateur) -> tuple[set, set]:
    """Remplace les rôles dérivés du statut ; rend `(ajoutés, retirés)` pour le journal.

    `role` (le rôle MONTRÉ) suit par `role_principal`, la seule hiérarchie.
    """
    derives = {r.value for r in ROLES_DERIVES}
    avant = list(user.roles)
    nouveaux = [r for r in avant if r not in derives]
    nouveaux += [r.value for r in roles_du_statut(statut) if r.value not in nouveaux]
    user.roles_json = ",".join(nouveaux)
    user.role = role_principal(nouveaux, defaut=nouveaux[0]) or user.role
    return set(nouveaux) - set(avant), set(avant) - set(nouveaux)
