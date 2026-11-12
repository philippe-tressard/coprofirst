"""Les gestes de rôle qu'Admin › Utilisateurs offre sur un compte — servis, jamais recomposés.

## Pourquoi au serveur (#2618, 10/11/2026)

L'écran décidait seul quels rôles un compte peut recevoir ou perdre
(`gestesAdminOperateur` et `compterTitulaires`, `#lib/droits`) : l'app iOS, qui ne
recopie aucune règle du site (`standards/09` §8, règle 1), ne pouvait ni porter ces
gestes ni dire pourquoi l'un manquait. La règle se calcule donc ici, et la liste des
comptes la SERT (`UtilisateurAdminRead.gestes_roles`) ; le site et l'app la lisent.

## Ce qu'elle dit — une valeur par rôle : `"ajouter"`, `"retirer"` ou `None`

| Rôle | Ajouter | Retirer |
|---|---|---|
| Conseil syndical | à un copropriétaire | toujours |
| Admin | à un copropriétaire | sauf à son dernier titulaire actif |
| Opérateur | à un administrateur, hors instance commune | sauf à son dernier titulaire actif, hors instance commune |

Un compte inactif n'a aucun geste, et seul un administrateur en a (les routes
prennent `require_admin`).

⚠️ « À un copropriétaire » est une règle d'ÉCRAN que les routes n'imposent pas :
l'écran offre MOINS que la route n'accepte — le sens permis (checklist de `ux-patterns`, « un geste
d'écriture n'est offert qu'aux rôles que sa route accepte »), jamais plus. Les deux
refus de la route, eux, sont ceux d'ici : `refus_operateur` et `titulaires`.
🔒 `test_gestes_roles.py` confronte chaque geste servi à la réponse de la route.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.operateur import designe_par_l_exploitant
from app.models.core import RoleUtilisateur, Utilisateur
from app.models.roles import ROLE_OPERATEUR
from app.utils.valeurs import valeur

#: Les rôles qui ne restent jamais VACANTS : sans administrateur, plus personne
#: ne gère les comptes ; sans opérateur, plus personne ne supervise l'installation.
#: Chacun se retire — à soi-même compris —, sauf à son dernier titulaire actif.
ROLES_JAMAIS_VACANTS = (RoleUtilisateur.admin.value, ROLE_OPERATEUR)

Geste = Optional[Literal["ajouter", "retirer"]]


class GestesRoles(BaseModel):
    """Le geste qu'Admin › Utilisateurs offre sur chaque rôle d'un compte."""

    conseil_syndical: Geste = None
    admin: Geste = None
    operateur: Geste = None


def titulaires(session: Session) -> dict[str, int]:
    """Combien de comptes ACTIFS portent chaque rôle de `ROLES_JAMAIS_VACANTS`.

    Lu en Python, par `has_role` : un `roles_json` vide retombe sur la colonne
    `role`, qu'un filtre SQL sur la chaîne ne verrait pas.
    """
    actifs = session.exec(select(Utilisateur).where(Utilisateur.actif == True)).all()  # noqa: E712
    return {role: sum(1 for u in actifs if u.has_role(role)) for role in ROLES_JAMAIS_VACANTS}


def refus_operateur(cible: Utilisateur, *, retrait: bool) -> Optional[tuple[int, str]]:
    """Le refus du geste Opérateur sur ce compte — `(code, message)` —, ou `None`.

    Il s'**accorde** à un administrateur, et se **garde** ensuite sans lui (#2029).
    Sur une instance COMMUNE, ni l'un ni l'autre : l'exploitant le désigne (31/10/2026).
    """
    if designe_par_l_exploitant():
        return (
            409,
            "L'opérateur de cette instance est désigné par son exploitant, "
            "dans la déclaration des copropriétés.",
        )
    if not retrait and not cible.has_role(RoleUtilisateur.admin):
        return (
            400,
            "Le rôle Opérateur s'accorde à un administrateur : ajoutez d'abord le rôle Admin.",
        )
    return None


def _coproprietaire(u: Utilisateur) -> bool:
    return (valeur(u.statut) or "").startswith("copropriétaire")


def gestes_roles(u: Utilisateur, comptes: dict[str, int], *, par_admin: bool) -> GestesRoles:
    """Les gestes offerts sur le compte `u` ; `comptes` vient de `titulaires`."""
    if not par_admin or not u.actif:
        return GestesRoles()

    def retirable(role: str) -> bool:
        return comptes.get(role, 0) > 1

    cs = RoleUtilisateur.conseil_syndical
    admin = RoleUtilisateur.admin.value
    gestes = GestesRoles(
        conseil_syndical="retirer"
        if u.has_role(cs)
        else ("ajouter" if _coproprietaire(u) else None),
        admin=(
            ("retirer" if retirable(admin) else None)
            if u.has_role(admin)
            else ("ajouter" if _coproprietaire(u) else None)
        ),
    )
    if u.has_role(ROLE_OPERATEUR):
        if refus_operateur(u, retrait=True) is None and retirable(ROLE_OPERATEUR):
            gestes.operateur = "retirer"
    elif refus_operateur(u, retrait=False) is None:
        gestes.operateur = "ajouter"
    return gestes
