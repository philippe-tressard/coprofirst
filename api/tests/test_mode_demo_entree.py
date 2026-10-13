"""L'entrée de la démo par personnage (spec `mode-demo.md` §5, lot D3 #1903).

1. hors démo, la route n'existe pas (404) ; un personnage inconnu non plus ;
2. en démo, l'entrée ouvre une VRAIE session — relue par `/auth/me` —, avec les
   cookies de la connexion et un jeton de rafraîchissement gardé par son empreinte ;
3. un compte absent (remise à zéro en cours) rend 503, jamais 500 ;
4. les personnages : quatre, adresses réservées, rôles cohérents.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import get_settings
from app.demo.personnages import DOMAINE, PERSONNAGES
from app.main import app
from app.models.core import RefreshToken
from tests.aides_base import compte
from tests.aides_http import base_http


@pytest.fixture
def en_demo(monkeypatch):
    monkeypatch.setattr(get_settings(), "mode_demo", "oui")


@pytest.fixture
def moteur():
    with base_http() as moteur:
        yield moteur


def _http() -> TestClient:
    return TestClient(app, follow_redirects=False)


def _poser(moteur, code: str) -> int:
    p = PERSONNAGES[code]
    with Session(moteur) as s:
        return compte(
            s,
            email=p.adresse,
            prenom=p.prenom,
            nom=p.nom,
            statut=p.statut,
            roles_json=p.roles_json,
            email_verifie=True,
        ).id


# ── 1. La route n'existe que dans la démo ──────────────────────────────────


def test_hors_demo_la_route_n_existe_pas(moteur):
    _poser(moteur, "resident")
    reponse = _http().get("/demo/entrer/resident")
    assert reponse.status_code == 404
    assert "access_token" not in reponse.cookies


def test_un_personnage_inconnu_n_existe_pas(moteur, en_demo):
    assert _http().get("/demo/entrer/syndic").status_code == 404


# ── 2. Une vraie session ────────────────────────────────────────────────────


@pytest.mark.parametrize("code", sorted(PERSONNAGES))
def test_en_demo_l_entree_ouvre_la_session_du_personnage(moteur, en_demo, code):
    ident = _poser(moteur, code)
    http = _http()
    reponse = http.get(f"/demo/entrer/{code}")
    assert reponse.status_code == 303
    assert reponse.headers["location"] == "/tableau-de-bord"
    assert {"access_token", "refresh_token"} <= set(reponse.cookies)
    entetes = reponse.headers.get_list("set-cookie")
    assert all("httponly" in e.lower() and "samesite=strict" in e.lower() for e in entetes)

    #  Le cookie porte `Secure` : le client de test, en HTTP, ne le renverrait pas.
    http.cookies.set("access_token", reponse.cookies["access_token"])
    moi = http.get("/auth/me")
    assert moi.status_code == 200 and moi.json()["id"] == ident

    with Session(moteur) as s:
        stocke = s.exec(select(RefreshToken).where(RefreshToken.user_id == ident)).one()
    assert stocke.token != reponse.cookies["refresh_token"], "jamais le jeton en clair (#1389)"


# ── 3. La remise à zéro en cours ────────────────────────────────────────────


def test_un_compte_absent_rend_503(moteur, en_demo):
    reponse = _http().get("/demo/entrer/resident")
    assert reponse.status_code == 503
    assert "réessayez" in reponse.json()["detail"]


# ── 4. Les personnages ──────────────────────────────────────────────────────


def test_les_quatre_personnages_de_la_spec():
    assert set(PERSONNAGES) == {"resident", "locataire", "conseil-syndical", "administrateur"}


def test_les_adresses_sont_reservees_et_uniques():
    adresses = [p.adresse for p in PERSONNAGES.values()]
    assert len(set(adresses)) == len(adresses)
    assert DOMAINE.endswith(".invalid"), "RFC 2606 : rien ne peut y être livré"
    assert all(a.endswith("@" + DOMAINE) for a in adresses)


def test_le_conseil_et_l_administrateur_portent_leur_role():
    assert "conseil_syndical" in PERSONNAGES["conseil-syndical"].roles_json.split(",")
    assert PERSONNAGES["administrateur"].roles_json.split(",") == ["admin"]
    assert "propriétaire" not in PERSONNAGES["locataire"].roles_json.split(",")
