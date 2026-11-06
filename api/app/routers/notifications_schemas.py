"""Les schémas des notifications : la lecture, et ce que rendent les gestes groupés.

Sortis de `app/schemas.py` (#1566) : seul `routers/notifications.py` s'en sert.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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


#: Le plafond d'une sélection : au-delà de ce qu'un compte réel accumule (146 au
#: 05/11/2026), et assez bas pour qu'une requête ne porte pas une liste sans fin.
SELECTION_MAX = 500


class SuppressionNotifications(BaseModel):
    """`POST /notifications/supprimer-selection` — les notifications choisies (l'app iOS, #2535).

    Un identifiant qui n'est pas une notification du demandeur est ignoré.
    """

    ids: list[int] = Field(min_length=1, max_length=SELECTION_MAX)


class NotificationsSupprimees(BaseModel):
    """`POST /notifications/supprimer-lues` et `…/supprimer-selection` — combien ont été supprimées."""

    supprimees: int
