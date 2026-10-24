"""« Mes périmètres » : une place desservie par un autre bâtiment en ouvre la circulation (#2214).

La table des cas de l'issue, rejouée couple par couple sur l'arbre semé (fixture
`batiments`) et des lots FICTIFS. Elle vérifie l'élargissement ET sa borne dans le
même fichier : l'ascenseur oui, le hall, le toit et le bâtiment entier non.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.database import engine
from app.models.copropriete import Lot, TypeLot
from app.models.core import StatutUtilisateur, UserLot
from app.utils import mes_batiments
from app.utils.perimetres import perimetre_du_batiment
from app.utils.perimetres.lots import rederiver
from app.utils.visibility import perimetre_visible
from tests.aides_base import compte

PORTAIL = "parking/portail"


def _titulaire(session, batiment_id, *lots, restreint=False):
    """Un compte, son rattachement, ses lots — périmètres dérivés en base."""
    personne = compte(
        session,
        statut=StatutUtilisateur.copropriétaire_bailleur,
        batiment_id=batiment_id,
        restreindre_a_mes_batiments=restreint,
    )
    session.add_all(lots)
    session.flush()
    for lot in lots:
        session.add(UserLot(user_id=personne.id, lot_id=lot.id))
    rederiver(session, lots)
    session.commit()
    session.refresh(personne)
    mes_batiments.invalider_cache()
    return personne


def _place(numero, desservie_par=None):
    noeud = perimetre_du_batiment(desservie_par) if desservie_par else None
    return Lot(numero=numero, type=TypeLot.parking, circulation_perimetre_id=noeud and noeud.id)


@pytest.fixture()
def b(batiments):
    yield batiments
    mes_batiments.invalider_cache()


def test_resident_avec_une_place_desservie_par_un_autre_batiment(b):
    b1, b3 = b[0], b[2]
    with Session(engine) as session:
        u = _titulaire(session, b1, _place("971", desservie_par=b3))
        assert perimetre_visible([f"bat:{b3}/ascenseur"], u)
        assert perimetre_visible([f"bat:{b3}/escaliers"], u)
        assert not perimetre_visible([f"bat:{b3}/toit"], u)
        assert not perimetre_visible([f"bat:{b3}/hall"], u)
        #  Arbitré le 24/10/2026 : le bâtiment desservant SEUL reste à ses résidents.
        assert not perimetre_visible([f"bat:{b3}"], u)
        assert perimetre_visible([f"bat:{b1}/hall"], u), "son propre bâtiment reste visible"


def test_resident_avec_une_cave_desservie_par_un_autre_batiment(b):
    b1, b2 = b[0], b[1]
    with Session(engine) as session:
        cave = Lot(
            numero="972",
            batiment_id=b2,
            type=TypeLot.cave,
            circulation_perimetre_id=perimetre_du_batiment(b2).id,
        )
        u = _titulaire(session, b1, cave)
        assert perimetre_visible([f"bat:{b2}/caves"], u)
        assert not perimetre_visible([f"bat:{b2}/paliers"], u)


def test_exterieur_avec_une_seule_place(b):
    b3 = b[2]
    with Session(engine) as session:
        u = _titulaire(session, None, _place("973", desservie_par=b3))
        assert perimetre_visible([f"bat:{b3}/ascenseur"], u)
        assert perimetre_visible([PORTAIL], u)
        assert not perimetre_visible([f"bat:{b3}/hall"], u)
        assert not perimetre_visible([f"bat:{b3}"], u)


def test_exterieur_avec_une_place_a_acces_direct(b):
    b3 = b[2]
    with Session(engine) as session:
        u = _titulaire(session, None, _place("974"))
        assert perimetre_visible([PORTAIL], u)
        assert not perimetre_visible([f"bat:{b3}/ascenseur"], u)


def test_compte_sans_rattachement_ni_lot_ne_voit_rien_de_cible(b):
    b3 = b[2]
    with Session(engine) as session:
        u = _titulaire(session, None)
        assert not perimetre_visible([f"bat:{b3}/ascenseur"], u)


def test_bailleur_rattache_au_1_voit_le_batiment_de_son_logement(b):
    """L'arbitrage du 02/09/2026 est conservé."""
    b1, b2 = b[0], b[1]
    with Session(engine) as session:
        logement = Lot(numero="975", batiment_id=b2, type=TypeLot.appartement)
        u = _titulaire(session, b1, logement)
        assert perimetre_visible([f"bat:{b2}"], u)


def test_la_restriction_volontaire_garde_la_circulation_et_retire_le_reste(b):
    b1, b3 = b[0], b[2]
    with Session(engine) as session:
        u = _titulaire(session, b1, _place("976", desservie_par=b3), restreint=True)
        assert perimetre_visible([f"bat:{b3}/ascenseur"], u, ouvert_a_la_copropriete=True)
        assert not perimetre_visible([f"bat:{b3}/toit"], u, ouvert_a_la_copropriete=True)
