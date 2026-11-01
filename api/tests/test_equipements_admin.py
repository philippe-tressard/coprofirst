"""Admin › Copropriété › Équipements — la route qui sert l'écran (#2442).

Les équipements ne sont plus une énumération du code : l'administrateur en
ajoute, en corrige, en retire et en supprime. Ce fichier tient ce que la route
garantit, par de VRAIES requêtes authentifiées (`aides_http`) :

- tout le monde les lit, retirés compris — ce qui les cite les affiche encore ;
- seul l'administrateur écrit : le conseil syndical, comme le résident, est refusé ;
- le code est déduit du libellé à la création, puis ne change plus ;
- `assurance`, `syndic` et `autre` ne se retirent ni ne se suppriment ;
- un équipement cité ne se supprime pas : on le retire ;
- ses périmètres s'écrivent, se relisent, et partent avec le périmètre supprimé.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.models.core import Prestataire, RoleUtilisateur
from app.models.equipements import Equipement, EquipementPerimetre
from app.models.perimetre import Perimetre
from app.seed import equipements_par_defaut
from tests.aides_http import base_http, client_http


@pytest.fixture()
def moteur():
    with base_http() as m:
        with Session(m) as s:
            equipements_par_defaut(s)
            s.add(Perimetre(code="ascenseur-a", libelle="Ascenseur A"))
            s.add(Perimetre(code="ascenseur-b", libelle="Ascenseur B"))
            s.commit()
        yield m


def _admin(moteur):
    return client_http(moteur, RoleUtilisateur.admin)[0]


def _id(moteur, code: str) -> int:
    with Session(moteur) as s:
        return s.exec(select(Equipement.id).where(Equipement.code == code)).one()


def test_toute_session_lit_la_liste_avec_ses_derives(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.résident)
    liste = http.get("/equipements").json()
    par_code = {e["code"]: e for e in liste}
    assert {"ascenseur", "assurance", "syndic", "autre"} <= par_code.keys()
    assert par_code["assurance"]["systeme"] and not par_code["assurance"]["pour_affaires"]
    assert par_code["ascenseur"]["pour_affaires"] and not par_code["ascenseur"]["systeme"]
    assert par_code["ascenseur"]["icone"] == "arrow-up-down"


def test_un_anonyme_ne_lit_rien(moteur):
    http, _ = client_http(moteur, None)
    assert http.get("/equipements").status_code == 401


@pytest.mark.parametrize("role", [RoleUtilisateur.résident, RoleUtilisateur.conseil_syndical])
def test_seul_l_administrateur_ecrit(moteur, role):
    http, _ = client_http(moteur, role)
    assert http.post("/equipements", json={"libelle": "Piscine"}).status_code == 403
    ident = _id(moteur, "ascenseur")
    assert http.patch(f"/equipements/{ident}", json={"libelle": "X"}).status_code == 403
    assert http.delete(f"/equipements/{ident}").status_code == 403
    assert http.get(f"/equipements/{ident}/usages").status_code == 403


def test_creer_deduit_le_code_puis_le_fige(moteur):
    http = _admin(moteur)
    cree = http.post(
        "/equipements",
        json={"libelle": "Porte de garage", "abreviation": "garage", "icone": "car"},
    )
    assert cree.status_code == 201, cree.text
    corps = cree.json()
    assert (corps["code"], corps["abreviation"]) == ("porte_de_garage", "GARAGE")
    modifie = http.patch(
        f"/equipements/{corps['id']}", json={"libelle": "Portail", "code": "portail"}
    )
    assert modifie.status_code == 200
    assert (modifie.json()["libelle"], modifie.json()["code"]) == ("Portail", "porte_de_garage")


def test_un_code_deja_pris_ou_mal_forme_est_refuse(moteur):
    http = _admin(moteur)
    assert http.post("/equipements", json={"libelle": "Ascenseur"}).status_code == 422
    assert http.post("/equipements", json={"libelle": "X", "code": "Pas Bon"}).status_code == 422
    assert http.post("/equipements", json={"libelle": "  "}).status_code == 422


def test_une_abreviation_trop_longue_est_refusee(moteur):
    http = _admin(moteur)
    corps = {"libelle": "Piscine", "abreviation": "PISCINES!"}
    assert http.post("/equipements", json=corps).status_code == 422


@pytest.mark.parametrize("code", ["assurance", "syndic", "autre"])
def test_un_equipement_systeme_ne_se_retire_ni_ne_se_supprime(moteur, code):
    http = _admin(moteur)
    ident = _id(moteur, code)
    assert http.patch(f"/equipements/{ident}", json={"actif": False}).status_code == 422
    assert http.delete(f"/equipements/{ident}").status_code == 409
    #  Son libellé et son icône, eux, s'administrent.
    assert http.patch(f"/equipements/{ident}", json={"libelle": "Renommé"}).status_code == 200


def test_un_equipement_cite_ne_se_supprime_pas_il_se_retire(moteur):
    http = _admin(moteur)
    with Session(moteur) as s:
        s.add(Prestataire(nom="Témoin", specialite="piscine"))
        s.add(Equipement(code="piscine", libelle="Piscine"))
        s.commit()
    ident = _id(moteur, "piscine")
    assert http.get(f"/equipements/{ident}/usages").json() == {
        "contrats": 0,
        "affaires": 0,
        "prestataires": 1,
    }
    refus = http.delete(f"/equipements/{ident}")
    assert refus.status_code == 409 and "1 prestataire" in refus.json()["detail"]
    retire = http.patch(f"/equipements/{ident}", json={"actif": False})
    assert retire.status_code == 200 and retire.json()["actif"] is False
    #  Retiré, il reste lu : la fiche du prestataire affiche encore son libellé.
    assert "piscine" in {e["code"] for e in http.get("/equipements").json()}


def test_un_equipement_libre_se_supprime(moteur):
    http = _admin(moteur)
    cree = http.post("/equipements", json={"libelle": "Borne de recharge"}).json()
    assert http.delete(f"/equipements/{cree['id']}").status_code == 204
    assert "borne_de_recharge" not in {e["code"] for e in http.get("/equipements").json()}


def test_les_perimetres_lies_s_ecrivent_et_se_relisent(moteur):
    http = _admin(moteur)
    ident = _id(moteur, "ascenseur")
    corps = {"perimetres": ["ascenseur-b", "ascenseur-a", "ascenseur-a"]}
    pose = http.patch(f"/equipements/{ident}", json=corps)
    assert pose.status_code == 200
    assert sorted(pose.json()["perimetres"]) == ["ascenseur-a", "ascenseur-b"]
    lu = next(e for e in http.get("/equipements").json() if e["code"] == "ascenseur")
    assert sorted(lu["perimetres"]) == ["ascenseur-a", "ascenseur-b"]
    inconnu = http.patch(f"/equipements/{ident}", json={"perimetres": ["licorne"]})
    assert inconnu.status_code == 422
    vide = http.patch(f"/equipements/{ident}", json={"perimetres": []})
    assert vide.json()["perimetres"] == []


def test_supprimer_un_perimetre_retire_ses_liens_jamais_l_equipement(moteur):
    http = _admin(moteur)
    ident = _id(moteur, "ascenseur")
    http.patch(f"/equipements/{ident}", json={"perimetres": ["ascenseur-a"]})
    with Session(moteur) as s:
        perimetre_id = s.exec(select(Perimetre.id).where(Perimetre.code == "ascenseur-a")).one()
    assert http.delete(f"/perimetres/{perimetre_id}").status_code == 204
    with Session(moteur) as s:
        assert s.get(Equipement, ident) is not None
        assert not s.exec(select(EquipementPerimetre)).all()
