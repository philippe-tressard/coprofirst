"""L'hôte commun d'une installation commune ne fait que REDIRIGER (#1894, §4.1 bis).

Les garde-fous demandés par le ticket :

- **l'hôte commun ne sert rien** : toute route de l'application, appelée sous son nom,
  reçoit 421 — sauf la santé et l'aiguillage, qui ne lisent aucune base ; aucune
  réponse de l'aiguillage ne pose de cookie ;
- **cas zéro** : un alias inconnu ne redirige NULLE PART ; une copropriété suspendue
  n'est jamais une destination ; tout échec reçoit la même réponse ;
- **correspondance exacte et tentatives limitées** ;
- **une installation propre à une copropriété** n'a ni aiguillage ni garde des pages.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.installation_commune.bases_pretes import INDISPONIBLE
from app.installation_commune.routeur import ECHEC
from app.main import app as application
from app.utils.limiter import limiter
from tests.aides_installation_commune import HOTE_COMMUN, installation_commune
from tests.aides_sources import operations_montees

TILLEULS = f"75015-les-tilleuls.{HOTE_COMMUN}"
ANCIEN_TILLEULS = f"75015-tilleuls.{HOTE_COMMUN}"


@pytest.fixture()
def commune(tmp_path, monkeypatch):
    limiter.reset()
    with installation_commune(tmp_path, monkeypatch):
        yield TestClient(application, follow_redirects=False)
    limiter.reset()


def _aiguiller(client, corps, hote=HOTE_COMMUN):
    if isinstance(corps, (bytes, str)):
        return client.post("/plateforme/aiguillage", content=corps, headers={"host": hote})
    return client.post("/plateforme/aiguillage", json=corps, headers={"host": hote})


# ── L'écran de connexion de l'hôte commun ────────────────────────────────────


def test_l_hote_commun_s_annonce(commune):
    assert commune.get("/plateforme/aiguillage", headers={"host": HOTE_COMMUN}).json() == {
        "hote_commun": True
    }


@pytest.mark.parametrize("hote", [TILLEULS, "residence-chenes.example", "autre.example"])
def test_ailleurs_l_aiguillage_n_existe_pas(commune, hote):
    assert commune.get("/plateforme/aiguillage", headers={"host": hote}).status_code == 404
    assert (
        _aiguiller(commune, {"code_postal": "75015", "nom": "Les Tilleuls"}, hote).status_code
        == 404
    )


# ── L'aiguillage ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("corps", "destination"),
    [
        ({"code_postal": "75015", "nom": "Les Tilleuls"}, f"https://{TILLEULS}/"),
        ({"code_postal": " 75015 ", "nom": "les   tilleuLS"}, f"https://{TILLEULS}/"),
        ({"alias": "75015-les-tilleuls"}, f"https://{TILLEULS}/"),
        #  L'ancien alias mène à l'adresse ACTUELLE : les liens envoyés restent bons.
        ({"alias": "75015-tilleuls"}, f"https://{TILLEULS}/"),
        #  Une copropriété qui a son domaine y est renvoyée.
        (
            {"code_postal": "69003", "nom": "Résidence des Chênes"},
            "https://residence-chenes.example/",
        ),
    ],
)
def test_une_correspondance_exacte_renvoie_a_la_copropriete(commune, corps, destination):
    reponse = _aiguiller(commune, corps)
    assert reponse.status_code == 200
    assert reponse.json() == {"destination": destination}


@pytest.mark.parametrize(
    "corps",
    [
        {"code_postal": "99999", "nom": "Inconnue"},  # cas zéro : personne
        {"code_postal": "75015", "nom": "Les Tilleuls Verts"},  # ni préfixe ni proximité
        {"code_postal": "75015", "nom": "Les Tilleul"},
        {"code_postal": "75016", "nom": "Les Tilleuls"},
        {"code_postal": "13001", "nom": "Les Érables"},  # suspendue
        {"alias": "13001-erables"},  # l'ancien alias d'une suspendue
        {"alias": "75015"},
        {"code_postal": "7501", "nom": "Les Tilleuls"},
        {"code_postal": 75015, "nom": "Les Tilleuls"},
        {"nom": "Les Tilleuls"},
        {},
        ["75015", "Les Tilleuls"],
        "pas du JSON",
        b"{" + b" " * 2000 + b"}",
    ],
)
def test_tout_echec_recoit_la_meme_reponse(commune, corps):
    reponse = _aiguiller(commune, corps)
    assert (reponse.status_code, reponse.json()) == (404, {"detail": ECHEC})


def test_les_tentatives_sont_limitees(commune):
    for _ in range(10):
        assert _aiguiller(commune, {"code_postal": "99999", "nom": "X"}).status_code == 404
    assert _aiguiller(commune, {"code_postal": "75015", "nom": "Les Tilleuls"}).status_code == 429


def test_l_aiguillage_ne_pose_aucun_cookie(commune):
    reponses = [
        commune.get("/plateforme/aiguillage", headers={"host": HOTE_COMMUN}),
        _aiguiller(commune, {"code_postal": "75015", "nom": "Les Tilleuls"}),
        _aiguiller(commune, {"code_postal": "99999", "nom": "X"}),
        commune.get("/plateforme/aiguillage/hote", headers={"host": ANCIEN_TILLEULS}),
    ]
    assert all("set-cookie" not in r.headers for r in reponses)


# ── La garde des pages (forward_auth de Caddy) ───────────────────────────────


def _garde(client, hote, uri="/"):
    return client.get("/plateforme/aiguillage/hote", headers={"host": hote, "x-forwarded-uri": uri})


def test_un_ancien_alias_redirige_vers_l_adresse_actuelle_chemin_compris(commune):
    reponse = _garde(commune, ANCIEN_TILLEULS, "/tickets/12?onglet=suite")
    assert reponse.status_code == 308
    assert reponse.headers["location"] == f"https://{TILLEULS}/tickets/12?onglet=suite"


@pytest.mark.parametrize("uri", ["//evil.example/x", "/\\evil.example", "https://evil.example"])
def test_la_redirection_ne_sort_jamais_de_la_copropriete(commune, uri):
    assert _garde(commune, ANCIEN_TILLEULS, uri).headers["location"] == f"https://{TILLEULS}/"


@pytest.mark.parametrize("hote", [TILLEULS, "residence-chenes.example", HOTE_COMMUN])
def test_un_hote_qui_designe_une_copropriete_et_l_hote_commun_passent(commune, hote):
    reponse = _garde(commune, hote)
    assert reponse.status_code == 204 and "location" not in reponse.headers


@pytest.mark.parametrize(
    "hote",
    [
        f"99999-inconnue.{HOTE_COMMUN}",
        f"13001-erables.{HOTE_COMMUN}",
        "autre.example",
        f"tilleuls.{HOTE_COMMUN}",
    ],
)
def test_cas_zero_un_alias_inconnu_ne_redirige_nulle_part(commune, hote):
    reponse = _garde(commune, hote, "/tickets/12")
    assert reponse.status_code == 421 and "location" not in reponse.headers


# ── L'hôte commun ne sert rien ───────────────────────────────────────────────

#: Ce qui répond à tout hôte, et pourquoi : rien de ce préfixe ou de cette route ne
#: lit la base d'une copropriété (`contexte.ROUTES_PLATEFORME`, `PREFIXE_PLATEFORME`).
REPONDENT_A_TOUT_HOTE = ("/health", "/plateforme/")


def _routes_get():
    for methode, chemin, _ in operations_montees(application):
        if methode == "GET":
            yield re.sub(r"\{[^}]+\}", "1", chemin)


def test_l_hote_commun_ne_sert_aucune_route_de_copropriete(commune):
    servies = [p for p in _routes_get() if not p.startswith(REPONDENT_A_TOUT_HOTE)]
    assert len(servies) > 100  # cas zéro : le balayage a bien porté sur l'application
    for chemin in servies:
        reponse = commune.get(chemin, headers={"host": HOTE_COMMUN})
        assert reponse.status_code == 421, chemin
        assert "set-cookie" not in reponse.headers, chemin
    # Témoin : sous l'adresse d'une copropriété, la requête est bien RÉSOLUE — elle
    # passe le 421 et bute sur la garde des bases (#2053) : la sienne est injoignable
    # ici, donc 503 pour cet hôte seul, jamais un 421.
    reponse = commune.get("/auth/me", headers={"host": TILLEULS})
    assert reponse.status_code == 503
    assert reponse.json() == {"detail": INDISPONIBLE}


# ── Une installation propre à une copropriété ────────────────────────────────


def test_une_installation_propre_n_a_ni_aiguillage_ni_garde():
    limiter.reset()
    client = TestClient(application, follow_redirects=False)
    for hote in ("testserver", "localhost", HOTE_COMMUN):
        assert client.get("/plateforme/aiguillage", headers={"host": hote}).status_code == 404
        assert _aiguiller(client, {"alias": "75015-les-tilleuls"}, hote).status_code == 404
        assert _garde(client, hote).status_code == 404
    limiter.reset()
