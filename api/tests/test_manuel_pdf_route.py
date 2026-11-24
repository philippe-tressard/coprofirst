"""La route du manuel en PDF : `GET /manuel/pdf` (#2914).

`test_manuel_pdf.py` tient la COMPOSITION du document ; la route, elle, n'était
appelée par aucun test — le contrôle des routeurs nommés la croyait couverte par
le mot « manuel ». Ce fichier tient ce qu'elle décide : elle est publique (un
manuel se lit avant de savoir se servir du site), elle sert un PDF nommé d'après
la résidence et le jour, et une panne du rendu répond 502, pas 500. Le rendu est
remplacé : WeasyPrint n'est pas au poste, et ce n'est pas ce qu'on juge ici.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

import app.routers.manuel as route_manuel
from app.models.core import ConfigSite
from app.utils import horloge
from app.utils.manuel_pdf import ManuelIndisponible
from tests.aides_http import base_http, client_http

URL = "/manuel/pdf"


@pytest.fixture
def anonyme():
    with base_http() as moteur:
        #  Un nom ASCII : un nom accentué part aujourd'hui en latin-1 dans l'en-tête
        #  (#2985) — le cas « Ma Résidence » s'ajoutera ici avec son correctif.
        with Session(moteur) as s:
            s.add(ConfigSite(cle="site_nom", valeur="Les Tilleuls"))
            s.commit()
        http, _ = client_http(moteur, None)
        yield http


def test_un_anonyme_recoit_le_pdf(anonyme, monkeypatch):
    recu = {}

    def _rendu(**identite):
        recu.update(identite)
        return b"%PDF-1.7 essai"

    monkeypatch.setattr(route_manuel, "generer_manuel_pdf", _rendu)

    r = anonyme.get(URL)

    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == b"%PDF-1.7 essai"
    disposition = r.headers["content-disposition"]
    jour = f"{horloge.aujourd_hui():%Y-%m-%d}"
    assert disposition == f'inline; filename="manuel-utilisateur-les-tilleuls-{jour}.pdf"'
    assert recu["site_nom"] == "Les Tilleuls", "l'identité du manuel vient de la résidence"


def test_une_panne_du_rendu_repond_502(anonyme, monkeypatch):
    def _panne(**_):
        raise ManuelIndisponible("le site ne répond pas")

    monkeypatch.setattr(route_manuel, "generer_manuel_pdf", _panne)

    r = anonyme.get(URL)

    assert r.status_code == 502
    assert "le site ne répond pas" in r.json()["detail"]
