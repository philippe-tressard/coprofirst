"""Le tableau de mes charges selon le règlement — prêt à afficher (#2507).

Un copropriétaire de plusieurs lots (un logement, une cave, deux places) contribue à
une clé par la SOMME de ses parts. Le tableau croisé de « Mes lots » (maquette A,
arbitrée le 25/10/2026, #2251) le montre d'un coup : une ligne par clé, une colonne
par lot, puis le total.

## Pourquoi ici (04/11/2026)

Le pivot se faisait dans le front (`tableauDesCharges`, `charges-lots.ts`) à partir
des `quotes_parts` de chaque lot. L'app iOS ne recopie aucune règle du site : elle
renvoyait au site. `GET /lots/mes-charges` sert le tableau rangé et additionné, et
le site le lit (`standards/09` §8, règle 1).

Le serveur reste la source de chaque part, de ce que finance la clé et de sa note
(`utils/lecture_lots`) ; ici on ne fait que les RANGER et les ADDITIONNER.
"""

from __future__ import annotations

from typing import Iterable, Optional

from pydantic import BaseModel

from app.utils.lecture import lire_objet
from app.utils.libelles_lot import nom_du_lot


class ColonneDeLot(BaseModel):
    """Une colonne du tableau : un de mes lots qui contribue à au moins une clé."""

    lot_id: int
    #: « Logement 15 », « Cave 417 », « Place 450 » (`libelles_lot.nom_du_lot`).
    nom: str


class PartDuLot(BaseModel):
    lot_id: int
    numerateur: int


class LigneDeCle(BaseModel):
    """Une clé de charges : sa définition, et ma part lot par lot."""

    cle: str
    libelle: str
    #: Ce que la clé finance, selon le règlement — `None` si l'acte ne le dit pas.
    description: Optional[str] = None
    #: Ce qu'il faut savoir de la clé (ses parts ne font pas le dénominateur).
    note: Optional[str] = None
    #: Faux : prévue au règlement, non appelée par le syndic en ce moment (#2252).
    appelee: bool = True
    #: Son libellé sur l'appel de fonds — le rapprochement ligne à ligne (#2252).
    libelle_syndic: Optional[str] = None
    nb_lots: int = 0
    denominateur: int
    #: La part de chacun de mes lots qui y contribue, dans l'ordre des colonnes.
    parts: list[PartDuLot] = []
    #: La somme de mes parts.
    total: int = 0


class TableauCharges(BaseModel):
    colonnes: list[ColonneDeLot] = []
    #: Les clés que le syndic appelle : les lignes de l'appel de fonds.
    lignes: list[LigneDeCle] = []
    #: Prévues au règlement, non appelées en ce moment : repliées, jamais cachées —
    #: le jour où le syndic en appelle une, la question inverse se poserait (#2252).
    non_appelees: list[LigneDeCle] = []


def tableau_des_charges(lots: Iterable) -> TableauCharges:
    """Le tableau croisé de mes lots, dans l'ordre des clés que la lecture rend.

    `lots` : des lectures de lot (`LotRead`) — `id`, `numero`, `nature`, `type`,
    `quotes_parts`. Un lot sans part lisible (un locataire reçoit `None`) n'a pas de
    colonne. PURE.
    """
    avec_parts = [lot for lot in lots if lot.quotes_parts]
    lignes: dict[str, LigneDeCle] = {}
    for lot in avec_parts:
        for part in lot.quotes_parts:
            ligne = lignes.get(part.cle)
            if ligne is None:
                #  La clé se LIT sur la part (sa définition est la même pour tous
                #  les lots) ; seules ma part et la somme se calculent ici.
                ligne = lire_objet(LigneDeCle, part, parts=[], total=0)
                lignes[part.cle] = ligne
            ligne.parts.append(PartDuLot(lot_id=lot.id, numerateur=part.numerateur))
            ligne.total += part.numerateur
    toutes = list(lignes.values())
    return TableauCharges(
        colonnes=[ColonneDeLot(lot_id=lot.id, nom=nom_du_lot(lot)) for lot in avec_parts],
        lignes=[x for x in toutes if x.appelee],
        non_appelees=[x for x in toutes if not x.appelee],
    )


__all__ = ["ColonneDeLot", "LigneDeCle", "PartDuLot", "TableauCharges", "tableau_des_charges"]
