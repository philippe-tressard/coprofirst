"""Les schémas des gestes d'un résident sur ses accès : commande, déclaration, perte.

Sortis de `app/schemas.py` (#1566) : seul `resident.py` s'en sert.

## Les réponses typées (#2507, 04/11/2026)

L'app iOS génère son client depuis le contrat : une route sans `response_model`
y est annoncée `{}`, et l'app relisait la réponse à la main. `BadgeDeclare` et
`AccesSignalePerdu` disent ce que les routes rendaient déjà.

🔴 Un refus de la déclaration (code vide, type inconnu) était un 422 au `detail`
TEXTE, quand le contrat annonce un `HTTPValidationError` — une liste. Un client
typé ne pouvait pas le décoder. La règle vit désormais dans `DeclarerBadgeBody`,
dont les validateurs rendent la forme annoncée ; le site lit les deux
(`detail-erreur.ts`), avec le même message.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.core import StatutAcces
from app.utils.types_acces import TYPES_ACCES


class CommandeAccesCreate(BaseModel):
    lot_id: int
    type: str  # vigik | telecommande
    quantite: int = 1
    motif: Optional[str] = None


class CommandeAccesRead(BaseModel):
    id: int
    user_id: int
    lot_id: int
    type: str
    quantite: int
    motif: Optional[str] = None
    statut: str
    cree_le: datetime

    class Config:
        from_attributes = True


class DeclarerBadgeBody(BaseModel):
    #: La clé d'un type d'accès (`TYPES_ACCES` : `vigik`, `telecommande`).
    type: str
    code: str

    @field_validator("code")
    @classmethod
    def _code_present(cls, v: str) -> str:
        code = v.strip()
        if not code:
            raise ValueError("Code vide")
        return code

    @field_validator("type")
    @classmethod
    def _type_connu(cls, v: str) -> str:
        #  Cherché dans `TYPES_ACCES`, jamais comparé à des chaînes écrites ici : une
        #  seconde liste des types connus diverge au troisième accès.
        if v not in TYPES_ACCES:
            raise ValueError("Type invalide : " + " ou ".join(TYPES_ACCES))
        return v


class BadgeDeclare(BaseModel):
    """Ce que rend la déclaration d'un badge par son porteur."""

    #: La clé du type (`vigik`, `telecommande`).
    type: str
    id: int
    code: str
    #: Une ligne du fichier du syndic a été rattachée au passage.
    import_resolu: bool


class AccesSignalePerdu(BaseModel):
    """Ce que rend le signalement d'une perte : le statut désormais porté."""

    statut: StatutAcces
