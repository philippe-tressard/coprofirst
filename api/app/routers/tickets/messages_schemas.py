"""Les schémas de la messagerie d'une affaire — ce qui entre, ce qui sort.

Sortis de `app/schemas.py` (#1566) : seul `messages.py` s'en sert.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas_communs import ListeJson
from app.utils.assiste_ia import AssisteIAEntree


class MessageCreate(AssisteIAEntree):
    contenu: str
    interne: bool = False
    fichiers_urls: List[str] = []
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement


class MessageRead(BaseModel):
    id: int
    ticket_id: int
    auteur_id: Optional[int] = None  # #1688
    contenu: str
    interne: bool
    cree_le: datetime
    fichiers_urls: ListeJson = []

    class Config:
        from_attributes = True
