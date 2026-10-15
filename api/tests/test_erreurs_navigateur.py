"""Les erreurs vues dans le navigateur sont COMPTÉES, à part et sans compte (#1631).

## Ce que ces tests tiennent

- un signalement (`action = ACTION_ERREUR`) arrive par la collecte publique et
  devient un compteur de `erreur_navigateur` — jamais une ligne de
  `telemetry_event`, où le tableau de bord le compterait comme une page vue ;
- le compteur ne porte AUCUN identifiant de compte, même quand la session est
  ouverte, et le refus de la mesure d'audience le coupe aussi ;
- le tableau de bord rend les erreurs sans toucher aux pages vues ;
- la synthèse additionne les lignes en double, la purge retire ce qui dépasse
  `CONSERVATION_JOURS`.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models.core import RoleUtilisateur
from app.models.telemetrie import ErreurNavigateur, TelemetryEvent
from app.utils import horloge
from app.utils.erreurs_navigateur import (
    ACTION_ERREUR,
    CONSERVATION_JOURS,
    purger_erreurs,
    synthese_erreurs,
)
from tests.aides_base import moteur_de_test
from tests.aides_http import base_http, client_http

ROUTE = "/telemetry/collect"


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def _erreur(page: str = "/tickets", code: str = "svelte:each_key_duplicate") -> dict:
    return {"page": page, "action": ACTION_ERREUR, "detail": code}


def _compteurs(moteur) -> list[ErreurNavigateur]:
    with Session(moteur) as s:
        return list(s.exec(select(ErreurNavigateur)).all())


def _vues(moteur) -> list[TelemetryEvent]:
    with Session(moteur) as s:
        return list(s.exec(select(TelemetryEvent)).all())


def test_un_signalement_est_compte_a_part_et_pas_comme_une_vue(moteur):
    corps = {"events": [{"page": "/tickets"}, _erreur(), _erreur()]}
    reponse = TestClient(app).post(ROUTE, json=corps)
    assert reponse.status_code == 204, reponse.text

    assert [e.page for e in _vues(moteur)] == ["/tickets"], "le signalement est passé pour une vue"
    (ligne,) = _compteurs(moteur)
    assert (ligne.page, ligne.code, ligne.total) == ("/tickets", "svelte:each_key_duplicate", 2)
    assert ligne.jour == horloge.aujourd_hui().isoformat()


def test_le_compteur_ne_sait_pas_qui_meme_session_ouverte(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.résident)
    assert http.post(ROUTE, json={"events": [_erreur()]}).status_code == 204
    colonnes = set(ErreurNavigateur.model_fields)
    assert not {c for c in colonnes if "user" in c or "utilisateur" in c}, colonnes
    assert len(_compteurs(moteur)) == 1


def test_le_refus_de_la_mesure_coupe_aussi_les_signalements(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.résident, opt_out_telemetrie=True)
    assert http.post(ROUTE, json={"events": [_erreur()]}).status_code == 204
    assert _compteurs(moteur) == []


@pytest.mark.parametrize("scope", ["jour", "mois", "annee"])
def test_le_tableau_de_bord_rend_les_erreurs_sans_les_compter_en_vues(moteur, scope):
    TestClient(app).post(ROUTE, json={"events": [_erreur(), _erreur("/accueil", "HTTP 502 /flux")]})
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    reponse = http.get("/telemetry/dashboard", params={"scope": scope})
    assert reponse.status_code == 200, reponse.text
    donnees = reponse.json()

    assert {(e["page"], e["code"], e["total"]) for e in donnees["erreurs"]} == {
        ("/tickets", "svelte:each_key_duplicate", 1),
        ("/accueil", "HTTP 502 /flux", 1),
    }
    assert donnees["kpi"]["vues"] == 0, "un signalement a été compté comme une page vue"


def test_la_synthese_additionne_les_lignes_en_double():
    """Deux collectes simultanées peuvent créer deux lignes pour le même couple."""
    moteur = moteur_de_test()
    instant = horloge.maintenant()
    jour = horloge.jour_civil(instant).isoformat()
    with Session(moteur) as s:
        for total in (2, 3):
            s.add(
                ErreurNavigateur(
                    jour=jour,
                    page="/p",
                    code="c",
                    total=total,
                    premiere_le=instant,
                    derniere_le=instant,
                )
            )
        s.commit()
        (ligne,) = synthese_erreurs(s, horloge.aujourd_hui())
    assert ligne["total"] == 5


def test_la_purge_retire_ce_qui_depasse_la_conservation():
    moteur = moteur_de_test()
    aujourd_hui = horloge.aujourd_hui()
    instant = horloge.maintenant()
    with Session(moteur) as s:
        for age in (0, CONSERVATION_JOURS, CONSERVATION_JOURS + 1):
            s.add(
                ErreurNavigateur(
                    jour=(aujourd_hui - timedelta(days=age)).isoformat(),
                    page=f"/age-{age}",
                    code="c",
                    total=1,
                    premiere_le=instant,
                    derniere_le=instant,
                )
            )
        s.commit()
        assert purger_erreurs(s, aujourd_hui) == 1
        restantes = sorted(e.page for e in s.exec(select(ErreurNavigateur)).all())
    assert restantes == ["/age-0", f"/age-{CONSERVATION_JOURS}"]
