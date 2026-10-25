"""Ce qu'un lot dit de sa désignation, lu pour une LISTE de lots (#2212).

La circulation, les périmètres et les tantièmes d'un lot vivent dans trois tables
(`lot`, `lot_perimetre`, `quote_part_lot` + `cle_de_charges`). Une liste de lots ne
les lit pas lot par lot (#1838) : deux requêtes groupées pour toute la liste, et
l'arbre des périmètres, déjà en cache, pour les libellés.
"""

from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.models.charges import CleDeCharges, QuotePartLot
from app.models.copropriete import NatureLot
from app.models.perimetre import LotPerimetre
from app.utils.alertes_lot import alertes_du_lot, note_de_cle
from app.utils.constats import Constat
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
    #: Ce que la clé finance — « Bât. 3 › Ascenseur » —, quand le règlement le rattache à un nœud.
    perimetre: str | None = None
    #: Combien de lots contribuent à cette clé (un compte, aucun nom).
    nb_lots: int = 0
    #: La somme des parts de TOUS les lots : le contrôle contre le dénominateur déclaré.
    somme: int = 0
    #: Ce que la clé finance, selon le règlement (« l'escalier des deux sous-sols », #2251).
    description: str | None = None
    #: Ce qu'il faut savoir de la clé quand ses parts ne font pas le dénominateur —
    #: une phrase du serveur (`alertes_lot.note_de_cle`), dite une fois sous la clé.
    note: str | None = None


class Designation(BaseModel):
    """Les champs calculés d'une lecture de lot — `LotRead` les reçoit tels quels."""

    circulation: PerimetreDuLot | None = None
    perimetres: list[PerimetreDuLot] = []
    #: `None` quand le lecteur n'a pas à les voir — jamais une liste vide trompeuse.
    quotes_parts: list[QuotePart] | None = None
    #: La phrase qui explique ce que le lot emporte (`utils/lots_explication`).
    explication: str | None = None
    #: Ce que le propriétaire doit savoir de son lot (`utils/alertes_lot`) : désignation
    #: incomplète, clé qui ne tombe pas juste. Jamais bloquant.
    alertes: list[Constat] = []


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

    #  Les sommes sont celles de TOUS les lots, pas seulement de la liste lue : une clé
    #  « ne tombe pas juste » à l'échelle de la copropriété.
    totaux = {
        cle_id: (nb, somme or 0)
        for cle_id, nb, somme in session.exec(
            select(
                QuotePartLot.cle_id,
                func.count(QuotePartLot.id),  # type: ignore[arg-type]
                func.sum(QuotePartLot.numerateur),
            ).group_by(QuotePartLot.cle_id)
        ).all()
    }
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
                perimetre=perimetre_label_un(par_id[cle.perimetre_id].code)
                if cle.perimetre_id in par_id
                else None,
                nb_lots=totaux.get(cle.id, (0, 0))[0],
                somme=totaux.get(cle.id, (0, 0))[1],
                description=cle.description,
                note=note_de_cle(cle.denominateur, totaux.get(cle.id, (0, 0))[1]),
            )
        )

    #  La phrase ne cite que la CIRCULATION et les caves : le stationnement concerne
    #  tout le monde, le nommer n'expliquerait rien.
    stationnement = {n.code for n in noeuds.values() if n.desserte == "stationnement"}

    def _designation(lot) -> Designation:
        lus = perimetres.get(lot.id, [])
        voit = avec_tantiemes(lot)
        declaree = valeur(getattr(lot, "nature", None))
        parts = quotes.get(lot.id, []) if voit else None
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
            alertes=alertes_du_lot(
                NatureLot(declaree) if declaree else None,
                nature_du_lot(lot),
                lot.etage,
                getattr(lot, "numero_usage", None),
                any(p.relation == "desservi_par" for p in lus)
                or lot.circulation_perimetre_id is not None,
                voit,
                [(q.libelle, q.numerateur, q.denominateur) for q in (parts or [])],
            ),
        )

    return {lot.id: _designation(lot) for lot in lots}
