"""Les gestes aboutis : ouvertures et envois d'un formulaire, COMPTÉS à part et sans compte (#1633).

## Ce que ces tests tiennent

- une ouverture (`ACTION_OUVERTURE`) et un envoi (`ACTION_ENVOI`) arrivent par la
  collecte publique et deviennent un compteur de `geste_formulaire` — jamais une
  ligne de `telemetry_event`, où le tableau de bord les compterait comme des
  pages vues ;
- le compteur ne porte AUCUN identifiant de compte, et le refus de la mesure
  d'audience le coupe aussi ;
- un `detail` qui n'a pas la forme d'un identifiant de geste (`objet.verbe`) ne
  s'enregistre pas : jamais un texte saisi ;
- la synthèse rend ouvertures, envois et taux par geste ; la purge retire ce qui
  dépasse `CONSERVATION_JOURS`.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models.core import RoleUtilisateur
from app.models.telemetrie import GesteFormulaire, TelemetryEvent
from app.utils import horloge
from app.utils.gestes_formulaire import (
    ACTION_ENVOI,
    ACTION_OUVERTURE,
    CONSERVATION_JOURS,
    purger_gestes,
    synthese_gestes,
)
from tests.aides_base import moteur_de_test
from tests.aides_http import base_http, client_http

ROUTE = "/telemetry/collect"


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def _ev(action: str, geste: str = "affaire.creer", page: str = "/tickets") -> dict:
    return {"page": page, "action": action, "detail": geste}


def _compteurs(moteur) -> list[GesteFormulaire]:
    with Session(moteur) as s:
        return list(s.exec(select(GesteFormulaire)).all())


def test_ouvertures_et_envois_sont_comptes_a_part_et_pas_comme_des_vues(moteur):
    corps = {
        "events": [
            {"page": "/tickets"},
            _ev(ACTION_OUVERTURE),
            _ev(ACTION_OUVERTURE),
            _ev(ACTION_ENVOI),
        ]
    }
    assert TestClient(app).post(ROUTE, json=corps).status_code == 204
    with Session(moteur) as s:
        vues = s.exec(select(TelemetryEvent)).all()
    assert [v.page for v in vues] == ["/tickets"], "un geste est passé pour une vue"
    (ligne,) = _compteurs(moteur)
    assert (ligne.geste, ligne.ouvertures, ligne.envois) == ("affaire.creer", 2, 1)
    assert ligne.jour == horloge.aujourd_hui().isoformat()


def test_le_compteur_ne_sait_pas_qui_et_le_refus_le_coupe(moteur):
    colonnes = set(GesteFormulaire.model_fields)
    assert not {c for c in colonnes if "user" in c or "utilisateur" in c}, colonnes
    http, _ = client_http(moteur, RoleUtilisateur.résident, opt_out_telemetrie=True)
    assert http.post(ROUTE, json={"events": [_ev(ACTION_OUVERTURE)]}).status_code == 204
    assert _compteurs(moteur) == []


@pytest.mark.parametrize(
    "detail",
    [None, "", "Mon titre d'affaire", "affaire.creer avec un texte", "AFFAIRE.CREER", "a" * 60],
)
def test_un_detail_qui_n_est_pas_un_identifiant_de_geste_ne_s_enregistre_pas(moteur, detail):
    ev = {"page": "/tickets", "action": ACTION_ENVOI, "detail": detail}
    assert TestClient(app).post(ROUTE, json={"events": [ev]}).status_code == 204
    assert _compteurs(moteur) == []


def test_la_synthese_rend_le_taux_par_geste():
    moteur = moteur_de_test()
    jour = horloge.aujourd_hui().isoformat()
    with Session(moteur) as s:
        #  Deux lignes pour un même couple (deux collectes simultanées) : additionnées.
        s.add(GesteFormulaire(jour=jour, geste="affaire.creer", ouvertures=3, envois=1))
        s.add(GesteFormulaire(jour=jour, geste="affaire.creer", ouvertures=1, envois=1))
        s.add(GesteFormulaire(jour=jour, geste="sondage.voter", ouvertures=0, envois=2))
        s.commit()
        lignes = {g["geste"]: g for g in synthese_gestes(s, horloge.aujourd_hui())}
    assert lignes["affaire.creer"] == {
        "geste": "affaire.creer",
        "ouvertures": 4,
        "envois": 2,
        "taux": 50,
    }
    #  Sans ouverture, pas de taux : un envoi sans ouverture mesurée ne fait pas 100 %.
    assert lignes["sondage.voter"]["taux"] is None


def test_la_purge_retire_ce_qui_depasse_la_conservation():
    moteur = moteur_de_test()
    aujourd_hui = horloge.aujourd_hui()
    with Session(moteur) as s:
        for age in (0, CONSERVATION_JOURS, CONSERVATION_JOURS + 1):
            jour = (aujourd_hui - timedelta(days=age)).isoformat()
            s.add(GesteFormulaire(jour=jour, geste=f"age.j{age}", ouvertures=1))
        s.commit()
        assert purger_gestes(s, aujourd_hui) == 1
        restants = sorted(g.geste for g in s.exec(select(GesteFormulaire)).all())
    assert restants == ["age.j0", f"age.j{CONSERVATION_JOURS}"]


@pytest.mark.parametrize("scope", ["jour", "mois", "annee", "total"])
def test_le_tableau_de_bord_rend_les_gestes(moteur, scope):
    TestClient(app).post(ROUTE, json={"events": [_ev(ACTION_OUVERTURE), _ev(ACTION_ENVOI)]})
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    d = http.get("/telemetry/dashboard", params={"scope": scope}).json()
    assert d["gestes"] == [{"geste": "affaire.creer", "ouvertures": 1, "envois": 1, "taux": 100}]
    assert d["kpi"].get("vues", 0) == 0, "un geste a été compté comme une page vue"
