"""Admin › Copropriété › Lots — constats, re-dérivation, périmètres posés à la main (#2216).

Inclus par `routers/lots.py`, même préfixe `/lots/admin/…`, même dépendance que
l'atelier d'import (`require_cs_or_admin`). La liste des lots elle-même est
`GET /lots/admin/tous`, qui rend déjà leur désignation : ce routeur n'en rend pas
une seconde.

🔴 Pas de création de lot ici : un lot naît d'un acte, il entre par l'import.
Ni de clé de charges : elle naît de l'état descriptif. Le conseil n'en règle que ce
que l'acte ne dit pas — appelée ou non par le syndic, son libellé sur l'appel de
fonds (#2252).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.charges import CleDeCharges
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


class CleRead(BaseModel):
    id: int
    code: str
    libelle: str
    denominateur: int
    description: str | None = None
    appelee: bool
    libelle_syndic: str | None = None

    class Config:
        from_attributes = True


class CleUpdate(BaseModel):
    appelee: bool | None = None
    #: Vide → aucun libellé : le rapprochement se tait plutôt que d'afficher un blanc.
    libelle_syndic: str | None = None


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


@router.get("/admin/cles", response_model=list[CleRead])
def cles_de_charges(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les clés du règlement, dans l'ordre de l'état descriptif (#2252)."""
    cles = session.exec(select(CleDeCharges).order_by(CleDeCharges.ordre, CleDeCharges.id))
    return [CleRead.model_validate(c) for c in cles.all()]


@router.patch("/admin/cles/{cle_id}", response_model=CleRead)
def regler_une_cle(
    cle_id: int,
    body: CleUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Appelée ou non par le syndic, et son libellé sur l'appel de fonds — rien d'autre :
    libellé, dénominateur et parts restent ceux de l'acte (#2252)."""
    cle = ou_404(session, CleDeCharges, cle_id, "Clé de charges")
    champs = body.model_dump(exclude_unset=True)
    if champs.get("appelee") is not None:
        cle.appelee = champs["appelee"]
    if "libelle_syndic" in champs:
        cle.libelle_syndic = (champs["libelle_syndic"] or "").strip() or None
    session.add(cle)
    session.commit()
    session.refresh(cle)
    return CleRead.model_validate(cle)
