"""Ce qu'un lot dit de sa désignation, lu pour une LISTE de lots (#2212).

La circulation, les périmètres et les tantièmes d'un lot vivent dans trois tables
(`lot`, `lot_perimetre`, `quote_part_lot` + `cle_de_charges`). Une liste de lots ne
les lit pas lot par lot (#1838) : deux requêtes groupées pour toute la liste, et
l'arbre des périmètres, déjà en cache, pour les libellés.
"""

from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel
from sqlmodel import Session, select

from app.models.charges import CleDeCharges, QuotePartLot
from app.models.perimetre import LotPerimetre
from app.utils.designation_lot import nature_du_lot
from app.utils.lots_explication import phrase
from app.utils.perimetres import arbre, perimetre_label_un
from app.utils.valeurs import valeur


class PerimetreDuLot(BaseModel):
    code: str
    libelle: str
    #: `situe_dans` ou `desservi_par`.
    relation: str
    #: Posé par la dérivation (vrai) ou à la main dans l'administration (faux).
    derive: bool = True


class QuotePart(BaseModel):
    cle: str
    libelle: str
    numerateur: int
    denominateur: int


class Designation(BaseModel):
    """Les champs calculés d'une lecture de lot — `LotRead` les reçoit tels quels."""

    circulation: PerimetreDuLot | None = None
    perimetres: list[PerimetreDuLot] = []
    #: `None` quand le lecteur n'a pas à les voir — jamais une liste vide trompeuse.
    quotes_parts: list[QuotePart] | None = None
    #: La phrase qui explique ce que le lot emporte (`utils/lots_explication`).
    explication: str | None = None


def designations(session: Session, lots: Iterable, avec_tantiemes) -> dict[int, Designation]:
    """La désignation de chaque lot, par identifiant.

    `avec_tantiemes(lot) -> bool` dit, lot par lot, si le lecteur en voit les
    tantièmes : la règle vit dans `auth/appartenance.lit_les_tantiemes`, l'appelant
    la compose avec ce qu'il sait du lien.
    """
    lots = list(lots)
    ids = [lot.id for lot in lots]
    if not ids:
        return {}
    noeuds = arbre()
    par_id = {n.id: n for n in noeuds.values() if n.id is not None}

    def _perimetre(perimetre_id, relation, derive=True) -> PerimetreDuLot | None:
        noeud = par_id.get(perimetre_id)
        if noeud is None:
            return None
        return PerimetreDuLot(
            code=noeud.code,
            libelle=perimetre_label_un(noeud.code),
            relation=relation,
            derive=derive,
        )

    perimetres: dict[int, list[PerimetreDuLot]] = {}
    for ligne in session.exec(
        select(LotPerimetre)
        .where(LotPerimetre.lot_id.in_(ids))  # type: ignore[union-attr]
        .order_by(LotPerimetre.relation, LotPerimetre.perimetre_id)
    ).all():
        lu = _perimetre(ligne.perimetre_id, str(valeur(ligne.relation)), ligne.derive)
        if lu is not None:
            perimetres.setdefault(ligne.lot_id, []).append(lu)

    quotes: dict[int, list[QuotePart]] = {}
    for part, cle in session.exec(
        select(QuotePartLot, CleDeCharges)
        .join(CleDeCharges, CleDeCharges.id == QuotePartLot.cle_id)
        .where(QuotePartLot.lot_id.in_(ids))  # type: ignore[union-attr]
        .order_by(CleDeCharges.ordre, CleDeCharges.id)
    ).all():
        quotes.setdefault(part.lot_id, []).append(
            QuotePart(
                cle=cle.code,
                libelle=cle.libelle,
                numerateur=part.numerateur,
                denominateur=cle.denominateur,
            )
        )

    #  La phrase ne cite que la CIRCULATION et les caves : le stationnement concerne
    #  tout le monde, le nommer n'expliquerait rien.
    stationnement = {n.code for n in noeuds.values() if n.desserte == "stationnement"}

    def _designation(lot) -> Designation:
        lus = perimetres.get(lot.id, [])
        parts = quotes.get(lot.id, []) if avec_tantiemes(lot) else None
        return Designation(
            circulation=_perimetre(lot.circulation_perimetre_id, "circulation"),
            perimetres=lus,
            quotes_parts=parts,
            explication=phrase(
                nature_du_lot(lot),
                lot.etage,
                [
                    p.libelle
                    for p in lus
                    if p.relation == "desservi_par" and p.code not in stationnement
                ],
                [(q.libelle, q.numerateur, q.denominateur) for q in parts] if parts else None,
            ),
        )

    return {lot.id: _designation(lot) for lot in lots}
