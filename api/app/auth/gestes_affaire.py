"""Les gestes d'une affaire que l'écran OFFRE — servis avec elle (#2508).

## Pourquoi ce module

L'app iOS ne parle qu'au contrat de l'API. Pour offrir « Archiver », « Changer
l'état » ou « Répondre », elle déduisait le rôle « modérateur » de `GET /auth/me`
et recomposait la règle du site (`$isCS`, `peutCommenter`) : une seconde copie,
dans un autre dépôt, qui divergerait au premier arbitrage (`standards/09` §8,
règle 1). Le serveur sert donc, sur chaque `TicketRead`, ce que CE lecteur peut
faire de CETTE affaire, et le site lit les mêmes champs.

## La règle de ce module : jamais plus large que la route

Chaque prédicat dit ce que la route du geste ACCEPTE, en appelant les prédicats
qu'elle appelle (`auth/deps`, `nature_affaire`) — jamais une copie. Un droit servi
plus large tendrait un bouton qui finit en 403 ; plus étroit, il tairait un geste
permis. 🔒 `test_gestes_affaire_servis.py` joue chaque geste par sa route, pour
chaque rôle, et confronte la réponse au champ servi.

⚠️ `peut_deplacer_au_kanban` est la seule règle PLUS ÉTROITE que sa route, et
c'est un arbitrage (23/09/2026, `VueKanbanAffaires`) : le conseil seul glisse
une carte, alors que la Suite d'état reste ouverte à l'auteur. Elle s'écrit donc
sur `peut_changer_etat`, qu'elle restreint — jamais à côté.

✏️ `peut_corriger` (#2633) est le geste du CRAYON : il ouvre la correction de
l'affaire — contenu, liées, diffusion, suivi —, et se lit sur `auth/deps.peut_editer`,
le droit que la route `PATCH` exige pour toucher au contenu. Il est plus LARGE que
`peut_modifier`, qui ajoute « tant qu'elle est ouverte » au contenu seul : l'auteur
d'une affaire engagée garde son crayon (la diffusion, les options passent encore).
Arbitré le 11/11/2026 : le conseil syndical le reçoit aussi sur une actualité,
comme la route l'accepte depuis #1091 ; l'écran le taisait.
"""

from __future__ import annotations

from typing import Any

from app.auth.deps import est_moderateur, peut_commenter, peut_editer
from app.models.core import RoleUtilisateur, StatutTicket, Utilisateur
from app.models.tickets import CategorieTicket
from app.utils.carnet_entretien import est_du_bati
from app.utils.etat_affaire import affaire_close
from app.utils.nature_affaire import categorie_reservee, est_actualite
from app.utils.valeurs import valeur

#: Les états où l'auteur corrige encore le contenu (`PATCH /tickets/{id}`) :
#: une fois le suivi engagé, corriger le texte ferait mentir ce que le conseil a
#: lu avant d'agir. L'administrateur n'y est pas tenu.
ETATS_CORRIGEABLES: tuple[str, ...] = (StatutTicket.ouvert.value, StatutTicket.publie.value)


def _absorbee(ticket: Any) -> bool:
    """Une affaire fusionnée dans une autre n'a plus de Suite (#1704, 422)."""
    return getattr(ticket, "fusionnee_dans_id", None) is not None


def peut_archiver(ticket: Any, user: Utilisateur) -> bool:
    """📦 `PATCH /tickets/{id}` avec `archive_manuel` : le conseil ou l'administration.

    La route exige `peut_commenter` puis `est_moderateur` ; un modérateur commente
    toute affaire (`peut_commenter` admet le conseil, `peut_editer` l'admin), la
    première condition est donc comprise dans la seconde.
    """
    return est_moderateur(user) and peut_commenter(ticket, user)


