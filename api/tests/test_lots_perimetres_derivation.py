"""Les périmètres d'un lot se DÉRIVENT de sa désignation (#2212, spec `lots-et-perimetres.md` §4).

Lots et arbre fictifs : le dépôt est public, aucune donnée d'une copropriété réelle
n'y entre. Les cas sont ceux que l'issue énumère — une place desservie par une autre
circulation que celle de son détenteur, une cave desservie par une circulation
différente du logement de son propriétaire, une place à accès direct, un logement,
un bâtiment sans circulation.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.database import engine
from app.models.copropriete import Lot, NatureLot, TypeLot
from app.models.perimetre import LotPerimetre, Perimetre, RelationLotPerimetre
from app.utils.perimetres import perimetre_du_batiment
from app.utils.perimetres.arbre import Noeud
from app.utils.perimetres.lots import deriver, rederiver

S = RelationLotPerimetre.situe_dans
D = RelationLotPerimetre.desservi_par


def _n(code, parent=None, batiment=None, desserte=None, globale=False) -> Noeud:
    return Noeud(
        code=code,
        libelle=code,
        libelle_court=code,
        description="",
        icone=None,
        parent=parent,
        batiment_id=batiment,
        portee_globale=globale,
        selectionnable=True,
        hors_copropriete=False,
        actif=True,
        ordre=0,
        desserte=desserte,
    )


#: Deux bâtiments, l'un avec ascenseur, escalier et caves, l'autre avec un escalier
#: seul ; un nœud de stationnement global.
ARBRE = {
    "bat:7": _n("bat:7", batiment=7),
    "bat:7/ascenseur": _n("bat:7/ascenseur", "bat:7", desserte="circulation"),
    "bat:7/escaliers": _n("bat:7/escaliers", "bat:7", desserte="circulation"),
    "bat:7/caves": _n("bat:7/caves", "bat:7", desserte="caves"),
    "bat:7/toit": _n("bat:7/toit", "bat:7"),
    "bat:8": _n("bat:8", batiment=8),
    "bat:8/escaliers": _n("bat:8/escaliers", "bat:8", desserte="circulation"),
    "bat:8/hall": _n("bat:8/hall", "bat:8"),
    "stationnement": _n("stationnement", globale=True, desserte="stationnement"),
}


def test_un_logement_est_situe_dans_son_batiment_et_desservi_par_lui():
    assert deriver(NatureLot.logement, "bat:8", None, ARBRE) == {
        ("bat:8", S),
        ("bat:8/escaliers", D),
    }


def test_une_place_desservie_par_un_autre_batiment_en_ouvre_la_circulation_seule():
    """Le résident du bâtiment 8 qui gare au pied du 7 : ascenseur et escalier du 7,
    jamais son toit — ni le bâtiment 7 lui-même (arbitrage du 24/10/2026)."""
    paires = deriver(NatureLot.parking, None, "bat:7", ARBRE)
    assert paires == {
        ("stationnement", S),
        ("bat:7/ascenseur", D),
        ("bat:7/escaliers", D),
        ("stationnement", D),
    }
    assert ("bat:7", D) not in paires and ("bat:7/toit", D) not in paires


def test_une_cave_desservie_par_un_autre_batiment_que_le_logement_en_ouvre_les_caves():
    paires = deriver(NatureLot.cave, "bat:7", "bat:7", ARBRE)
    assert ("bat:7/caves", D) in paires
    assert ("bat:7", S) in paires
    assert not any(code.startswith("bat:8") for code, _ in paires)


def test_une_place_a_acces_direct_n_a_que_le_stationnement():
    assert deriver(NatureLot.parking, None, None, ARBRE) == {
        ("stationnement", S),
        ("stationnement", D),
    }


def test_une_cave_sans_circulation_n_a_pas_de_desserte():
    """Accès direct : rien n'est inventé, pas même le bâtiment où elle est située."""
    assert deriver(NatureLot.cave, "bat:8", None, ARBRE) == {("bat:8", S)}


def test_un_arbre_vide_ne_derive_rien():
    assert deriver(NatureLot.logement, None, None, {}) == set()


def test_rederiver_ecrit_et_garde_les_lignes_posees_a_la_main(batiments):
    """La dérivation écrit en base ; une ligne manuelle survit à la re-dérivation."""
    with Session(engine) as session:
        b1, b2 = batiments[0], batiments[1]
        circulation = perimetre_du_batiment(b2)
        place = Lot(numero="901", type=TypeLot.parking, circulation_perimetre_id=circulation.id)
        logement = Lot(numero="902", batiment_id=b1, type=TypeLot.appartement)
        session.add_all([place, logement])
        session.flush()
        toit = session.exec(select(Perimetre).where(Perimetre.code == f"bat:{b2}/toit")).one()
        session.add(LotPerimetre(lot_id=place.id, perimetre_id=toit.id, relation=D, derive=False))
        session.flush()

        rederiver(session, [place, logement])
        rederiver(session, [place, logement])  # idempotente
        session.flush()

        codes = {
            (p.code, lp.relation, lp.derive)
            for lp, p in session.exec(
                select(LotPerimetre, Perimetre)
                .join(Perimetre, Perimetre.id == LotPerimetre.perimetre_id)
                .where(LotPerimetre.lot_id == place.id)
            ).all()
        }
        assert (f"bat:{b2}/ascenseur", D, True) in codes
        assert (f"bat:{b2}/escaliers", D, True) in codes
        assert (f"bat:{b2}/toit", D, False) in codes, "la ligne manuelle a disparu"
        assert not any(c == f"bat:{b2}" for c, _, _ in codes)
        session.rollback()
