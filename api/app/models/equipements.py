"""Les équipements de la copropriété — ce SUR QUOI l'on intervient (#2442).

## Pourquoi une table

Les dix-huit valeurs (ascenseur, chauffage collectif…, assurance, syndic,
autre) étaient l'énumération `TypeEquipement`, recopiée à l'écran avec ses
émojis et ses marques de gouttière. En ajouter une demandait du code, une
migration et une livraison ; une autre copropriété — une piscine, un portail,
une borne de recharge — ne pouvait pas compléter la liste. Elle s'administre
désormais dans Admin › Copropriété › Équipements, comme les périmètres.

## Le code est la clé, et il ne change plus

`ContratEntretien.type_equipement`, `Ticket.equipement` et
`Prestataire.specialite` stockent le CODE, en texte, pas une clé étrangère :
c'est la forme qu'ils avaient sous l'énumération, et un équipement retiré ou
supprimé doit laisser lisible ce qui le citait. Le code est donc **immuable**
après création, comme celui d'un périmètre.

Trois codes sont connus du code lui-même (`utils/equipements.CODES_SYSTEME`) :
`assurance`, `syndic` et `autre`. Leur libellé et leur icône s'administrent ;
ils ne se retirent ni ne se suppriment.

## Équipement et périmètre : deux notions

Le périmètre dit OÙ (et décide qui lit) ; l'équipement dit QUOI — le corps de
métier, la nature d'un contrat. Une fuite de plomberie au bâtiment 3 a pour
lieu le bâtiment, pas un « espace plomberie » ; un contrat d'assurance couvre
toute la copropriété. Là où les deux se recouvrent (l'ascenseur du bâtiment A),
`EquipementPerimetre` les relie : l'écran d'une affaire propose l'un depuis
l'autre, sans rien imposer.
"""

from typing import Optional

from pydantic import NaiveDatetime
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.utils import horloge


class Equipement(SQLModel, table=True):
    __tablename__ = "equipement"
    id: Optional[int] = Field(default=None, primary_key=True)
    #: Ce que stockent les contrats, les affaires et les prestataires.
    #: **Immuable après création** : le changer orphelinerait ce qui le cite.
    code: str = Field(unique=True, index=True)
    libelle: str
    #: Le mot de la gouttière d'une carte (« ASC. »), en petites capitales.
    abreviation: Optional[str] = None
    #: Un nom du catalogue au trait (`icones-svg.json`), jamais un émoji.
    icone: str = Field(default="wrench")
    description: Optional[str] = None
    ordre: int = Field(default=0)
    #: Proposé à la saisie. Décoché, l'équipement quitte les sélecteurs et
    #: reste affiché sur ce qui le cite déjà (`test_archivage_colonnes_booleennes`).
    actif: bool = Field(default=True)
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    modifie_le: Optional[NaiveDatetime] = None


class EquipementPerimetre(SQLModel, table=True):
    """Les périmètres où se trouve un équipement — saisis dans l'administration.

    Facultatif, et sans effet sur qui lit quoi : il ne sert qu'à PROPOSER, dans
    une affaire, le périmètre d'un équipement choisi ou l'équipement d'un
    périmètre choisi. Supprimer un périmètre retire ses liens, jamais
    l'équipement (`routers/patrimoine.py`).
    """

    __tablename__ = "equipement_perimetre"
    __table_args__ = (
        UniqueConstraint("equipement_id", "perimetre_id", name="uq_equipement_perimetre"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    equipement_id: int = Field(foreign_key="equipement.id", index=True)
    perimetre_id: int = Field(foreign_key="perimetre.id")
