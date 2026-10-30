"""Santé des tâches planifiées — la DÉCISION, séparée de la requête.

Ce module ne connaît ni la base, ni FastAPI, ni le nœud qui répond : on lui
donne des lignes d'historique et une horloge, il rend un état par nœud et une
synthèse. C'est ce qui permet de l'éprouver par mutation, en quelques
millisecondes, sans conteneur — `api/tests/test_sante_taches_periodes.py`.

## Pourquoi il a été extrait (#542)

`routers/admin/exploitation.py` a franchi les 500 lignes en accueillant le
correctif des fausses alertes. La règle de modularité (rang 1) impose de
découper, et la coupure était déjà dessinée : d'un côté trois fonctions pures,
de l'autre des endpoints qui lisent la base. Le fichier n'a pas été coupé « à
l'endroit où ça dépassait », mais à la seule couture qui existait.

## Les deux notions que ce module tient séparées

**La période de la TÂCHE** — à quel rythme elle doit s'exécuter — et **la
période de chaque NŒUD** — à quel rythme *ce nœud-là* doit y participer. Les
confondre produit une fausse alerte quotidienne sur une infrastructure saine, et
c'est arrivé deux fois : le 09/08/2026 sur `bascule`, le 20/08/2026 sur
`backup` et `telemetrie`.
"""

from __future__ import annotations

