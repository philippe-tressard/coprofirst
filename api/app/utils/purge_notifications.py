"""Les notifications LUES se conservent douze mois, puis la tâche nocturne les retire (#2535).

Décidé par l'administrateur le 08/11/2026 : « 12 mois ». La cloche et la page
Notifications grossissaient sans fin — un compte du syndic en portait 146, dont
134 lues — et rien ne retirait jamais une alerte.

## La règle

- Une notification **lue** dont la **création** remonte à plus de 365 jours est
  retirée. L'ancienneté se compte depuis `cree_le` : la table ne date pas la lecture.
- Une notification **non lue** ne se purge **jamais**, quel que soit son âge : elle
  dit encore quelque chose à son destinataire.
- La règle vaut pour tous les destinataires, sans exception ni réglage.

## La tâche

Une fois par nuit (`main.py`, `TACHES_PERMANENTES`), dans le contexte de chaque
copropriété. ⚠️ Elle ne lève jamais — une exception sous le planificateur tuerait
le job pour de bon — et laisse une ligne à CHAQUE passage, rien à retirer compris :
un battement qu'on n'entend pas ne se distingue pas d'une tâche morte
(`standards/07`). La ligne ne dit qu'un nombre, jamais un destinataire.

⚠️ La durée est ANNONCÉE aux utilisateurs par la politique de confidentialité
(lot #2495) : la changer ici, c'est changer ce texte aussi.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlmodel import Session, col, delete

from app.models.core import Notification
from app.utils import horloge

logger = logging.getLogger("hostachy.purge_notifications")

#: L'identifiant de la tâche permanente (`main.py`, `TACHES_PERMANENTES`).
ID_TACHE = "purge_notifications_lues"

#: Douze mois (décision du 08/11/2026) : 365 jours, pas un mois de calendrier — la
#: règle ne dépend pas de la longueur des mois traversés.
CONSERVATION_JOURS = 365


def notification_echue(notification: Any, maintenant: datetime) -> bool:
    """Cette notification est-elle lue ET plus ancienne que la conservation ?

    Pile à la limite, elle se garde : on retire strictement au-delà.
    """
    if not getattr(notification, "lue", False):
        return False
    return maintenant - notification.cree_le > timedelta(days=CONSERVATION_JOURS)


def purger_notifications_lues(
    session: Optional[Session] = None, maintenant: Optional[datetime] = None
) -> int:
    """La tâche permanente : retire les notifications lues de plus de douze mois.

    Rend leur nombre. ⚠️ Ne lève jamais.
    """
    from app import contexte

    propre = session is None
    session = session or contexte.nouvelle_session()
    maintenant = maintenant or horloge.maintenant()
    limite = maintenant - timedelta(days=CONSERVATION_JOURS)
    retirees = 0
    try:
        resultat = session.exec(
            delete(Notification).where(
                col(Notification.lue).is_(True),
                col(Notification.cree_le) < limite,
            )
        )
        session.commit()
        retirees = resultat.rowcount or 0
        logger.info(
            "Notifications lues retirées (plus de %d jours) : %d", CONSERVATION_JOURS, retirees
        )
    except Exception as exc:  # pragma: no cover - la tâche ne meurt pas
        session.rollback()
        logger.warning("Purge des notifications lues non faite : %s", exc)
        retirees = 0
    finally:
        if propre:
            session.close()
    return retirees


def enregistrer(planificateur) -> None:
    """La tâche permanente, chaque jour à 04:38 — après la bascule de nuit et la purge des
    comptes —, jouée pour chaque copropriété. Un passage manqué décale d'un jour, dans le
    sens de la conservation."""
    from app import contexte

    planificateur.add_job(
        contexte.pour_chaque_copropriete(purger_notifications_lues, "purge_notifications_lues"),
        "cron",
        hour=4,
        minute=38,
        id="purge_notifications_lues",
    )


__all__ = [
    "CONSERVATION_JOURS",
    "ID_TACHE",
    "enregistrer",
    "notification_echue",
    "purger_notifications_lues",
]
