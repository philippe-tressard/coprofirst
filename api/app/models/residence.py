"""Ce que la résidence DIT à ses habitants : la FAQ et les règles de vie.

Extraites de `models/core.py` le 30/10/2026 (#2316) — `core.py` ne garde que
l'utilisateur et ce qui lui est attaché (`test_core_sans_modele_neuf.py`). Ni
l'une ni l'autre ne porte de `Relationship` : l'extraction ne change rien au
schéma, la table garde son nom.

⚠️ `core.py` les **ré-exporte** : `from app.models.core import FaqItem` reste
valable, et c'est cet import qui les enregistre — `alembic/env.py` n'importe
que `core` (#1157).
"""

from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge


class FaqItem(SQLModel, table=True):
    __tablename__ = "faq_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    categorie: str  # ex. "🗑️ Tri des déchets"
    question: str
    reponse: str
    ordre: int = 0  # ordre d'affichage dans la catégorie
    actif: bool = True
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class RegleResidence(SQLModel, table=True):
    __tablename__ = "regle_residence"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    contenu: str = ""
    ordre: int = Field(default=0)
    cree_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    modifie_le: Optional[NaiveDatetime] = None
