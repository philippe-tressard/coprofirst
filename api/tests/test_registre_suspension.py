"""La SUSPENSION appliquée : lecture seule, export ouvert (D20 — R6 #1882).

Ce que ce fichier tient (spec `multi-coproprietes.md` §4.11) :

1. la liste des gestes ouverts suit les routes, dans les deux sens : rien n'y est
   déclaré pour une route qui n'existe plus ;
2. une installation suspendue refuse TOUTE route d'écriture montée hors liste —
   balayée par de vraies requêtes, une par route —, et sert les lectures, la
   connexion et l'export ;
3. un bail échu, même suspendu, ramène au mode limité, jamais à la lecture seule
   (D19) ; la référence n'est jamais suspendue ; le retour au constat lève la garde.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from app.config import get_settings
from app.inscription import suspension
from app.inscription.client import constat_courant
from app.main import app
from app.models.core import RoleUtilisateur
from app.utils import horloge, installation
from tests.aides_baux import replique_au_bail
from tests.aides_http import base_http, client_http
from tests.aides_sources import operations_montees

#: Le cas zéro : 271 routes d'écriture montées au 16/11/2026.
MINIMUM_ECRITURES = 200


@pytest.fixture
def moteur():
    with base_http() as moteur:
        yield moteur


@pytest.fixture
def suspendue(monkeypatch, tmp_path):
    """Une réplique au bail signé, valide et SUSPENDU ; la référence éteinte."""
    replique_au_bail(monkeypatch, tmp_path, etat="suspendue")
    assert constat_courant().etat == "suspendue"


def _ecritures() -> set[tuple[str, str]]:
    return {(m, c) for m, c, _r in operations_montees(app) if m in suspension.ECRITURES}


def _concret(chemin: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", chemin)


def _refusee_par_la_garde(reponse) -> bool:
    """403 ET le message de la suspension — une route peut répondre autre chose qu'un JSON."""
    if reponse.status_code != 403:
        return False
    try:
        return reponse.json().get("detail") == suspension.MESSAGE
    except ValueError:
        return False


# ── 1. La liste suit les routes ──────────────────────────────────────────────


def test_cas_zero_le_balayage_voit_les_routes_d_ecriture():
    assert len(_ecritures()) >= MINIMUM_ECRITURES, "le parcours des routes ne mesure plus rien"


def test_rien_n_est_ouvert_pour_une_route_qui_n_existe_pas():
    fantomes = sorted(set(suspension.OUVERTS_EN_SUSPENSION) - _ecritures())
    assert fantomes == [], f"ouverts en suspension mais absents de l'application : {fantomes}"


def test_chaque_geste_ouvert_dit_pourquoi():
    assert all(raison.strip() for raison in suspension.OUVERTS_EN_SUSPENSION.values())


@pytest.mark.parametrize(
    ("methode", "chemin", "ferme"),
    [
        ("POST", "/tickets", True),
        ("PATCH", "/admin/utilisateurs/12", True),
        ("DELETE", "/notifications/7", True),
        ("PATCH", "/notifications/7/lue", False),
        ("POST", "/auth/login/", False),
        ("POST", "/admin/export-copropriete", False),
        ("GET", "/tickets", False),
        ("HEAD", "/tickets", False),
    ],
)
def test_geste_ferme_reconnait_les_chemins_concrets(methode, chemin, ferme):
    assert suspension.geste_ferme(methode, chemin) is ferme


# ── 2. La garde, par de vraies requêtes ──────────────────────────────────────


def test_suspendue_toute_ecriture_hors_liste_est_refusee(moteur, suspendue):
    """UNE requête par route d'écriture montée : 403 et le message, avant toute route."""
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    passees = []
    for methode, chemin in sorted(_ecritures()):
        if (methode, chemin) in suspension.OUVERTS_EN_SUSPENSION:
            continue
        reponse = http.request(methode, _concret(chemin), json={})
        if not _refusee_par_la_garde(reponse):
            passees.append(f"{methode} {chemin} → {reponse.status_code}")
    assert passees == [], f"écritures servies par une installation suspendue : {passees}"


def test_suspendue_les_gestes_ouverts_passent_la_garde(suspendue):
    """La garde SEULE, devant une application qui répond « servi » : chaque geste ouvert
    la traverse (l'appeler pour de vrai lancerait une sauvegarde, une maintenance…)."""

    async def servir(scope, receive, send):
        await PlainTextResponse("servi")(scope, receive, send)

    http = TestClient(suspension.GardeSuspension(servir))
    for methode, chemin in suspension.OUVERTS_EN_SUSPENSION:
        assert http.request(methode, _concret(chemin)).text == "servi", f"{methode} {chemin}"
    assert _refusee_par_la_garde(http.post("/tickets")), "le témoin : la garde refuse"


def test_suspendue_la_lecture_la_connexion_et_l_export_restent(moteur, suspendue):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    assert http.get("/auth/me").status_code == 200
    assert http.get("/config").json()[suspension.CLE_PUBLIQUE] == "1"
    connexion = http.post("/auth/login", json={"email": "x@exemple.test", "password": "x"})
    assert connexion.status_code == 401, "la connexion répond comme toujours"
    assert http.post("/admin/export-copropriete/verifier").status_code == 200


def test_hors_suspension_la_garde_laisse_passer(moteur, monkeypatch, tmp_path):
    replique_au_bail(monkeypatch, tmp_path)  # active
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    assert http.get("/config").json()[suspension.CLE_PUBLIQUE] == "0"
    assert not _refusee_par_la_garde(http.patch("/admin/utilisateurs/1", json={}))


# ── 3. Jamais à tort ─────────────────────────────────────────────────────────


def test_un_bail_suspendu_mais_echu_ramene_au_mode_limite_jamais_a_la_lecture_seule(
    moteur, monkeypatch, tmp_path
):
    echeance = replique_au_bail(monkeypatch, tmp_path, etat="suspendue")
    monkeypatch.setattr(horloge, "maintenant", lambda: echeance + timedelta(seconds=1))
    assert constat_courant().etat == "limitee"
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    assert not _refusee_par_la_garde(http.post("/faq", json={}))


def test_la_reference_n_est_jamais_suspendue(moteur, monkeypatch, tmp_path):
    replique_au_bail(monkeypatch, tmp_path, etat="suspendue")
    monkeypatch.setattr(installation, "role_installation", lambda valeur=None: "reference")
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    assert not _refusee_par_la_garde(http.post("/faq", json={}))


def test_le_retour_au_constat_leve_la_lecture_seule(moteur, suspendue, monkeypatch):
    monkeypatch.setattr(get_settings(), "registre_constat", True)
    assert constat_courant().etat == "suspendue", "l'état se constate toujours"
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    assert not _refusee_par_la_garde(http.post("/faq", json={}))
    assert http.get("/config").json()[suspension.CLE_PUBLIQUE] == "0"
