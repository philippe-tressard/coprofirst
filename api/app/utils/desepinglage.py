"""📌 Une affaire close perd son épingle 24 heures après sa clôture (16/10/2026).

Épingler, c'est « garder en vue » ce qui demande encore l'attention. Une affaire
résolue ou annulée n'en demande plus : on la laisse épinglée un jour, le temps que
chacun voie l'issue, puis la tâche horaire retire l'épingle. L'affaire quitte alors
la tête de la liste et le bandeau « Épinglé ».

La règle vaut pour **toute** affaire close, actualités suivies comprises : leur
suivi se clôt comme une affaire, et `ferme_le` le date (`utils/suivi_actualite`).
L'état se lit par `etat_de_la_suite`, la seule question « où en est-elle ? ».

Arbitré avec l'utilisateur le 16/10/2026 :

- une épingle remise par le conseil **après** les 24 heures retombe au passage
  suivant — la règle n'a pas d'exception ;
- une affaire rouverte reste désépinglée ;
- rien n'est écrit au fil de l'affaire : le retrait n'est pas une décision.

⚠️ `mis_a_jour_le` n'est PAS touché : ce retrait n'est pas une modification, et
la date sert de référence à l'archivage d'une actualité (`utils/archivage`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlmodel import Session, col, select

from app.models.core import Ticket
from app.models.tickets import STATUTS_TICKET_CLOS
from app.utils import horloge
from app.utils.suivi_actualite import etat_de_la_suite

logger = logging.getLogger("hostachy.desepinglage")

#: L'identifiant de la tâche permanente (`main.py`, `TACHES_PERMANENTES`).
ID_TACHE = "desepinglage_affaires_closes"

#: Le temps pendant lequel une affaire close reste épinglée.
DELAI_EPINGLE_APRES_CLOTURE = timedelta(hours=24)


def epingle_echue(ticket: Any, maintenant: datetime) -> bool:
    """Cette affaire épinglée est-elle close depuis plus de 24 heures ?

    🔴 Close **aujourd'hui** : `ferme_le` reste posé quand une affaire se rouvre,
    il ne suffit donc pas à dire qu'elle est close.
    """
    if not getattr(ticket, "epingle", False) or ticket.ferme_le is None:
        return False
    if etat_de_la_suite(ticket) not in STATUTS_TICKET_CLOS:
        return False
    return maintenant - ticket.ferme_le >= DELAI_EPINGLE_APRES_CLOTURE


def desepingler_affaires_closes(
    session: Optional[Session] = None, maintenant: Optional[datetime] = None
) -> int:
    """La tâche permanente : retire l'épingle des affaires closes depuis 24 heures.

    Rend le nombre d'affaires désépinglées. ⚠️ Ne lève jamais : sous le
    planificateur, une exception tuerait le job pour de bon.
    """
    from app import contexte

    propre = session is None
    session = session or contexte.nouvelle_session()
    maintenant = maintenant or horloge.maintenant()
    retirees = 0
    try:
        candidates = session.exec(
            select(Ticket).where(
                Ticket.epingle == True,  # noqa: E712
                col(Ticket.ferme_le).is_not(None),
                col(Ticket.ferme_le) <= maintenant - DELAI_EPINGLE_APRES_CLOTURE,
            )
        ).all()
        for ticket in candidates:
            if epingle_echue(ticket, maintenant):
                ticket.epingle = False
                session.add(ticket)
                retirees += 1
        session.commit()
        #  Une trace à CHAQUE passage, rien à retirer compris : un battement qu'on
        #  n'entend pas ne se distingue pas d'une tâche morte (`standards/07`).
        logger.info("Affaires closes désépinglées : %d", retirees)
    except Exception as exc:  # pragma: no cover - la tâche ne meurt pas
        session.rollback()
        logger.warning("Désépinglage des affaires closes non fait : %s", exc)
        retirees = 0
    finally:
        if propre:
            session.close()
    return retirees


__all__ = [
    "DELAI_EPINGLE_APRES_CLOTURE",
    "ID_TACHE",
    "desepingler_affaires_closes",
    "epingle_echue",
]
