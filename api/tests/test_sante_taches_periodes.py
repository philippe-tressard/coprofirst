"""Deux fausses alertes que l'écran a produites en production (#542).

Le 20/08/2026, après avoir donné leurs sous-lignes par nœud à « Sauvegarde
quotidienne » et « Agrégation télémétrie » (#540), l'écran en affichait **trois**
par tâche, dont deux fausses :

    ↳ INCONNU   Exécution manquante   12 août 2026, 03:00
    ↳ RPI1      Exécution manquante   19 août 2026, 04:00
    ↳ RPI2      À jour                20 août 2026, 04:00

## 🔴 Fausse alerte n° 1 — « INCONNU » n'est pas une sonde

Les lignes antérieures à la migration 0137 n'ont pas de `noeud`. Les regrouper
leur donnait l'apparence d'une troisième sonde que **rien ne pourra jamais
rafraîchir** : la colonne est renseignée à chaque écriture depuis. Cette
sous-ligne restait donc « Exécution manquante » à jamais, et contaminait le pire
nœud — d'où un badge « INCONNU en retard » permanent sur la synthèse.

## 🔴 Fausse alerte n° 2 — 24 h par nœud, sur une tâche qui alterne

La sauvegarde tourne sur l'ACTIF, chaque nuit. La tâche a donc bien une période
de 24 h, mais **chaque nœud n'agit qu'une nuit sur deux**. Lui appliquer 24 h
marque un nœud sur deux comme « manquante » tous les jours, sur une
infrastructure parfaitement saine.

⚠️ **Cette leçon était déjà écrite dans le fichier**, pour `bascule` : *« 48 h et
non 24, parce que le rôle ALTERNE… constaté le 09/08/2026 »*. Elle n'avait pas
été reportée sur ces deux tâches-là, faute qu'elles aient jamais eu de
sous-lignes. Le jour où elles en ont eu, le défaut est réapparu à l'identique.

## Pourquoi ces tests-ci, et pas un test d'endpoint

Les deux défauts sont des **décisions**, pas des chemins : quel seuil pour quelle
sonde, et qu'est-ce qui compte comme sonde. Ils s'éprouvent sur la fonction
pure, avec une horloge fixe — sans base, sans conteneur, en quelques
millisecondes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.utils.sante_taches import (
    _PERIODICITE_ATTENDUE_H,
    _TACHES_DE_L_ACTIF,
    _TACHES_HORS_DES_NOEUDS,
    _TOUR_NORMAL_H,
    _entree_sante,
    _sante_par_noeud,
)

#: Horloge FIXE. Sans elle, un test qui passe à 23 h 59 échoue à 0 h 01.
MAINTENANT = datetime(2026, 8, 20, 16, 30)


def ligne(noeud, jours_avant, statut="succes", heure=4):
    """Une exécution, telle que la lit `_sante_par_noeud`."""
    return SimpleNamespace(
        noeud=noeud,
        statut=statut,
        cree_le=datetime(2026, 8, 20, heure, 0) - timedelta(days=jours_avant),
    )


def _grouper(lignes, tache="backup", periode_h=24):
    """La tâche entre, les deux seuils s'en déduisent.

    ⚠️ Les tests passaient d'abord les deux seuils explicitement. Un test de
    mutation a montré qu'ils étaient alors **aveugles au câblage** : remplacer
    la recherche du tour d'un nœud par `periode_h` aux deux points
    d'appel ne les faisait pas broncher. Passer par la tâche réelle éprouve la
    décision ET la table qui la porte.
    """
    return _sante_par_noeud(tache, lignes, periode_h, "echouee", MAINTENANT)


#  ── Fausse alerte n° 1 : « inconnu » n'est pas un nœud ──────────────────────


def test_une_ligne_sans_noeud_ne_cree_pas_de_sous_ligne():
    """Le cas exact vu à l'écran : une 3ᵉ sonde qui n'existe pas."""
    res = _grouper([ligne("rpi2", 0), ligne("rpi1", 1), ligne(None, 8)])
    assert [d["noeud"] for d in res["detail"]] == ["rpi1", "rpi2"], (
        "les lignes sans nœud enregistré forment une sonde fantôme"
    )


def test_une_ligne_sans_noeud_ne_contamine_pas_le_pire():
    """🔴 C'est elle qui produisait le badge « INCONNU en retard » permanent.

    Une sonde que rien ne peut rafraîchir reste éternellement en retard, et un
    avertissement permanent ne se lit plus (`standards/04` §18).
    """
    res = _grouper([ligne("rpi2", 0), ligne("rpi1", 1), ligne(None, 30)])
    assert res["pire"]["noeud"] != "inconnu"
    assert res["pire"]["statut"] == "ok", "un nœud sain est déclaré en retard"


def test_une_ligne_sans_noeud_compte_QUAND_MEME_pour_la_synthese():
    """⚠️ Elle n'est pas une sonde, mais la tâche a bien tourné.

    L'exclure de la synthèse ferait dire « aucune exécution » à un écran qui a
    des exécutions sous les yeux — le défaut inverse, et plus grave.
    """
    res = _grouper([ligne(None, 0)])
    assert res["synthese"]["derniere"] is not None
    assert res["synthese"]["statut"] == "ok"
    assert res["detail"] == [], "aucun nœud enregistré : aucune sous-ligne"


#  ── Fausse alerte n° 2 : la période de la TÂCHE ≠ celle d'un NŒUD ───────────


def test_un_noeud_qui_a_agi_avant_hier_n_est_pas_en_retard():
    """Le rôle alterne : chaque nœud n'agit qu'une nuit sur deux.

    rpi1 a sauvegardé il y a ~36 h. Avec 24 h, il était « manquante » — tous les
    jours, sur une infrastructure saine.
    """
    res = _grouper([ligne("rpi2", 0), ligne("rpi1", 1)])
    etats = {d["noeud"]: d["statut"] for d in res["detail"]}
    assert etats == {"rpi1": "ok", "rpi2": "ok"}, etats


def test_un_noeud_vraiment_muet_reste_signale():
    """⚠️ La tolérance ne doit pas devenir un aveuglement.

    Quatre jours sans agir dépassent largement les 48 h + 6 h : c'est le cas que
    les sous-lignes existent pour montrer.
    """
    res = _grouper([ligne("rpi2", 0), ligne("rpi1", 4)])
    etats = {d["noeud"]: d["statut"] for d in res["detail"]}
    assert etats["rpi1"] == "manquante"
    assert etats["rpi2"] == "ok"


def test_la_synthese_se_juge_sur_la_periode_de_la_TACHE():
    """Deux seuils, deux questions — et c'est le fond de ce lot.

    Aucun nœud n'a sauvegardé depuis 36 h. Chacun pris isolément est dans les
    clous (48 h), mais la TÂCHE, elle, aurait dû tourner cette nuit : la
    synthèse doit le dire.
    """
    res = _grouper([ligne("rpi1", 1), ligne("rpi2", 3)])
    assert res["synthese"]["statut"] == "manquante", (
        "la synthèse hérite du seuil par nœud : une tâche non exécutée passe inaperçue"
    )
    assert {d["statut"] for d in res["detail"]} == {"ok", "manquante"}


#  ── La déclaration elle-même ────────────────────────────────────────────────


def test_les_taches_qui_alternent_sont_declarees():
    """🔴 Le cas zéro de ce lot : sans la déclaration, rien ne change.

    `_TACHES_DE_L_ACTIF` est le seul endroit qui distingue « la tâche tourne
    toutes les 24 h » de « chaque nœud agit à son tour ». Vide ou amputée, le
    repli sur la période de la tâche ramène exactement la fausse alerte
    quotidienne. Le failover, lui, est éprouvé par `test_sante_taches_failover.py`.
    """
    assert _TACHES_DE_L_ACTIF == {"bascule", "backup", "telemetrie"}
    assert _TOUR_NORMAL_H == 48, "le rôle alterne : chaque nœud n'agit qu'une nuit sur deux"


def test_une_tache_absente_de_la_table_garde_la_periode_de_la_tache():
    """La maintenance hebdomadaire tourne sur les DEUX nœuds, pas en alternance.

    Le repli sur la période de la tâche n'est donc pas un défaut de
    configuration : c'est le cas normal, et il ne faut surtout pas lui appliquer
    le doublement réservé aux tâches qui alternent.

    rpi2 n'a pas fait sa maintenance depuis huit jours (192 h). Avec la période
    de la tâche (168 h + 6 h de marge) il est signalé — c'est le comportement
    attendu. S'il héritait d'un doublement, il faudrait deux SEMAINES de silence
    pour qu'un nœud muet apparaisse.
    """
    res = _grouper([ligne("rpi1", 0), ligne("rpi2", 8)], tache="maintenance", periode_h=168)
    etats = {d["noeud"]: d["statut"] for d in res["detail"]}
    assert etats == {"rpi1": "ok", "rpi2": "manquante"}, etats


#  ── La FORME des sous-lignes, éprouvée à l'exécution ────────────────────────


#: Ce que l'écran lit sur chaque sous-ligne. Une clé absente n'explose pas : la
#: ligne s'affiche vide et se lit « rien à signaler » — le défaut de #538.
CLES_SOUS_LIGNE = {"noeud", "statut", "portee", "derniere", "retard_heures"}


def test_chaque_sous_ligne_porte_les_cles_attendues():
    """🔴 Reprend, à l'exécution, ce que l'analyse statique ne voit plus.

    `test_sante_taches_forme.py` inspectait les littéraux affectés à `noeuds`.
    Depuis l'assemblage unique, `noeuds` reçoit un NOM — il n'y a plus de
    dictionnaire à lire dans le source. La vérification n'a pas disparu : elle a
    changé de nature, et c'est ici qu'elle vit.
    """
    res = _grouper([ligne("rpi1", 0), ligne("rpi2", 1)])
    assert res["detail"], "cas zéro : sans sous-ligne, ce test ne mesure rien"
    for sous_ligne in res["detail"]:
        assert set(sous_ligne) == CLES_SOUS_LIGNE, sorted(set(sous_ligne))
        assert isinstance(sous_ligne["noeud"], str), (
            "une sous-ligne doit porter un OBJET, pas une chaîne (#538)"
        )
    assert set(res["synthese"]) == CLES_SOUS_LIGNE, (
        "la synthèse et les sous-lignes partagent la même forme : l'écran les "
        "rend avec le même composant"
    )


#  ── Le battement de début : la seconde sonde (#488) ─────────────────────────
#
#  🔴 L'écran lisait LES RAPPORTS et rien d'autre. Une tâche qui TOURNE et dont
#  le rapport est refusé s'affichait « À jour » sur le rapport précédent, puis
#  « en retard » — deux jours de faux vert, puis un faux rouge, du 16 au
#  18/08/2026. Trois situations, deux états pour les dire.


def test_un_battement_RECENT_se_lit_EN_COURS():
    """La tâche a démarré il y a quelques minutes : elle travaille."""
    res = _grouper([ligne("rpi1", 0, statut="en_cours", heure=16)])
    assert res["detail"][0]["statut"] == "en_cours"


def test_un_battement_SANS_FIN_DE_COURSE_se_lit_RAPPORT_PERDU():
    """🔴 Le cas exact du 16/08 : la tâche a tourné, son rapport n'est pas arrivé.

    Six heures après son démarrage, une maintenance qui tient en quelques
    minutes n'est plus « en cours ». Et elle n'est pas « manquante » non plus :
    on a la trace de son démarrage. Confondre les deux enverrait chercher au
    mauvais endroit — du côté de la tâche, quand c'est la remontée qui est
    cassée.
    """
    res = _grouper([ligne("rpi1", 0, statut="en_cours", heure=10)])
    assert res["detail"][0]["statut"] == "rapport_perdu"


def test_le_battement_prime_sur_l_AGE():
    """⚠️ L'ordre des tests compte, et c'est tout le sujet.

    Un battement vieux de trois jours dépasse largement la période : tester
    « manquante » d'abord dirait « exécution manquante » d'une tâche dont on a
    la PREUVE du démarrage. C'est le faux rouge qu'on vient de supprimer.
    """
    res = _grouper([ligne("rpi1", 3, statut="en_cours")], periode_h=24)
    assert res["detail"][0]["statut"] == "rapport_perdu", (
        "un battement de début doit rester lisible comme « a tourné », quel que soit son âge"
    )


def test_un_rapport_de_FIN_efface_le_battement():
    """Le cas nominal : la tâche a bat, puis rendu compte. On lit la fin.

    Les deux lignes coexistent en base ; c'est la PLUS RÉCENTE qui parle, et
    c'est le rapport de fin. Sans cela, le battement rendrait la tâche
    éternellement « en cours ».
    """
    res = _grouper(
        [
            ligne("rpi1", 0, statut="succes", heure=4),
            ligne("rpi1", 0, statut="en_cours", heure=3),
        ]
    )
    assert res["detail"][0]["statut"] == "ok"


@pytest.mark.parametrize("ordre", ["battement_d_abord", "fin_d_abord"])
def test_le_rapport_de_FIN_l_emporte_a_DATE_EGALE(ordre):
    """🔴 Le cas RÉEL (#1367, 27/09/2026, signalé à l'écran) : même `cree_le`.

    `maintenance.sh` envoie son battement et son rapport de fin avec la MÊME
    heure de début (`$MAINTE_DEBUT`). Le test ci-dessus les séparait d'une heure
    — une valeur supposée, pas celle que le script envoie. À égalité, l'ordre de
    la base décidait, et c'était le battement : « Rapport non reçu » sur les
    deux nœuds, au premier dimanche où le battement a enfin été enregistré.
    """
    battement = ligne("rpi1", 0, statut="en_cours", heure=3)
    fin = ligne("rpi1", 0, statut="succes", heure=3)
    lignes = [battement, fin] if ordre == "battement_d_abord" else [fin, battement]
    res = _grouper(lignes, tache="maintenance", periode_h=168)
    assert res["detail"][0]["statut"] == "ok"
    assert res["synthese"]["statut"] == "ok"


def test_le_rapport_perdu_est_PLUS_GRAVE_qu_une_erreur():
    """Une erreur se voit ; un rapport perdu rend l'écran MUET.

    C'est ce silence qui a duré deux jours. La synthèse doit donc désigner le
    nœud dont le rapport manque, pas celui qui a échoué bruyamment.
    """
    res = _grouper(
        [
            ligne("rpi2", 0, statut="echouee", heure=4),
            ligne("rpi1", 0, statut="en_cours", heure=10),
        ]
    )
    assert res["pire"]["noeud"] == "rpi1"
    assert res["pire"]["statut"] == "rapport_perdu"


#  ── Fausse alerte n° 3 : la copie hors site n'a pas de nœud exécutant ───────


def _copie(lignes):
    tache = "export_hors_site"
    periode = _PERIODICITE_ATTENDUE_H[tache]
    return _entree_sante(
        tache, periode, _sante_par_noeud(tache, lignes, periode, "erreur", MAINTENANT)
    )


def test_la_copie_hors_site_ne_juge_pas_le_noeud_qui_n_a_pas_servi():
    """🔴 Le cas exact du 16/10/2026 : « RPI2 — Exécution manquante ».

    Le poste copie l'archive du nœud qui sert, puis rattrape celles de l'autre.
    Deux copies de suite sur le même actif laissaient le dernier rapport « de
    rpi2 » vieux de neuf jours, et rpi2 passait rouge — ses archives copiées.
    """
    entree = _copie([ligne("rpi1", 2), ligne("rpi1", 6), ligne("rpi2", 9)])
    assert entree["statut"] == "ok"
    assert entree["noeud"] == "rpi1", "le nœud source de la dernière copie reste nommé"
    assert entree["noeuds"] == [], "une sous-ligne par nœud pour une tâche du POSTE"
    assert entree["noeud_en_retard"] is None, "RPI2 en retard : la fausse alerte revient"


def test_la_copie_hors_site_vraiment_absente_reste_signalee():
    """Supprimer le jugement par nœud ne doit pas taire le seul qui compte."""
    entree = _copie([ligne("rpi1", 9), ligne("rpi2", 12)])
    assert entree["statut"] == "manquante"


def test_seule_la_copie_hors_site_est_hors_des_noeuds():
    """Cas zéro et garde : la déclaration sert, et ne s'étend pas en silence.

    Une tâche de plus dans cette table perdrait ses sous-lignes — donc la
    protection de #331 (un nœud sain ne compense pas un nœud muet).
    """
    assert _TACHES_HORS_DES_NOEUDS == {"export_hors_site"}
    #  Témoin : une tâche d'un NŒUD garde ses sous-lignes, rpi2 muet compris.
    res = _grouper([ligne("rpi1", 0), ligne("rpi2", 8)], tache="maintenance", periode_h=168)
    assert {d["noeud"]: d["statut"] for d in res["detail"]} == {"rpi1": "ok", "rpi2": "manquante"}