_PERIODICITE_ATTENDUE_H = {
    "maintenance": 7 * 24,  # dimanche 03:00, sur les deux nœuds
    #  48 h est la période de la TÂCHE, et non 24 : une bascule ANNULÉE (pair
    #  injoignable, disque plein, code non synchronisé) sort sans rapport, après
    #  son propre courriel d'alerte — l'actif reste en place et rebascule la nuit
    #  suivante. Une nuit sans bascule n'est donc pas une panne ; deux le sont.
    #  Le rythme de CHAQUE NŒUD est une autre question : `_TACHES_DE_L_ACTIF`.
    #  (Ce commentaire disait jusqu'au 18/10/2026 « une nuit sur deux par nœud »
    #  — vrai en alternance stricte, faux au premier failover, #2072.)
    "bascule": 48,  # 02:00, sur l'actif seul
    #  Copie hors site : lancée À LA MAIN depuis le poste, qui n'est pas
    #  allumé en permanence. Attendre 24 h ferait crier ce contrôle presque
    #  tous les jours, et une alerte qui crie tout le temps finit ignorée —
    #  c'est ainsi qu'un contrôle meurt (standards/07 §5). Une semaine est le
    #  rythme réellement tenable ; au-delà, l'absence redevient un signal.
    "export_hors_site": 7 * 24,
    #  Les contrôles de fiabilité (`check-reliability.sh`, */15, les deux
    #  nœuds) ne rendent compte que quand leurs constats CHANGENT, et au moins
    #  une fois par jour (`lib-notification.sh`, 27/09/2026) : 24 h est donc
    #  leur battement, et son absence dit un contrôleur mort.
    "reliability": 24,
    #  L'audit de sécurité nocturne (`audit-securite.sh`, S1 à S6) : une fois par
    #  jour sur CHAQUE nœud, lancé par check-reliability après 04:00 — un rapport
    #  par passage, nœud par nœud. Son absence dit un nœud qui ne s'audite plus.
    "audit_securite": 24,
}
#
#  Même principe pour l'agrégation de TÉLÉMÉTRIE : sa propre table
#  `historique_telemetrie`, alimentée in-process par `run_telemetry_aggregation`.
#  Si ce job s'arrête, les statistiques d'usage deviennent silencieusement
#  fausses sans qu'aucun écran ne le signale — c'est le même besoin que pour la
#  maintenance et la sauvegarde, donc le même traitement plutôt qu'un régime à
#  part pour une troisième table.
_PERIODICITE_SAUVEGARDE_H = 24  # 03:00, tracée dans historique_sauvegarde
_PERIODICITE_TELEMETRIE_H = 24  # 02:00, tracée dans historique_telemetrie
#: 🔴 Les tâches qui ne tournent que sur l'ACTIF — chaque nuit, sur le nœud qui
#: sert. La TÂCHE a sa période (24 h, 48 h pour la bascule) ; chaque NŒUD n'y
#: participe qu'à son TOUR, et ce tour ne se règle pas sur une période fixe.
#:
#: Le rôle alterne chaque nuit : en régime, un nœud agit une nuit sur deux, et
#: ses deux exécutions sont espacées de 48 h (`_TOUR_NORMAL_H`). Mais un nombre
#: IMPAIR de changements de rôle — un failover, une bascule annulée — le laisse
#: hors du rôle actif deux nuits de suite : 72 h (`_TOUR_APRES_FAILOVER_H`).
#: Juger chaque nœud sur 48 h + 6 h l'a mis en « Exécution manquante » le
#: lendemain du failover du 17/10/2026 (15:42), sur les trois tâches, alors
#: qu'elles avaient tourné chaque nuit (#2072). C'était la troisième fois que ce
#: seuil faisait crier une infrastructure saine (09/08 sur `bascule`, 20/08 sur
#: `backup` et `telemetrie`, #542).
#:
#: ⚠️ « Ce nœud était-il l'actif à l'heure prévue ? » ne se lit pas en base : le
#: failover ne rend aucun rapport à l'API, et celui de la bascule ne dit que la
#: passation de 02:00. D'où la règle, qui ne demande que les rapports :
#:
#: - la SYNTHÈSE reste le juge de la tâche : ne tourne-t-elle plus, elle est
#:   rouge, et chaque nœud avec elle ;
#: - au-delà de son tour normal, un nœud dont la tâche tourne est « Pas actif à
#:   l'heure » (neutre) — c'est l'autre nœud qui a eu les nuits ;
#: - au-delà de ce qu'un failover explique (trois nuits), il redevient rouge :
#:   c'est le nœud muet quand il est actif, celui que les sous-lignes existent
#:   pour montrer (#331, #540).
#:
#: Ce que la règle ne voit pas : une nuit manquée par un nœud, suivie d'une
#: nuit de l'autre, se lit « Pas actif à l'heure » — la synthèse, elle, a été
#: rouge entre les deux. 🔒 `test_sante_taches_failover.py`.
#:
#: Une tâche absente de cette table est jugée sur sa propre période : c'est le
#: cas quand les deux nœuds l'exécutent vraiment chacun (maintenance, contrôles).
_TACHES_DE_L_ACTIF = frozenset({"bascule", "backup", "telemetrie"})
_TOUR_NORMAL_H = 48
_TOUR_APRES_FAILOVER_H = 72

#: L'état neutre d'une sous-ligne : le nœud n'a pas eu son tour, l'autre l'a eu.
STATUT_PAS_ACTIF = "pas_actif"

_TOLERANCE_H = 6  # marge avant de déclarer un retard

#: 🔴 Les tâches qu'AUCUN nœud n'exécute : pas de sous-ligne par nœud.
#:
#: La copie hors site est lancée depuis le POSTE (`scripts/poste/export-hors-site.sh`).
#: Le `noeud` de son rapport est la SOURCE de l'archive du jour — le nœud qui
#: sert —, pas un exécutant : le même passage rattrape ensuite les archives de
#: l'autre nœud (§4 du script). Juger chaque nœud sur 7 j + 6 h mettait donc
#: « Exécution manquante » sur celui qui n'avait pas servi lors des deux
#: dernières copies, alors que ses archives étaient copiées — constaté le
#: 16/10/2026 : RPI2 rouge, dernier rapport le 07/10, copie à jour le 14/10.
#:
#: Attribuer le rapport aux deux nœuds quand le rattrapage réussit a été écarté :
#: le standby ne produit d'archive que les nuits où il était actif, et un
#: rattrapage « réussi » sans rien à rattraper n'atteste rien de lui. La seule
#: question juste est celle de la synthèse : la copie a-t-elle eu lieu ?
#: La fraîcheur de l'archive copiée, elle, est jugée par `_check_export_hors_site`.
_TACHES_HORS_DES_NOEUDS = frozenset({"export_hors_site"})

