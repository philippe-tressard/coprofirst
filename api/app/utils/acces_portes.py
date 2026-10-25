"""Les portes qu'un badge DEVRAIT ouvrir, dérivées des lots de son porteur (#2217).

## La règle (spec `specs/architecture/lots-et-perimetres.md` §7)

- l'occupant d'un logement ouvre son bâtiment ;
- le détenteur d'une place ou d'une cave ouvre le bâtiment de la CIRCULATION qui la
  dessert (`Lot.circulation_perimetre_id`) — pas celui de son logement ;
- une place en accès direct (sans circulation) n'ouvre aucun hall ;
- un locataire reçoit les portes des lots de SES liens actifs, jamais celles des
  autres lots du bailleur (`rattachements_actifs` ne rend que les siens).

## 🔴 Proposer, jamais poser (arbitrage du 25/10/2026, rang 1 : sécurité)

Un badge ouvre des portes PHYSIQUES. Cette dérivation ne sert qu'à PROPOSER, avec
la raison de chaque porte, dans le formulaire du conseil syndical ; c'est le
conseil qui reprend la proposition, la retranche, et enregistre. Les chemins
silencieux — import, acceptation d'une commande, déclaration — gardent la règle de
#953 (`utils/acces_perimetre`) à l'identique : deux bâtiments y rendent « on ne
sait pas ». Les cas où la proposition ouvre PLUS que #953 sont énumérés et nommés
dans `tests/test_acces_portes.py`.

Le constat (`utils/acces_constats`) compare ce que le badge ouvre à ce que ses lots
justifient : il signale, il ne corrige rien.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from sqlmodel import Session

from app.models.copropriete import Lot, NatureLot
from app.models.core import Utilisateur
from app.models.perimetre import Perimetre
from app.utils.acces_perimetre import code_batiment
from app.utils.designation_lot import nature_du_lot
from app.utils.lots_rattaches import rattachements_actifs


@dataclass(frozen=True)
class Porte:
    """Un périmètre que le badge ouvrirait, et pourquoi — la raison se lit à l'écran."""

    code: str
    raison: str


#: Ce que le lot apporte, dit à son détenteur.
_RAISON_SITUE: dict[Optional[NatureLot], str] = {
    NatureLot.logement: "votre logement",
    NatureLot.commerce: "votre commerce",
    NatureLot.divers: "votre lot",
    None: "votre lot",
}
_RAISON_DESSERT: dict[NatureLot, str] = {
    NatureLot.cave: "dessert votre cave",
    NatureLot.parking: "dessert votre place",
}


def portes_du_lot(
    nature: Optional[NatureLot],
    batiment_code: Optional[str],
    circulation_code: Optional[str],
) -> list[Porte]:
    """PURE. Les portes d'UN lot, selon sa nature.

    Une annexe (cave, place) ouvre sa circulation, et rien d'autre : le bâtiment
    où l'acte la situe n'est pas son chemin. Sans circulation, accès direct.
    """
    if nature in _RAISON_DESSERT:
        return [Porte(circulation_code, _RAISON_DESSERT[nature])] if circulation_code else []
    return [Porte(batiment_code, _RAISON_SITUE.get(nature, "votre lot"))] if batiment_code else []


def fusionner(portes: Iterable[Porte]) -> list[Porte]:
    """PURE. Une porte une fois, ses raisons réunies, dans l'ordre d'arrivée."""
    raisons: dict[str, list[str]] = {}
    for porte in portes:
        vues = raisons.setdefault(porte.code, [])
        if porte.raison not in vues:
            vues.append(porte.raison)
    return [Porte(code, " · ".join(r)) for code, r in raisons.items()]


def _portes_de(session: Session, lot: Lot) -> list[Porte]:
    circulation = (
        session.get(Perimetre, lot.circulation_perimetre_id)
        if lot.circulation_perimetre_id
        else None
    )
    return portes_du_lot(
        nature_du_lot(lot),
        code_batiment(lot.batiment_id) if lot.batiment_id else None,
        circulation.code if circulation else None,
    )


def lots_du_badge(session: Session, badge) -> list[Lot]:
    """Les lots qui justifient un badge : le sien, et ceux de ses porteurs (liens actifs).

    Le badge appartient au LOT (#1194) : ses porteurs se lisent par
    `porteurs_acces` — les copropriétaires du lot, et celui qui le détient. 🔴 Un
    badge remis AU LOCATAIRE ne se justifie que par les lots de celui-ci : jamais
    par les autres lots du bailleur (spec §7).
    """
    from app.utils.porteurs_acces import porteurs

    lots: dict[int, Lot] = {}
    if badge.lot_id and (lot := session.get(Lot, badge.lot_id)):
        lots[lot.id] = lot
    if badge.chez_locataire:
        ids = {badge.user_id} if badge.user_id else set()
    else:
        ids = porteurs(session, badge)
    for user_id in sorted(ids):
        if porteur := session.get(Utilisateur, user_id):
            for lot, _lien in rattachements_actifs(session, porteur):
                lots.setdefault(lot.id, lot)
    return list(lots.values())


def portes_de_badge(session: Session, badge) -> list[Porte]:
    """Ce que les lots d'un badge justifient — la PROPOSITION, et la mesure du constat."""
    return fusionner(
        porte for lot in lots_du_badge(session, badge) for porte in _portes_de(session, lot)
    )


def portes_proposees(
    session: Session, porteur_id: Optional[int], lot_id: Optional[int]
) -> list[Porte]:
    """Ce que le formulaire PROPOSE pour un badge Vigik encore à saisir — jamais ce qu'on pose."""
    from types import SimpleNamespace

    return portes_de_badge(
        session, SimpleNamespace(id=0, lot_id=lot_id, user_id=porteur_id, chez_locataire=False)
    )
