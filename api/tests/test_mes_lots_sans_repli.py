"""`GET /lots/mes-lots` rend les lots du COMPTE, jamais le patrimoine entier (16/10/2026).

## 🔴 Le défaut

Sans lien actif, un administrateur, un conseiller ou un opérateur recevait TOUS
les lots de la résidence — un repli « pour consulter le patrimoine ». Les écrans
y lisent « mes lots » : sur la démo, le profil d'`operateur@localhost` listait
trente logements avec un champ d'étage chacun, l'accueil lui prêtait l'étage du
premier appartement venu, et les accès lui proposaient de commander un badge
pour des lots où la commande est refusée. Consulter le patrimoine a sa route,
`GET /lots/admin/tous` — tenue ici aussi, pour que le retrait du repli ne
retire rien au conseil.

L'écriture de l'étage n'a jamais suivi ce repli : `test_etage_du_lot.py` le tient.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.copropriete import Lot, TypeLot
from app.models.core import RoleUtilisateur, TypeLien, UserLot
from app.models.roles import ROLE_OPERATEUR
from tests.aides_http import base_http, client_http

COMPTES_SANS_LOT = {
    "administrateur": (RoleUtilisateur.admin, {}),
    "opérateur": (RoleUtilisateur.admin, {"roles_json": f"admin,{ROLE_OPERATEUR}"}),
    "conseil syndical": (RoleUtilisateur.conseil_syndical, {}),
    "résident": (RoleUtilisateur.résident, {}),
}


def _poser_lots(moteur, nombre: int = 3) -> list[int]:
    with Session(moteur) as s:
        lots = [Lot(numero=str(10 + i), type=TypeLot.appartement, etage=i) for i in range(nombre)]
        s.add_all(lots)
        s.commit()
        return [lot.id for lot in lots]


@pytest.mark.parametrize("nom", COMPTES_SANS_LOT)
def test_un_compte_sans_lot_n_a_aucun_lot_quel_que_soit_son_role(nom):
    role, champs = COMPTES_SANS_LOT[nom]
    with base_http() as moteur:
        _poser_lots(moteur)
        http, _ = client_http(moteur, role, **champs)
        reponse = http.get("/lots/mes-lots")
    assert reponse.status_code == 200
    assert reponse.json() == [], f"un {nom} sans lot reçoit le patrimoine entier"


def test_un_administrateur_rattache_ne_recoit_que_SON_lot():
    """🔴 Le cas zéro : une route qui rendrait toujours `[]` passerait le test ci-dessus."""
    with base_http() as moteur:
        a, _b, _c = _poser_lots(moteur)
        http, ident = client_http(moteur, RoleUtilisateur.admin)
        with Session(moteur) as s:
            s.add(UserLot(user_id=ident, lot_id=a, type_lien=TypeLien.propriétaire, actif=True))
            s.commit()
        lots = http.get("/lots/mes-lots").json()
    assert [(lot["id"], lot["type_lien"]) for lot in lots] == [(a, "propriétaire")]
    assert lots[0]["est_logement_de_reference"] is True


def test_un_lien_INACTIF_ne_rend_pas_le_lot():
    with base_http() as moteur:
        a, _b, _c = _poser_lots(moteur)
        http, ident = client_http(moteur, RoleUtilisateur.conseil_syndical)
        with Session(moteur) as s:
            s.add(UserLot(user_id=ident, lot_id=a, type_lien=TypeLien.propriétaire, actif=False))
            s.commit()
        assert http.get("/lots/mes-lots").json() == []


def test_le_patrimoine_entier_reste_au_conseil_par_sa_route():
    with base_http() as moteur:
        ids = _poser_lots(moteur)
        http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        tous = http.get("/lots/admin/tous").json()
    assert sorted(lot["id"] for lot in tous) == sorted(ids)