#: Ce que l'écran appelle « en échec récemment » : les échecs des N derniers
#: jours, pas les dix derniers de tous les temps. Sans borne, les deux échecs
#: de `reliability` du 15/10/2026 (#1997) seraient restés « récents » jusqu'à
#: ce que dix autres les poussent dehors. Une semaine : le rythme des plus
#: lentes des tâches (maintenance, copie hors site), dont un échec doit rester
#: visible jusqu'au passage suivant. L'API rend la valeur, l'écran la dit.
FENETRE_ANOMALIES_J = 7


#  Gravité croissante : sert à choisir l'état d'une tâche qui s'exécute sur les
#  DEUX nœuds. C'est toujours le PIRE qui doit remonter — un nœud sain ne
#  compense pas un nœud muet, il le masque.
#: 🔴 LE STATUT QU'UN SCRIPT ÉCRIT AVANT DE TRAVAILLER (#488).
#:
#: L'écran lisait LES RAPPORTS et rien d'autre : il répondait donc à « ai-je un
#: compte rendu récent ? » quand la question posée est « la tâche a-t-elle
#: tourné ? ». Une tâche qui tourne et dont le rapport est refusé s'affichait
#: « À jour » sur le rapport précédent, puis « en retard » — deux jours de faux
#: vert puis un faux rouge, du 16 au 18/08/2026.
#:
#: `maintenance.sh` écrit désormais une ligne AVANT son travail. Si le rapport
#: de fin n'arrive pas, la dernière ligne du nœud reste `en_cours`, et l'écart
#: devient lisible en base.
STATUT_EN_COURS = "en_cours"

#: Un rapport qui a tourné et relève des POINTS DE VIGILANCE, sans échec
#: (`check-reliability.sh` : des WARN, aucun FAIL). Ni « À jour », qui les
#: tairait, ni « En échec », qui crierait sur un défaut de confort.
STATUT_AVERTISSEMENT = "avertissement"


def sans_battements_remplaces(lignes) -> list:
    """Les lignes d'historique, sans les battements qu'un rapport de fin remplace.

    Un battement et son rapport partagent tâche, nœud, portée et heure de début.
    Depuis le 27/09/2026 (#1367), le rapport REPREND la ligne du battement
    (`rapports_scripts.enregistrer_rapport`) ; ce filtre sert les lignes écrites
    avant, pour que l'historique n'affiche pas d'exécution vide en double.
    """
    lignes = list(lignes)

    def cle(ligne):
        return (ligne.tache, ligne.noeud, getattr(ligne, "portee", None), ligne.cree_le)

    fins = {cle(ligne) for ligne in lignes if ligne.statut != STATUT_EN_COURS}
    return [
        ligne for ligne in lignes if not (ligne.statut == STATUT_EN_COURS and cle(ligne) in fins)
    ]


#: ⚠️ Au-delà de ce délai, un battement sans fin de course n'est plus « en
#: cours » : c'est un rapport PERDU. La maintenance la plus longue tient en
#: quelques minutes — deux heures sont larges, et le fait qu'elles soient larges
#: est le but : on ne veut pas signaler une exécution qui traîne.
#:
#: 🔴 Un battement de démarrage sans fin de course ne doit JAMAIS se lire comme
#: un succès (`standards/04` §4). Les deux états ci-dessous existent pour cela,
#: et ils sont DISTINCTS de « manquante » : la tâche a tourné, c'est sa remontée
#: qui est cassée. Confondre les deux enverrait chercher au mauvais endroit.
_DELAI_FIN_DE_COURSE_H = 2

