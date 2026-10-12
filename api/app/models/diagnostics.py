"""Les diagnostics et contrôles réglementaires : leur type, et les rapports déposés.

Extraits de `models/core.py` le 28/09/2026, au fil de l'eau (#1412) : ce fichier
était à 822 lignes, et annoter ses dates `NaiveDatetime` le faisait grossir — le
contrôle de modularité refuse qu'un fichier déjà au-dessus de 500 grossisse
(rang 1). Le bloc se détache proprement : ses deux tables ne sont liées qu'entre
elles, et leur seul lien vers le reste est une clé étrangère déclarée par nom de
table (`utilisateur.id`).

⚠️ `core.py` les **ré-exporte** : `from app.models.core import DiagnosticType`
reste valable, et c'est cet import qui les enregistre auprès de SQLModel —
`alembic/env.py` n'importe que `core` (#1157).
"""

from datetime import date
from typing import List, Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, Relationship, SQLModel

from app.utils import horloge


class DiagnosticType(SQLModel, table=True):
    __tablename__ = "diagnostic_type"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)
    nom: str
    texte_legislatif: str
    frequence: Optional[str] = None  # ex: "10 ans", "3 ans", "Permanent", None
    ordre: int = 0
    actif: bool = True
    non_applicable: bool = False

    rapports: List["DiagnosticRapport"] = Relationship(back_populates="type_diagnostic")


class DiagnosticRapport(SQLModel, table=True):
    __tablename__ = "diagnostic_rapport"
    id: Optional[int] = Field(default=None, primary_key=True)
    diagnostic_type_id: int = Field(foreign_key="diagnostic_type.id")
    titre: str
    date_rapport: Optional[date] = None
    fichier_nom: str
    #  La clé du fichier (#1816) — voir `Document.fichier_cle`.
    fichier_cle: Optional[str] = None
    taille_octets: Optional[int] = None
    mime_type: str = "application/octet-stream"
    synthese: Optional[str] = None  # synthèse des conclusions du rapport
    publie_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    publie_le: NaiveDatetime = Field(default_factory=horloge.maintenant)

    type_diagnostic: Optional[DiagnosticType] = Relationship(back_populates="rapports")
