"""Le schéma de lecture d'une notification.

Sorti de `app/schemas.py` (#1566) : seul `routers/notifications.py` le rend.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationRead(BaseModel):
    id: int
    type: str
    titre: str
    corps: str
    lien: Optional[str] = None
    lue: bool
    urgente: bool
    cree_le: datetime

    class Config:
        from_attributes = True


class ToutMarquerLu(BaseModel):
    """`POST /notifications/tout-marquer-lu` — combien de notifications ont été marquées."""

    marquees: int
