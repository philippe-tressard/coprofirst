"""Le tableau de bord de télémétrie rend ce que les données disent — par portée (#1564).

Les trois portées (`jour`, `mois`, `annee`) et `users-active` recopiaient chacune
leur requête « top utilisateurs » et « uniques par jour ». Ce test fige ce que
l'administrateur voit **avant** de factoriser, sur une base minuscule dont chaque
chiffre se compte à la main : une factorisation qui changerait une réponse le dit.

Depuis le 03/10/2026 : la portée `annee` lit les 12 derniers mois, `total` cumule
par année sur 10 ans, et le filtre « sans gestionnaire du site » écarte les vues
du compte désigné — proposé seulement s'il changerait quelque chose.

L'horloge est figée : les libellés de jour et d'heure en dépendent.
"""

from datetime import datetime

import pytest

from app.models.core import (
    ConfigSite,
    HistoriqueTelemetrie,
    RoleUtilisateur,
    TelemetryDaily,
    TelemetryEvent,
    TelemetryMonthly,
)
from app.utils import horloge
from sqlmodel import Session, select
from tests.aides_http import base_http, client_http

#: Un jeudi d'automne, 12 h UTC (14 h à Paris, heure d'été).
MAINTENANT = datetime(2026, 10, 1, 12, 0, 0)


def _jeu(s: Session) -> None:
    #  Aujourd'hui : l'utilisateur 7 voit deux pages, le 8 une seule.
    for user_id, page, heure in [
        (7, "/actualites", 9),
        (7, "/tickets", 10),
        (7, "/tickets", 11),
        (8, "/actualites", 9),
        (None, "/connexion", 8),
    ]:
        s.add(TelemetryEvent(user_id=user_id, page=page, cree_le=MAINTENANT.replace(hour=heure)))
    #  Il y a dix jours : l'utilisateur 8 seul, et 9 (qui n'a rien fait aujourd'hui).
    for user_id in (8, 9):
        s.add(
            TelemetryEvent(
                user_id=user_id,
                page="/documents",
                cree_le=datetime(2026, 9, 21, 10, 0, 0),
            )
        )
    #  Agrégats : un jour qui n'a PLUS d'évènements bruts, et son total — agrégés
    #  avant le drapeau `gestionnaire` (None : non distingués).
    s.add(TelemetryDaily(jour="2026-09-15", page="/tickets", utilisateurs_uniques=3, total=9))
    s.add(TelemetryDaily(jour="2026-09-15", page="__total__", utilisateurs_uniques=3, total=9))
    s.add(TelemetryMonthly(mois="2026-08", page="/tickets", utilisateurs_uniques=5, total=20))
    s.add(TelemetryMonthly(mois="2026-08", page="__total__", utilisateurs_uniques=5, total=20))
    #  Et un mois hors des 12 derniers, que seul Total voit.
    s.add(TelemetryMonthly(mois="2025-03", page="/faq", utilisateurs_uniques=2, total=4))
    s.add(TelemetryMonthly(mois="2025-03", page="__total__", utilisateurs_uniques=2, total=4))


@pytest.fixture()
def admin_http(monkeypatch):
    with base_http() as moteur:
        #  Le jeton est émis AVANT de figer l'horloge : sinon il expire dans le passé.
        http, _ = client_http(moteur, RoleUtilisateur.admin)
        monkeypatch.setattr(horloge, "maintenant", lambda: MAINTENANT)
        with Session(moteur) as s:
            _jeu(s)
            s.commit()
        yield http


@pytest.fixture()
def gestionnaire_http(monkeypatch):
    """Le même jeu, l'administrateur connecté désigné gestionnaire du site, qui a
    vu deux pages aujourd'hui — et deux lignes agrégées à son nom le 20/09."""
    with base_http() as moteur:
        http, admin_id = client_http(moteur, RoleUtilisateur.admin)
        monkeypatch.setattr(horloge, "maintenant", lambda: MAINTENANT)
        with Session(moteur) as s:
            _jeu(s)
            s.add(ConfigSite(cle="site_manager_user_id", valeur=str(admin_id)))
            for heure in (13, 14):
                s.add(
                    TelemetryEvent(
                        user_id=admin_id, page="/admin", cree_le=MAINTENANT.replace(hour=heure)
                    )
                )
            for gestionnaire, page, total in [(True, "/admin", 6), (False, "/tickets", 2)]:
                for p in (page, "__total__"):
                    s.add(
                        TelemetryDaily(
                            jour="2026-09-20",
                            page=p,
                            utilisateurs_uniques=1,
                            total=total,
                            gestionnaire=gestionnaire,
                        )
                    )
            s.commit()
        yield http


def _palmares(reponse) -> list[tuple]:
    return [(u["total"], u["pages"]) for u in reponse["top_users"]]


def test_jour_ne_compte_que_aujourd_hui(admin_http):
    r = admin_http.get("/telemetry/dashboard?scope=jour")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["scope"] == "jour"
    assert d["kpi"]["utilisateurs"] == 2 and d["kpi"]["vues"] == 5
    #  7 : trois vues sur deux pages ; 8 : une vue sur une page ; l'anonyme n'en est pas un.
    assert _palmares(d) == [(3, 2), (1, 1)]


