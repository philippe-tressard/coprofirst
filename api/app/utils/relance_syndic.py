"""Quelles affaires se relancent auprès du syndic — la règle, écrite une fois.

**Toutes, sauf les résolues, les annulées, les supprimées et les archivées**
(arbitré par l'utilisateur le 10/10/2026). La catégorie « bug » et le marquage
« non relançable » en écartaient d'autres : ils ne comptent plus, et le geste a
quitté l'écran.

🔧 **Une exception, une seule, arbitrée le même jour** : l'**entretien
périodique** — le passage d'un prestataire sous contrat ou à récurrence
(`utils/entretien_periodique`). Il ne se relance pas auprès du syndic : il se
constate, dans la vue « Entretien périodique » du reporting. Un Entretien ouvert
à la main, sans contrat ni récurrence, reste à relancer.

Elle était écrite deux fois : dans la liste de l'Espace CS (Reporting → Relance
syndic) et dans le compteur « N affaires syndic à relancer » du tableau de bord,
avec chacune son délai par défaut — et le compteur ne retenait que les affaires
déjà adressées au syndic. Aucune n'excluait une affaire 📦 archivée par le
conseil, ni une affaire absorbée par une fusion (close avec sa principale).

La liste, le compteur, l'envoi et les réponses du syndic la lisent ici — et le
**Suivi des affaires** du reporting, qui porte la relance depuis #2035 : un seul
écran, deux modes, une seule liste (il en comptait cinq de plus : les visites
périodiques et les affaires archivées).
Une affaire SUPPRIMÉE n'existe plus en base : aucune requête ne la ramène.
"""

from __future__ import annotations

from sqlalchemy import not_
from sqlmodel import Session, col, select

from app.models.core import STATUTS_TICKET_ACTIFS, ConfigSite, Ticket, TicketEvolution
from app.utils.affaire_absorbee import pas_absorbee
from app.utils.entretien_periodique import condition_periodique

#: Délai par défaut, en jours, sans avancée avant qu'une affaire soit éligible.
DELAI_DEFAUT_J = 30


def delai_relance_jours(session: Session) -> int:
    """Le délai réglé par l'administrateur (`relance_syndic_delai_jours`), sinon 30."""
    cfg = session.exec(
        select(ConfigSite).where(ConfigSite.cle == "relance_syndic_delai_jours")
    ).first()
    return int(cfg.valeur) if cfg else DELAI_DEFAUT_J


def conditions_relancable() -> tuple:
    """Les conditions SQL « affaire à relancer »."""
    return (
        #  ACTIFS, pas « non clos » : une actualité (`publie`) n'est pas une
        #  affaire suivie — elle n'a ni cycle ni syndic à relancer (#1091).
        col(Ticket.statut).in_(STATUTS_TICKET_ACTIFS),
        ~col(Ticket.archive_manuel),
        pas_absorbee(),
        not_(condition_periodique()),
    )


def relances_envoyees(session: Session, ids) -> dict[int, list]:
    """Par affaire, les instants des relances déjà envoyées au syndic, la plus ancienne en tête.

    Une affaire jamais relancée n'a pas de clé. Leur NOMBRE se lit par
    `routers/tickets/lecture_groupee.relances_par_affaire`, qui compte en base.
    """
    dates: dict[int, list] = {}
    if not ids:
        return dates
    for ticket_id, instant in session.exec(
        select(TicketEvolution.ticket_id, TicketEvolution.cree_le)
        .where(col(TicketEvolution.ticket_id).in_(ids), TicketEvolution.type == "relance")
        .order_by(TicketEvolution.cree_le)
    ).all():
        dates.setdefault(ticket_id, []).append(instant)
    return dates


def ids_relancables(session: Session, ids: set[int]) -> set[int]:
    """Parmi `ids`, ceux que la règle admet encore."""
    if not ids:
        return set()
    return set(
        session.exec(
            select(Ticket.id).where(col(Ticket.id).in_(ids), *conditions_relancable())
        ).all()
    )
