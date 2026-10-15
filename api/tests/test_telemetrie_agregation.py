"""L'agrégation de la télémétrie écrit deux séries et la présence mensuelle (03/10/2026).

Jeu fictif, horloge figée au 01/10/2026 12 h UTC (14 h à Paris). Un
gestionnaire du site désigné (G) et deux résidents (A, B) :

| Quand | Qui | Quoi |
|---|---|---|
| 30/09 | G ×2 `/admin`, A `/tickets`, un anonyme `/connexion` | la veille : à agréger |
| 29/09 | B `/tickets` | |
| 20/09 | A ×3 `/documents` | DÉJÀ agrégé sans drapeau (`None`) : à réagréger |
| 15/08 | — | agrégé sans drapeau, plus d'évènements : reste `None` |
| 01/10 | A `/actualites` | aujourd'hui : jamais agrégé |

Ce que le test fige : les deux séries d'un jour et leurs `__total__`, la présence
par (mois, compte) écrite une fois même si l'on rejoue, la réagrégation des jours
récents non distingués, le mois rebâti depuis le journalier, et la purge de la
présence au-delà de 12 mois.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlmodel import Session, select

from app.models.core import (
    ConfigSite,
    PresenceMensuelle,
    TelemetryDaily,
    TelemetryEvent,
    TelemetryMonthly,
)
from app.models.telemetrie import DerniereVisite
from app.utils import horloge, telemetry_aggregation
from app.utils.telemetrie_tableau import non_distingue_jusqu_au
from tests.aides_base import compte, moteur_de_test

MAINTENANT = datetime(2026, 10, 1, 12, 0, 0)


def _utc(jour: int, heure: int = 10, mois: int = 9) -> datetime:
    return datetime(2026, mois, jour, heure, 0, 0)


@pytest.fixture()
def jeu(monkeypatch):
    moteur = moteur_de_test()
    monkeypatch.setattr("app.database.engine", moteur)
    monkeypatch.setattr(horloge, "maintenant", lambda: MAINTENANT)
    with Session(moteur) as s:
        g = compte(s, prefixe="gestionnaire", roles_json="admin")
        a = compte(s, prefixe="a")
        b = compte(s, prefixe="b")
        s.add(ConfigSite(cle="site_manager_user_id", valeur=str(g.id)))
        for user_id, page, quand in [
            (g.id, "/admin", _utc(30, 9)),
            (g.id, "/admin", _utc(30, 11)),
            (a.id, "/tickets", _utc(30, 10)),
            (None, "/connexion", _utc(30, 8)),
            (b.id, "/tickets", _utc(29)),
            (a.id, "/documents", _utc(20, 9)),
            (a.id, "/documents", _utc(20, 10)),
            (a.id, "/documents", _utc(20, 11)),
            (a.id, "/actualites", _utc(1, 9, mois=10)),
        ]:
            s.add(TelemetryEvent(user_id=user_id, page=page, cree_le=quand))
        #  Déjà agrégés AVANT le drapeau.
        for jour, page, total in [
            ("2026-09-20", "/documents", 3),
            ("2026-09-20", "__total__", 3),
            ("2026-08-15", "/faq", 5),
            ("2026-08-15", "__total__", 5),
        ]:
            s.add(TelemetryDaily(jour=jour, page=page, total=total, utilisateurs_uniques=1))
        s.add(TelemetryMonthly(mois="2026-08", page="/faq", total=5, utilisateurs_uniques=1))
        s.add(TelemetryMonthly(mois="2026-08", page="__total__", total=5, utilisateurs_uniques=1))
        #  Une présence vieille de plus de 12 mois, et une à la limite.
        s.add(PresenceMensuelle(mois="2025-09", user_id=b.id))
        s.add(PresenceMensuelle(mois="2025-10", user_id=b.id))
        s.commit()
        ids = {"g": g.id, "a": a.id, "b": b.id}
    return moteur, ids


def _daily(s: Session, jour: str) -> set[tuple]:
    lignes = s.exec(select(TelemetryDaily).where(TelemetryDaily.jour == jour)).all()
    return {(r.page, r.gestionnaire, r.total, r.utilisateurs_uniques) for r in lignes}


def test_un_jour_s_agrege_en_deux_series_disjointes(jeu):
    moteur, _ = jeu
    rapport = telemetry_aggregation.run_telemetry_aggregation()
    assert rapport["erreurs"] == []
    with Session(moteur) as s:
        assert _daily(s, "2026-09-30") == {
            ("/admin", True, 2, 1),
            ("/tickets", False, 1, 1),
            ("/connexion", False, 1, 0),
            ("__total__", True, 2, 1),
            #  L'anonyme compte dans les vues, pas dans les uniques.
            ("__total__", False, 2, 1),
        }
        #  Aujourd'hui n'est jamais agrégé : données incomplètes.
        assert _daily(s, "2026-10-01") == set()
    #  Trois jours avaient des vues : le 20, le 29, le 30.
    assert rapport["jours_agreges"] == 3


def test_un_jour_recent_non_distingue_est_reagrege_le_vieux_reste(jeu):
    moteur, _ = jeu
    with Session(moteur) as s:
        assert non_distingue_jusqu_au(s, "mois") == "2026-09-20"
    telemetry_aggregation.run_telemetry_aggregation()
    with Session(moteur) as s:
        assert _daily(s, "2026-09-20") == {
            ("/documents", False, 3, 1),
            ("__total__", False, 3, 1),
        }
        #  Le 15/08 n'a plus d'évènements : il reste tel quel, et l'écran le dira.
        assert _daily(s, "2026-08-15") == {("/faq", None, 5, 1), ("__total__", None, 5, 1)}
        assert non_distingue_jusqu_au(s, "mois") == "2026-08-15"
        #  Et le mensuel d'août, bâti sur un journalier non distingué, n'est pas rebâti.
        assert non_distingue_jusqu_au(s, "total") == "2026-08-31"


def test_la_presence_mensuelle_s_ecrit_une_fois_et_se_purge(jeu):
    moteur, ids = jeu
    rapport = telemetry_aggregation.run_telemetry_aggregation()
    assert rapport["presences_purgees"] == 1
    with Session(moteur) as s:
        presences = {(p.mois, p.user_id) for p in s.exec(select(PresenceMensuelle)).all()}
    assert presences == {
        ("2026-09", ids["g"]),
        ("2026-09", ids["a"]),
        ("2026-09", ids["b"]),
        ("2025-10", ids["b"]),  # à la limite des 12 mois : gardée
    }
    #  Rejouer n'écrit personne deux fois — et ne réagrège rien.
    rapport = telemetry_aggregation.run_telemetry_aggregation()
    assert rapport["jours_agreges"] == 0 and rapport["erreurs"] == []
    with Session(moteur) as s:
        assert len(s.exec(select(PresenceMensuelle)).all()) == 4


def test_le_mois_termine_se_batit_depuis_le_journalier_en_deux_series(jeu):
    moteur, _ = jeu
    telemetry_aggregation.run_telemetry_aggregation()
    with Session(moteur) as s:
        lignes = s.exec(select(TelemetryMonthly).where(TelemetryMonthly.mois == "2026-09")).all()
        assert {(r.page, r.gestionnaire, r.total) for r in lignes} == {
            ("/admin", True, 2),
            ("/tickets", False, 2),
            ("/connexion", False, 1),
            ("/documents", False, 3),
            ("__total__", True, 2),
            ("__total__", False, 6),
        }


def test_le_jour_de_la_derniere_visite_se_note_et_se_purge(jeu):
    """#1629 : chaque compte venu garde le DERNIER jour agrégé ; au-delà de 12 mois, il part."""
    moteur, ids = jeu
    with Session(moteur) as s:
        vieux = compte(s, prefixe="vieux").id
        s.add(DerniereVisite(user_id=vieux, jour="2025-09-15"))
        s.commit()
    rapport = telemetry_aggregation.run_telemetry_aggregation()
    assert rapport["dernieres_visites_purgees"] == 1
    with Session(moteur) as s:
        visites = {d.user_id: d.jour for d in s.exec(select(DerniereVisite)).all()}
    #  Aujourd'hui n'est jamais agrégé : la visite du 01/10 de A se lit dans les évènements.
    assert visites == {ids["g"]: "2026-09-30", ids["a"]: "2026-09-30", ids["b"]: "2026-09-29"}
