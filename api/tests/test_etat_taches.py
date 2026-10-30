"""L'état des tâches planifiées, LU en base — une lecture, deux lecteurs (#1569).

`utils/etat_taches` (extrait d'`admin/exploitation` le 27/09/2026) n'était nommé par
aucun test : `test_sante_taches_*` éprouvent la DÉCISION, pure, sur des lignes
fabriquées ; rien ne lisait les trois tables. Ce fichier tient la lecture :

1. une entrée par tâche attendue — les cinq de la table des périodicités, plus la
   sauvegarde et l'agrégation de télémétrie lues dans LEUR table ;
2. une base vide est un état VALIDE : « aucune exécution », jamais une exception ;
3. une exécution récente est « ok », un échec « erreur », une exécution trop
   ancienne « manquante » — chaque tâche jugée sur SA période ;
4. le contrôle de 06:00 ne répète pas ce qu'un autre canal couvre déjà
   (`DEJA_SIGNALE`) : la sauvegarde en échec n'y paraît pas, la bascule en échec non
   plus, mais une maintenance jamais exécutée, oui.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.models.core import (
    HistoriqueMaintenance,
    RoleUtilisateur,
    HistoriqueSauvegarde,
    HistoriqueTelemetrie,
    StatutSauvegarde,
)
from app.utils import horloge
from app.models.roles import ROLE_OPERATEUR
from app.utils.etat_taches import anomalies_recentes, etat_des_taches, problemes_taches
from app.utils.sante_taches import FENETRE_ANOMALIES_J, _PERIODICITE_ATTENDUE_H
from tests.aides_http import base_http, client_http

TACHES_ATTENDUES = [*_PERIODICITE_ATTENDUE_H, "backup", "telemetrie"]


@pytest.fixture()
def maintenant():
    return horloge.maintenant()


def _ligne(session, tache, noeud, *, statut="succes", il_y_a: timedelta, **champs):
    quand = horloge.maintenant() - il_y_a
    session.add(
        HistoriqueMaintenance(
            tache=tache, noeud=noeud, statut=statut, cree_le=quand, terminee_le=quand, **champs
        )
    )
    session.commit()


def _par_tache(entrees) -> dict[str, dict]:
    return {e["tache"]: e for e in entrees}


# ── Une entrée par tâche ────────────────────────────────────────────────────


def test_une_base_vide_donne_une_entree_par_tache_sans_execution(session, maintenant):
    entrees = etat_des_taches(session, maintenant)

    assert [e["tache"] for e in entrees] == TACHES_ATTENDUES
    assert {e["statut"] for e in entrees} == {"aucune_execution"}
    assert all(e["noeuds"] == [] and e["derniere"] is None for e in entrees)


def test_les_entrees_executees_ont_toutes_la_meme_forme(session, maintenant):
    """Les deux branches (table partagée, table propre) rendent les mêmes clés (#538).

    Une tâche jamais exécutée n'a pas de `portee` à dire : son entrée est plus courte,
    mais elle porte tout ce que l'écran lit.
    """
    _ligne(session, "maintenance", "rpi1", il_y_a=timedelta(hours=1))
    session.add(HistoriqueTelemetrie(statut="succes", noeud="rpi2", cree_le=maintenant))
    session.commit()

    par_tache = _par_tache(etat_des_taches(session, maintenant))

    executees = {frozenset(par_tache[t]) for t in ("maintenance", "telemetrie")}
    assert len(executees) == 1, "les deux branches n'ont pas les mêmes clés"
    vide = set(par_tache["bascule"])
    assert vide <= set(par_tache["maintenance"])
    assert {"tache", "noeud", "noeuds", "statut", "derniere", "periodicite_heures"} <= vide


def test_les_periodicites_sont_celles_de_la_table(session, maintenant):
    par_tache = _par_tache(etat_des_taches(session, maintenant))
    for tache, heures in _PERIODICITE_ATTENDUE_H.items():
        assert par_tache[tache]["periodicite_heures"] == heures
    assert par_tache["backup"]["periodicite_heures"] == 24
    assert par_tache["telemetrie"]["periodicite_heures"] == 24


# ── Les verdicts ────────────────────────────────────────────────────────────


def test_une_execution_recente_est_ok_et_nomme_son_noeud(session, maintenant):
    _ligne(session, "maintenance", "rpi1", il_y_a=timedelta(hours=2))

    entree = _par_tache(etat_des_taches(session, maintenant))["maintenance"]

    assert entree["statut"] == "ok"
    assert entree["noeud"] == "rpi1"
    assert entree["noeud_enregistre"] is True
    assert entree["derniere"] is not None


def test_un_echec_est_signale_comme_erreur(session, maintenant):
    _ligne(session, "bascule", "rpi1", statut="erreur", il_y_a=timedelta(hours=2), erreur="boom")

    assert _par_tache(etat_des_taches(session, maintenant))["bascule"]["statut"] == "erreur"


def test_une_execution_trop_ancienne_est_manquante(session, maintenant):
    _ligne(session, "export_hors_site", "rpi1", il_y_a=timedelta(days=30))

    assert _par_tache(etat_des_taches(session, maintenant))["export_hors_site"]["statut"] == (
        "manquante"
    )


def test_chaque_tache_est_jugee_sur_sa_periode(session, maintenant):
    """40 h : une bascule (48 h) est à jour, une sauvegarde (24 h) ne l'est plus."""
    _ligne(session, "bascule", "rpi1", il_y_a=timedelta(hours=40))
    _ligne(session, "maintenance", "rpi1", il_y_a=timedelta(hours=40))

    par_tache = _par_tache(etat_des_taches(session, maintenant))

    assert par_tache["bascule"]["statut"] == "ok"
    assert par_tache["maintenance"]["statut"] == "ok", "hebdomadaire : 40 h est dans sa période"


def test_la_sauvegarde_est_lue_dans_sa_propre_table(session, maintenant):
    session.add(
        HistoriqueSauvegarde(
            statut=StatutSauvegarde.echouee, noeud="rpi1", cree_le=maintenant - timedelta(hours=1)
        )
    )
    session.commit()

    entree = _par_tache(etat_des_taches(session, maintenant))["backup"]

    assert entree["statut"] == "erreur"
    assert entree["noeud"] == "rpi1"


def test_la_telemetrie_est_lue_dans_sa_propre_table(session, maintenant):
    session.add(
        HistoriqueTelemetrie(statut="succes", noeud="rpi2", cree_le=maintenant - timedelta(hours=1))
    )
    session.commit()

    entree = _par_tache(etat_des_taches(session, maintenant))["telemetrie"]

    assert (entree["statut"], entree["noeud"]) == ("ok", "rpi2")


def test_une_ligne_sans_noeud_n_en_invente_pas(session, maintenant):
    """Les lignes antérieures à 0137 restent « non enregistré » (#312)."""
    _ligne(session, "maintenance", None, il_y_a=timedelta(hours=2))

    entree = _par_tache(etat_des_taches(session, maintenant))["maintenance"]

    assert entree["noeud"] is None
    assert entree["noeud_enregistre"] is False


def test_les_deux_noeuds_d_une_tache_sont_listes(session, maintenant):
    _ligne(session, "maintenance", "rpi1", il_y_a=timedelta(hours=2))
    _ligne(session, "maintenance", "rpi2", il_y_a=timedelta(hours=3))

    entree = _par_tache(etat_des_taches(session, maintenant))["maintenance"]

    assert sorted(d["noeud"] for d in entree["noeuds"]) == ["rpi1", "rpi2"]


# ── Ce que le courriel de 06:00 en retient ──────────────────────────────────


def test_le_courriel_signale_une_tache_jamais_executee(session):
    lignes = problemes_taches(session)

    assert any("« maintenance » : aucune_execution" in ligne for ligne in lignes)
    assert lignes[-1].startswith("Détail : Administration")


def test_le_courriel_ne_repete_pas_ce_qu_un_autre_canal_couvre(session):
    """`backup` et `export_hors_site` ont leur canal ; `bascule` en échec envoie sa propre alerte."""
    _ligne(session, "bascule", "rpi1", statut="erreur", il_y_a=timedelta(hours=2))
    session.add(
        HistoriqueSauvegarde(
            statut=StatutSauvegarde.echouee,
            noeud="rpi1",
            cree_le=horloge.maintenant() - timedelta(hours=1),
        )
    )
    session.commit()

    lignes = "\n".join(problemes_taches(session))

    assert "« backup »" not in lignes
    assert "« export_hors_site »" not in lignes
    assert "« bascule »" not in lignes


def test_le_courriel_signale_une_maintenance_en_erreur(session):
    _ligne(session, "maintenance", "rpi1", statut="erreur", il_y_a=timedelta(hours=2))

    lignes = problemes_taches(session)

    assert any("« maintenance » : erreur" in ligne for ligne in lignes)


def test_sans_anomalie_le_courriel_n_ajoute_aucune_ligne(session, maintenant):
    """Tout est à jour : ni anomalie, ni ligne « Détail » orpheline."""
    for tache in ("maintenance", "bascule", "export_hors_site", "reliability", "audit_securite"):
        _ligne(session, tache, "rpi1", il_y_a=timedelta(hours=1))
    session.add(HistoriqueTelemetrie(statut="succes", noeud="rpi1", cree_le=maintenant))
    session.add(
        HistoriqueSauvegarde(statut=StatutSauvegarde.reussie, noeud="rpi1", cree_le=maintenant)
    )
    session.commit()

    assert problemes_taches(session) == []


#  ── « En échec récemment » : une fenêtre, pas les dix derniers de tous les temps ──


def test_les_echecs_recents_sont_bornes_dans_le_temps(session, maintenant):
    """🔴 Les deux échecs `reliability` du 15/10/2026 (#1997) ne restent pas « récents ».

    La requête prenait les dix dernières lignes en erreur, sans date : sur une
    infrastructure saine, un échec réglé restait affiché des mois.
    """
    fenetre = timedelta(days=FENETRE_ANOMALIES_J)
    _ligne(session, "reliability", "rpi1", statut="erreur", il_y_a=fenetre + timedelta(hours=1))
    _ligne(session, "bascule", "rpi2", statut="erreur", il_y_a=fenetre - timedelta(hours=1))
    _ligne(session, "maintenance", "rpi1", il_y_a=timedelta(hours=1))  # un succès : jamais

    assert [(a.tache, a.noeud) for a in anomalies_recentes(session, maintenant)] == [
        ("bascule", "rpi2")
    ]


def test_l_ecran_recoit_la_fenetre_qu_il_affiche():
    """Le libellé dit « ces N derniers jours » : N vient de l'API, jamais recopié."""
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.admin, roles_json=ROLE_OPERATEUR)
        reponse = http.get("/admin/maintenance/sante")
    assert reponse.status_code == 200
    assert reponse.json()["anomalies_fenetre_jours"] == FENETRE_ANOMALIES_J
