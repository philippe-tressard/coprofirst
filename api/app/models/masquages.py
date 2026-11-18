"""Les masques qu'un résident pose sur ce que publie un autre (#2861).

Une ligne : « `masque_par` ne veut plus voir ce que publie `auteur` ». Les deux
références sont obligatoires : un compte supprimé emporte ses masques, posés ou
subis (`utils/purge_referentielle`). La règle : `utils/masquage`.
"""

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel, UniqueConstraint

from app.utils import horloge


class MasquageAuteur(SQLModel, table=True):
    __tablename__ = "masquage_auteur"
    __table_args__ = (UniqueConstraint("masque_par_id", "auteur_id", name="uq_masquage_auteur"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    masque_par_id: int = Field(foreign_key="utilisateur.id", index=True)
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
