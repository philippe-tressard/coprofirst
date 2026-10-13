"""Les badges Vigik et les télécommandes, rattachés aux lots (spec §6.2).

Un badge appartient au LOT ; ses porteurs se lisent par le lot. Le périmètre suit
la règle de l'écran d'administration (`utils/acces_gestes._acces_json`) : le
bâtiment du lot pour un badge, le réglage des accès fixes pour une télécommande.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.demo.patrimoine import Patrimoine
from app.models.acces import Telecommande, Vigik
from app.models.core import UserLot
from app.utils.acces_gestes import _acces_json
from app.utils.types_acces import TELECOMMANDE, VIGIK


def poser(session: Session, pat: Patrimoine) -> None:
    occupes = set(session.exec(select(UserLot.lot_id).where(UserLot.actif == True)).all())  # noqa: E712
    rang = 0
    for lot in pat.appartements.values():
        if lot.id not in occupes:
            continue
        for _ in range(2):
            rang += 1
            session.add(
                Vigik(
                    code=f"VK-{rang:04d}",
                    lot_id=lot.id,
                    perimetre_cible=_acces_json(session, VIGIK, None, lot.id, None),
                )
            )
    for numero, lot in enumerate(pat.parkings, start=1):
        if lot.id not in occupes:
            continue
        session.add(
            Telecommande(
                code=f"TC-{numero:04d}",
                lot_id=lot.id,
                perimetre_cible=_acces_json(session, TELECOMMANDE, None, lot.id, None),
            )
        )
