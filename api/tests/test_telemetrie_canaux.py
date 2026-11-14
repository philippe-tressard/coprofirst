"""La mesure d'audience distingue le CANAL d'accès : site web, app iPhone (14/11/2026).

Demandé : « savoir si une page est consultée depuis l'accès web ou depuis
l'application iOS ». Ce que ces tests figent :

- la collecte garde le canal que le lot déclare, le site par défaut, et refuse un
  canal inconnu (422) ;
- l'agrégation écrit les vues par page, canal et série du gestionnaire — idempotente,
  le mois rebâti depuis le jour ;
- le tableau sert la répartition sur les MÊMES lignes que l'indicateur « Pages vues »
  (le total des canaux est ce total), la part en pour cent calculée par le serveur,
  les visiteurs par canal tant que les évènements existent, et `canaux` sur chaque
  top page ; le filtre « sans le gestionnaire du site » vaut aussi ici ;
- la 0335 reprend l'historique des agrégats en vues du site, et la 0336 pose la puce
  de la politique dans la forme de l'éditeur.

Horloge figée au 01/10/2026 12 h UTC (14 h à Paris).
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from app.models.core import (
    ConfigSite,
    RoleUtilisateur,
    TelemetryDaily,
    TelemetryEvent,
    TelemetryMonthly,
)
from app.models.telemetrie import AudienceCanalJour, AudienceCanalMois
from app.seed.contenus_legaux import TELEMETRIE_ARRIVEES
from app.seed.contenus_legaux_canal import TELEMETRIE_ACCES
from app.utils import horloge, telemetry_aggregation
from app.utils.limiter import limiter
from app.utils.textes_livres import forme_editeur
from tests.aides_base import compte, moteur_de_test
from tests.aides_http import base_http, client_http
from tests.aides_migrations import charger_migration

MAINTENANT = datetime(2026, 10, 1, 12, 0, 0)
ROUTE = "/telemetry/collect"


# ── La collecte ──────────────────────────────────────────────────────────────


def _evenements(moteur) -> list[tuple]:
    with Session(moteur) as s:
        return sorted((e.page, e.canal) for e in s.exec(select(TelemetryEvent)).all())


def test_la_collecte_garde_le_canal_declare_et_le_site_par_defaut():
    with base_http() as moteur:
        http, _ = client_http(moteur, None)
        limiter.reset()
        assert http.post(ROUTE, json={"events": [{"page": "/tickets"}]}).status_code == 204
        reponse = http.post(ROUTE, json={"canal": "ios", "events": [{"page": "/actualites"}]})
        assert reponse.status_code == 204
        assert _evenements(moteur) == [("/actualites", "ios"), ("/tickets", "site")]


def test_un_canal_inconnu_est_refuse_en_bloc():
    with base_http() as moteur:
        http, _ = client_http(moteur, None)
        limiter.reset()
        reponse = http.post(ROUTE, json={"canal": "minitel", "events": [{"page": "/tickets"}]})
        assert reponse.status_code == 422
        assert _evenements(moteur) == []


# ── L'agrégation ─────────────────────────────────────────────────────────────


@pytest.fixture()
def jeu_agregation(monkeypatch):
    moteur = moteur_de_test()
    monkeypatch.setattr("app.database.engine", moteur)
    monkeypatch.setattr(horloge, "maintenant", lambda: MAINTENANT)
    with Session(moteur) as s:
        g = compte(s, prefixe="gestionnaire", roles_json="admin")
        a = compte(s, prefixe="a")
        s.add(ConfigSite(cle="site_manager_user_id", valeur=str(g.id)))
        for user_id, page, canal in [
            (g.id, "/admin", "ios"),
            (a.id, "/tickets", "site"),
            (a.id, "/tickets", "ios"),
            (a.id, "/tickets", "ios"),
            (None, "/connexion", "site"),
        ]:
            s.add(
                TelemetryEvent(
                    user_id=user_id, page=page, canal=canal, cree_le=datetime(2026, 9, 30, 10)
                )
            )
        s.commit()
    return moteur


def _repartition_jour(moteur, jour: str) -> set[tuple]:
    with Session(moteur) as s:
        lignes = s.exec(select(AudienceCanalJour).where(AudienceCanalJour.jour == jour)).all()
        return {(r.page, r.canal, r.gestionnaire, r.vues) for r in lignes}


def test_un_jour_s_agrege_par_page_canal_et_serie(jeu_agregation):
    attendu = {
        ("/admin", "ios", True, 1),
        ("/tickets", "site", False, 1),
        ("/tickets", "ios", False, 2),
        ("/connexion", "site", False, 1),
    }
    assert telemetry_aggregation.run_telemetry_aggregation()["erreurs"] == []
    assert _repartition_jour(jeu_agregation, "2026-09-30") == attendu
    #  Réagréger ne compte rien deux fois.
    with Session(jeu_agregation) as s:
        for ligne in s.exec(select(TelemetryDaily)).all():
            s.delete(ligne)
        s.commit()
    telemetry_aggregation.run_telemetry_aggregation()
    assert _repartition_jour(jeu_agregation, "2026-09-30") == attendu


def test_le_mois_se_rebatit_depuis_le_jour(jeu_agregation, monkeypatch):
    telemetry_aggregation.run_telemetry_aggregation()
    #  Le mois de septembre se termine : l'agrégation suivante l'écrit.
    monkeypatch.setattr(horloge, "maintenant", lambda: datetime(2026, 10, 2, 12))
    telemetry_aggregation.run_telemetry_aggregation()
    with Session(jeu_agregation) as s:
        lignes = s.exec(select(AudienceCanalMois).where(AudienceCanalMois.mois == "2026-09")).all()
        assert {(r.page, r.canal, r.vues) for r in lignes} == {
            ("/admin", "ios", 1),
            ("/tickets", "site", 1),
            ("/tickets", "ios", 2),
            ("/connexion", "site", 1),
        }


# ── Le tableau ───────────────────────────────────────────────────────────────


@pytest.fixture()
def gestionnaire_http(monkeypatch):
    """Aujourd'hui : un résident sur le site et l'app, le gestionnaire sur l'app.
    Il y a dix jours (agrégé) : 3 vues du site, 1 de l'app. En août : 5 de l'app."""
    with base_http() as moteur:
        http, admin_id = client_http(moteur, RoleUtilisateur.admin)
        monkeypatch.setattr(horloge, "maintenant", lambda: MAINTENANT)
        with Session(moteur) as s:
            a = compte(s, prefixe="a")
            s.add(ConfigSite(cle="site_manager_user_id", valeur=str(admin_id)))
            for user_id, page, canal in [
                (a.id, "/tickets", "site"),
                (a.id, "/tickets", "ios"),
                (a.id, "/actualites", "ios"),
                (admin_id, "/admin", "ios"),
                (admin_id, "/admin", "ios"),
                (None, "/connexion", "site"),
            ]:
                s.add(
                    TelemetryEvent(
                        user_id=user_id, page=page, canal=canal, cree_le=MAINTENANT.replace(hour=9)
                    )
                )
            for page, canal, vues in [("/tickets", "site", 3), ("/tickets", "ios", 1)]:
                s.add(
                    AudienceCanalJour(
                        jour="2026-09-21", page=page, canal=canal, gestionnaire=False, vues=vues
                    )
                )
                s.add(TelemetryDaily(jour="2026-09-21", page=page, total=vues, gestionnaire=False))
            #  Août, terminé : seul le mensuel le porte — l'Année le lit, le Mois non.
            s.add(AudienceCanalMois(mois="2026-08", page="/faq", canal="ios", vues=5))
            s.add(TelemetryMonthly(mois="2026-08", page="/faq", total=5))
            s.commit()
        yield http


def _tableau(http, scope: str, filtre: str = "avec") -> dict:
    reponse = http.get("/telemetry/dashboard", params={"scope": scope, "gestionnaire": filtre})
    assert reponse.status_code == 200, reponse.text
    return reponse.json()


def test_le_jour_reparti_les_vues_et_les_visiteurs_par_canal(gestionnaire_http):
    donnees = _tableau(gestionnaire_http, "jour")
    assert donnees["canaux"] == [
        {"canal": "site", "libelle": "Site web", "vues": 2, "part": 33, "visiteurs": 1},
        {"canal": "ios", "libelle": "App iPhone", "vues": 4, "part": 67, "visiteurs": 2},
    ]
    #  Le total des canaux est l'indicateur « Pages vues ».
    assert sum(c["vues"] for c in donnees["canaux"]) == donnees["kpi"]["vues"]
    tickets = next(p for p in donnees["top_pages"] if p["page"] == "/tickets")
    assert [(c["canal"], c["vues"]) for c in tickets["canaux"]] == [("site", 1), ("ios", 1)]


def test_sans_le_gestionnaire_ses_vues_quittent_la_repartition(gestionnaire_http):
    donnees = _tableau(gestionnaire_http, "jour", "sans")
    assert donnees["filtre_gestionnaire"]["applique"] == "sans"
    assert [(c["canal"], c["vues"], c["visiteurs"]) for c in donnees["canaux"]] == [
        ("site", 2, 1),
        ("ios", 2, 1),
    ]


def test_le_mois_lit_l_agregat_et_tombe_sur_le_total(gestionnaire_http):
    donnees = _tableau(gestionnaire_http, "mois")
    assert [(c["canal"], c["vues"], c["part"]) for c in donnees["canaux"]] == [
        ("site", 3, 75),
        ("ios", 1, 25),
    ]
    assert sum(c["vues"] for c in donnees["canaux"]) == donnees["kpi"]["vues"]


def test_l_annee_lit_le_mensuel_sans_visiteurs(gestionnaire_http):
    donnees = _tableau(gestionnaire_http, "annee")
    assert donnees["canaux"] == [
        {"canal": "ios", "libelle": "App iPhone", "vues": 5, "part": 100, "visiteurs": None}
    ]
    assert sum(c["vues"] for c in donnees["canaux"]) == donnees["kpi"]["vues"]


# ── Les migrations ───────────────────────────────────────────────────────────


def test_la_0335_reprend_les_agregats_en_vues_du_site(session: Session):
    migration = charger_migration("0335")
    for page, action, total, gestionnaire in [
        ("/tickets", "view", 4, False),
        ("/tickets", "click", 1, False),
        ("/admin", "view", 2, True),
        ("__total__", "view", 7, None),
    ]:
        session.add(
            TelemetryDaily(
                jour="2026-09-20", page=page, action=action, total=total, gestionnaire=gestionnaire
            )
        )
    session.commit()
    migration.op = SimpleNamespace(get_bind=session.connection)
    migration._reprendre("audience_canal_jour", "jour", "telemetry_daily")
    session.commit()
    lignes = session.exec(select(AudienceCanalJour)).all()
    assert {(r.jour, r.page, r.canal, r.gestionnaire, r.vues) for r in lignes} == {
        ("2026-09-20", "/tickets", "site", False, 5),
        ("2026-09-20", "/admin", "site", True, 2),
    }


@pytest.mark.parametrize("forme", [lambda p: p, forme_editeur], ids=["gabarit", "editeur"])
def test_la_0336_pose_la_puce_apres_les_arrivees(session: Session, forme):
    migration = charger_migration("0336")
    avant = "<ul>" + forme(TELEMETRIE_ARRIVEES) + "<li>suite</li></ul>"
    session.add(ConfigSite(cle="politique_confidentialite", valeur=avant))
    session.commit()
    migration.op = SimpleNamespace(get_bind=session.connection)
    for sens in ("upgrade", "upgrade", "downgrade"):
        getattr(migration, sens)()
        session.commit()
        session.expire_all()
        valeur = session.get(ConfigSite, "politique_confidentialite").valeur
        if sens == "upgrade":
            #  Une seule fois, même rejouée.
            assert valeur.count(forme(TELEMETRIE_ACCES)) == 1
            assert forme(TELEMETRIE_ARRIVEES) + forme(TELEMETRIE_ACCES) in valeur
    assert valeur == avant
