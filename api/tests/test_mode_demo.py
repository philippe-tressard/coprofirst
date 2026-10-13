"""Le socle du mode démo (spec `specs/architecture/mode-demo.md`, lot D1 #1901).

Ce que ce fichier tient :

1. le réglage ne se lit qu'à un endroit, et une valeur mal écrite n'allume rien ;
2. le registre des gestes fermés suit les routes montées, dans les deux sens : toute
   route du périmètre est fermée ou ouverte exprès, et rien n'est déclaré pour une
   route qui n'existe plus ;
3. la garde refuse en démo, et laisse tout passer hors démo — vérifié par de vraies
   requêtes ;
4. les fichiers reçus sont refusés à leur porte, pas seulement à la route.
"""

from __future__ import annotations

import re

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.main import app
from app.models.core import RoleUtilisateur
from app.utils import demo, fichiers
from tests.aides_http import base_http, client_http
from tests.aides_sources import modules_app, operations_montees

#: Le cas zéro : 70 routes du périmètre au 13/10/2026.
MINIMUM_PERIMETRE = 60


@pytest.fixture
def en_demo(monkeypatch):
    monkeypatch.setattr(get_settings(), "mode_demo", "oui")


@pytest.fixture
def moteur():
    with base_http() as moteur:
        yield moteur


def _montees() -> set[tuple[str, str]]:
    return {(m, c) for m, c, _r in operations_montees(app) if m != "HEAD"}


def _dans_le_perimetre(methode: str, chemin: str) -> bool:
    return any(
        (methodes is None or methode in methodes) and re.search(motif, chemin)
        for methodes, motif in demo.PERIMETRE
    )


def _fermes() -> set[tuple[str, str]]:
    return {geste for famille in demo.GESTES_FERMES for geste in famille.gestes}


# ── 1. Le réglage ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("valeur", ["oui", "OUI", " oui ", "1", "true", "yes", "on"])
def test_les_valeurs_qui_allument_la_demo(valeur):
    assert demo.est_demo(valeur)


@pytest.mark.parametrize("valeur", ["", "non", "0", "false", "ouii", "démo"])
def test_une_valeur_absente_ou_mal_ecrite_n_allume_rien(valeur):
    assert not demo.est_demo(valeur)


def test_le_reglage_ne_se_lit_qu_ici():
    """`mode_demo` ne s'écrit que dans `utils/demo.py` et dans `Settings`."""
    lecteurs = [
        m.rel
        for m in modules_app()
        if "mode_demo" in m.source and m.rel not in ("utils/demo.py", "config.py")
    ]
    assert lecteurs == [], lecteurs


# ── 2. Le registre suit les routes ──────────────────────────────────────────


def test_cas_zero_le_perimetre_voit_les_routes():
    vues = [op for op in _montees() if _dans_le_perimetre(*op)]
    assert len(vues) >= MINIMUM_PERIMETRE, (
        f"{len(vues)} route(s) dans le périmètre : le parcours des routes ne mesure plus rien"
    )


def test_toute_route_du_perimetre_est_fermee_ou_ouverte_expres():
    fermes, ouverts = _fermes(), set(demo.OUVERTS_EXPRES)
    oubliees = sorted(
        op for op in _montees() if _dans_le_perimetre(*op) and op not in fermes | ouverts
    )
    assert oubliees == [], (
        "routes du périmètre du mode démo ni fermées ni ouvertes exprès — les déclarer "
        f"dans `utils/demo.GESTES_FERMES` ou `OUVERTS_EXPRES`, avec leur raison : {oubliees}"
    )


def test_rien_n_est_declare_pour_une_route_qui_n_existe_pas():
    montees = _montees()
    fantomes = sorted((_fermes() | set(demo.OUVERTS_EXPRES)) - montees)
    assert fantomes == [], (
        f"déclarées dans `utils/demo` mais absentes de l'application : {fantomes}"
    )


def test_un_geste_n_est_pas_a_la_fois_ferme_et_ouvert():
    assert _fermes() & set(demo.OUVERTS_EXPRES) == set()


@pytest.mark.parametrize(
    ("methode", "chemin", "famille"),
    [
        ("PATCH", "/admin/utilisateurs/12", "Identité des comptes partagés"),
        ("POST", "/admin/utilisateurs/12/ajouter-role", "Identité des comptes partagés"),
        ("HEAD", "/config/whatsapp-qr", "Canaux d'envoi"),
        ("POST", "/auth/register/", "Inscription et comptes anonymes"),
        ("GET", "/admin/utilisateurs/12", None),
        ("POST", "/auth/login", None),
        ("POST", "/admin/utilisateurs/12/ajouter-role/autre", None),
    ],
)
def test_famille_fermee_reconnait_les_chemins_concrets(methode, chemin, famille):
    trouvee = demo.famille_fermee(methode, chemin)
    assert (trouvee.nom if trouvee else None) == famille


# ── 3. La garde, par de vraies requêtes ─────────────────────────────────────


def test_hors_demo_la_garde_laisse_passer(moteur):
    http, _ = client_http(moteur, None)
    reponse = http.post("/auth/register", json={})
    assert reponse.status_code == 422, "hors démo, l'inscription répond comme toujours"
    assert http.get("/config").json()[demo.CLE_PUBLIQUE] == "0"


def test_en_demo_un_geste_ferme_recoit_403(moteur, en_demo):
    http, _ = client_http(moteur, None)
    reponse = http.post("/auth/register", json={})
    assert reponse.status_code == 403
    assert reponse.json()["detail"].startswith(demo.MESSAGE)
    assert http.get("/config").json()[demo.CLE_PUBLIQUE] == "1"


def test_en_demo_l_administrateur_ne_reconfigure_rien(moteur, en_demo):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    assert http.put("/config", json={"smtp_server": "ailleurs.example"}).status_code == 403
    assert http.post("/admin/utilisateurs/1/retirer-role", json={}).status_code == 403


def test_en_demo_un_geste_ouvert_reste_ouvert(moteur, en_demo):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    assert http.get("/config/services").status_code == 200


def test_le_mode_demo_ne_s_ecrit_pas_depuis_l_interface(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    assert http.put("/config", json={demo.CLE_PUBLIQUE: "0"}).status_code == 422


# ── 4. Les fichiers reçus, à leur porte ─────────────────────────────────────


def test_en_demo_la_porte_des_fichiers_refuse(en_demo):
    with pytest.raises(HTTPException) as refus:
        fichiers.enregistrer_fichier_recu(b"\x89PNG", "a.png", "image/png", "image", "photos")
    assert refus.value.status_code == 403


def test_hors_demo_la_porte_des_fichiers_ne_refuse_pas_pour_la_demo():
    demo.refuser_fichier_recu()  # ne lève rien
