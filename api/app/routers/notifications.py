"""Router notifications — liste, marquer lue, tout marquer lu, supprimer.

🔴 **Une notification n'appartient qu'à son destinataire**, et cette phrase ne
s'écrit qu'à UN endroit : `ma_notification`, dans `app/auth/deps.py` — le module
d'autorisation, pas ce routeur. Elle était écrite QUATRE fois au
18/09/2026 : deux dans ce fichier, et deux de plus dans
`routers/admin/communications.py`, qui doublait purement et simplement ces
routes. `standards/03` §1 — l'autorisation est centralisée, et une règle
d'autorisation en quatre exemplaires se durcit une fois sur quatre. Les gestes sur
PLUSIEURS notifications prennent son pendant, `mes_notifications`.

Supprimer en groupe (#2535) : une requête `DELETE` en base, jamais une boucle — l'app
iOS envoyait une requête par alerte, 134 pour vider les lues d'un compte.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, delete, select

from app.auth.deps import get_current_user, ma_notification, mes_notifications
from app.database import get_session
from app.models.core import Notification, Utilisateur
from app.routers.notifications_schemas import (
    NotificationRead,
    NotificationsSupprimees,
    SuppressionNotifications,
    ToutMarquerLu,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return session.exec(
        select(Notification).where(mes_notifications(user)).order_by(Notification.cree_le.desc())
    ).all()


@router.patch("/{notif_id}/lue", response_model=NotificationRead)
def marquer_lue(
    notif: Notification = Depends(ma_notification),
    session: Session = Depends(get_session),
):
    notif.lue = True
    session.add(notif)
    session.commit()
    session.refresh(notif)
    return notif


@router.post("/tout-marquer-lu", response_model=ToutMarquerLu)
def tout_marquer_lu(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    notifs = session.exec(
        select(Notification).where(mes_notifications(user)).where(Notification.lue == False)  # noqa: E712
    ).all()
    for n in notifs:
        n.lue = True
        session.add(n)
    session.commit()
    return {"marquees": len(notifs)}


@router.delete("/{notif_id}", status_code=204)
def supprimer_notification(
    notif: Notification = Depends(ma_notification),
    session: Session = Depends(get_session),
):
    session.delete(notif)
    session.commit()


def _supprimer(session: Session, user: Utilisateur, *conditions) -> NotificationsSupprimees:
    """Supprime, en une requête, les notifications de `user` qui remplissent `conditions`."""
    resultat = session.exec(delete(Notification).where(mes_notifications(user), *conditions))
    session.commit()
    return NotificationsSupprimees(supprimees=resultat.rowcount)


@router.post("/supprimer-lues", response_model=NotificationsSupprimees)
def supprimer_lues(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _supprimer(session, user, Notification.lue == True)  # noqa: E712


@router.post("/supprimer-selection", response_model=NotificationsSupprimees)
def supprimer_selection(
    corps: SuppressionNotifications,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return _supprimer(session, user, Notification.id.in_(corps.ids))
