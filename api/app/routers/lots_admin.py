"""Admin › Copropriété › Lots — constats, re-dérivation, périmètres posés à la main (#2216).

Inclus par `routers/lots.py`, même préfixe `/lots/admin/…`, même dépendance que
l'atelier d'import (`require_cs_or_admin`). La liste des lots elle-même est
`GET /lots/admin/tous`, qui rend déjà leur désignation : ce routeur n'en rend pas
une seconde.

🔴 Pas de création de lot ici : un lot naît d'un acte, il entre par l'import.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.copropriete import Lot
from app.models.core import Utilisateur
from app.models.perimetre import LotPerimetre, Perimetre, RelationLotPerimetre
from app.utils.constats import Constat
from app.utils.constats_lots import constater, relever
from app.utils.perimetres.lots import rederiver
from app.utils.recuperer import ou_404, present_ou_404

router = APIRouter()


class Rederivation(BaseModel):
    modifies: int


class PerimetreManuel(BaseModel):
    perimetre_id: int
    relation: Literal["situe_dans", "desservi_par"]


@router.get("/admin/constats", response_model=list[Constat])
def constats_des_lots(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    return constater(relever(session))


@router.post("/admin/rederiver", response_model=Rederivation)
def rederiver_les_lots(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Recalcule les périmètres DÉRIVÉS de tous les lots ; les lignes manuelles restent."""
    modifies = rederiver(session, session.exec(select(Lot)).all())
    session.commit()
    return Rederivation(modifies=modifies)


@router.post("/admin/{lot_id}/perimetres", status_code=201)
def poser_un_perimetre(
    lot_id: int,
    body: PerimetreManuel,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Un périmètre posé à la main (`derive = faux`) : une re-dérivation le garde."""
    ou_404(session, Lot, lot_id, "Lot")
    ou_404(session, Perimetre, body.perimetre_id, "Périmètre")
    relation = RelationLotPerimetre(body.relation)
    existante = session.exec(
        select(LotPerimetre).where(
            LotPerimetre.lot_id == lot_id,
            LotPerimetre.perimetre_id == body.perimetre_id,
            LotPerimetre.relation == relation,
        )
    ).first()
    if existante is None:
        session.add(
            LotPerimetre(
                lot_id=lot_id, perimetre_id=body.perimetre_id, relation=relation, derive=False
            )
        )
    else:
        existante.derive = False
        session.add(existante)
    session.commit()
    from app.utils import mes_batiments

    mes_batiments.invalider_cache()
    return {"ok": True}


@router.delete("/admin/{lot_id}/perimetres/{perimetre_id}/{relation}", status_code=204)
def retirer_un_perimetre(
    lot_id: int,
    perimetre_id: int,
    relation: Literal["situe_dans", "desservi_par"],
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Retire une ligne posée À LA MAIN — une ligne dérivée revient à la re-dérivation."""
    ligne = session.exec(
        select(LotPerimetre).where(
            LotPerimetre.lot_id == lot_id,
            LotPerimetre.perimetre_id == perimetre_id,
            LotPerimetre.relation == RelationLotPerimetre(relation),
        )
    ).first()
    ligne = present_ou_404(ligne, "Ce périmètre n'est pas posé sur ce lot")
    if ligne.derive:
        raise HTTPException(409, "Un périmètre dérivé se recalcule : il ne se retire pas à la main")
    session.delete(ligne)
    session.commit()
    from app.utils import mes_batiments

    mes_batiments.invalider_cache()