#: `rapport_perdu` est plus grave qu'une erreur : une erreur, on la voit ; un
#: rapport perdu rend l'écran MUET, et c'est ce silence qui a duré deux jours.
_GRAVITE = {
    "ok": 0,
    "en_cours": 0,
    STATUT_PAS_ACTIF: 0,
    "vigilance": 1,
    "erreur": 2,
    "rapport_perdu": 3,
    "manquante": 4,
    "aucune_execution": 5,
}


#: Combien de lignes remonter pour retrouver les deux nœuds d'une tâche.
#:
#: Le rôle alterne chaque nuit : une tâche qui ne tourne que sur l'ACTIF change
#: donc de nœud tous les jours, et deux exécutions suffisent en théorie. Vingt
#: laissent de la marge pour une tâche hebdomadaire ou un nœud qui a manqué
#: plusieurs tours — c'est justement celui-là qu'on cherche à voir.
_LIGNES_REMONTEES = 20


def _pas_actif_a_l_heure(tache: str, age_h: float, statut_synthese: str) -> bool:
    """PURE. Le silence d'un nœud s'explique-t-il par le rôle, et non par une panne ?

    Oui pour une tâche de l'actif seul, tant que la TÂCHE tourne (l'autre nœud a
    eu les nuits) et que le silence tient dans ce qu'un failover explique.
    Règle et raisons : `_TACHES_DE_L_ACTIF` (#2072).
    """
    return (
        tache in _TACHES_DE_L_ACTIF
        and statut_synthese != "manquante"
        and age_h <= _TOUR_APRES_FAILOVER_H + _TOLERANCE_H
    )


