"""La délégation d'un résident à un proche aidant.

Extrait de `core.py` le 28/09/2026, au fil de l'eau (#779, modularité). La règle
d'appartenance de l'aidant vit dans `auth/appartenance.py`, les délégations en
vigueur dans `utils/delegations_actives.py` : ce module ne porte que la table.

Ré-exportée par `core.py` : les imports existants ne bougent pas, et c'est cet
import qui enregistre la table auprès de SQLModel.
"""

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge


class StatutDelegation(str, Enum):
    en_attente = "en_attente"  # créée par le CS, en attente d'acceptation
    active = "active"  # acceptée par l'aidant
    revoquee = "revoquee"  # révoquée par le mandant ou le CS
    expiree = "expiree"  # date de fin dépassée


class Delegation(SQLModel, table=True):
    __tablename__ = "delegation"
    id: Optional[int] = Field(default=None, primary_key=True)
    mandant_id: int = Field(foreign_key="utilisateur.id")  # la personne aidée
    aidant_id: int = Field(foreign_key="utilisateur.id")  # le proche aidant
    statut: StatutDelegation = StatutDelegation.en_attente
    motif: str = ""  # raison de la délégation
    date_debut: date = Field(default_factory=horloge.aujourd_hui)
    date_fin: Optional[date] = None  # null = pas de limite
    cree_par_id: Optional[int] = Field(
        default=None, foreign_key="utilisateur.id"
    )  # CS/admin qui a créé
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    revoque_le: Optional[NaiveDatetime] = None
    revoque_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
