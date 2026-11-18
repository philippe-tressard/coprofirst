"""L'ALERTE d'une actualité ⚡ urgente — la seule notification qui sonne sur un téléphone (#2789).

## La décision de Philippe (18/11/2026)

Mot pour mot : « les actualités ⚡ Marquer urgente en provenance de CS ou du syndic »,
précisé le même soir par « oui, la recommandation » :

| Question | Tranchée |
|---|---|
| Qui reçoit | les LECTEURS de l'actualité — `ticket_visible`, le prédicat qui refuse la lecture —, chacun selon son profil (`cloche.sonner`, par bâtiment du périmètre) ; l'auteur du geste excepté |
| « En provenance de CS » | le geste ⚡ d'un MODÉRATEUR : conseil syndical ou admin (`est_moderateur`) |
| « Ou du syndic » | pour la suite : un compte syndic ne publie pas d'actualité aujourd'hui (#1091), et ses droits ne changent pas |
| Ce qui part sur un téléphone | ces notifications-là, et rien d'autre : elles portent `porte.TYPE_POUSSE`, le seul type que la porte du push pousse |

Avant cette décision, publier une actualité ne faisait sonner la cloche d'aucun
résident (WhatsApp, courriels, affiche) : l'alerte est donc AUSSI une notification
neuve dans l'application (type « urgence », pictogramme ⚡ pour les apps : `utils/types_notification`), et c'est voulu — le téléphone et la cloche disent la même
chose, et la porte unique du push (N6, `notifications-push.md`) reste la cloche.

## Une fois par passage à l'urgence

L'alerte suit le geste ⚡, pas l'état : `appliquer_options` dit ce qui a changé, et
une actualité déjà urgente qu'on corrige ou qu'on suit ne resonne pas (« jamais
deux fois le même avis pour un même fait »). Rien ne sonne d'une actualité réservée
au conseil (`reservee_au_conseil`) : rien ne sort d'elle.

🔒 `tests/test_alerte_actualite.py` — y compris : chaque appelant d'`appliquer_options`
appelle `sonner_l_alerte` (les trois chemins de ⚡ : création, correction, Suite).
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.auth.deps import est_moderateur
from app.models.core import Ticket, Utilisateur
from app.utils.categories_ticket import ticket_urgent
from app.utils.cloche import sonner
from app.utils.destinataires import batiments_du_perimetre
from app.utils.liens import lien_ticket
from app.utils.nature_affaire import est_actualite
from app.utils.perimetres import parse_json_perimetres
from app.utils.visibility import reservee_au_conseil, ticket_visible

#: L'option d'`appliquer_options` dont le passage déclenche l'alerte.
OPTION_URGENTE = "urgente"


def alerte_due(ticket: Ticket, auteur: Utilisateur, changees: list[str]) -> bool:
    """PURE. Ce geste fait-il de cette actualité une alerte ?"""
    return (
        OPTION_URGENTE in changees
        and ticket_urgent(ticket)
        and est_actualite(ticket)
        and est_moderateur(auteur)
        and not reservee_au_conseil(ticket)
    )


def sonner_l_alerte(
    session: Session, ticket: Ticket, auteur: Utilisateur, changees: list[str]
) -> int:
    """Fait sonner la cloche des lecteurs de l'actualité devenue urgente — rend combien.

    Ne valide pas la transaction : l'appelant le fait, et c'est après son commit que
    la porte du push avertit les téléphones (`utils/push/porte`).
    """
    if not alerte_due(ticket, auteur, changees):
        return 0
    batiments = batiments_du_perimetre(parse_json_perimetres(ticket.perimetre_cible))
    lecteurs = session.exec(
        select(Utilisateur).where(
            Utilisateur.actif == True,  # noqa: E712
            Utilisateur.id != auteur.id,
        )
    ).all()
    sonnees = 0
    for lecteur in lecteurs:
        if ticket_visible(ticket, lecteur) and sonner(
            session,
            destinataire_id=lecteur.id,
            batiments=batiments,
            #  Écrit en clair pour `test_types_notification.py` ; `test_alerte_actualite.py`
            #  vérifie que c'est bien le type que la porte pousse (`porte.TYPE_POUSSE`).
            type="urgence",
            titre=f"⚡ {ticket.titre}",
            corps="Actualité urgente de la résidence.",
            lien=lien_ticket(ticket.id),
            urgente=True,
        ):
            sonnees += 1
    return sonnees


__all__ = ["OPTION_URGENTE", "alerte_due", "sonner_l_alerte"]
