"""Le schéma de lecture d'un document de la bibliothèque.

Sorti de `app/schemas.py` (#1566) : seul `routers/documents.py` le rend.
"""

import json
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class DocumentRead(BaseModel):
    id: int
    titre: str
    #  Section 6 du cadre, ajoutée le 08/09/2026 (#852). Défaut à vide plutôt
    #  qu'`Optional` : une description absente et une description vide sont la
    #  même chose pour le lecteur, et l'écran n'a alors rien à distinguer.
    description: str = ""
    fichier_nom: str
    taille_octets: Optional[int] = None
    mime_type: str
    categorie_id: Optional[int] = None
    contrat_id: Optional[int] = None
    #  Rattachements des pièces jointes (#390) : le front en a besoin pour savoir
    #  à quel porteur une ligne appartient sans refaire la requête.
    ticket_id: Optional[int] = None
    evenement_id: Optional[int] = None
    #  La fiche de Ma résidence qui porte cette annexe (migration 0276) : l'écran
    #  range ainsi sous chaque fiche les annexes de toute une rubrique.
    document_parent_id: Optional[int] = None
    diagnostic_rapport_id: Optional[int] = None
    regle_residence_id: Optional[int] = None
    perimetre: str
    batiment_id: Optional[int] = None
    publie_le: datetime
    annee: Optional[int] = None
    date_ag: Optional[date] = None
    date_document: Optional[date] = None
    batiments_ids_json: Optional[str] = None
    #  De quoi parle le document, en codes de périmètre (#470). Descriptif, pas
    #  un droit — voir `models/documents.py`.
    #
    #  🔴 Sort en LISTE, jamais en JSON brut — même convention que
    #  `PublicationRead` et `AnnonceRead`. C'est ce que `PerimetrePicker` et
    #  `perimetreLabel` lisent côté front : leur faire parser une chaîne les
    #  obligerait à connaître le format de stockage, et la troisième copie de
    #  `JSON.parse` serait celle qui oublierait le `try`.
    perimetre_cible: Optional[list[str]] = None

    @field_validator("perimetre_cible", mode="before")
    @classmethod
    def _perimetre_en_liste(cls, v):
        """La colonne est du texte ; l'API rend une liste.

        ⚠️ Une valeur illisible rend `None`, pas une exception : un document
        dont le ciblage est abîmé doit rester LISIBLE — il n'a alors simplement
        plus de badge de périmètre. Lever ici rendrait toute la bibliothèque
        inaccessible pour une ligne mal formée.
        """
        if v is None or isinstance(v, list):
            return v
        try:
            valeur = json.loads(v)
        except (ValueError, TypeError):
            return None
        return valeur if isinstance(valeur, list) else None

    class Config:
        from_attributes = True
