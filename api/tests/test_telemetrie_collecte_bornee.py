"""`POST /telemetry/collect` est public : son volume est BORNÉ (#1597).

## Le défaut (audit du 02/10/2026)

La route est publique — `sendBeacon`, visiteurs anonymes compris — et elle
écrit en base. Elle acceptait 60 appels par minute et par adresse, 50
événements par appel, un `detail` de 500 caractères : **3 000 lignes et
~1,5 Mo par minute et par adresse**, sur un Raspberry Pi, gardées
30 jours. Rien ne plafonnait la journée.

## Ce que ces tests tiennent

- une limite **par jour** en plus de la limite par minute, nommée dans
  `utils/limiter` comme toutes les autres ;
- un lot borné en NOMBRE et des champs bornés en TAILLE — refusés en bloc
  (422) et non plus tronqués en silence : une charge hors norme ne vient pas
  du client du site ;
- un visiteur est enregistré sans compte, et la route ne refuse jamais faute
  de session — elle rattache au compte quand il y en a un (rétabli le
  02/10/2026, après le retrait de #1545).
"""

from __future__ import annotations

import ast

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import get_session
from app.main import app
from app.models.telemetrie import TelemetryEvent
from app.utils import limiter as module_limiter
from app.utils.limiter import limiter
from tests.aides_base import moteur_de_test
from tests.aides_sources import module_app

ROUTE = "/telemetry/collect"


@pytest.fixture(name="moteur")
def moteur_fixture():
    moteur = moteur_de_test()

    def _session():
        with Session(moteur) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    limiter.reset()
    yield moteur
    app.dependency_overrides.clear()
    limiter.reset()


def _evenements(moteur) -> list[TelemetryEvent]:
    with Session(moteur) as s:
        return list(s.exec(select(TelemetryEvent)).all())


def _limite_de_la_route() -> str:
    """La valeur de la constante posée par `@limiter.limit(...)` sur `collect`."""
    for noeud in ast.walk(module_app("routers/telemetry_collecte.py").arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == "collect":
            for deco in noeud.decorator_list:
                if isinstance(deco, ast.Call) and ast.unparse(deco.func) == "limiter.limit":
                    nom = ast.unparse(deco.args[0])
                    assert hasattr(module_limiter, nom), f"`{nom}` n'est pas une constante nommée"
                    return getattr(module_limiter, nom)
    raise AssertionError("`collect` ne porte aucun `@limiter.limit`")


def test_la_collecte_porte_un_plafond_par_minute_et_par_jour():
    limite = _limite_de_la_route()
    assert "/minute" in limite and "/day" in limite, (
        f"`POST {ROUTE}` est limitée à « {limite} » : une route publique qui écrit en "
        "base porte aussi un plafond JOURNALIER par adresse (#1597)."
    )


def test_un_lot_trop_nombreux_est_refuse_et_rien_n_est_ecrit(moteur):
    corps = {"events": [{"page": f"/p{i}"} for i in range(51)]}
    reponse = TestClient(app).post(ROUTE, json=corps)
    assert reponse.status_code == 422, reponse.text
    assert _evenements(moteur) == [], "un lot refusé a quand même écrit"


@pytest.mark.parametrize(
    "evenement",
    [
        {"page": "/" + "x" * 300},
        {"page": "/actualites", "detail": "x" * 5000},
        {"page": "/actualites", "action": "x" * 200},
        {"page": ""},
    ],
    ids=["page-longue", "detail-long", "action-longue", "page-vide"],
)
def test_un_champ_hors_borne_fait_refuser_le_lot(moteur, evenement):
    reponse = TestClient(app).post(ROUTE, json={"events": [evenement]})
    assert reponse.status_code == 422, reponse.text
    assert _evenements(moteur) == []


def test_un_lot_normal_d_un_visiteur_est_enregistre_sans_compte(moteur):
    corps = {"events": [{"page": "/actualites"}, {"page": "/tickets", "action": "view"}]}
    reponse = TestClient(app).post(ROUTE, json=corps)
    assert reponse.status_code == 204, reponse.text
    lignes = _evenements(moteur)
    assert sorted(e.page for e in lignes) == ["/actualites", "/tickets"]
    assert all(e.user_id is None for e in lignes)


def test_un_cookie_invalide_ne_fait_pas_refuser_la_collecte(moteur):
    """`utilisateur_ou_anonyme` rend `None`, jamais un 401 : `sendBeacon` ne lit pas la réponse."""
    http = TestClient(app, cookies={"access_token": "pas-un-jeton"})
    reponse = http.post(ROUTE, json={"events": [{"page": "/actualites"}]})
    assert reponse.status_code == 204, reponse.text
    assert [e.user_id for e in _evenements(moteur)] == [None]


def test_une_rafale_est_coupee_par_la_limite(moteur):
    http = TestClient(app)
    codes = [http.post(ROUTE, json={"events": [{"page": "/a"}]}).status_code for _ in range(30)]
    assert 429 in codes, f"30 appels en rafale sans un seul refus : {sorted(set(codes))}"