def test_mois_remonte_trente_jours_et_les_uniques_de_chaque_jour(admin_http):
    r = admin_http.get("/telemetry/dashboard?scope=mois")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["scope"] == "mois"
    #  Sur trente jours : 7 (3 vues), 8 (2 vues : aujourd'hui et il y a dix jours), 9 (1 vue).
    assert _palmares(d) == [(3, 2), (2, 2), (1, 1)]
    #  Les uniques du 15/09 ne viennent d'aucun évènement brut : c'est le repli sur le
    #  total agrégé qui en fait le jour de pointe, devant le 21/09 (deux uniques).
    assert d["kpi"]["jour_pointe"] == {"jour": "2026-09-15", "uniques": 3}


def test_annee_lit_les_douze_derniers_mois(admin_http):
    r = admin_http.get("/telemetry/dashboard?scope=annee")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["scope"] == "annee"
    #  Un bâton par mois agrégé ; mars 2025 est hors des 12 derniers mois.
    assert [(c["label"], c["total"]) for c in d["chart"]] == [("2026-08", 20)]
    assert d["kpi"]["vues"] == 20 and d["kpi"]["mois_actifs"] == 1
    #  Le 15/09 (3 uniques, repli sur l'agrégat) bat le 21/09 (2) et aujourd'hui (2).
    assert d["kpi"]["record_jour"] == {"jour": "2026-09-15", "uniques": 3}
    assert d["kpi"]["record_mois"] == {"mois": "2026-08", "uniques": 5}
    #  « Qui vient » couvre l'année ; pas de palmarès au-delà des évènements.
    assert d["adoption"]["periode"] == "12 derniers mois"
    assert d["top_users"] == []


def test_total_cumule_par_annee_sur_dix_ans(admin_http):
    d = admin_http.get("/telemetry/dashboard?scope=total").json()
    assert d["scope"] == "total"
    assert [(c["label"], c["total"]) for c in d["chart"]] == [("2025", 4), ("2026", 20)]
    assert d["kpi"]["vues"] == 24 and d["kpi"]["annees_actives"] == 2
    assert d["kpi"]["moy_vues_an"] == 12.0
    assert [p["page"] for p in d["top_pages"]] == ["/tickets", "/faq"]
    #  Au-delà de 12 mois, personne ne sait plus qui est venu : la section est vide.
    assert d["adoption"] is None


def test_le_filtre_n_est_pas_propose_sans_gestionnaire(admin_http):
    d = admin_http.get("/telemetry/dashboard?scope=jour&gestionnaire=sans").json()
    #  Demandé « sans », appliqué « avec » : rien à écarter, l'écran ne le propose pas.
    assert d["filtre_gestionnaire"] == {
        "propose": False,
        "gestionnaire_designe": False,
        "applique": "avec",
        "non_distingue_jusqu_au": None,
    }
    assert d["kpi"]["vues"] == 5


def test_sans_gestionnaire_ecarte_ses_vues_du_jour(gestionnaire_http):
    avec = gestionnaire_http.get("/telemetry/dashboard?scope=jour").json()
    assert avec["kpi"]["vues"] == 7 and avec["kpi"]["utilisateurs"] == 3
    assert avec["filtre_gestionnaire"]["propose"] is True
    assert avec["filtre_gestionnaire"]["gestionnaire_designe"] is True
    sans = gestionnaire_http.get("/telemetry/dashboard?scope=jour&gestionnaire=sans").json()
    assert sans["filtre_gestionnaire"]["applique"] == "sans"
    #  Les cinq vues des résidents, l'anonyme comprise ; le gestionnaire sort du palmarès.
    assert sans["kpi"]["vues"] == 5 and sans["kpi"]["utilisateurs"] == 2
    assert _palmares(sans) == [(3, 2), (1, 1)]
    assert "/admin" not in {p["page"] for p in sans["top_pages"]}
    #  « Qui vient » ne compte plus le gestionnaire, ni en haut ni en bas.
    assert sans["adoption"]["global"]["comptes"] == avec["adoption"]["global"]["comptes"] - 1


def test_sans_gestionnaire_lit_la_serie_des_agregats(gestionnaire_http):
    sans = gestionnaire_http.get("/telemetry/dashboard?scope=mois&gestionnaire=sans").json()
    assert sans["filtre_gestionnaire"]["applique"] == "sans"
    #  Le 20/09 : la série du gestionnaire (6) sort, celle des autres (2) reste ;
    #  le 15/09, non distingué, compte en entier (9).
    totaux = {c["label"]: c["total"] for c in sans["chart"]}
    assert totaux["09-20"] == 2 and totaux["09-15"] == 9
    assert sans["filtre_gestionnaire"]["non_distingue_jusqu_au"] == "2026-09-15"
    avec = gestionnaire_http.get("/telemetry/dashboard?scope=mois").json()
    assert {c["label"]: c["total"] for c in avec["chart"]}["09-20"] == 8


