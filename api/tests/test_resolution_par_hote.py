"""La copropriété se résout par le nom d'hôte (#1751, P2-9).

Spec `specs/architecture/multi-coproprietes.md` §4.1 :

1. **résolution par nom d'hôte**, jamais par un paramètre ni un en-tête libre ;
2. **un hôte inconnu ne résout rien** — 421 (« requête mal dirigée », arbitrage
   du 10/10/2026), jamais une copropriété « par défaut ».

Phase 2, une copropriété par installation : son registre porte le nom de son
`ORIGIN` et ceux de `HOTES_COPROPRIETE`. Une IP privée ou un nom interne
(`localhost`, `api`) — les sondes et scripts des nœuds, le rendu côté serveur
du front — la désigne TANT QU'ELLE EST SEULE : avec deux copropriétés, ils ne
désignent plus personne. `/health` répond à tout hôte : c'est une question sur
la plateforme, pas sur une copropriété.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import contexte
from app.main import app as application
from tests.aides_processus import SERVEUR_INJOIGNABLE


@pytest.fixture()
def origine(monkeypatch):
    """Le registre de l'installation : un nom public, un nom de plus."""
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "origin", "https://5hostachy.fr")
    monkeypatch.setattr(s, "hotes_copropriete", "testserver, Residence.example ")
    return s


@pytest.mark.parametrize(
    "hote",
    ["5hostachy.fr", "5HOSTACHY.fr", "5hostachy.fr:443", "residence.example", "testserver"],
)
def test_un_hote_declare_resout_la_copropriete(origine, hote):
    assert contexte.copropriete_de_l_hote(hote).identifiant == contexte.IDENTIFIANT_UNIQUE


@pytest.mark.parametrize(
    "hote", ["10.0.0.23", "10.0.0.22:80", "127.0.0.1", "localhost", "api", "api:8000"]
)
def test_ip_privee_et_noms_internes_tant_qu_elle_est_seule(origine, hote):
    assert contexte.copropriete_de_l_hote(hote) is not None


@pytest.mark.parametrize("hote", ["autre.example", "8.8.8.8", "", "5hostachy.fr.evil.example"])
def test_un_hote_inconnu_ne_resout_rien(origine, hote):
    assert contexte.copropriete_de_l_hote(hote) is None


def test_avec_deux_coproprietes_une_ip_ne_designe_plus_personne(origine, monkeypatch):
    seule = contexte.courante()
    autre = contexte.Copropriete(
        identifiant="voisine",
        url_base=f"postgresql+psycopg://voisine@{SERVEUR_INJOIGNABLE}/voisine",
        racine_fichiers=seule.racine_fichiers,
        secret=seule.secret,
        expediteur=seule.expediteur,
        nom_expediteur=seule.nom_expediteur,
    )
    monkeypatch.setattr(
        contexte,
        "registre",
        lambda: {
            seule.identifiant: (seule, frozenset({"5hostachy.fr"})),
            "voisine": (autre, frozenset({"voisine.example"})),
        },
    )
    assert contexte.copropriete_de_l_hote("voisine.example").identifiant == "voisine"
    assert contexte.copropriete_de_l_hote("5hostachy.fr").identifiant == seule.identifiant
    assert contexte.copropriete_de_l_hote("10.0.0.23") is None
    assert contexte.copropriete_de_l_hote("localhost") is None


# ── À l'entrée, par le middleware ────────────────────────────────────────────


def test_un_hote_inconnu_recoit_421_sans_rien_lire(origine):
    reponse = TestClient(application).get("/config", headers={"host": "autre.example"})
    assert reponse.status_code == 421
    assert "autre.example" not in reponse.text  # rien de ce qu'il a envoyé ne revient


def test_la_sante_repond_a_tout_hote(origine):
    reponse = TestClient(application).get("/health", headers={"host": "autre.example"})
    assert reponse.status_code == 200


def test_la_copropriete_resolue_est_celle_de_la_requete(origine, monkeypatch):
    """Un contexte par requête : l'hôte de A sert A, celui de B sert B — et hors requête,
    la seule copropriété de la phase 2."""
    seule = contexte.courante()
    autre = contexte.Copropriete(
        identifiant="voisine",
        url_base=f"postgresql+psycopg://voisine@{SERVEUR_INJOIGNABLE}/voisine",
        racine_fichiers=seule.racine_fichiers,
        secret=seule.secret,
        expediteur=seule.expediteur,
        nom_expediteur=seule.nom_expediteur,
    )
    monkeypatch.setattr(
        contexte,
        "registre",
        lambda: {
            seule.identifiant: (seule, frozenset({"a.example"})),
            "voisine": (autre, frozenset({"b.example"})),
        },
    )
    banc = FastAPI()
    banc.add_middleware(contexte.ResolutionCopropriete)

    @banc.get("/qui")
    def qui():
        return {"copropriete": contexte.courante().identifiant}

    client = TestClient(banc)
    assert client.get("/qui", headers={"host": "a.example"}).json() == {
        "copropriete": seule.identifiant
    }
    assert client.get("/qui", headers={"host": "b.example"}).json() == {"copropriete": "voisine"}
    assert client.get("/qui", headers={"host": "c.example"}).status_code == 421
    assert contexte.courante().identifiant == seule.identifiant
