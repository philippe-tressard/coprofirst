"""La mesure d'audience garde la CLASSE d'appareil, sous le canal (#2774, 15/11/2026).

« Pour la télémétrie, tu décomposeras en web, iOS et Android et si possible tu
éclateras pour l'OS concerné sur le matériel. » Ce que ces tests figent :

- la collecte garde l'appareil déclaré, refuse une classe hors de son canal (422), et
  admet un lot sans appareil (« non précisé ») — les clients d'avant restent valides ;
- l'agrégation écrit les vues par appareil, du jour au mois ;
- le tableau sert, sous chaque canal, ses appareils dans l'ordre déclaré, la part en
  pour cent DU CANAL calculée par le serveur, « non précisé » en dernier ;
- l'export RGPD porte l'appareil de chaque évènement ;
- la 0345 remplace la puce de la politique, dans la forme de l'éditeur ;
- la liste des classes est publiée aux apps (`constantes-clients.json`).
"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

from app.contrat import constantes_clients
from app.models.core import ConfigSite, RoleUtilisateur, TelemetryEvent
from app.models.telemetrie import AudienceCanalJour, AudienceCanalMois
from app.seed.contenus_legaux_canal import TELEMETRIE_ACCES
from app.utils import horloge, telemetry_aggregation
from app.utils.canaux_audience import (
    APPAREILS_PAR_CANAL,
    CANAUX,
    libelle_appareil,
    libelle_canal,
)
from app.utils.limiter import limiter
from app.utils.textes_livres import forme_editeur
from tests.aides_base import moteur_de_test
from tests.aides_http import base_http, client_http
from tests.aides_migrations import charger_migration

MAINTENANT = datetime(2026, 10, 1, 12, 0, 0)
HIER = datetime(2026, 9, 30, 9, 0, 0)
ROUTE = "/telemetry/collect"


def _evenements(moteur) -> list[tuple]:
    with Session(moteur) as s:
        return sorted(
            (e.page, e.canal, e.appareil or "") for e in s.exec(select(TelemetryEvent)).all()
        )


def test_la_collecte_garde_l_appareil_et_admet_son_absence():
    with base_http() as moteur:
        http, _ = client_http(moteur, None)
        limiter.reset()
        lots = [
            {"canal": "ios", "appareil": "ipad", "events": [{"page": "/a"}]},
            {"appareil": "telephone", "events": [{"page": "/b"}]},  # le site, par défaut
            {"canal": "android", "events": [{"page": "/c"}]},  # sans appareil : non précisé
        ]
        for lot in lots:
            assert http.post(ROUTE, json=lot).status_code == 204
        assert _evenements(moteur) == [
            ("/a", "ios", "ipad"),
            ("/b", "site", "telephone"),
            ("/c", "android", ""),
        ]


@pytest.mark.parametrize(
    "lot",
    [
        {"canal": "ios", "appareil": "telephone"},  # une classe d'un AUTRE canal
        {"canal": "site", "appareil": "iphone"},
        {"canal": "android", "appareil": "Pixel 9 Pro"},  # un modèle, jamais
        {"canal": "site", "appareil": "x" * 21},
    ],
)
def test_un_appareil_hors_de_son_canal_est_refuse_en_bloc(lot):
    with base_http() as moteur:
        http, _ = client_http(moteur, None)
        limiter.reset()
        reponse = http.post(ROUTE, json={**lot, "events": [{"page": "/a"}]})
        assert reponse.status_code == 422
        assert _evenements(moteur) == []


@pytest.fixture()
def tableau_http(monkeypatch):
    """Aujourd'hui : 3 vues iPhone, 1 iPad, 2 sans appareil sur l'app ; 4 du site en
    ordinateur. Hier (agrégé par la tâche de la nuit) : les mêmes, rejouées."""
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        monkeypatch.setattr(horloge, "maintenant", lambda: MAINTENANT)
        with Session(moteur) as s:
            s.add(ConfigSite(cle="site_manager_user_id", valeur="0"))
            vues = [("ios", "iphone")] * 3 + [("ios", "ipad"), ("ios", None), ("ios", None)]
            vues += [("site", "ordinateur")] * 4
            for jour in (MAINTENANT.replace(hour=9), HIER):
                for canal, appareil in vues:
                    s.add(TelemetryEvent(page="/p", canal=canal, appareil=appareil, cree_le=jour))
            s.commit()
        yield http, moteur


def test_le_tableau_sert_les_appareils_sous_chaque_canal(tableau_http):
    http, _ = tableau_http
    donnees = http.get("/telemetry/dashboard", params={"scope": "jour"}).json()
    par_canal = {c["canal"]: c["appareils"] for c in donnees["canaux"]}
    assert par_canal["ios"] == [
        {"appareil": "iphone", "libelle": "iPhone", "vues": 3, "part": 50},
        {"appareil": "ipad", "libelle": "iPad", "vues": 1, "part": 17},
        {"appareil": "non_precise", "libelle": "Non précisé", "vues": 2, "part": 33},
    ]
    assert par_canal["site"] == [
        {"appareil": "ordinateur", "libelle": "Ordinateur", "vues": 4, "part": 100}
    ]
    #  Les appareils d'un canal tombent sur ses vues.
    for c in donnees["canaux"]:
        assert sum(a["vues"] for a in c["appareils"]) == c["vues"]


def test_l_agregation_garde_l_appareil_du_jour_au_mois(monkeypatch):
    moteur = moteur_de_test()
    monkeypatch.setattr("app.database.engine", moteur)
    monkeypatch.setattr(horloge, "maintenant", lambda: MAINTENANT)
    attendu = {
        ("ios", "iphone"): 3,
        ("ios", "ipad"): 1,
        ("ios", None): 2,
        ("site", "ordinateur"): 4,
    }
    with Session(moteur) as s:
        for (canal, appareil), n in attendu.items():
            for _ in range(n):
                s.add(TelemetryEvent(page="/p", canal=canal, appareil=appareil, cree_le=HIER))
        s.commit()
    assert telemetry_aggregation.run_telemetry_aggregation()["erreurs"] == []
    with Session(moteur) as s:
        lignes = s.exec(select(AudienceCanalJour).where(AudienceCanalJour.jour == "2026-09-30"))
        assert {(r.canal, r.appareil): r.vues for r in lignes} == attendu
    #  Septembre terminé : l'agrégation suivante écrit le mois, appareils compris.
    monkeypatch.setattr(horloge, "maintenant", lambda: datetime(2026, 10, 2, 12))
    telemetry_aggregation.run_telemetry_aggregation()
    with Session(moteur) as s:
        lignes = s.exec(select(AudienceCanalMois).where(AudienceCanalMois.mois == "2026-09"))
        assert {(r.canal, r.appareil): r.vues for r in lignes} == attendu


def test_l_export_rgpd_porte_l_appareil():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.propriétaire)
        limiter.reset()
        http.post(ROUTE, json={"canal": "ios", "appareil": "iphone", "events": [{"page": "/a"}]})
        export = http.get("/auth/me/telemetrie").json()
        assert [(e["canal"], e["appareil"]) for e in export["evenements"]] == [("ios", "iphone")]


@pytest.mark.parametrize("forme", [lambda p: p, forme_editeur], ids=["gabarit", "editeur"])
def test_la_0345_remplace_la_puce_de_la_politique(session: Session, forme):
    migration = charger_migration("0345")
    avant = "<ul><li>avant</li>" + forme(migration.ANCIENNE) + "<li>suite</li></ul>"
    session.add(ConfigSite(cle="politique_confidentialite", valeur=avant))
    session.commit()
    migration.op = SimpleNamespace(get_bind=session.connection)
    for sens in ("upgrade", "upgrade", "downgrade"):
        getattr(migration, sens)()
        session.commit()
        session.expire_all()
        valeur = session.get(ConfigSite, "politique_confidentialite").valeur
        if sens == "upgrade":
            #  Remplacée une fois, même rejouée ; le reste du texte ne bouge pas.
            assert valeur == avant.replace(forme(migration.ANCIENNE), forme(TELEMETRIE_ACCES))
            assert "type d'appareil" in valeur
    assert valeur == avant


def test_les_classes_d_appareil_sont_publiees_aux_apps():
    reference = json.loads(constantes_clients.REFERENCE.read_text(encoding="utf-8"))
    publiee = reference["constantes"]["appareilsParCanal"]["valeur"]
    assert publiee == {canal: list(classes) for canal, classes in APPAREILS_PAR_CANAL.items()}


@pytest.mark.parametrize("canal", CANAUX)
def test_un_canal_ne_porte_le_nom_d_aucun_de_ses_appareils(canal):
    """🔴 #2877 : le canal `ios` s'appelait « App iPhone » et se dépliait sur « iPad »,
    « Mac »… Le libellé d'un canal nomme la famille, jamais l'un de ses appareils."""
    nom = libelle_canal(canal).casefold()
    for appareil in APPAREILS_PAR_CANAL[canal]:
        assert libelle_appareil(appareil).casefold() not in nom, (
            f"le canal {canal} (« {libelle_canal(canal)} ») porte le nom de l'appareil "
            f"« {libelle_appareil(appareil)} », l'un de ceux qu'il regroupe"
        )