def _sante_par_noeud(
    tache: str,
    lignes,
    periode_h: float,
    statut_erreur,
    maintenant,
) -> dict:
    """L'état d'une tâche, **un sous-état par nœud** — pour TOUTES les tâches.

    ## Pourquoi cette fonction existe (#540)

    Signalé à l'écran le 20/08/2026, capture à l'appui : « Sauvegarde
    quotidienne » et « Agrégation télémétrie » n'affichaient qu'**une** sous-ligne
    là où « Bascule » et « Copie hors site » en affichaient deux.

    Ce n'était pas un défaut d'affichage. Les deux branches de calcul ne
    lisaient pas la même chose :

    | Tâches | Lecture | Nœuds possibles |
    |---|---|---|
    | maintenance, bascule, export | 20 dernières lignes, groupées par nœud | 2 |
    | sauvegarde, télémétrie | `.limit(1)` — **une seule ligne** | 1, toujours |

    🔴 La seconde branche ne pouvait **physiquement** pas montrer deux nœuds,
    quel que soit le contenu de la base. Or ces deux tables portent une colonne
    `noeud` indexée depuis la migration 0137, et ces tâches tournent sur l'actif
    — qui alterne chaque nuit. Les deux nœuds y sont donc, et l'écran n'en
    montrait qu'un.

    ⚠️ **Conséquence, et c'est le sujet de #488** : si un nœud cessait
    complètement de sauvegarder, l'écran continuerait d'afficher « À jour » avec
    le nœud de l'autre. Un nœud sain compenserait un nœud muet — exactement ce
    que les sous-lignes ont été introduites pour empêcher (#331).

    ⚠️ Le commentaire de la boucle historique attribuait ce manque à des tâches
    « qui n'enregistrent pas leur nœud ». C'était vrai le 11/08/2026 ; la colonne
    existe depuis, et la raison n'a pas été relue. Une explication juste à
    l'écriture devient un alibi quand ce qu'elle décrit a changé.

    ## Ce que la fonction rend

    `detail` (un état par nœud, trié), `recente` (la dernière exécution réelle,
    tous nœuds confondus) et `pire` (le nœud le plus dégradé). La synthèse porte
    la date de `recente` : retenir le pire ÉTAT est juste, lui emprunter sa DATE
    fait mentir la colonne « Dernier rapport » (#331, 13/08/2026).
    """
    #  🔴 À DATE ÉGALE, LE RAPPORT DE FIN L'EMPORTE SUR LE BATTEMENT (#1367).
    #  `maintenance.sh` envoie les deux avec la même heure de début : départagées
    #  par `cree_le` seul, c'est l'ordre de la base qui décidait — et il donnait
    #  le battement, donc « Rapport non reçu » sur une maintenance réussie. Le tri
    #  ICI, et non chez l'appelant : la règle ne doit dépendre d'aucune requête.
    lignes = sorted(
        lignes,
        key=lambda ligne: (ligne.cree_le, ligne.statut != STATUT_EN_COURS),
        reverse=True,
    )
    if not lignes:
        return {}

    #  🔴 Les deux seuils se déduisent ICI, pas chez les appelants.
    #
    #  La recherche du tour d'un nœud a d'abord vécu aux deux
    #  points d'appel : deux copies du même geste, donc deux occasions de
    #  diverger — et un test de mutation les a trouvées TOUTES DEUX aveugles,
    #  puisque les tests de cette fonction lui passent des seuils explicites.
    #  Rentrer la recherche dans la fonction supprime le câblage plutôt que de
    #  le tester (`standards/02` §1).
    periode_noeud_h = _TOUR_NORMAL_H if tache in _TACHES_DE_L_ACTIF else periode_h

    def _etat(ligne, seuil_h):
        age_h = (maintenant - ligne.cree_le).total_seconds() / 3600
        #  🔴 Le battement de début se lit AVANT tout le reste : une tâche qui a
        #  démarré a TOURNÉ, quoi qu'en dise l'âge de son dernier rapport.
        #  L'ordre compte — tester « manquante » d'abord dirait « jamais
        #  exécutée » d'une tâche dont on a la trace du démarrage.
        if ligne.statut == STATUT_EN_COURS:
            statut = "en_cours" if age_h <= _DELAI_FIN_DE_COURSE_H else "rapport_perdu"
        elif age_h > seuil_h + _TOLERANCE_H:
            statut = "manquante"
        elif ligne.statut == statut_erreur:
            statut = "erreur"
        elif ligne.statut == STATUT_AVERTISSEMENT:
            statut = "vigilance"
        else:
            statut = "ok"
        return statut, round(age_h, 1)

    #  🔴 « inconnu » N'EST PAS UN NŒUD (#542).
    #
    #  Les lignes antérieures à la migration 0137 n'ont pas de `noeud`. Les
    #  regrouper sous « INCONNU » leur donnait une sous-ligne — donc l'apparence
    #  d'une troisième sonde — que RIEN ne pourra jamais rafraîchir : la colonne
    #  est renseignée à chaque écriture depuis. Elle restait donc « Exécution
    #  manquante » à jamais, et contaminait `pire`, d'où un badge « INCONNU en
    #  retard » permanent sur la synthèse.
    #
    #  ⚠️ Un avertissement permanent ne se lit plus (`standards/04` §18) — et le
    #  commentaire de `noeud_en_retard`, vingt lignes plus bas, le cite déjà.
    #  Ces lignes restent comptées pour la SYNTHÈSE : la tâche a bien tourné, on
    #  ne sait simplement pas où.
    par_noeud: dict = {}
    for ligne in lignes:
        cle = getattr(ligne, "noeud", None)
        #  Une tâche que le poste exécute n'a pas de nœud à juger : son `noeud`
        #  dit d'où vient l'archive, pas qui l'a copiée.
        if not cle or tache in _TACHES_HORS_DES_NOEUDS:
            continue
        if cle not in par_noeud:
            par_noeud[cle] = ligne

    #  La SYNTHÈSE porte la dernière exécution réelle, nœud enregistré ou non,
    #  et se juge sur la période de la TÂCHE.
    #  La première de la liste triée : `max(cree_le)` rouvrirait l'égalité.
    plus_recente = lignes[0]
    statut_s, retard_s = _etat(plus_recente, periode_h)
    synthese = {
        "noeud": getattr(plus_recente, "noeud", None),
        "statut": statut_s,
        "portee": getattr(plus_recente, "portee", "applicative"),
        "derniere": plus_recente.cree_le,
        "retard_heures": retard_s,
    }

    #  Chaque NŒUD se juge sur SON tour — une nuit sur deux pour les tâches
    #  qui ne tournent que sur l'actif, trois après un failover.
    detail = []
    for noeud, ligne in sorted(par_noeud.items()):
        statut, retard = _etat(ligne, periode_noeud_h)
        if statut == "manquante" and _pas_actif_a_l_heure(tache, retard, statut_s):
            statut = STATUT_PAS_ACTIF
        detail.append(
            {
                "noeud": noeud,
                "statut": statut,
                #  `portee` n'existe que sur `historique_maintenance` ; les deux
                #  autres tables n'ont qu'une portée, applicative.
                "portee": getattr(ligne, "portee", "applicative"),
                "derniere": ligne.cree_le,
                "retard_heures": retard,
            }
        )
    return {
        "detail": detail,
        "synthese": synthese,
        #  Aucun nœud enregistré : pas de « pire nœud » à nommer.
        "pire": max(detail, key=lambda d: _GRAVITE.get(d["statut"], 0)) if detail else None,
    }


