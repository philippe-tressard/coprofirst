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
    #: l'auteur détaché par la conservation (#2014) : « Un résident », « Le conseil syndical »
    auteur_qualite: Optional[str] = None
    #: le nom AFFICHÉ de l'auteur, servi par `routers/tickets/messages.message_lu`
    #: (`utils/noms.nom_auteur`, qui tient compte de la qualité) — le fil le lit (#2680)
    auteur_nom: str = ""
    #: CE lecteur en est-il l'auteur ? (`auth/deps.est_auteur`) — la bulle se range
    #: à droite ; l'écran ne compare pas les identifiants lui-même (#2680)
    est_auteur: bool = False
    contenu: str
    interne: bool
    cree_le: datetime
    fichiers_urls: ListeJson = []

    class Config:
        from_attributes = True
