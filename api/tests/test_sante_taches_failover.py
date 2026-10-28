"""Le tour d'un nœud, rejoué heure par heure — failover compris (#2072).

## Le faux rouge du 18/10/2026

Les tâches de l'actif seul (bascule, sauvegarde, agrégation de télémétrie)
jugeaient chaque nœud sur 48 h + 6 h : une alternance stricte. Le failover
rpi1 → rpi2 du 17/10 à 15:42 a fait un nombre IMPAIR de changements de rôle, et
un nœud est resté deux nuits de suite hors du rôle actif. Le lendemain, RPI1 était
rouge « Exécution manquante » sur la bascule et la télémétrie (dernier rapport le
16/10 à 02:00) et RPI2 le devenait sur la sauvegarde (le 16/10 à 03:00) — alors
que les trois tâches avaient tourné chaque nuit.

## Ce que ces tests rejouent

Pas des lignes posées à la main : une CHRONOLOGIE des rôles — bascules de 02:05,
failover — d'où l'on tire qui a exécuté chaque tâche, puis l'écran est jugé à
chaque demi-heure. Un seuil choisi pour passer un instant précis passerait le
test et crierait l'heure suivante ; c'est ainsi que les 48 h ont tenu deux mois.

Les témoins disent l'inverse : une tâche qui ne tourne plus est rouge, et un
nœud qui reste muet quand il est actif aussi — c'est ce que les sous-lignes
existent pour montrer (#331, #540).
"""

from __future__ import annotations

import pathlib
import re
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.utils.sante_taches import (
    _GRAVITE,
    _PERIODICITE_ATTENDUE_H,
    _PERIODICITE_SAUVEGARDE_H,
    _PERIODICITE_TELEMETRIE_H,
    STATUT_PAS_ACTIF,
    _entree_sante,
    _sante_par_noeud,
    anomalies_a_signaler,
)

#: tâche → (heure d'exécution, période de la tâche). Les heures sont celles des
#: rapports constatés le 18/10 : la bascule et la télémétrie partent à 02:00 du
#: nœud encore actif, la sauvegarde à 03:00 de celui qui vient de le devenir.
TACHES = {
    "bascule": (2, _PERIODICITE_ATTENDUE_H["bascule"]),
    "telemetrie": (2, _PERIODICITE_TELEMETRIE_H),
    "backup": (3, _PERIODICITE_SAUVEGARDE_H),
}

#: Ce que l'écran peint en rouge ou en orange : rien de tel n'est permis sur une
#: infrastructure saine.
ETATS_ALARMANTS = {"manquante", "erreur", "rapport_perdu", "aucune_execution", "vigilance"}

FAILOVER_DU_17 = datetime(2026, 10, 17, 15, 42)


def _chronologie(debut, fin, actif_initial, failovers=()):
    """Les changements de rôle : une bascule chaque nuit à 02:05, plus les failovers.

    Rend une fonction « quel nœud est actif à cet instant ? ».
    """
    autre = {"rpi1": "rpi2", "rpi2": "rpi1"}
    evenements = sorted(
        [debut.replace(hour=2, minute=5) + timedelta(days=j) for j in range((fin - debut).days + 1)]
        + list(failovers)
    )

    def actif_a(instant):
        noeud = actif_initial
        for e in evenements:
            if e > instant:
                break
            noeud = autre[noeud]
        return noeud

    return actif_a


def _rapports(tache, actif_a, debut, fin, muet=lambda noeud, jour: False):
    """Les lignes d'historique qu'aurait écrites l'actif, nuit après nuit."""
    heure = TACHES[tache][0]
    lignes = []
    jour = debut.replace(hour=heure, minute=0)
    while jour <= fin:
        noeud = actif_a(jour)
        if not muet(noeud, jour):
            lignes.append(SimpleNamespace(noeud=noeud, statut="succes", cree_le=jour))
        jour += timedelta(days=1)
    return lignes


