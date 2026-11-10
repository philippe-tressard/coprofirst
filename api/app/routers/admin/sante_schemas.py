"""La forme de `GET /admin/maintenance/sante` — la santé des tâches planifiées.

Typée depuis #2618 (10/11/2026) : la route rendait un dict que le contrat annonçait
`{}`, et l'app iOS le relisait « en miroir ». Ces schémas décrivent ce que
`utils/etat_taches` et `utils/sante_taches` servent déjà — rien n'est ajouté.
`portee` manque à une tâche jamais exécutée : elle sort `null`, le site ne la lit pas.

🔒 `test_reponses_typees_parametrage.py` compare la réponse à la lecture.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SanteNoeud(BaseModel):
    noeud: str
    statut: str
    portee: str
    derniere: datetime
    retard_heures: float


class SanteTache(BaseModel):
    tache: str
    noeud: Optional[str] = None
    noeuds: list[SanteNoeud]
    noeud_enregistre: bool
    portee: Optional[str] = None
    statut: str
    derniere: Optional[datetime] = None
    retard_heures: Optional[float] = None
    periodicite_heures: int
    noeud_en_retard: Optional[str] = None
    statut_en_retard: Optional[str] = None


class AnomalieRecente(BaseModel):
    tache: str
    noeud: Optional[str] = None
    cree_le: datetime
    erreur: Optional[str] = None


class SanteMaintenance(BaseModel):
    taches: list[SanteTache]
    anomalies_recentes: list[AnomalieRecente]
    anomalies_fenetre_jours: int
    genere_le: datetime