def peut_changer_etat(ticket: Any, user: Utilisateur) -> bool:
    """Une Suite qui change l'état (`POST /tickets/{id}/evolutions`, `type=etat`).

    Qui commente l'affaire, tant qu'elle n'est pas absorbée ; une actualité, le
    conseil seul et seulement si son suivi est activé (`suivi_actualite.refuser_etat`).
    """
    if _absorbee(ticket) or not peut_commenter(ticket, user):
        return False
    if est_actualite(ticket):
        return bool(getattr(ticket, "suivi_actualite", None)) and est_moderateur(user)
    return True


def peut_deplacer_au_kanban(ticket: Any, user: Utilisateur) -> bool:
    """Glisser la carte d'une colonne à l'autre — le conseil seul (arbitrage du 23/09/2026)."""
    return (
        est_moderateur(user)
        and bool(getattr(ticket, "suivi_kanban", False))
        and peut_changer_etat(ticket, user)
    )


def peut_repondre(ticket: Any, user: Utilisateur) -> bool:
    """« Répondre » : une Suite sans changement d'état — qui commente, hors absorbée."""
    return not _absorbee(ticket) and peut_commenter(ticket, user)


def peut_modifier(ticket: Any, user: Utilisateur) -> bool:
    """✏️ Corriger le CONTENU (`PATCH /tickets/{id}`) : `peut_editer`, puis l'état.

    L'auteur ne corrige que tant que l'affaire est ouverte (ou publiée, pour une
    actualité) ; l'administrateur toujours.
    """
    if not peut_editer(ticket, user):
        return False
    if user.has_role(RoleUtilisateur.admin):
        return True
    return valeur(getattr(ticket, "statut", None)) in ETATS_CORRIGEABLES


def peut_changer_prestataires(ticket: Any, user: Utilisateur) -> bool:
    """🛠️ Désigner les prestataires (#2704, Q1) : le conseil, sur une affaire du bâti ouverte.

    `peut_modifier` ne suffit pas : il admet l'auteur, alors que la liste est au
    conseil seul (`utils/intervenant` ignore celle d'un résident). La route l'accepte
    aussi sur une affaire close ; l'écran ne l'offre que tant qu'elle est ouverte —
    arbitré le 12/11/2026, comme `peut_deplacer_au_kanban` restreint sa route.
    """
    return (
        est_moderateur(user)
        and not _absorbee(ticket)
        and not est_actualite(ticket)
        and est_du_bati(getattr(ticket, "categorie", None))
        and not affaire_close(getattr(ticket, "statut", None))
    )


def categorie_permise(categorie: Any, user: Utilisateur) -> bool:
    """Ce compte peut-il poser cette catégorie (création, correction) ? 403 sinon."""
    return est_moderateur(user) or not categorie_reservee(categorie)


def categories_permises(user: Utilisateur) -> list[str]:
    """Les catégories que la grille « Nouvelle affaire » offre à ce compte."""
    return [c.value for c in CategorieTicket if categorie_permise(c, user)]


def gestes_servis(ticket: Any, lecteur: Utilisateur | None) -> dict[str, bool]:
    """Les champs `peut_*` de `TicketRead` pour ce lecteur — tous FERMÉS sans lui."""
    gestes = {
        "peut_archiver": peut_archiver,
        "peut_changer_etat": peut_changer_etat,
        "peut_deplacer_au_kanban": peut_deplacer_au_kanban,
        "peut_repondre": peut_repondre,
        "peut_modifier": peut_modifier,
        "peut_corriger": peut_editer,
        "peut_changer_prestataires": peut_changer_prestataires,
    }
    return {nom: lecteur is not None and regle(ticket, lecteur) for nom, regle in gestes.items()}


__all__ = [
    "gestes_servis",
    "ETATS_CORRIGEABLES",
    "categorie_permise",
    "categories_permises",
    "peut_archiver",
    "peut_changer_etat",
    "peut_changer_prestataires",
    "peut_deplacer_au_kanban",
    "peut_modifier",
    "peut_repondre",
]
