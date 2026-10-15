"""Les durées d'affichage sont mesurées à part, sans compte, et résumées en centiles (#1632).

## Ce que ces tests tiennent

- une mesure (`action = ACTION_MESURE`) arrive par la collecte publique et
  devient une ligne de `mesure_affichage` — jamais une page vue ;
- une mesure mal formée (indicateur inconnu, durée hors bornes ou non
  numérique) ne s'enregistre pas ;
- le refus de la mesure d'audience la coupe aussi ;
- médiane et 75ᵉ centile au RANG le plus proche, par indicateur et par page,
  les pages les plus lentes d'abord ; la purge retire ce qui dépasse la
  conservation ;
- les indicateurs reconnus sont ceux qu'envoie le navigateur (#1846) : le
  front et l'API ne partagent aucun fichier, la liste est tenue des deux côtés.
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models.core import RoleUtilisateur
from app.models.telemetrie import MesureAffichage, TelemetryEvent
from app.utils import horloge
from app.utils.mesures_affichage import (
    ACTION_MESURE,
    CONSERVATION_JOURS,
    DUREE_MAX_MS,
    INDICATEURS,
    centile,
    lire_mesure,
    purger_mesures,
    synthese_mesures,
)
from tests.aides_base import moteur_de_test
from tests.aides_http import base_http, client_http

ROUTE = "/telemetry/collect"


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def _mesure(detail: str, page: str = "/tickets/#") -> dict:
    return {"page": page, "action": ACTION_MESURE, "detail": detail}


def _lignes(moteur) -> list[MesureAffichage]:
    with Session(moteur) as s:
        return list(s.exec(select(MesureAffichage)).all())


def test_une_mesure_est_gardee_a_part_et_pas_comme_une_vue(moteur):
    corps = {"events": [{"page": "/tickets"}, _mesure("navigation:340")]}
    assert TestClient(app).post(ROUTE, json=corps).status_code == 204

    with Session(moteur) as s:
        assert [e.page for e in s.exec(select(TelemetryEvent)).all()] == ["/tickets"]
    (ligne,) = _lignes(moteur)
    assert (ligne.page, ligne.indicateur, ligne.duree_ms) == ("/tickets/#", "navigation", 340)
    assert not {c for c in MesureAffichage.model_fields if "user" in c or "utilisateur" in c}


@pytest.mark.parametrize(
    "detail",
    [
        "inconnu:12",
        "navigation:",
        "navigation:-5",
        "navigation:1.5",
        f"chargement:{DUREE_MAX_MS + 1}",
        None,
    ],
)
def test_une_mesure_mal_formee_ne_s_enregistre_pas(moteur, detail):
    evenement = {"page": "/p", "action": ACTION_MESURE, **({"detail": detail} if detail else {})}
    assert TestClient(app).post(ROUTE, json={"events": [evenement]}).status_code == 204
    assert _lignes(moteur) == []
    assert lire_mesure(detail) is None


def test_le_refus_de_la_mesure_coupe_aussi_les_durees(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.résident, opt_out_telemetrie=True)
    assert http.post(ROUTE, json={"events": [_mesure("chargement:900")]}).status_code == 204
    assert _lignes(moteur) == []


def test_le_centile_est_une_valeur_mesuree_au_rang_le_plus_proche():
    valeurs = [100, 200, 300, 400, 500, 600, 700, 800]
    assert centile(valeurs, 0.5) == 400
    assert centile(valeurs, 0.75) == 600
    assert centile([900], 0.75) == 900
    assert centile([3, 1, 2], 0.5) == 2  # l'ordre d'arrivée ne compte pas


def test_la_synthese_classe_les_pages_les_plus_lentes_d_abord():
    moteur = moteur_de_test()
    jour = horloge.aujourd_hui().isoformat()
    with Session(moteur) as s:
        for page, indicateur, durees in [
            ("/rapide", "navigation", [100, 120, 140]),
            ("/lente", "navigation", [900, 1000, 1100, 5000]),
            ("/lente", "chargement", [2000]),
        ]:
            for d in durees:
                s.add(MesureAffichage(jour=jour, page=page, indicateur=indicateur, duree_ms=d))
        s.commit()
        synthese = synthese_mesures(s, horloge.aujourd_hui())

    assert [(p["page"], p["indicateur"]) for p in synthese["pages"]] == [
        ("/lente", "chargement"),
        ("/lente", "navigation"),
        ("/rapide", "navigation"),
    ]
    lente = synthese["pages"][1]
    assert (lente["mesures"], lente["mediane"], lente["p75"]) == (4, 1000, 1100)
    assert {i["indicateur"]: i["mesures"] for i in synthese["indicateurs"]} == {
        "chargement": 1,
        "navigation": 7,
    }


@pytest.mark.parametrize("scope", ["jour", "mois", "annee"])
def test_le_tableau_de_bord_rend_les_durees_sans_les_compter_en_vues(moteur, scope):
    TestClient(app).post(ROUTE, json={"events": [_mesure("navigation:250")]})
    http, _ = client_http(moteur, RoleUtilisateur.admin)
    donnees = http.get("/telemetry/dashboard", params={"scope": scope}).json()
    assert donnees["performance"]["indicateurs"] == [
        {"indicateur": "navigation", "mesures": 1, "mediane": 250, "p75": 250}
    ]
    assert donnees["kpi"]["vues"] == 0, "une mesure a été comptée comme une page vue"


def test_la_purge_retire_ce_qui_depasse_la_conservation():
    moteur = moteur_de_test()
    aujourd_hui = horloge.aujourd_hui()
    with Session(moteur) as s:
        for age in (0, CONSERVATION_JOURS, CONSERVATION_JOURS + 1):
            s.add(
                MesureAffichage(
                    jour=(aujourd_hui - timedelta(days=age)).isoformat(),
                    page=f"/age-{age}",
                    indicateur="navigation",
                    duree_ms=1,
                )
            )
        s.commit()
        assert purger_mesures(s, aujourd_hui) == 1
        restantes = sorted(m.page for m in s.exec(select(MesureAffichage)).all())
    assert restantes == ["/age-0", f"/age-{CONSERVATION_JOURS}"]


TELEMETRY_TS = Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "telemetry.ts"


def test_les_indicateurs_sont_ceux_qu_envoie_le_navigateur():
    """Un indicateur ajouté d'un seul côté se perd sans un mot : refusé ici,
    ou envoyé sans que rien ne l'enregistre (#1846)."""
    source = TELEMETRY_TS.read_text(encoding="utf-8")
    trouve = re.search(r"const INDICATEURS = \[([^\]]*)\]", source)
    assert trouve, "INDICATEURS introuvable dans telemetry.ts"
    assert tuple(re.findall(r"'(\w+)'", trouve.group(1))) == INDICATEURS


def test_une_duree_de_donnees_s_enregistre(moteur):
    assert lire_mesure("donnees:861") == ("donnees", 861)
