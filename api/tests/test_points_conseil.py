"""Le point conseil syndical / syndic du Reporting CS (#2041, maquettes A1 et C1).

Ce qui est tenu :
- **la porte** : le conseil et l'administration, ni un résident ni un anonyme ;
- **le Qui** : un membre du CS ou du syndic est recopié depuis l'annuaire (le
  nom envoyé par l'écran est ignoré), un invité garde ses seuls champs saisis ;
- **un point en cours par mode**, et la **reprise à moins de deux heures** d'un
  point d'un autre mode — pas au-delà ;
- **le CR d'une affaire** : seulement une affaire du relevé du mode, réécrit en
  place, retiré quand il est vide, brouillon et « Conseil seul » gardés ;
- **le CR global** : les affaires abordées, puis les non traitées — figées à
  « Terminer », après quoi le point ne se modifie plus ;
- **les lieux proposés** : la résidence, le cabinet du syndic, les derniers lieux.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import Session

from app.models.copropriete import Copropriete
from app.models.core import RoleUtilisateur
from app.models.gouvernance import GenreCivilite, MembreCS, MembreSyndic, SyndicInfo
from app.models.points_conseil import PointConseil
from app.utils import horloge
from app.utils.points_conseil import a_reprendre
from tests.aides_http import base_http, client_http
from tests.aides_suivi import affaire_ouverte

DEBUT = "2026-10-19T17:00:00"


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


@pytest.fixture(name="cs")
def cs_fixture(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    return http


def _annuaire(moteur) -> tuple[int, int]:
    with Session(moteur) as s:
        m_cs = MembreCS(genre=GenreCivilite.mme, prenom="Reine", nom="Martin")
        m_sy = MembreSyndic(
            genre=GenreCivilite.mr, prenom="Paul", nom="Bernard", fonction="Gestionnaire"
        )
        s.add(m_cs)
        s.add(m_sy)
        s.add(SyndicInfo(nom_syndic="Cabinet Test", adresse="2 rue Test"))
        s.add(Copropriete(nom="Test", adresse="1 rue Test"))
        s.commit()
        return m_cs.id, m_sy.id


def _ouvrir(http, mode="affaires", **champs):
    corps = {"mode": mode, "debut": DEBUT, "a_distance": False, "lieu": "Loge", **champs}
    return http.post("/points-conseil", json=corps)


# ── La porte ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "methode,route",
    [
        ("get", "/points-conseil/participants"),
        ("get", "/points-conseil/courant?mode=affaires"),
        ("post", "/points-conseil"),
        ("put", "/points-conseil/1/affaires/1"),
        ("post", "/points-conseil/1/terminer"),
        ("delete", "/points-conseil/1"),
    ],
)
def test_un_resident_est_refuse(moteur, methode, route):
    http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    kwargs = {"json": {}} if methode in ("post", "put") else {}
    assert getattr(http, methode)(route, **kwargs).status_code == 403


def test_un_anonyme_est_refuse(moteur):
    http, _ = client_http(moteur, None)
    assert http.get("/points-conseil/courant?mode=affaires").status_code == 401


def test_un_mode_inconnu_est_refuse(cs):
    assert cs.get("/points-conseil/courant?mode=inconnu").status_code == 422
    assert _ouvrir(cs, mode="inconnu").status_code == 422


# ── Le Qui ──────────────────────────────────────────────────────────────────


def test_les_membres_sont_recopies_depuis_l_annuaire(moteur, cs):
    m_cs, m_sy = _annuaire(moteur)
    r = _ouvrir(
        cs,
        presents=[
            {"nature": "cs", "membre_id": m_cs, "nom": "Usurpé"},
            {"nature": "syndic", "membre_id": m_sy},
            {"nature": "invite", "prenom": " Paul ", "entreprise": "Étanchéité Sud", "email": ""},
        ],
    )
    assert r.status_code == 201, r.text
    presents = {p["nature"]: p for p in r.json()["presents"]}
    assert presents["cs"]["nom"] == "Martin"
    assert presents["syndic"]["fonction"] == "Gestionnaire"
    assert presents["syndic"]["entreprise"] == "Cabinet Test"
    invite = presents["invite"]
    assert invite["prenom"] == "Paul" and invite["entreprise"] == "Étanchéité Sud"
    assert invite["email"] is None and invite["nom"] is None


def test_un_membre_inconnu_est_refuse(cs):
    assert _ouvrir(cs, presents=[{"nature": "cs", "membre_id": 999}]).status_code == 404
    assert _ouvrir(cs, presents=[{"nature": "voisin"}]).status_code == 422


def test_participants_et_lieux_proposes(moteur, cs):
    _annuaire(moteur)
    _ouvrir(cs, lieu="Salle municipale")
    r = cs.get("/points-conseil/participants").json()
    assert [m["nom"] for m in r["conseil"]] == ["Martin"]
    assert [m["nom"] for m in r["syndic"]] == ["Bernard"]
    assert [(lieu["libelle"], lieu["adresse"]) for lieu in r["lieux"]] == [
        ("Résidence", "1 rue Test"),
        ("Cabinet Test", "2 rue Test"),
        ("Dernier lieu", "Salle municipale"),
    ]


# ── Un point par mode, et la reprise ───────────────────────────────────────


def test_un_seul_point_en_cours_par_mode(cs):
    assert _ouvrir(cs).status_code == 201
    assert _ouvrir(cs).status_code == 409


def _point(mode: str, il_y_a: timedelta) -> PointConseil:
    maintenant = horloge.maintenant()
    return PointConseil(mode=mode, debut=maintenant, cree_le=maintenant - il_y_a)


def test_reprise_d_un_autre_mode_a_moins_de_deux_heures():
    maintenant = horloge.maintenant()
    recent = _point("affaires", timedelta(minutes=90))
    assert a_reprendre([recent], "entretien", maintenant) is recent


def test_pas_de_reprise_au_dela_de_deux_heures_ni_du_meme_mode():
    maintenant = horloge.maintenant()
    ancien = _point("affaires", timedelta(hours=2, minutes=1))
    meme_mode = _point("entretien", timedelta(minutes=10))
    assert a_reprendre([ancien, meme_mode], "entretien", maintenant) is None


# ── Le CR d'une affaire ─────────────────────────────────────────────────────


def test_le_cr_d_une_affaire_s_ecrit_se_reecrit_et_se_retire(moteur, cs):
    t = affaire_ouverte(moteur, "Infiltration hall B", jours=40)
    point = _ouvrir(cs).json()["point"]["id"]
    route = f"/points-conseil/{point}/affaires/{t}"

    r = cs.put(route, json={"contenu": "<p>Relance</p>", "brouillon": True, "conseil_seul": True})
    assert r.status_code == 200, r.text
    (abordee,) = r.json()["abordees"]
    assert abordee["cr"]["brouillon"] and abordee["cr"]["conseil_seul"]

    r = cs.put(route, json={"contenu": "<p>Devis sous 15 jours</p>"})
    (abordee,) = r.json()["abordees"]
    assert abordee["cr"]["contenu"] == "<p>Devis sous 15 jours</p>"
    assert not abordee["cr"]["brouillon"]

    r = cs.put(route, json={"contenu": "  "})
    assert r.json()["abordees"] == []
    assert [a["id"] for a in r.json()["non_traitees"]] == [t]


def test_une_affaire_hors_du_rapport_ne_recoit_pas_de_cr(moteur, cs):
    close = affaire_ouverte(moteur, "Close", statut="résolu")
    point = _ouvrir(cs).json()["point"]["id"]
    r = cs.put(f"/points-conseil/{point}/affaires/{close}", json={"contenu": "<p>x</p>"})
    assert r.status_code == 404


# ── Le CR global et « Terminer » ────────────────────────────────────────────


def test_terminer_fige_les_non_traitees_et_ferme_le_point(moteur, cs):
    abordee = affaire_ouverte(moteur, "Abordée", jours=60)
    oubliee = affaire_ouverte(moteur, "Oubliée", jours=30)
    point = _ouvrir(cs).json()["point"]["id"]
    cs.put(f"/points-conseil/{point}/affaires/{abordee}", json={"contenu": "<p>Vu</p>"})

    r = cs.post(f"/points-conseil/{point}/terminer")
    assert r.status_code == 200, r.text
    cr = r.json()
    assert cr["point"]["etat"] == "a_valider"
    assert [a["affaire"]["id"] for a in cr["abordees"]] == [abordee]
    assert [a["id"] for a in cr["non_traitees"]] == [oubliee]

    #  Une affaire ouverte APRÈS « Terminer » n'entre pas au CR figé.
    affaire_ouverte(moteur, "Arrivée après")
    courant = cs.get("/points-conseil/courant?mode=affaires").json()["compte_rendu"]
    assert [a["id"] for a in courant["non_traitees"]] == [oubliee]

    assert (
        cs.put(
            f"/points-conseil/{point}/affaires/{oubliee}", json={"contenu": "<p>x</p>"}
        ).status_code
        == 409
    )
    assert cs.patch(f"/points-conseil/{point}", json={"lieu": "Ailleurs"}).status_code == 409
    assert cs.delete(f"/points-conseil/{point}").status_code == 409
    #  Un nouveau point peut s'ouvrir : l'ancien attend sa validation.
    assert _ouvrir(cs).status_code == 201


def test_abandonner_un_point_en_cours(moteur, cs):
    t = affaire_ouverte(moteur)
    point = _ouvrir(cs).json()["point"]["id"]
    cs.put(f"/points-conseil/{point}/affaires/{t}", json={"contenu": "<p>x</p>"})
    assert cs.delete(f"/points-conseil/{point}").status_code == 204
    assert cs.get("/points-conseil/courant?mode=affaires").json()["compte_rendu"] is None


def test_corriger_le_quand_le_ou_le_qui(moteur, cs):
    m_cs, _ = _annuaire(moteur)
    point = _ouvrir(cs).json()["point"]["id"]
    r = cs.patch(
        f"/points-conseil/{point}",
        json={"a_distance": True, "lieu": " ", "presents": [{"nature": "cs", "membre_id": m_cs}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["point"]["a_distance"] and r.json()["point"]["lieu"] is None
    assert [p["nom"] for p in r.json()["presents"]] == ["Martin"]
