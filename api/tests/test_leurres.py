"""Les leurres de l'application : chacun éprouvé, et un seul registre (#2365).

Voir `app/utils/leurres.py`. Ce qui est vérifié ici :

1. une connexion sur le faux compte rend le même 401 qu'un mauvais mot de passe
   et journalise `connexion_leurre` — sans leurre posé, rien ne change ;
2. la fausse clé de maintenance rend le même 403 qu'une clé fausse et journalise
   `cle_maintenance_leurre` — et ne ferme jamais le canal si elle égale la vraie ;
3. le registre est celui du `Caddyfile` (un `handle` par route, le faux fichier
   lit les MÊMES variables), de `docker-compose.yml` et de S6
   (`lib-audit-acces.sh`), et chaque évènement est un code de `_NIVEAUX`.
"""

from __future__ import annotations

import logging
import pathlib
import re
import subprocess

import pytest
from fastapi import HTTPException, Response

from app.auth.cle_maintenance import exiger_cle_maintenance
from app.config import get_settings
from app.routers import auth
from app.routers.auth_schemas import LoginRequest
from app.utils import journal_securite
from app.utils.leurres import (
    EVENEMENTS_LEURRES,
    ROUTES_LEURRES,
    est_adresse_leurre,
    est_cle_maintenance_leurre,
)
from tests.conftest import requete_de_test

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_CADDYFILE = (_RACINE / "Caddyfile").read_text(encoding="utf-8")
_COMPOSE = (_RACINE / "docker-compose.yml").read_text(encoding="utf-8")
_S6 = _RACINE / "scripts" / "lib" / "lib-audit-acces.sh"

ADRESSE = "secours-leurre@exemple.invalid"
CLE_LEURRE = "cle-leurre-de-test"
VRAIE_CLE = "vraie-cle-de-maintenance"


@pytest.fixture()
def leurres(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "leurre_adresse", ADRESSE)
    monkeypatch.setattr(s, "leurre_cle_maintenance", CLE_LEURRE)
    monkeypatch.setattr(s, "maintenance_key", VRAIE_CLE)


def _connexion(session, email):
    return auth.login(
        requete_de_test("/auth/login"),
        body=LoginRequest(email=email, password="n-importe-lequel"),
        response=Response(),
        session=session,
    )


def _evenements(caplog) -> list[str]:
    return [
        r.getMessage().split()[1]
        for r in caplog.records
        if r.name == "securite" and r.getMessage().startswith("securite ")
    ]


# ── 1. Le faux compte ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("saisie", [ADRESSE, f"  {ADRESSE.upper()} "])
def test_une_connexion_sur_le_faux_compte_se_trahit(session, leurres, caplog, saisie):
    caplog.set_level(logging.INFO, logger="securite")
    with pytest.raises(HTTPException) as refus:
        _connexion(session, saisie)
    assert refus.value.status_code == 401
    assert refus.value.detail == "Email ou mot de passe incorrect."
    assert _evenements(caplog) == ["connexion_leurre"]


def test_sans_leurre_pose_la_meme_adresse_est_un_compte_inconnu(session, monkeypatch, caplog):
    """Cas zéro : un leurre vide n'attrape personne — pas même une adresse vide."""
    monkeypatch.setattr(get_settings(), "leurre_adresse", "")
    caplog.set_level(logging.INFO, logger="securite")
    assert not est_adresse_leurre("") and not est_adresse_leurre(None)
    with pytest.raises(HTTPException):
        _connexion(session, ADRESSE)
    assert _evenements(caplog) == ["connexion_refusee"]


def test_une_autre_adresse_n_est_pas_le_leurre(leurres):
    assert not est_adresse_leurre("secours-leurre@exemple.invalid.autre")
    assert not est_adresse_leurre("")


# ── 2. La fausse clé de maintenance ───────────────────────────────────────────


def test_la_fausse_cle_se_trahit_avec_le_meme_403(leurres, caplog):
    caplog.set_level(logging.INFO, logger="securite")
    with pytest.raises(HTTPException) as refus:
        exiger_cle_maintenance(CLE_LEURRE)
    assert (refus.value.status_code, refus.value.detail) == (403, "Clé maintenance invalide")
    assert _evenements(caplog) == ["cle_maintenance_leurre"]


def test_la_vraie_cle_passe_et_une_cle_fausse_ne_dit_rien(leurres, caplog):
    caplog.set_level(logging.INFO, logger="securite")
    exiger_cle_maintenance(VRAIE_CLE)
    with pytest.raises(HTTPException):
        exiger_cle_maintenance("autre-chose")
    assert _evenements(caplog) == []


def test_un_leurre_egal_a_la_vraie_cle_ne_ferme_pas_le_canal(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "maintenance_key", VRAIE_CLE)
    monkeypatch.setattr(s, "leurre_cle_maintenance", VRAIE_CLE)
    assert not est_cle_maintenance_leurre(VRAIE_CLE)
    exiger_cle_maintenance(VRAIE_CLE)


# ── 3. Un seul registre ───────────────────────────────────────────────────────


def test_chaque_route_leurre_est_servie_par_caddy():
    handles = re.findall(r"^\thandle (\S+) \{\n\t\timport leurre\n\t\}", _CADDYFILE, re.M)
    assert handles, "cas zéro : aucun `handle … import leurre` lu dans le Caddyfile"
    assert sorted(handles) == sorted(ROUTES_LEURRES)


def test_le_faux_fichier_lit_les_variables_que_lit_l_api():
    """`{$LEURRE_ADRESSE}` dans le Caddyfile, la même variable passée par compose, et
    le même nom côté API (`Settings.leurre_adresse`)."""
    for champ in ("leurre_adresse", "leurre_cle_maintenance"):
        variable = champ.upper()
        assert hasattr(get_settings(), champ)
        assert "{$" + variable + "}" in _CADDYFILE, f"le faux fichier ne montre pas {variable}"
        assert f"{variable}=${{{variable}:-}}" in _COMPOSE, (
            f"compose ne passe pas {variable} à Caddy"
        )


def _variable_s6(nom: str) -> str:
    sortie = subprocess.run(
        ["bash", "-c", f'source "{_S6}"; printf "%s" "${nom}"'],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert sortie, f"cas zéro : {nom} ne se lit plus dans {_S6.name}"
    return sortie


def test_s6_connait_les_routes_leurres_et_rien_d_autre():
    motif = re.compile(_variable_s6("ACCES_CHEMINS_LEURRES"))
    for route in ROUTES_LEURRES:
        assert motif.search(route), (
            f"S6 lirait la route leurre {route} servie en 200 comme une brèche"
        )
    for voisine in ("/.env.local", "/admin/backup.zip.old", "/api/v1/exports", "/x/.env"):
        assert not motif.search(voisine), f"S6 tiendrait la sonde {voisine} pour un leurre"


def test_s6_fait_un_fail_de_chaque_evenement_leurre():
    assert _variable_s6("ACCES_EVENEMENTS_LEURRES").split() == list(EVENEMENTS_LEURRES)
    for code in EVENEMENTS_LEURRES:
        assert journal_securite._NIVEAUX.get(code) == logging.WARNING, (
            f"{code} : WARNING dans _NIVEAUX (un ERROR bloquerait la MEP au point 6)"
        )
