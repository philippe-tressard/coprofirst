"""Qui voit quelle page au menu — la règle CALCULÉE par le serveur (#2969, #2905).

## 🔴 Pourquoi ici

Le filtre du menu vivait dans `Nav.svelte`, en littéraux de rôles et de statuts ; les
apps iOS et Android en portaient chacune leur copie, et les trois divergeaient : le
syndic et le mandataire n'avaient AUCUNE entrée sur le site (#2905), les sept pages
générales dans les apps ; l'aidant voyait la Communauté dans les apps, pas sur le
site ; le compte technique, les pages des résidents dans les apps seulement. Une règle
d'affichage que le site et l'app montrent se calcule dans l'API (`CLAUDE.md`).

## Le partage

- chaque page du menu déclare son PUBLIC (`acces`) dans `front/src/lib/pages.ts` et
  `pages-roles.ts`, publié aux apps par `front/tables-clients.json` (table `pages`) ;
- le serveur dit à quels publics appartient le compte : `acces_menu` de
  `GET /auth/me` (`UserRead`), calculé ici et nulle part ailleurs ;
- un client montre une page si son `acces` est dans `acces_menu` — rien d'autre.

## Les publics (tranché le 23/11/2026, par délégation, sur l'écrit majoritaire)

- `tous` — les pages générales : toute personne liée à la résidence par son statut
  (copropriétaire, locataire, syndic, mandataire, aidant) ou par un rôle qu'un statut
  confère. PAS le compte technique (`admin_technique`, administrateur ou opérateur
  seul) : il n'habite pas la résidence.
- `resident` — la Communauté : les résidents, et le syndic et le mandataire, que
  l'entrée mène au seul onglet Avis (arbitrage du 18/10/2026, #2075,
  `communaute.motif_de_refus`) ; pas l'aidant (manuel, carte Communauté).
- `cs` — Prestataires, Espace CS : qui modère (`est_moderateur`), sauf le compte
  administrateur seul.
- `cs-ou-aidant` — Délégations : les mêmes, et l'aidant (statut, ou délégation active).
- `admin` — l'administration : l'administrateur et l'opérateur.

Masquer ne protège rien : chaque route tranche ses droits elle-même.
🔒 `tests/test_acces_menu.py` (la règle, et sa concordance avec `pages.ts` et
`ROLES_DU_DROIT`).
"""

from __future__ import annotations

from app.auth.deps import est_moderateur
from app.models.core import Utilisateur
from app.models.roles import ROLE_OPERATEUR, RoleUtilisateur, StatutUtilisateur
from app.utils.roles_du_statut import ROLES_DERIVES

#: Les publics du menu, dans l'ordre où le manuel les présente. Leurs noms sont ceux
#: des `acces` de `front/src/lib/pages.ts` (🔒 concordance).
ACCES_MENU = ("tous", "resident", "cs", "cs-ou-aidant", "admin")

#: Le compte « administrateur seul » : `admin` sans aucun de ceux-ci — la copie de
#: `ROLES_DU_DROIT.sansAdminSeul` (`front/src/lib/roles.ts`, 🔒 concordance).
SANS_ADMIN_SEUL = frozenset(
    {
        RoleUtilisateur.propriétaire.value,
        RoleUtilisateur.résident.value,
        RoleUtilisateur.conseil_syndical.value,
    }
)
_ADMINISTRATION = frozenset({RoleUtilisateur.admin.value, ROLE_OPERATEUR})


def acces_du_menu(user: Utilisateur, roles: list[str], aidant_actif: bool) -> list[str]:
    """PURE. Les publics du menu auxquels ce compte appartient, dans l'ordre d'`ACCES_MENU`.

    `roles` : les rôles EFFECTIFS (`auth/operateur.roles_effectifs`) ; `aidant_actif` :
    le compte est l'aidant d'au moins une délégation active.
    """
    r = set(roles)
    derives = {d.value for d in ROLES_DERIVES}
    admin_seul = RoleUtilisateur.admin.value in r and not (r & SANS_ADMIN_SEUL)
    cs = est_moderateur(user) and not admin_seul
    aidant = user.statut == StatutUtilisateur.aidant
    lie = bool(r & derives) or user.statut not in (None, StatutUtilisateur.admin_technique)
    ouverts = {
        "tous": lie,
        "resident": lie and not aidant,
        "cs": cs,
        "cs-ou-aidant": cs or aidant or aidant_actif,
        "admin": bool(r & _ADMINISTRATION),
    }
    return [a for a in ACCES_MENU if ouverts[a]]
