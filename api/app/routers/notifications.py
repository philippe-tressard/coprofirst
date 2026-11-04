"""Router notifications — liste, marquer lue, tout marquer lu.

🔴 **Une notification n'appartient qu'à son destinataire**, et cette phrase ne
s'écrit qu'à UN endroit : `ma_notification`, dans `app/auth/deps.py` — le module
d'autorisation, pas ce routeur. Elle était écrite QUATRE fois au
18/09/2026 : deux dans ce fichier, et deux de plus dans
`routers/admin/communications.py`, qui doublait purement et simplement ces
routes. `standards/03` §1 — l'autorisation est centralisée, et une règle
d'autorisation en quatre exemplaires se durcit une fois sur quatre.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.deps import get_current_user, ma_notification
from app.database import get_session
from app.models.core import Notification, Utilisateur
from app.routers.notifications_schemas import NotificationRead, ToutMarquerLu

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return session.exec(
        select(Notification)
        .where(Notification.destinataire_id == user.id)
        .order_by(Notification.cree_le.desc())
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
        select(Notification)
        .where(Notification.destinataire_id == user.id)
        .where(Notification.lue == False)  # noqa: E712
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
