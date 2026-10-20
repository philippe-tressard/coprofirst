"""Les AFFAIRES LIÉES — un lien réciproque entre deux affaires (#1342, 26/09/2026).

Demandé à l'écran : « dans une affaire, ajouter une section Affaires liées, et
permettre de lier d'autres affaires ». Arbitré : le lien vaut dans les DEUX
sens — lier B à A fait apparaître A dans les affaires liées de B.

Une seule ligne par paire, rangée (`affaire_id` < `liee_id`) : c'est ce qui
rend le lien réciproque par construction, sans deux lignes à tenir d'accord.
Les règles — lecture filtrée par la visibilité, ajout, retrait — vivent dans
`utils/affaires_liees`.

## « Ne pas fusionner » (#2083, 20/10/2026)

Le conseil peut écarter la fusion de deux affaires liées depuis le Suivi des
affaires : le lien reste, mais la paire ne se rassemble plus dans le tri et
n'est plus proposée à la fusion — ni là, ni à la clôture de l'une d'elles
(`fusion_ecartee_le`). Les règles : `utils/fusion_en_cours`.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.utils import horloge
from pydantic import NaiveDatetime


class AffaireLiee(SQLModel, table=True):
    __tablename__ = "affaire_liee"
    __table_args__ = (UniqueConstraint("affaire_id", "liee_id", name="uq_affaire_liee"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    #: La plus petite des deux références, puis la plus grande.
    affaire_id: int = Field(foreign_key="ticket.id", index=True)
    liee_id: int = Field(foreign_key="ticket.id", index=True)
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    cree_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    #: Le conseil a écarté la fusion de cette paire (#2083) — et qui.
    fusion_ecartee_le: Optional[NaiveDatetime] = None
    fusion_ecartee_par_id: Optional[int] = None