def test_un_filtre_qui_ne_changerait_rien_n_est_pas_applique(gestionnaire_http):
    """En Année, l'agrégat mensuel ne porte aucune vue du gestionnaire : « sans »
    retombe sur « avec » plutôt que de montrer une série qui ne change pas."""
    d = gestionnaire_http.get("/telemetry/dashboard?scope=annee&gestionnaire=sans").json()
    #  Le mois en cours (octobre) n'a pas de journalier ; le 20/09 n'entre pas dans
    #  l'agrégat mensuel : la portée ne voit aucune vue du gestionnaire.
    assert d["filtre_gestionnaire"]["propose"] is False
    assert d["filtre_gestionnaire"]["applique"] == "avec"


def test_users_active_rend_le_meme_palmares_que_le_mois(admin_http):
    mois = admin_http.get("/telemetry/dashboard?scope=mois").json()
    lignes = admin_http.get("/telemetry/users-active").json()
    assert [(ligne["total"], ligne["pages"]) for ligne in lignes] == _palmares(mois)
    assert [ligne["user_id"] for ligne in lignes] == [7, 8, 9]


def test_une_reagregation_en_attente_se_rejoue_sans_attendre_02h(monkeypatch):
    """🔴 La vue Mois ne proposait pas le filtre le jour de la mise en production
    (03/10/2026) : les lignes déjà agrégées portent `None` jusqu'au passage de
    02:00, donc zéro vue du gestionnaire. Le rattrapage du démarrage les rejoue —
    il lisait seulement « la dernière agrégation a-t-elle moins de 24 h ? »."""
    from app.utils.telemetry_aggregation import (
        derniere_agregation_ou_rejeu,
        reagregation_en_attente,
    )

    with base_http() as moteur:
        monkeypatch.setattr(horloge, "maintenant", lambda: MAINTENANT)
        with Session(moteur) as s:
            #  Une agrégation réussie il y a une heure…
            s.add(HistoriqueTelemetrie(statut="succes", cree_le=MAINTENANT.replace(hour=11)))
            #  …et un jour récent resté non distingué.
            s.add(TelemetryDaily(jour="2026-09-25", page="__total__", total=4, gestionnaire=None))
            s.commit()
            assert reagregation_en_attente(s) is True
            assert derniere_agregation_ou_rejeu(s) is None  # → le rattrapage rejoue
            #  Distingué (ou trop ancien pour être réagrégé) : plus rien à rejouer.
            for ligne in s.exec(select(TelemetryDaily)).all():
                ligne.gestionnaire = False
                s.add(ligne)
            s.add(TelemetryDaily(jour="2026-08-01", page="__total__", total=1, gestionnaire=None))
            s.commit()
            assert reagregation_en_attente(s) is False
            assert derniere_agregation_ou_rejeu(s) == MAINTENANT.replace(hour=11)


@pytest.mark.parametrize("scope", ["jour", "mois", "annee", "total"])
def test_le_retour_des_comptes_suit_toute_vue(admin_http, scope):
    """#1629 : dormants et arrivants sont à seuils fixes — rendus quelle que soit la vue."""
    d = admin_http.get(f"/telemetry/dashboard?scope={scope}").json()
    assert [s["seuil"] for s in d["retour"]["dormants"]] == [60, 90]
    assert d["retour"]["arrivants"]["fenetre_jours"] == 7
    assert isinstance(d["retour"]["liste_dormants"], list)


def test_le_retour_des_comptes_est_reserve_a_l_administrateur():
    """La liste nominative des dormants passe par le tableau de bord : `require_admin`."""
    with base_http() as moteur:
        for role in (RoleUtilisateur.conseil_syndical, RoleUtilisateur.résident):
            http, _ = client_http(moteur, role)
            assert http.get("/telemetry/dashboard?scope=jour").status_code == 403


@pytest.mark.parametrize("portee", ["jour", "mois", "annee", "total"])
def test_la_reponse_typee_ne_perd_rien_de_la_lecture(admin_http, portee):
    """#2618 : `response_model=TableauTelemetrie` filtre — chaque clé que
    `tableau()` produit, à chaque portée, doit sortir telle quelle."""
    from app.utils.telemetrie_tableau import tableau
    from tests.aides_reponse_servie import ecarts

    servi = admin_http.get(f"/telemetry/dashboard?scope={portee}")
    assert servi.status_code == 200, servi.text
    from app.database import get_session
    from app.main import app

    #  La session de la base de test, celle que la route vient de lire.
    s = next(app.dependency_overrides[get_session]())
    lu = tableau(s, portee, "avec")
    assert ecarts(lu, servi.json()) == []


def test_le_contrat_annonce_le_schema_de_la_reponse():
    """#2618 : l'app iOS se génère depuis `openapi.json` — la réponse y porte
    `TableauTelemetrie` (`app.routers.telemetry_schemas`), et non `{}`."""
    from app.main import app
    from app.routers.telemetry_schemas import TableauTelemetrie

    reponse = app.openapi()["paths"]["/telemetry/dashboard"]["get"]["responses"]["200"]
    assert reponse["content"]["application/json"]["schema"] == {
        "$ref": f"#/components/schemas/{TableauTelemetrie.__name__}"
    }
