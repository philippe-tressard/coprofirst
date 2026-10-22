"""L'adresse du bridge WhatsApp ne désigne que le bridge (#2151).

## 🔴 Pourquoi

`whatsapp_api_url` s'écrit par `PUT /config`, donc par l'administrateur de la
copropriété — qui n'est pas l'opérateur de la plateforme (#1750). Libre, elle
emmenait la clé du bridge (`x-api-key`, tenue hors de `ConfigSite` exprès,
#1596) vers l'hôte de son choix, et `GET /config/whatsapp-qr` lui rendait le
corps de n'importe quelle page du réseau interne.

## Ce que ces tests tiennent

1. La règle (`refus_adresse_bridge`) : le service Compose ou son conteneur, un
   port, rien d'autre.
2. L'écriture : `PUT /config` refuse une adresse étrangère, et n'écrit rien.
3. L'usage : une adresse étrangère déjà en base ne reçoit AUCUNE requête —
   ni envoi, ni statut, ni QR.
4. Le QR : ce qui n'est pas un PNG ne sort pas, et l'erreur ne cite pas l'hôte.
5. La porte : toute fonction qui pose la clé du bridge lit l'adresse par
   `adresse_du_bridge`, jamais par `config.get("whatsapp_api_url")`.
"""

from __future__ import annotations

import ast

import pytest
from fastapi import HTTPException
from sqlmodel import select

import app.utils.whatsapp as W
from app.models.core import ConfigSite
from app.routers.config import save_config, whatsapp_qr
from tests.aides_sources import modules_app

ETRANGERES = [
    "http://tiers.example",
    "https://tiers.example:8090",
    "http://10.0.0.5:8090",
    "http://whatsapp-bridge.tiers.example:8090",
    "http://whatsapp-bridge:8090@tiers.example",
    "http://user:mdp@whatsapp-bridge:8090",
    "http://whatsapp-bridge:8090/page",
    "http://whatsapp-bridge:8090/?x=",
    "file:///etc/passwd",
    "whatsapp-bridge:8090",
    "http://whatsapp-bridge:abc",
]


class _Admin:
    id = 1


# ── 1. La règle ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "http://whatsapp-bridge:8090",
        "http://whatsapp-bridge:8090/",
        "http://hostachy_whatsapp:8090",
    ],
)
def test_l_adresse_du_bridge_est_admise(url):
    assert W.refus_adresse_bridge(url) is None
    assert W.adresse_du_bridge({"whatsapp_api_url": url}) == url.rstrip("/")


@pytest.mark.parametrize("url", ETRANGERES)
def test_une_adresse_etrangere_est_refusee(url):
    assert W.refus_adresse_bridge(url)
    with pytest.raises(W.AdresseBridgeRefusee):
        W.adresse_du_bridge({"whatsapp_api_url": url})


def test_une_adresse_vide_n_est_pas_reglee():
    assert W.adresse_du_bridge({}) == "" and W.adresse_du_bridge({"whatsapp_api_url": " "}) == ""


# ── 2. L'écriture ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("url", ETRANGERES[:3])
def test_put_config_refuse_une_adresse_etrangere_et_n_ecrit_rien(session, url):
    with pytest.raises(HTTPException) as refus:
        save_config({"site_email": "admin@exemple.fr", "whatsapp_api_url": url}, _Admin(), session)
    assert refus.value.status_code == 422
    assert session.exec(select(ConfigSite)).all() == []


def test_put_config_accepte_de_vider_l_adresse(session):
    save_config({"whatsapp_api_url": ""}, _Admin(), session)
    assert session.get(ConfigSite, "whatsapp_api_url").valeur == ""


# ── 3. L'usage : rien ne part vers une adresse étrangère ─────────────────────


@pytest.fixture()
def reseau(monkeypatch):
    """Toute requête sortante est relevée — et aucune ne doit l'être."""
    appels: list = []

    class Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, **k):
            appels.append(url)
            raise AssertionError(f"requête vers {url}")

        post = get

    monkeypatch.setattr(W.httpx, "Client", Client)
    monkeypatch.setattr(W, "_poster_au_bridge", lambda url, *a, **k: appels.append(url))
    return appels


def test_une_adresse_etrangere_en_base_ne_recoit_aucune_requete(reseau):
    config = {
        "whatsapp_enabled": "1",
        "whatsapp_api_url": "http://tiers.example",
        "whatsapp_group_jid": "123@g.us",
    }
    W.envoyer_whatsapp("Titre", "Contenu", False, None, None, config)  # silencieux
    for geste in (W.envoyer_whatsapp_raw, W.get_whatsapp_status, W.qr_du_bridge):
        with pytest.raises(W.AdresseBridgeRefusee):
            geste(*(("t", config) if geste is W.envoyer_whatsapp_raw else (config,)))
    assert reseau == []


# ── 4. Le QR : une image PNG, ou une erreur qui ne cite rien ────────────────


def _bridge_qui_repond(monkeypatch, contenu: bytes):
    class Reponse:
        status_code = 200
        content = contenu

        def raise_for_status(self):
            pass

    class Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, **k):
            return Reponse()

    monkeypatch.setattr(W.httpx, "Client", Client)


def _regler_bridge(session):
    session.add(ConfigSite(cle="whatsapp_api_url", valeur="http://whatsapp-bridge:8090"))
    session.commit()


def test_le_qr_sert_une_image_png(session, monkeypatch):
    _regler_bridge(session)
    png = b"\x89PNG\r\n\x1a\n" + b"donnees"
    _bridge_qui_repond(monkeypatch, png)
    assert whatsapp_qr(_Admin(), session).body == png


def test_une_reponse_qui_n_est_pas_un_png_ne_sort_pas(session, monkeypatch):
    _regler_bridge(session)
    _bridge_qui_repond(monkeypatch, b"<html>page interne secrete</html>")
    with pytest.raises(HTTPException) as refus:
        whatsapp_qr(_Admin(), session)
    assert refus.value.status_code == 502
    assert "secrete" not in refus.value.detail and "html" not in refus.value.detail


# ── 5. La porte ──────────────────────────────────────────────────────────────


def _appels(fonction: ast.AST) -> set[str]:
    noms = set()
    for n in ast.walk(fonction):
        if isinstance(n, ast.Call):
            f = n.func
            noms.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
    return noms


def test_qui_pose_la_cle_du_bridge_lit_l_adresse_par_la_porte():
    vus, fautes = 0, []
    for m in modules_app():
        for f in ast.walk(m.arbre):
            if isinstance(f, ast.FunctionDef) and "entetes_bridge" in _appels(f):
                vus += 1
                if "adresse_du_bridge" not in _appels(f):
                    fautes.append(f"{m.rel}:{f.name}")
    assert vus >= 4, "moins de quatre appels au bridge relevés : le contrôle ne lit plus rien"
    assert not fautes, f"la clé du bridge part vers une adresse non vérifiée : {fautes}"