def _ecran(tache, lignes, maintenant):
    """L'entrée que rend l'API pour cette tâche, à cet instant."""
    periode = TACHES[tache][1]
    vues = [lg for lg in lignes if lg.cree_le <= maintenant]
    return _entree_sante(
        tache, periode, _sante_par_noeud(tache, vues, periode, "echouee", maintenant)
    )


def _instants(debut, fin):
    t = debut
    while t <= fin:
        yield t
        t += timedelta(minutes=30)


#  ── La séquence du 16-18/10 : bascule, bascule, failover, bascule ──────────

#  rpi2 actif jusqu'au 15/10 02:05 ; rpi1 a donc fait la bascule du 16/10 à 02:00.
DEBUT, FIN = datetime(2026, 10, 10), datetime(2026, 10, 22)
ACTIF_A = _chronologie(DEBUT, FIN, "rpi1", failovers=[FAILOVER_DU_17])


def test_la_chronologie_est_celle_constatee_le_18():
    """Cas zéro : sans les rapports vus à l'écran, le rejeu ne prouve rien."""
    bascules = _rapports("bascule", ACTIF_A, DEBUT, datetime(2026, 10, 18, 12))
    sauvegardes = _rapports("backup", ACTIF_A, DEBUT, datetime(2026, 10, 18, 12))
    assert max(lg.cree_le for lg in bascules if lg.noeud == "rpi1") == datetime(2026, 10, 16, 2)
    assert max(lg.cree_le for lg in sauvegardes if lg.noeud == "rpi2") == datetime(2026, 10, 16, 3)
    assert (
        ACTIF_A(FAILOVER_DU_17) == "rpi2"
        and ACTIF_A(FAILOVER_DU_17 - timedelta(minutes=1)) == "rpi1"
    )


def test_le_failover_du_17_ne_met_aucun_noeud_au_rouge():
    """🔴 Le garde-fou de #2072 : la séquence réelle, jugée toutes les demi-heures."""
    vus_hors_tour = set()
    for tache in TACHES:
        lignes = _rapports(tache, ACTIF_A, DEBUT, FIN)
        for maintenant in _instants(datetime(2026, 10, 14), datetime(2026, 10, 21, 23)):
            entree = _ecran(tache, lignes, maintenant)
            assert entree["statut"] == "ok", (tache, maintenant, entree["statut"])
            for n in entree["noeuds"]:
                assert n["statut"] not in ETATS_ALARMANTS, (tache, maintenant, n)
                if n["statut"] == STATUT_PAS_ACTIF:
                    vus_hors_tour.add((tache, n["noeud"]))
            assert entree["noeud_en_retard"] is None, (tache, maintenant, entree)
            assert anomalies_a_signaler([entree]) == [], (tache, maintenant)
    #  Témoin : le cas du 18/10 a bien été traversé — sinon ce test ne mesure rien.
    assert {("bascule", "rpi1"), ("telemetrie", "rpi1"), ("backup", "rpi2")} <= vus_hors_tour


def test_en_alternance_stricte_les_deux_noeuds_sont_a_jour():
    """Sans failover, aucun nœud n'a à être excusé : l'état neutre ne sert pas."""
    actif_a = _chronologie(DEBUT, FIN, "rpi1")
    for tache in TACHES:
        lignes = _rapports(tache, actif_a, DEBUT, FIN)
        for maintenant in _instants(datetime(2026, 10, 14), datetime(2026, 10, 21)):
            etats = {n["statut"] for n in _ecran(tache, lignes, maintenant)["noeuds"]}
            assert etats == {"ok"}, (tache, maintenant, etats)


#  ── Les témoins : un vrai silence reste rouge ───────────────────────────────


