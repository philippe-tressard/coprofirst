"""Les lots IMPORTÉS d'un classeur, en attente d'être rattachés — la table de passage.

Extraite de `models/core.py` le 28/09/2026, au fil de l'eau (#779) : le fichier
faisait 797 lignes, et le contrôle de modularité refuse qu'un fichier déjà
au-dessus de 500 grossisse. La table se détache proprement : aucune
`Relationship`, et son seul lien vers le reste est `lot.id`, déclaré par nom de
table.

⚠️ `core.py` la **ré-exporte** : `from app.models.core import LotImport` reste
valable, et c'est cet import qui l'enregistre — `alembic/env.py` n'importe que
`core` (#1157).
"""

from enum import Enum
from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.utils import horloge


class StatutLotImport(str, Enum):
    en_attente = "en_attente"  # importé, rien de lié
    utilisateur_lie = "utilisateur_lie"  # occupant(s) identifié(s), lot pas encore trouvé
    lot_lie = "lot_lie"  # lot_id trouvé/confirmé en base
    resolu = "resolu"  # UserLot créé (lot + occupants confirmés)
    ignore = "ignore"


class LotImport(SQLModel, table=True):
    """Staging des lots importés depuis l'Excel,
    en attente de liaison avec les utilisateurs de l'application."""

    __tablename__ = "lot_import"

    id: Optional[int] = Field(default=None, primary_key=True)

    # ── Données brutes de l'Excel ─────────────────────────────────────────
    batiment_id: Optional[int] = None  # col A — None pour les parkings
    numero: str  # col B
    type_raw: str  # col C (AP, ST, T2, CA, PS…)
    etage_raw: Optional[str] = None  # col D
    no_coproprietaire: Optional[str] = None  # col F
    nom_coproprietaire: Optional[str] = None  # col G

    # ── Résolution par l'admin ────────────────────────────────────────────
    statut: StatutLotImport = StatutLotImport.en_attente

    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")

    # JSON array de {user_id, type_lien} — plusieurs occupants possibles
    # ex. [{"user_id": 12, "type_lien": "propriétaire"},
    #       {"user_id": 15, "type_lien": "locataire"}]
    utilisateurs_json: str = Field(default="[]")

    notes_admin: Optional[str] = None
    importe_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    resolu_le: Optional[NaiveDatetime] = None