def _entree_sante(tache: str, periode_h: float, groupes: dict) -> dict:
    """Assemble l'entrée de réponse à partir des sous-états — une seule fois.

    Les deux branches composaient ce dictionnaire séparément, et c'est ainsi que
    `noeuds` a fini par porter deux formes (#538) : une liste d'objets d'un côté,
    une liste de chaînes de l'autre. Un assemblage unique rend la divergence
    impossible plutôt qu'improbable.
    """
    if not groupes:
        return {
            "tache": tache,
            "noeud": None,
            "noeuds": [],
            "noeud_enregistre": False,
            "statut": "aucune_execution",
            "derniere": None,
            "retard_heures": None,
            "periodicite_heures": periode_h,
            "noeud_en_retard": None,
            "statut_en_retard": None,
        }
    detail, synthese, pire = groupes["detail"], groupes["synthese"], groupes["pire"]
    degrade = bool(pire) and _GRAVITE.get(pire["statut"], 0) > _GRAVITE.get(synthese["statut"], 0)
    return {
        "tache": tache,
        "noeud": synthese["noeud"],
        "noeuds": detail,
        #  Faux quand la dernière exécution est antérieure à 0137 : l'écran écrit
        #  alors « non enregistré » plutôt qu'un nom de nœud inventé.
        "noeud_enregistre": bool(synthese["noeud"]),
        "portee": synthese["portee"],
        "statut": synthese["statut"],
        "derniere": synthese["derniere"],
        "retard_heures": synthese["retard_heures"],
        "periodicite_heures": periode_h,
        #  Nommé seulement s'il est RÉELLEMENT plus grave que la dernière
        #  exécution : sinon l'écran afficherait un avertissement sur une
        #  infrastructure saine, et un avertissement permanent ne se lit plus
        #  (`standards/04-fiabilite-des-controles.md` §18).
        "noeud_en_retard": pire["noeud"] if degrade else None,
        "statut_en_retard": pire["statut"] if degrade else None,
    }


