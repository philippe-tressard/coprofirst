"""Une notification dans l'application — la cloche, pas le courriel.

Extraite de `models/core.py` le 30/10/2026 (#2316). Aucune `Relationship` : son
seul lien est `utilisateur.id`, déclaré par nom de table. `core.py` la
ré-exporte (c'est ce qui l'enregistre pour Alembic, #1157).
"""

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge


class Notification(SQLModel, table=True):
    __tablename__ = "notification"
    id: Optional[int] = Field(default=None, primary_key=True)
    destinataire_id: int = Field(foreign_key="utilisateur.id")
    type: str  # ticket_update | publication | vigik | urgence | system
    titre: str
    corps: str = ""
    lien: Optional[str] = None
    lue: bool = False
    urgente: bool = False
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
