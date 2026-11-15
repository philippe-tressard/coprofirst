"""Le serveur ne casse aucune version publiée des apps (#2744).

Le contrat COURANT est comparé au contrat FIGÉ de chaque version en circulation
(`app/contrat/circulation.py`) par le jugement du contrat lui-même
(`inventaire.comparer`) : une opération retirée, un champ de réponse retiré ou
retypé, une entrée requise neuve casseraient l'app installée.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.contrat import circulation as circ
from app.contrat import inventaire as inv


@pytest.fixture(scope="module")
def courant():
    from app.main import app

    return inv.inventaire(app.openapi())


def test_aucune_version_publiee_n_est_cassee(courant):
    """LE garde-fou, requis sur chaque PR (suite pytest)."""
    assert circ.ruptures(courant) == []


def test_retirer_une_route_de_l_ios_1_0_fait_passer_le_controle_au_rouge(courant):
    """Faute injectée sur le VRAI contrat : une route que la 1.0 a compilée disparaît."""
    ios = next(v for v in circ.EN_CIRCULATION if v.nom == "coprofirst-ios 1.0")
    retiree = sorted(circ.contrat_fige(ios)["operations"])[0]
    ampute = {k: op for k, op in courant.items() if k != retiree}
    assert any(retiree in m for m in circ.ruptures(ampute, (ios,)))


def test_chaque_contrat_fige_est_celui_de_son_plancher():
    """Un contrat figé se relit : sa forme et son empreinte sont celles d'une référence."""
    assert circ.EN_CIRCULATION, "cas zéro : aucune version déclarée ne protège rien"
    for v in circ.EN_CIRCULATION:
        fige = circ.contrat_fige(v)
        assert set(fige) == {"version", "empreinte", "operations"}, v.nom
        assert fige["empreinte"] == inv.empreinte(fige["operations"]), v.nom
        assert len(fige["operations"]) > 100, v.nom


# ── Le contrôle lui-même, sur une faute injectée ───────────────────────────────


@pytest.fixture
def version_essai(tmp_path, monkeypatch):
    """Une version publiée dont on écrit le contrat figé."""
    monkeypatch.setattr(circ, "DOSSIER", tmp_path)
    v = circ.VersionPubliee("app-essai", "9.9", "v0.0.0", "essai")

    def figer(operations):
        v.fichier.write_text(
            json.dumps({"version": "1.0.0", "empreinte": "", "operations": operations})
        )
        return v

    return figer


def _op(reponse=None, entree=()):
    return {"deprecie": False, "entree": list(entree), "reponse": reponse or {"$": "objet"}}


def test_une_route_retiree_qu_emploie_une_version_publiee_est_refusee(version_essai):
    fige = {"GET /a": _op(), "GET /b": _op()}
    v = version_essai(fige)
    assert circ.ruptures({"GET /a": _op()}, (v,), {}) == [
        "app-essai 9.9 : GET /b — la version publiée s'en sert peut-être"
    ]


def test_un_champ_retire_et_une_entree_requise_neuve_sont_refuses(version_essai):
    fige = {"GET /a": _op({"$": "objet", "$.nom": "string"})}
    v = version_essai(fige)
    courant = {"GET /a": _op({"$": "objet"}, entree=["corps.neuf"])}
    messages = circ.ruptures(courant, (v,), {})
    assert any("GET /a → $.nom" in m for m in messages)
    assert any("GET /a ← corps.neuf" in m for m in messages)


def test_un_ajout_ne_casse_rien(version_essai):
    v = version_essai({"GET /a": _op()})
    assert circ.ruptures({"GET /a": _op(), "GET /neuve": _op()}, (v,), {}) == []


def test_une_derogation_declaree_passe_puis_echoit_et_ne_sert_plus(version_essai):
    v = version_essai({"GET /a": _op(), "GET /b": _op()})
    derog = {("app-essai 9.9", "GET /b"): ("15/11/2026", "non employée", "2026-12-31")}
    courant = {"GET /a": _op()}
    assert circ.ruptures(courant, (v,), derog, date(2026, 11, 15)) == []
    assert any("échue" in m for m in circ.ruptures(courant, (v,), derog, date(2027, 1, 1)))
    inutile = circ.ruptures({"GET /a": _op(), "GET /b": _op()}, (v,), derog, date(2026, 11, 15))
    assert any("ne sert plus" in m for m in inutile)