def test_une_tache_qui_ne_tourne_plus_est_rouge_et_ses_noeuds_aussi():
    """La synthèse reste le juge : plus d'agrégation après celle du 17/10 02:00.

    Le failover du même jour ne doit rien excuser : l'état neutre suppose que
    l'autre nœud a eu les nuits, et ici personne ne les a eues.
    """
    arret = datetime(2026, 10, 17, 3)
    lignes = _rapports("telemetrie", ACTIF_A, DEBUT, FIN, muet=lambda noeud, jour: jour > arret)
    assert _ecran("telemetrie", lignes, datetime(2026, 10, 18, 10))["statut"] == "manquante"
    #  Le 19/10 à 10:00, rpi2 se tait depuis 56 h : dans la fenêtre qu'un failover
    #  excuserait — mais la tâche ne tourne plus, et rien ne l'excuse.
    for jour in (datetime(2026, 10, 19, 10), datetime(2026, 10, 20, 12)):
        tard = _ecran("telemetrie", lignes, jour)
        assert tard["statut"] == "manquante"
        assert {n["statut"] for n in tard["noeuds"]} == {"manquante"}, (jour, tard["noeuds"])
    assert anomalies_a_signaler([tard]), "le courriel de 06:00 doit le dire"


def test_un_noeud_muet_quand_il_est_actif_redevient_rouge():
    """🔴 Le défaut que les sous-lignes existent pour montrer (#331).

    rpi1 ne sauvegarde plus depuis le 12/10 ; rpi2 sauvegarde ses nuits. Un nœud
    sain ne doit pas compenser un nœud muet : au-delà de trois nuits, ce que
    même un failover n'explique pas, rpi1 est rouge — et nommé sur la synthèse.
    """
    actif_a = _chronologie(DEBUT, FIN, "rpi1")
    lignes = _rapports(
        "backup",
        actif_a,
        DEBUT,
        FIN,
        muet=lambda noeud, jour: noeud == "rpi1" and jour > datetime(2026, 10, 12, 4),
    )
    for maintenant in _instants(datetime(2026, 10, 16), datetime(2026, 10, 21)):
        entree = _ecran("backup", lignes, maintenant)
        rpi1 = next(n for n in entree["noeuds"] if n["noeud"] == "rpi1")
        assert rpi1["statut"] == "manquante", (maintenant, rpi1)
        if entree["statut"] == "ok":
            assert entree["noeud_en_retard"] == "rpi1", (maintenant, entree)


def test_une_tache_des_deux_noeuds_n_est_jamais_excusee():
    """La maintenance tourne sur les DEUX nœuds : le rôle n'explique aucun silence."""
    maintenant = datetime(2026, 10, 18, 12)
    lignes = [
        SimpleNamespace(noeud="rpi1", statut="succes", cree_le=datetime(2026, 10, 18, 3)),
        SimpleNamespace(noeud="rpi2", statut="succes", cree_le=datetime(2026, 10, 10, 3)),
    ]
    res = _sante_par_noeud("maintenance", lignes, 168, "erreur", maintenant)
    assert {d["noeud"]: d["statut"] for d in res["detail"]} == {"rpi1": "ok", "rpi2": "manquante"}


#  ── L'écran sait le dire ─────────────────────────────────────────────────────

_TACHES_TS = pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "taches.ts"


def test_chaque_etat_rendu_par_l_api_a_son_libelle_a_l_ecran():
    """Un état sans libellé s'affiche en clair (« pas_actif ») et en ROUGE.

    L'écran retombe sur `badge-red` pour une clé inconnue : un état neutre ajouté
    ici sans son entrée dans `#lib/taches.ts` recréerait le faux rouge qu'il
    supprime. Les états se lisent dans `_GRAVITE`, la table qui les ordonne.
    """
    source = _TACHES_TS.read_text(encoding="utf-8")
    declares = set(re.findall(r"^\t(\w+): \{$", source, re.MULTILINE))
    assert "ok" in declares, "cas zéro : la lecture de taches.ts ne trouve rien"
    manquants = set(_GRAVITE) - declares
    assert not manquants, f"États sans libellé dans front/src/lib/taches.ts : {sorted(manquants)}"
