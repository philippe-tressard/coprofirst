#!/usr/bin/env bash
# =============================================================================
#  lib-verdicts-site-selftest.sh — auto-tests de C1 (site public) et de
#  `bascule_en_cours`, extraits de `lib-verdicts-selftest.sh` le 21/10/2026.
#
#  POURQUOI. Les cas de la troisième sonde (#2093) faisaient passer ce fichier à
#  501 lignes, au-dessus du plafond de modularité. La coupe suit un contrôle :
#  tout ce qui éprouve « le site public est-il réellement en panne ? ».
#
#  Module SOURCÉ après `lib-verdicts.sh`, jamais seul : `verdicts_selftest`
#  appelle `site_public_selftest`, qui écrit dans le même `st_fail`.
#  `bash check-reliability.sh --selftest` reste la seule commande.
# =============================================================================

site_public_selftest() {
  echo "-- verdict_site_public (C1) --"
  vs() { # description attendu code1 code2 deploiement
    local desc="$1" exp="$2"; shift 2
    local got; got=$(verdict_site_public "$@")
    if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
    else echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; fi
  }
  vs "site debout"                        "OK"              200 ""    non
  #  Le cas du 01/09/2026 à 05:42, qu'aucune sonde unique ne sait distinguer d'une
  #  panne : health-watch l'a écarté, C1 aurait alerté.
  vs "hoquet : revenu à la 2e sonde"      "TRANSITOIRE:503" 503 200   non
  #  Le cas du 01/09/2026 à 01:21 : le build tenait le verrou, Caddy rendait 503.
  vs "build en cours sur l'actif"         "DEPLOIEMENT:503" 503 503   oui
  #  🔴 Et le cas qui doit RESTER rouge — c'est pour lui que le contrôle existe.
  vs "vraiment KO, hors déploiement"      "KO:503"          503 503   non
  vs "injoignable (curl a échoué)"        "KO:000"          000 000   non
  #  Un déploiement n'excuse QUE le temps de son verrou : une fois relâché, le
  #  même 503 redevient un FAIL à l'exécution suivante.
  vs "503 persistant, verrou relâché"     "KO:503"          503 503   ""
  #  Une sonde qui n'a pas pu s'exécuter n'est pas un vert — `standards/04` §1.
  vs "première sonde impossible"          "INCONNU"         ""  ""    non
  #  ⚠️ Le code rendu est celui de la SECONDE sonde : c'est l'état au moment de
  #  décider. Un 502 devenu 503 doit se lire 503, pas 502.
  vs "l'état le plus récent gagne"        "KO:503"          502 503   non
  #  Sans seconde sonde (cas de repli), on garde ce qu'on a mesuré.
  vs "pas de seconde sonde"               "KO:502"          502 ""    non
  #  🔴 Le cas du 04/09/2026 à 02:06 : la bascule avait coupé cloudflared depuis
  #  47 secondes. Trois contrôles ont crié pour une opération planifiée réussie.
  vs "bascule en cours"                   "BASCULE:503"     503 503   non oui
  #  ⚠️ Et la borne : une bascule figée n'excuse plus rien. C'est
  #  `bascule_en_cours` qui rend "non" au-delà du seuil — vérifié juste après.
  vs "bascule finie, 503 persistant"      "KO:503"          503 503   non non
  #  L'ordre compte : une bascule pendant un build reste une bascule, c'est
  #  l'explication la plus proche de la coupure.
  vs "bascule ET build"                   "BASCULE:503"     503 503   oui oui
  #  🔴 Le cas du 20/10/2026 à 22:36 : le résolveur du nœud expirait, le site
  #  servait. La troisième sonde, résolue autrement, le dit.
  vs "DNS du nœud muet, site joint autrement" "RESOLUTION:000" 000 000 non non 200
  #  …et le cas qui doit RESTER rouge : l'autre chemin n'atteint rien non plus.
  vs "DNS muet, autre chemin KO aussi"    "KO:000"          000 000   non non 000
  vs "autre chemin : le site est en erreur" "KO:503"        000 000   non non 503
  #  Pas de troisième sonde (échec hors résolution) : rien ne change.
  vs "sans troisième sonde"               "KO:000"          000 000   non non ""

  echo "-- bascule_en_cours (C1/C2/C3) --"
  vb() { # description attendu lock_self lock_peer maintenant seuil
    local desc="$1" exp="$2"; shift 2
    local got; got=$(bascule_en_cours "$@")
    if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
    else echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; fi
  }
  #  1 000 000 = un instant arbitraire ; seuls les ÉCARTS comptent.
  vb "verrou posé il y a 1 min"        "oui" 999940 0      1000000 20
  vb "verrou sur le peer seulement"    "oui" 0      999940 1000000 20
  vb "verrou de 19 min : encore en cours" "oui" 998860 0   1000000 20
  #  🔴 La borne, et c'est elle qui empêche un verrou oublié de rendre les trois
  #  contrôles muets pour toujours.
  vb "verrou de 21 min : ORPHELIN"     "non" 998740 0      1000000 20
  vb "aucun verrou"                    "non" 0      0      1000000 20
  #  Un horodatage illisible ne vaut pas « en cours » : on ne tait un contrôle
  #  que sur une preuve, jamais sur une absence.
  vb "horodatage illisible"            "non" "abc"  ""     1000000 20
  #  Une horloge qui recule (verrou dans le futur) ne doit pas ouvrir une
  #  fenêtre de silence illimitée.
  vb "verrou daté du futur"            "non" 1000600 0     1000000 20
}
