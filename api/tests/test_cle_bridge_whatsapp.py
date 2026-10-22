"""La clé du bridge WhatsApp : une source, un lecteur, toujours en en-tête (#1596).

## Ce que l'audit du 02/10/2026 a trouvé

La clé vivait DEUX fois : dans `.env` (`WHATSAPP_API_KEY`), que compose donne au
bridge, et dans `ConfigSite.whatsapp_api_key`, saisie à l'écran d'administration
et relue par l'API à cinq endroits (trois dans `utils/whatsapp.py`, le moniteur
de santé, le QR de l'administration). Rien ne confrontait les deux : un écart ne
se voyait qu'au 401 de l'envoi. Et le bridge acceptait la clé en paramètre
d'URL, où elle finit dans les journaux d'accès (`standards/03` §4).

## Ce que ces tests tiennent

- l'API lit la clé dans l'ENVIRONNEMENT, par `entetes_bridge` et nulle part
  ailleurs ; la base ne peut plus la recevoir ;
- chaque requête au bridge la porte en EN-TÊTE, jamais dans l'URL ;
- un 401 du bridge se nomme (« clé refusée »), au lieu de passer pour une panne.

Côté bridge — valeur d'exemple, clé trop courte ou vide refusées au démarrage,
`?apikey=` ignoré : `whatsapp-bridge/tests/contrat-http.test.js`.
"""

from __future__ import annotations

import ast

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.models.core import ConfigSite, RoleUtilisateur
from app.routers.config import save_config
from app.utils import whatsapp as W
from tests.aides_base import compte
from tests.aides_sources import modules_app

CLE = "cle-de-test-assez-longue-0123456789"


@pytest.fixture()
def cle_env(monkeypatch):
    """La clé posée dans l'environnement, comme compose le fait (`env_file`)."""
    monkeypatch.setenv("WHATSAPP_API_KEY", CLE)
    get_settings.cache_clear()
    yield CLE
    get_settings.cache_clear()


def test_la_cle_vient_de_l_environnement(cle_env):
    assert W.entetes_bridge() == {"x-api-key": cle_env}
    assert W.entetes_bridge(json=True) == {
        "x-api-key": cle_env,
        "Content-Type": "application/json",
    }


# ── Chaque requête au bridge : la clé en en-tête, jamais dans l'URL ────────

_CONFIG = {
    "whatsapp_enabled": "1",
    "whatsapp_api_url": "http://whatsapp-bridge:8090/",
    "whatsapp_group_jid": "123@g.us",
}


class _Reponse:
    def __init__(self, code: int):
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return {"state": "open"}


def _client_espion(appels: list, code: int = 200):
    class Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, headers=None, **k):
            appels.append((url, headers or {}, k))
            return _Reponse(code)

    return Client


def _sans_cle_dans_l_url(url: str, params: dict) -> None:
    assert CLE not in url and "apikey" not in url.lower(), url
    assert not params.get("params"), params


def test_le_statut_porte_la_cle_en_en_tete(cle_env, monkeypatch):
    appels: list = []
    monkeypatch.setattr(W.httpx, "Client", _client_espion(appels))
    assert W.get_whatsapp_status(_CONFIG) == {"state": "open"}
    ((url, entetes, params),) = appels
    assert url == "http://whatsapp-bridge:8090/status"
    assert entetes["x-api-key"] == cle_env
    _sans_cle_dans_l_url(url, params)


def test_l_envoi_porte_la_cle_en_en_tete(cle_env, monkeypatch):
    appels: list = []

    class _Ok:
        def json(self):
            return {"ok": True}

    def poster(url, payload, headers):
        appels.append((url, headers))
        return _Ok()

    monkeypatch.setattr(W, "_poster_au_bridge", poster)
    W.envoyer_whatsapp_raw("t", _CONFIG)
    W.envoyer_whatsapp("Titre", "Contenu", False, None, None, _CONFIG)
    assert len(appels) == 2
    for url, entetes in appels:
        assert url == "http://whatsapp-bridge:8090/send"
        assert entetes["x-api-key"] == cle_env
        _sans_cle_dans_l_url(url, {})


def test_un_401_du_bridge_se_nomme_sans_citer_la_cle(cle_env, monkeypatch):
    monkeypatch.setattr(W.httpx, "Client", _client_espion([], code=401))
    with pytest.raises(W.CleBridgeRefusee) as refus:
        W.get_whatsapp_status(_CONFIG)
    assert "WHATSAPP_API_KEY" in str(refus.value)
    assert cle_env not in str(refus.value)


def test_le_moniteur_de_sante_dit_clé_refusée_et_non_injoignable(session, monkeypatch):
    from app.utils.health_monitor import _check_whatsapp

    for cle, valeur in _CONFIG.items():
        session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()

    def refuse(_config):
        raise W.CleBridgeRefusee("Le bridge WhatsApp refuse la clé de l'API")

    monkeypatch.setattr(W, "get_whatsapp_status", refuse)
    assert _check_whatsapp(session) == ["Le bridge WhatsApp refuse la clé de l'API"]


# ── La base ne reçoit plus la clé ──────────────────────────────────────────


def test_l_enregistrement_de_la_configuration_refuse_la_cle(session):
    admin = compte(session, prefixe="admin", role=RoleUtilisateur.admin)
    with pytest.raises(HTTPException) as refus:
        save_config({"whatsapp_api_key": "x" * 20}, user=admin, session=session)
    assert refus.value.status_code == 422
    assert "WHATSAPP_API_KEY" in refus.value.detail
    assert session.get(ConfigSite, "whatsapp_api_key") is None


# ── Une source, un lecteur ─────────────────────────────────────────────────

#: Où chaque littéral a le droit d'apparaître, et pourquoi. Chaque entrée doit
#: SERVIR : une exception qui ne sert plus se retire (cas zéro, `standards/04` §2).
_LITTERAUX_PERMIS = {
    #  Le refus de la clé à l'enregistrement : c'est lui qui la nomme — la liste
    #  blanche des réglages depuis #2055 (`reglages.REFUSEES`), plus `routers/config.py`.
    "whatsapp_api_key": {"utils/reglages.py"},
    #  L'en-tête du bridge — et celui d'Anthropic, autre service, autre clé.
    "x-api-key": {"utils/whatsapp.py", "utils/llm_fournisseurs.py"},
}


def _porteurs(litteral: str) -> set[str]:
    return {
        m.rel
        for m in modules_app()
        if any(isinstance(n, ast.Constant) and n.value == litteral for n in ast.walk(m.arbre))
    }


@pytest.mark.parametrize("litteral", sorted(_LITTERAUX_PERMIS))
def test_la_cle_du_bridge_n_a_qu_un_lecteur(litteral):
    porteurs = _porteurs(litteral)
    permis = _LITTERAUX_PERMIS[litteral]
    assert porteurs <= permis, (
        f"« {litteral} » écrit hors de {sorted(permis)} : {sorted(porteurs - permis)}. "
        "La clé du bridge se lit par `utils/whatsapp.entetes_bridge()`, dans "
        "l'environnement — jamais dans ConfigSite, jamais en paramètre d'URL."
    )
    assert porteurs == permis, f"exception qui ne sert plus : {sorted(permis - porteurs)}"
