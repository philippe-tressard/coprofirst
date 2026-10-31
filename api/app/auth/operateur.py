"""Qui est l'OPÉRATEUR de l'instance — une seule réponse (spec §4.7, 31/10/2026).

L'opérateur supervise l'INSTANCE (santé, tâches, base, inscription, bail) ;
l'administrateur gère UNE copropriété. Ce qui les désigne diffère :

- **Instance propre** à une copropriété : le rôle porté par le compte, accordé
  dans Admin › Utilisateurs. Son administrateur est aussi son exploitant.
- **Instance commune** (`contexte.est_commune()`) : la déclaration de
  l'EXPLOITANT, champ `operateurs` de chaque copropriété du fichier
  `COPROPRIETES_FICHIER`. Le drapeau du compte n'y compte pas : l'administrateur
  d'une copropriété hébergée, qui peut accorder des rôles dans SA base, se serait
  sinon fait opérateur de l'instance entière.

`roles_effectifs` est la seule lecture : le refus (`auth/deps.require_operateur`)
et l'affichage (`UserRead.roles`) la partagent, pour que l'écran n'offre jamais
un onglet que la route refuse.
"""

from __future__ import annotations

from app import contexte
from app.auth.adresse_compte import normaliser_adresse
from app.models.core import Utilisateur
from app.models.roles import ROLE_OPERATEUR


def designe_par_l_exploitant() -> bool:
    """L'opérateur de cette instance se déclare-t-il dans le fichier de l'exploitant ?"""
    return contexte.est_commune()


def _declare(user: Utilisateur) -> bool:
    """Ce compte est-il déclaré opérateur pour la copropriété servie ?"""
    from app.installation_commune.declaration import declaration

    lue = declaration()
    if lue is None:
        return False
    servie = contexte.courante().identifiant
    adresse = normaliser_adresse(user.email)
    return any(e.copropriete.identifiant == servie and adresse in e.operateurs for e in lue.entrees)


def roles_effectifs(user: Utilisateur) -> list[str]:
    """Les rôles du compte, l'Opérateur jugé selon l'instance (voir l'en-tête)."""
    if not designe_par_l_exploitant():
        return list(user.roles)
    roles = [r for r in user.roles if r != ROLE_OPERATEUR]
    if _declare(user):
        roles.append(ROLE_OPERATEUR)
    return roles


def est_operateur(user: Utilisateur) -> bool:
    """Cet utilisateur est-il l'OPÉRATEUR de l'instance (#1750, spec §4.7) ?

    Il ne lit aucune donnée personnelle (D5) : ce qu'il lit,
    `test_operateur_sans_donnee_personnelle.py` le vérifie. Distinct de
    l'administrateur de copropriété, qu'il n'est pas forcément.
    """
    return ROLE_OPERATEUR in roles_effectifs(user)