def _etat_tache_a_table_propre(
    tache: str,
    lignes_historique,
    periode_h: float,
    statut_erreur,
    maintenant,
) -> dict:
    """Santé d'une tâche qui a SA PROPRE table (sauvegarde, agrégation).

    ⚠️ Elle reçoit désormais **les N dernières lignes** et non la seule dernière
    (#540). Avec `.limit(1)`, cette branche ne pouvait physiquement montrer qu'UN
    nœud — quel que soit le contenu de la base — là où les tâches de
    `historique_maintenance` en montraient deux. Or ces tables portent une
    colonne `noeud` depuis la migration 0137, et ces tâches tournent sur l'ACTIF,
    qui alterne chaque nuit : les deux nœuds y sont.

    Le nœud est **lu en base**, jamais déduit ici. Jusqu'au 11/08/2026 on y
    mettait `noeud_courant()` — le nœud qui répond à CETTE requête — dans une
    colonne que le lecteur comprend comme « le nœud qui a exécuté la tâche ». Le
    rôle alternant, c'était faux une fois sur deux.

    Les lignes antérieures à 0137 restent `None`, donc « inconnu » — jamais une
    valeur inventée (`standards/04` : ne pas présenter un défaut comme une
    mesure).
    """
    return _entree_sante(
        tache,
        periode_h,
        _sante_par_noeud(tache, lignes_historique, periode_h, statut_erreur, maintenant),
    )


# ── Ce que le contrôle de 06:00 signale par courriel (27/09/2026) ──────────────
#
#  L'écran montrait une tâche « Exécution manquante » ou « En échec », et
#  personne n'en était prévenu : le courriel de 06:00 ne regardait que la
#  sauvegarde et la copie hors site. Une maintenance hebdomadaire en erreur
#  attendait donc qu'on ouvre l'écran.
#
#  🔴 Mais JAMAIS deux fois le même fait : plusieurs tâches ont déjà leur canal,
#  et les répéter ici enverrait deux courriels pour un seul défaut. Ce qui est
#  couvert ailleurs se DÉCLARE ici, avec le canal qui le couvre — une exclusion
#  non écrite serait un oubli qui ressemble à une décision.
#  🔒 `test_sante_taches_alerte.py` exige que chaque tâche nommée existe.

#: Les états qui méritent un courriel. `vigilance` n'y est pas : c'est un point
#: de confort, et le digest quotidien de `check-reliability` le porte déjà.
ETATS_SIGNALES = frozenset({"erreur", "rapport_perdu", "manquante", "aucune_execution"})

#: tâche → (états déjà signalés ailleurs, par quel canal). `"noeud"` couvre le
#: retard d'UN nœud quand l'autre rend compte.
DEJA_SIGNALE: dict[str, tuple[frozenset, str]] = {
    "backup": (ETATS_SIGNALES | {"noeud"}, "_check_backups, dans le même courriel"),
    "export_hors_site": (
        ETATS_SIGNALES | {"noeud"},
        "_check_export_hors_site, dans le même courriel",
    ),
    "bascule": (frozenset({"erreur"}), "bascule.sh envoie sa propre alerte à l'échec"),
    "reliability": (
        frozenset({"erreur", "noeud"}),
        "check-reliability alerte de ses FAIL, et C15 de l'arrêt du contrôleur voisin",
    ),
    "audit_securite": (
        frozenset({"erreur", "noeud"}),
        "audit-securite.sh alerte de ses FAIL, et C40 du nœud où il n'a pas eu lieu",
    ),
}


def anomalies_a_signaler(taches: list[dict]) -> list[str]:
    """PURE. Les entrées de la synthèse → les lignes du courriel de 06:00.

    Le nom de la tâche est son identifiant, et l'état sa clé : leurs libellés
    vivent dans le front (`#lib/taches.ts`), et les recopier ici ferait deux
    sources. La dernière ligne envoie à l'écran, qui les nomme.
    """
    lignes = []
    for t in taches:
        couverts = DEJA_SIGNALE.get(t["tache"], (frozenset(), ""))[0]
        if t["statut"] in ETATS_SIGNALES and t["statut"] not in couverts:
            lignes.append(f"Tâche planifiée « {t['tache']} » : {t['statut']}")
        elif t.get("statut_en_retard") in ETATS_SIGNALES and "noeud" not in couverts:
            lignes.append(
                f"Tâche planifiée « {t['tache']} » : {t['statut_en_retard']} "
                f"sur {t.get('noeud_en_retard') or '?'}"
            )
    if lignes:
        lignes.append("Détail : Administration › Maintenance › Santé des tâches planifiées")
    return lignes
