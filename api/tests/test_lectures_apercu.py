"""L'aperçu de la pastille de lecture — `POST /lectures/apercu` (#2633).

Arbitré le 11/11/2026 : le formulaire ne compose plus « qui la lira », il le
demande au serveur, et l'aperçu se juge par la MÊME règle que l'objet enregistré.
Le cas qui compte : une affaire saisie puis enregistrée dit, servie, exactement
ce que son aperçu disait.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur, Ticket
from app.utils.lecture_pastille.objets import destinataires_par_etat, lecture_du_ticket
from app.utils.lecture_pastille.regle import lecture_de
from tests.aides_http import base_http, client_http

PANNE_DU_BATIMENT = {"categorie": "panne", "statut": "ouvert", "perimetre_cible": ["bat:1"]}


@pytest.fixture()
def moteur():
    with base_http() as m:
        yield m


def _apercu(moteur, corps, role=RoleUtilisateur.conseil_syndical):
    http, _ = client_http(moteur, role)
    return http.post("/lectures/apercu", json=corps)


def test_un_anonyme_n_a_pas_d_apercu(moteur):
    assert _apercu(moteur, PANNE_DU_BATIMENT, role=None).status_code == 401


def test_l_apercu_dit_ce_que_la_regle_dit(moteur):
    corps = _apercu(moteur, PANNE_DU_BATIMENT).json()
    attendu = lecture_de(
        actualite=False,
        confidentiel=False,
        public_cible=[],
        perimetre_restreint=True,
        reserve_perimetre=False,
        categorie="panne",
        statut="ouvert",
    )
    assert corps["lecture"] == attendu.model_dump()
    assert corps["destinataires_par_defaut"] == [
        "copropriétaires_occupants",
        "bailleurs",
        "locataires",
    ]
    assert corps["lue_du_seul_conseil"] is False


@pytest.mark.parametrize(
    "saisie, seul_conseil, defauts",
    [
        ({"categorie": "panne", "confidentiel": True}, True, None),
        ({"categorie": "etude_travaux", "statut": "ouvert"}, True, ["conseil_syndical"]),
        (
            {"categorie": "etude_travaux", "statut": "en_ag"},
            False,
            ["copropriétaires_occupants", "bailleurs"],
        ),
        ({"categorie": "actualite", "public_cible": ["conseil_syndical"]}, True, []),
        ({"categorie": "actualite"}, False, []),
    ],
)
def test_lu_du_seul_conseil_et_defauts(moteur, saisie, seul_conseil, defauts):
    corps = _apercu(moteur, saisie).json()
    assert corps["lue_du_seul_conseil"] is seul_conseil
    if defauts is not None:
        assert corps["destinataires_par_defaut"] == defauts


def test_trop_de_codes_est_refuse(moteur):
    corps = PANNE_DU_BATIMENT | {"public_cible": ["locataires"] * 65}
    assert _apercu(moteur, corps).status_code == 422


def test_l_affaire_enregistree_sert_ce_que_son_apercu_disait(moteur):
    """Le cas fautif que l'arbitrage exclut : un aperçu qui dirait autre chose
    que la pastille de l'affaire une fois créée."""
    saisie = {
        "categorie": "panne",
        "public_cible": ["copropriétaires_occupants", "locataires"],
        "perimetre_cible": ["bat:1"],
        "reserve_perimetre": True,
    }
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    cree = http.post("/tickets", json={"titre": "Fuite", "description": "Au plafond.", **saisie})
    assert cree.status_code in (200, 201), cree.text
    servie = http.get(f"/tickets/{cree.json()['id']}").json()
    apercu = http.post("/lectures/apercu", json=saisie | {"statut": servie["statut"]}).json()
    assert servie["lecture"] == apercu["lecture"]
    with Session(moteur) as s:
        assert lecture_du_ticket(s.get(Ticket, servie["id"])).model_dump() == servie["lecture"]


def test_les_destinataires_par_etat_d_une_etude():
    etude = Ticket(categorie="etude_travaux", statut="ouvert")
    par_etat = destinataires_par_etat(etude)
    assert par_etat["ouvert"] == ["conseil_syndical"]
    assert par_etat["en_ag"] == ["copropriétaires_occupants", "bailleurs"]
    assert destinataires_par_etat(Ticket(categorie="actualite", statut="publie")) is None
