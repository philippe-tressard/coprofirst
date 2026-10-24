"""Une ANNEXE — cave ou place — n'ouvre pas son bâtiment (#2212, spec `lots-et-perimetres.md` §5–6).

L'import de l'état descriptif situe désormais une cave dans SON bâtiment, et non plus
dans celui de son propriétaire. Sans cette règle, il ouvrirait ce bâtiment en entier —
hall, toit, actualités confidentielles, PV de bâtiment — à qui n'y range que sa
voiture. Mesuré en production le 24/10/2026 : aucun compte ne tenait un bâtiment de
ses seules annexes, la règle ne retire donc rien à personne.

Lots fictifs.
"""

from __future__ import annotations

from sqlmodel import Session

from app.database import engine
from app.models.copropriete import Lot, NatureLot, TypeLot
from app.models.core import StatutUtilisateur, UserLot
from app.utils import mes_batiments
from app.utils.designation_lot import est_annexe, nature_du_lot
from tests.aides_base import compte


def test_la_nature_se_deduit_du_type_tant_que_le_reglement_ne_l_a_pas_dite():
    assert nature_du_lot(Lot(numero="1", type=TypeLot.appartement)) == NatureLot.logement
    assert nature_du_lot(Lot(numero="1", type=TypeLot.appartement, nature=NatureLot.commerce)) == (
        NatureLot.commerce
    )
    assert est_annexe(Lot(numero="1", type=TypeLot.cave))
    assert not est_annexe(Lot(numero="1", type=TypeLot.appartement))


def test_une_cave_n_apporte_pas_son_batiment_un_logement_si(batiments):
    b1, b2 = batiments[0], batiments[1]
    with Session(engine) as session:
        titulaire = compte(session, statut=StatutUtilisateur.copropriétaire_bailleur)
        cave = Lot(numero="961", batiment_id=b2, type=TypeLot.cave)
        logement = Lot(numero="962", batiment_id=b1, type=TypeLot.appartement)
        session.add_all([cave, logement])
        session.flush()
        session.add(UserLot(user_id=titulaire.id, lot_id=cave.id))
        session.add(UserLot(user_id=titulaire.id, lot_id=logement.id))
        session.commit()
        session.refresh(titulaire)
        mes_batiments.invalider_cache()
        assert mes_batiments.batiments_de_l_utilisateur(titulaire) == frozenset({b1})
    mes_batiments.invalider_cache()
