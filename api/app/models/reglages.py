"""La table clé → valeur des réglages du site (`config_site`).

Extraite de `models/core.py` le 30/10/2026 (#2316). Ce module ne porte que la
FORME : quelles clés s'écrivent, et par quel onglet, se décide dans
`utils/reglages` (#2055). `core.py` la ré-exporte (enregistrement Alembic, #1157).
"""

from sqlmodel import Field, SQLModel


class ConfigSite(SQLModel, table=True):
    """Paramètres de configuration sauvegardés par l'admin (titre, descriptif, nom du site…).
    Stockés en base pour être visibles de tous les appareils."""

    __tablename__ = "config_site"
    cle: str = Field(primary_key=True)
    valeur: str
