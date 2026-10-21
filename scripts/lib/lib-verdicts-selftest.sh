#!/usr/bin/env bash
# =============================================================================
#  Auto-tests des fonctions de décision — extrait de `lib-verdicts.sh` le
#  19/08/2026, au fil de l'eau.
#
#  POURQUOI. Le garde-fou de modularité a refusé les 47 lignes qu'ajoutaient le
#  cas zéro du motif de crontab et le contrôle de non-divergence : `lib-verdicts.sh`
#  passait de 460 à 507 lignes. La règle est « on découpe QUAND on y touche ».
#
#  La coupe n'est pas arbitraire : d'un côté les fonctions PURES que la
#  production appelle toutes les quinze minutes, de l'autre ce qui les éprouve.
#  Les deux n'ont pas la même raison de changer.
#
#  ⚠️ Ce fichier a besoin de `lib-verdicts.sh` : il est sourcé APRÈS lui, jamais
#  seul. `check-reliability.sh --selftest` s'en charge.
#
#  ⚠️ `${BASH_SOURCE[0]}` désigne désormais CE fichier. Le contrôle qui compare
#  les deux écritures du motif de crontab doit donc viser `lib-points-entree.sh`
#  (`scripts_cites`, #1546) explicitement — c'est `_LV` ci-dessous. Un contrôle
#  qui se lirait lui-même trouverait ses fixtures et se déclarerait cohérent.
# =============================================================================


# ── Self-test des fonctions pures (aucun effet de bord) ──────────────────────

# ── Contrat du module ────────────────────────────────────────────────────────
verdicts_selftest() {

  st_fail=0
  check() { # description attendu args…
    local desc="$1" exp="$2"; shift 2
    local got; got=$(beat_verdict "$@")
    if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
    else echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; fi
  }
  echo "== self-test check-reliability.beat_verdict =="
  check "battement de 3 min"                    "ok"      3    "$HB_MAX_AGE_MIN"
  check "battement pile au seuil"               "ok"      20   "$HB_MAX_AGE_MIN"
  check "battement de 45 min (script bloqué)"   "absent"  45   "$HB_MAX_AGE_MIN"
  # Le cas qui manquait : l'ancien contrôle comptait `grep -c … || echo 0`, ce qui
  # rendait « 0\n0 » quand il n'y avait AUCUNE ligne. La comparaison d'entiers
  # échouait alors en erreur, l'expression passait à faux… et le contrôle affichait
  # [ OK ] exactement dans le cas qu'il existe pour attraper (log vide/illisible).
  check "aucun horodatage exploitable"          "inconnu" -1   "$HB_MAX_AGE_MIN"
  check "valeur non numérique"                  "inconnu" "0
0"  "$HB_MAX_AGE_MIN"
  echo "-- beat_age_min --"
  AGE=$(beat_age_min "2026-07-30 01:00:00" "$(date -d '2026-07-30 01:30:00' +%s)")
  [ "$AGE" = "30" ] && echo "PASS  âge calculé sur 30 min  → $AGE" || { echo "FAIL  âge attendu=30 obtenu=$AGE"; st_fail=1; }
  AGE=$(beat_age_min "" 0)
  [ "$AGE" = "-1" ] && echo "PASS  horodatage vide → inconnu (-1)" || { echo "FAIL  attendu=-1 obtenu=$AGE"; st_fail=1; }
  AGE=$(beat_age_min "pas une date" 0)
  [ "$AGE" = "-1" ] && echo "PASS  horodatage invalide → inconnu (-1)" || { echo "FAIL  attendu=-1 obtenu=$AGE"; st_fail=1; }
  echo "-- verdict_notification --"
  vn() { # description attendu fails warns
    local desc="$1" exp="$2"; shift 2
    local got; got=$(verdict_notification "$@")
    [ "$got" = "$exp" ] && echo "PASS  $desc  → $got" \
      || { echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; }
  }
  vn "tout vert"                        "silence"  0 0
  vn "un FAIL"                          "critique" 1 0
  vn "un FAIL et des WARN"              "critique" 1 3
  #  LE cas de #449 : ce qui, le 16/08/2026, n'a atteint personne.
  vn "aucun FAIL, un WARN (C19)"        "digest"   0 1
  #  Cas zéro : un compteur vide ou illisible ne vaut PAS zéro. Sans ces trois
  #  lignes, `${1:-0}` rabattrait une variable vide sur « tout va bien ».
  vn "décompte vide"                    "critique" "" ""
  vn "FAIL vide, WARN à 0"              "critique" "" 0
  vn "décompte non numérique"           "critique" "n/a" 0
  echo "-- cache_go --"
  for c in "64.68GB:64" "11.16GB:11" "980MB:0" "512kB:0" "1.5TB:1024" ":-1" "n/a:-1"; do
    exp=${c##*:}; got=$(cache_go "${c%:*}")
    [ "$got" = "$exp" ] && echo "PASS  cache '${c%:*}' → $got Go" || { echo "FAIL  cache '${c%:*}' attendu=$exp obtenu=$got"; st_fail=1; }
  done
  echo "-- cache_verdict --"
  cv() { # description attendu go seuil
    local desc="$1" exp="$2"; shift 2
    local got; got=$(cache_verdict "$@")
    [ "$got" = "$exp" ] && echo "PASS  $desc  → $got" \
      || { echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; }
  }
  cv "régime normal du dimanche"        "ok"      10 "$BUILD_CACHE_WARN_GB"
  cv "régime de veille de dimanche"     "ok"      29 "$BUILD_CACHE_WARN_GB"
  cv "pile au seuil"                    "depasse" 40 "$BUILD_CACHE_WARN_GB"
  cv "purge réellement en panne"        "depasse" 64 "$BUILD_CACHE_WARN_GB"
  # Le CAS ZÉRO, celui qui a déjà fait mentir C14 le 30/07 : une mesure illisible
  # rend -1, et -1 n'est PAS « 0 Go, donc tout va bien ».
  cv "mesure illisible (-1)"            "inconnu" -1 "$BUILD_CACHE_WARN_GB"
  cv "mesure vide"                      "inconnu" "" "$BUILD_CACHE_WARN_GB"
  cv "mesure non numérique"             "inconnu" "n/a" "$BUILD_CACHE_WARN_GB"
  echo "-- cohérence seuil / politique de rétention --"
  # C'est l'erreur du 06/08/2026 mise sous garde-fou : le seuil avait été déduit
  # du plafond du dimanche (10 → 20), en oubliant que le cache regrossit six
  # nuits avant la purge suivante. Un seuil sous le régime rend le contrôle WARN
  # en permanence sur une infra saine. Si la croissance mesurée augmente, c'est
  # ce test qui doit rappeler de relever le seuil — pas un log qu'on ignore.
  REGIME=$(( BUILD_CACHE_FLOOR_GB + 6 * BUILD_CACHE_GROWTH_GB ))
  if [ "$BUILD_CACHE_WARN_GB" -gt "$REGIME" ]; then
    echo "PASS  seuil ${BUILD_CACHE_WARN_GB} Go > régime ${REGIME} Go (plafond ${BUILD_CACHE_FLOOR_GB} + 6 nuits × ${BUILD_CACHE_GROWTH_GB})"
  else
    echo "FAIL  seuil ${BUILD_CACHE_WARN_GB} Go ≤ régime ${REGIME} Go — C16 sera WARN sur une infra saine"; st_fail=1
  fi
  echo "-- crontab_scripts --"
  cs() { # description attendu crontab-brut
    local desc="$1" exp="$2"; shift 2
    local got; got=$(crontab_scripts "$1")
    [ "$got" = "$exp" ] && echo "PASS  $desc  → '$got'" \
      || { echo "FAIL  $desc  attendu='$exp' obtenu='$got'"; st_fail=1; }
  }
  #  Les redirections des fixtures respectent le motif des logs rotés : le job CI
  #  `test-scripts` scanne TOUS les .sh à la recherche d'un chemin de journal que
  #  `maintenance.sh` ne roterait pas, et il ne distingue — à raison — ni le code
  #  de la donnée de test, ni le code du commentaire. Des fixtures avec un nom
  #  court et arbitraire le faisaient donc échouer ; attrapé en rejouant la CI en
  #  local, pas en s'en souvenant.
  #  🔴 CAS ZÉRO — l'arborescence RÉELLE depuis #337 (15/08/2026). C'est elle que
  #  le motif ne savait plus lire, et aucune fixture ne la décrivait : les tests
  #  passaient sur l'ancienne forme pendant que la production n'en produisait plus
  #  une seule. Un test dont les données décrivent un monde disparu vérifie la
  #  fonction contre elle-même.
  cs "chemins rangés (#337) — CAS ZÉRO du 19/08" "bascule.sh,check-reliability.sh" \
"0 2 * * * /opt/5hostachy/scripts/exploitation/bascule.sh >> /var/log/hostachy-bascule.log 2>&1
6,21,36,51 * * * * /opt/5hostachy/scripts/exploitation/check-reliability.sh >> /var/log/hostachy-reliability.log 2>&1"
  cs "deux tâches, triées" "bascule.sh,maintenance.sh" \
"0 3 * * 0 /opt/5hostachy/maintenance.sh >> /var/log/hostachy-maintenance.log 2>&1
0 2 * * * /opt/5hostachy/bascule.sh >> /var/log/hostachy-bascule.log 2>&1"
  cs "commentaires et lignes vides ignorés" "health-watch.sh" \
"# Health check toutes les 5 min

2,7 * * * * /opt/5hostachy/health-watch.sh >> /var/log/hostachy-health-watch.log 2>&1"
  #  Le cas qui a motivé C18 : le même crontab, plus une entrée d'un seul côté.
  cs "le script en trop apparaît" "bascule.sh,check-stack.sh" \
"0 2 * * * /opt/5hostachy/bascule.sh
4,14 * * * * /opt/5hostachy/check-stack.sh >> /var/log/hostachy-check.log 2>&1"
  #  Une ligne COMMENTÉE ne compte pas : désactiver un cron doit se voir comme un
  #  retrait, sinon le contrôle dirait « identiques » sur deux nœuds qui diffèrent.
  cs "entrée commentée non comptée" "bascule.sh" \
"0 2 * * * /opt/5hostachy/bascule.sh
#4,14 * * * * /opt/5hostachy/check-stack.sh"
  #  Cas ZÉRO : crontab illisible ou vide → chaîne vide, que C18 traite en INCONNU
  #  et jamais en « identiques » (deux vides seraient égaux — le piège exact).
  cs "crontab vide" "" ""
  cs "crontab sans tâche 5Hostachy" "" "0 5 * * * /usr/bin/autre-chose"
  sudo_selftest
  echo "-- âge de maintenance (réutilise beat_age_min/beat_verdict) --"
  check "maintenance de 4 j"                    "ok"      5760  "$MAINT_MAX_AGE_MIN"
  check "maintenance pile à 8 j"                "ok"      11520 "$MAINT_MAX_AGE_MIN"
  check "deux dimanches manqués"                "absent"  20160 "$MAINT_MAX_AGE_MIN"
  check "maintenance jamais horodatée"          "inconnu" -1    "$MAINT_MAX_AGE_MIN"
  echo "-- C19 : le journal et la base disent-ils la même chose ? --"
  sm() {  # $1 = libellé, $2 = attendu, $3 = âge journal, $4 = âge base, $5 = tolérance
    r=$(verdict_sondes_maintenance "$3" "$4" "$5")
    if [ "$r" = "$2" ]; then echo "PASS  $1 → $r"
    else echo "FAIL  $1  attendu=$2 obtenu=$r"; st_fail=1; fi
  }
  #  Le cas vécu : la maintenance a tourné il y a 2 j, aucun rapport en base.
  sm "a tourné, aucun rapport (09-11/08)"  DIVERGENCE 2880 ""    720
  sm "rapport aussi vieux que l'exécution" OK         2880 2880  720
  sm "rapport en retard mais dans la marge" OK        2880 3300  720
  sm "rapport bien plus vieux que la course" DIVERGENCE 2880 5760 720
  #  Un déclenchement manuel depuis l'interface n'écrit pas dans le journal :
  #  un rapport PLUS RÉCENT que la dernière ligne du journal est normal.
  sm "rapport plus récent que le journal"  OK         2880 60    720
  #  Standby : aucune API locale, la base n'est pas interrogeable depuis ce nœud.
  sm "base non interrogeable (standby)"    INCONNU    2880 "-"   720
  sm "journal illisible"                   INCONNU    ""   2880  720
  sm "âge journal aberrant"                INCONNU    "x"  2880  720
  sm "âge base aberrant"                   INCONNU    2880 "hier" 720

  #  ── sonde_base : la traduction « ce qu'a rendu l'API » → entrée de C19 ─────
  #  C'est ICI qu'était le défaut du 11/08/2026, et non dans la décision : la
  #  collecte ne savait pas produire « interrogée, vide », donc DIVERGENCE était
  #  inatteignable en pratique. Ces cas verrouillent la distinction (#305).
  echo "-- sonde_base : « pas pu demander » n'est pas « rien à dire » --"
  sb() {  # $1=libellé $2=attendu $3=carte $4=nœud
    r=$(sonde_base "$3" "$4")
    if [ "$r" = "$2" ]; then echo "PASS  $1 → '$r'"
    else echo "FAIL  $1  attendu='$2' obtenu='$r'"; st_fail=1; fi
  }
  #  Le cas de production du 11/08 : l'API a répondu 200 avec `"noeuds": {}`.
  sb "API 200, carte vide → DIVERGENCE possible"  ""  "ok:"  rpi2
  #  Le cas du standby : aucun nœud n'a pu interroger la base.
  sb "aucun nœud n'a interrogé la base"          "-"  ""     rpi2
  sb "clé absente des deux côtés"                "-"  ""     rpi1
  #  Nominal : la carte porte les deux nœuds. Le `Z` RESSORT — sans lui, `date -d`
  #  lirait de l'heure locale et se tromperait de deux heures.
  sb "nœud présent dans la carte"                "2026-08-11T00:00:01Z" \
     "ok:rpi1:2026-08-11T00:00:01Z;rpi2:2026-08-10T00:00:01Z;" rpi1
  sb "second nœud de la carte"                   "2026-08-10T00:00:01Z" \
     "ok:rpi1:2026-08-11T00:00:01Z;rpi2:2026-08-10T00:00:01Z;" rpi2
  #  Horodatage à fraction de seconde, la forme que rend réellement l'API.
  sb "fraction de seconde conservée"             "2026-08-11T20:29:53.712806Z" \
     "ok:rpi2:2026-08-11T20:29:53.712806Z;" rpi2
  #  Carte non vide, mais SANS ligne pour ce nœud-là : la base a répondu et n'a
  #  rien sur lui → DIVERGENCE, surtout pas INCONNU.
  sb "carte peuplée, nœud absent"                ""  \
     "ok:rpi1:2026-08-11T00:00:01Z;" rpi2
  #  Un seul nœud porte l'API : sa carte couvre les deux, celle du standby est
  #  vide. La concaténation doit rester exploitable.
  sb "concaténation actif + standby muet"        "2026-08-11T00:00:01Z" \
     "ok:rpi1:2026-08-11T00:00:01Z;" rpi1

  #  ── extraire_rapports : le tuyau qui NOURRIT sonde_base ────────────────────
  #  Le défaut du 11/08/2026 vivait ici, pas dans la décision : le motif ne
  #  pouvait correspondre à aucune réponse réelle. Ces cas partent donc de VRAIES
  #  réponses de l API, copiées telles quelles depuis la production.
  echo "-- extraire_rapports : de la réponse brute à la carte --"
  er() {  # $1=libellé $2=attendu $3=réponse brute
    r=$(extraire_rapports "$3")
    if [ "$r" = "$2" ]; then echo "PASS  $1 → '$r'"
    else echo "FAIL  $1  attendu='$2' obtenu='$r'"; st_fail=1; fi
  }
  er "réponse réelle, un nœud" "ok:rpi2:2026-08-11T20:29:53.712806Z;" \
     '{"tache": "maintenance", "noeuds": {"rpi2": "2026-08-11T20:29:53.712806Z"}, "genere_le": "2026-08-11T20:36:56.297066Z"}|200'
  er "réponse réelle, deux nœuds" "ok:rpi1:2026-08-11T00:00:01Z;rpi2:2026-08-10T00:00:01Z;" \
     '{"tache": "bascule", "noeuds": {"rpi1": "2026-08-11T00:00:01Z", "rpi2": "2026-08-10T00:00:01Z"}, "genere_le": "2026-08-11T19:15:53Z"}|200'
  #  Carte vide MAIS API interrogée : le marqueur doit être là, seul.
  er "API 200, aucun rapport" "ok:" \
     '{"tache": "maintenance", "noeuds": {}, "genere_le": "2026-08-11T19:15:24.890687Z"}|200'
  #  `genere_le` ne doit JAMAIS être pris pour un rapport de nœud.
  er "genere_le non confondu avec un nœud" "ok:" \
     '{"noeuds": {}, "genere_le": "2026-08-11T19:15:24Z"}|200'
  #  Pas 200 → aucun marqueur, donc INCONNU en aval et non DIVERGENCE.
  er "API en erreur"   "" '{"detail":"Not authenticated"}|401'
  er "hôte injoignable" "" '|000'
  er "réponse vide"     "" ''

  #  ── Ordre des blocs : aucun verdict APRÈS la ligne de résumé ──────────────
  #  Statique, parce que le défaut de #304 n'était pas une valeur fausse mais une
  #  POSITION : C19 avait été livré après le résumé ET après le bloc d'alerte. Il
  #  rendait donc des verdicts justes que personne ne comptait ni ne recevait —
  #  « Résumé : 0 FAIL, 0 WARN » suivi de deux [WARN], en production le 11/08.
  #  Aucun test de fonction pure ne pouvait le voir : c'est le FICHIER qu'il faut
  #  regarder. Le prochain contrôle ajouté en fin de fichier échouera ici.
  #  ── Le snippet ASSEMBLÉ est-il du shell valide ? ──────────────────────────
  #  `bash -n check-reliability.sh` ne voit RIEN de ce qui est dans COLLECT :
  #  pour lui c'est une chaîne. Or cette chaîne est du code, exécuté sur les deux
  #  nœuds. Le 11/08/2026 une injection de motif y a produit un `grep -oE` sans
  #  guillemets autour d'un motif contenant des parenthèses — syntaxe invalide
  #  côté distant, assemblage parfaitement valide côté local. Même famille que le
  #  défaut d'origine : ce qui n'est pas exécuté pendant le test ne prouve rien.
  #  ── Les DEUX écritures du motif de crontab disent-elles la même chose ? ────
  #  `crontab_scripts()` ci-dessus est pure et testée ; `lib-collecte.sh` en porte
  #  un JUMEAU inline, parce que ce fragment est exécuté à distance par SSH et ne
  #  peut donc pas appeler une fonction locale. Deux écritures d'une même règle
  #  sont deux valeurs libres de diverger (`standards/02` §2) — et elles ont
  #  divergé : le 19/08/2026 les deux portaient le même défaut, mais seule la
  #  version pure avait des tests… qui passaient sur des fixtures périmées.
  #
  #  Ce contrôle compare les deux motifs caractère par caractère. Il ne dit pas
  #  qu'ils sont JUSTES — c'est le rôle des fixtures ci-dessus — mais qu'ils sont
  #  les MÊMES, ce qu'aucun test de fonction ne peut voir.
  echo "-- les deux écritures du motif de crontab sont identiques --"
  _LC="$(dirname "${BASH_SOURCE[0]}")/lib-collecte.sh"
  if [ ! -r "$_LC" ]; then
    echo "FAIL  lib-collecte.sh illisible — comparaison impossible, donc INCONNU"; st_fail=1
  else
    #  ⚠️ Le module de `scripts_cites` explicitement, PAS `${BASH_SOURCE[0]}` :
    #  se lire soi-même trouverait les fixtures et déclarerait la cohérence sans
    #  avoir regardé la fonction. (Le motif a quitté lib-verdicts.sh le 02/10.)
    _LV="$(dirname "${BASH_SOURCE[0]}")/lib-points-entree.sh"
    _M_PUR=$(grep -oE '/opt/5hostachy/\[[^]]+\]\+' "$_LV" | head -1)
    _M_COL=$(grep -oE '/opt/5hostachy/\[[^]]+\]\+' "$_LC" | head -1)
    if [ -z "$_M_PUR" ] || [ -z "$_M_COL" ]; then
      echo "FAIL  motif introuvable (pur='$_M_PUR' collecte='$_M_COL') — le contrôle ne mesure rien"; st_fail=1
    elif [ "$_M_PUR" = "$_M_COL" ]; then
      echo "PASS  motif identique des deux côtés : $_M_PUR"
    else
      echo "FAIL  motifs DIVERGENTS — pur='$_M_PUR' vs collecte='$_M_COL'"; st_fail=1
    fi
  fi

  echo "-- le snippet de collecte est du shell valide --"
  if [ -z "${COLLECT:-}" ]; then
    echo "FAIL  COLLECT vide ou absent — le contrôle ne mesure rien"; st_fail=1
  elif printf '%s\n' "$COLLECT" | bash -n 2>/tmp/collect-syntaxe.$$; then
    echo "PASS  COLLECT assemblé ($(printf '%s' "$COLLECT" | wc -l) lignes) : syntaxe valide"
  else
    echo "FAIL  COLLECT assemblé est du shell INVALIDE :"
    sed 's/^/      /' /tmp/collect-syntaxe.$$
    st_fail=1
  fi
  rm -f /tmp/collect-syntaxe.$$

  echo "-- ordre des blocs : tout verdict avant le résumé --"
  #  Les modules vivent dans scripts/lib/, le script contrôlé dans
  #  scripts/exploitation/ (#337). Le chemin traverse donc les deux.
  CR="$(dirname "${BASH_SOURCE[0]}")/../exploitation/check-reliability.sh"
  L_RESUME=$(grep -n '^echo "Résumé' "$CR" 2>/dev/null | head -1 | cut -d: -f1)
  compte_verdicts() {  # $1=fichier $2=ligne à partir de laquelle compter
    awk -v l="$2" '
      NR<=l { next }
      { t=$0; sub(/^[[:space:]]+/,"",t); if (t ~ /^#/) next }
      /(^|[[:space:];)])(ok|warn|fail) "/ { n++ }
      END { print n+0 }' "$1"
  }
  #  Auto-contrôle avant de conclure : sans fichier, sans repère ou sans motif
  #  reconnu, ce contrôle ne mesure rien — il échoue au lieu de passer au vert
  #  (`standards/04-fiabilite-des-controles.md` §2).
  if [ ! -r "$CR" ]; then
    echo "FAIL  check-reliability.sh illisible — contrôle d ordre inopérant"; st_fail=1
  elif [ -z "$L_RESUME" ]; then
    echo "FAIL  ligne de résumé introuvable — le repère a changé, contrôle inopérant"; st_fail=1
  else
    TOTAL=$(compte_verdicts "$CR" 0)
    APRES=$(compte_verdicts "$CR" "$L_RESUME")
    if [ "$TOTAL" -lt 15 ]; then
      echo "FAIL  $TOTAL verdict(s) reconnus dans $CR — motif changé, contrôle inopérant"; st_fail=1
    elif [ "$APRES" -ne 0 ]; then
      echo "FAIL  $APRES verdict(s) rendus APRÈS la ligne $L_RESUME (résumé) :"
      echo "      ils sortent du décompte ET du mail d alerte, comme C19 en v2.52.0."
      st_fail=1
    else
      echo "PASS  les $TOTAL verdicts sont rendus avant le résumé (ligne $L_RESUME)"
    fi
  fi

  echo "-- C23 : les en-tetes de securite reellement servis --"
  ve() { # description attendu recus liste [role]
    local desc="$1" exp="$2" recus="$3" liste="$4" role="${5:-actif}"
    local got; got=$(verdict_entetes_securite "$recus" "$liste" "$role")
    if [ "$got" = "$exp" ]; then echo "PASS  $desc"
    else echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; fi
  }
  _TOUS=$'HTTP/1.1 200 OK\nX-Content-Type-Options: nosniff\nX-Frame-Options: DENY\nContent-Security-Policy: frame-ancestors'
  ve "les trois en-têtes présents"        "OK" "$_TOUS" \
     "X-Content-Type-Options X-Frame-Options Content-Security-Policy"
  #  Les en-têtes HTTP sont insensibles à la casse ; Caddy peut en changer.
  ve "casse différente acceptée"          "OK" $'HTTP/2 200\nx-frame-options: DENY' "X-Frame-Options"
  ve "un en-tête retiré du Caddyfile"     "MANQUANT:Content-Security-Policy" \
     $'HTTP/1.1 200 OK\nX-Frame-Options: DENY' "X-Frame-Options Content-Security-Policy"
  #  🔴 Les deux cas qui doivent rendre INCONNU. Répondre OK ferait d'un site
  #  injoignable un site conforme — le cas zéro, `standards/04` §1.
  ve "aucune réponse (site injoignable)"  "INCONNU" "" "X-Frame-Options"
  ve "réponse illisible"                  "INCONNU" "curl: (7) Failed to connect" "X-Frame-Options"
  #  ⚠️ La VALEUR n'est pas vérifiée, à dessein : c'est une attente de valeur
  #  périmée (« SAMEORIGIN » contre « DENY ») qui a fait désarmer le contrôle
  #  précédent, retiré du cron de rpi2 le 06/08/2026 après 144 échecs par jour.
  ve "valeur inattendue, en-tête présent" "OK" $'HTTP/1.1 200 OK\nX-Frame-Options: SAMEORIGIN' "X-Frame-Options"
  #  🔴 LE STANDBY N'A RIEN À MESURER, et ce n'est pas une panne (27/08/2026).
  #  Les conteneurs ne tournent que sur l'actif : c'est l'invariant, pas un
  #  incident. Ce contrôle rendait pourtant INCONNU toutes les quinze minutes sur
  #  la moitié du parc, et un digest partait chaque jour. Un contrôle dont le vert
  #  est inatteignable finit par se contourner (`standards/04` §25).
  ve "standby : rien à constater"         "SANS_OBJET" "" "X-Frame-Options" "standby"
  #  ⚠️ Et il le reste même si quelque chose répondait : ce n'est pas le site.
  ve "standby, réponse parasite"          "SANS_OBJET" "$_TOUS" "X-Frame-Options" "standby"
  #  ⚠️ Sur l'ACTIF, l'absence de réponse reste INCONNU — là, c'est un fait à
  #  regarder. La distinction est tout l'objet du correctif.
  ve "actif muet : toujours INCONNU"      "INCONNU" "" "X-Frame-Options" "actif"

  site_public_selftest

  echo "-- C23 bis : la CSP bloquante porte ses directives --"
  vc() { # description attendu recus directives
    local desc="$1" exp="$2"; shift 2
    local got; got=$(verdict_csp_directives "$@")
    if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
    else echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; fi
  }
  _CSP_OK=$(printf 'HTTP/2 200\r\nContent-Security-Policy: frame-ancestors '"'"'none'"'"'; object-src '"'"'none'"'"'; base-uri '"'"'self'"'"'; form-action '"'"'self'"'"'; connect-src '"'"'self'"'"'\r\n')
  _CSP_SANS=$(printf 'HTTP/2 200\r\nContent-Security-Policy: frame-ancestors '"'"'none'"'"'; object-src '"'"'none'"'"'\r\n')
  #  🔴 LE cas qui donne son sens au motif : le report-only porte TOUTES les
  #  directives. Sans les deux-points dans `^Content-Security-Policy:`, le
  #  contrôle serait vert alors que le mode bloquant est vide.
  _CSP_RO=$(printf 'HTTP/2 200\r\nContent-Security-Policy-Report-Only: default-src '"'"'self'"'"'; connect-src '"'"'self'"'"'; form-action '"'"'self'"'"'\r\n')

  vc "toutes les directives présentes"     OK "$_CSP_OK" "frame-ancestors connect-src form-action"
  vc "connect-src perdue en silence"       "MANQUANT:connect-src" "$_CSP_SANS" "frame-ancestors connect-src"
  vc "deux manquantes, toutes deux dites"  "MANQUANT:connect-src,form-action" "$_CSP_SANS" "connect-src form-action"
  #  Le report-only ne doit RIEN valider : sinon le contrôle mesure la politique
  #  observée en croyant mesurer celle qui bloque.
  vc "seul le Report-Only est servi"       INCONNU "$_CSP_RO" "connect-src"
  #  Les deux cas zéro : pas de réponse, et une réponse sans CSP du tout.
  vc "aucune réponse"                      INCONNU "" "connect-src"
  vc "réponse sans en-tête CSP"            INCONNU "$(printf 'HTTP/2 200\r\nX-Frame-Options: DENY\r\n')" "connect-src"
  #  🔴 Le rôle, et il a MANQUÉ à la première écriture — constaté en production
  #  une heure après la mise en service : le contrôle rendait WARN toutes les
  #  quinze minutes sur le standby, qui ne sert rien. C'est le défaut que le
  #  commentaire de C23, juste à côté, décrit et corrige depuis le 20/08/2026.
  #  Écrire un contrôle voisin sans relire ce que son voisin a appris, c'est
  #  refaire son défaut (`standards/04` §25).
  vc "standby : rien à constater"          SANS_OBJET "" "connect-src" standby
  #  ⚠️ Et il le reste même si quelque chose répondait : ce n'est pas le site.
  vc "standby, réponse parasite"           SANS_OBJET "$_CSP_OK" "connect-src" standby

  echo "-- C25 : aucun script tiers dans la page publique --"
  vt() { # description attendu html hotes [role]
    local desc="$1" exp="$2"; shift 2
    local got; got=$(verdict_script_tiers "$@")
    if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
    else echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; fi
  }
  _HTML_PROPRE='<html><head><script src="/_app/immutable/x.js"></script></head></html>'
  _HTML_BEACON='<html><body><script src="https://static.cloudflareinsights.com/beacon.min.js"></script></body></html>'
  _HOTES="static.cloudflareinsights.com googletagmanager.com"

  vt "page sans tiers"                     OK          "$_HTML_PROPRE" "$_HOTES"
  vt "le beacon Cloudflare est revenu"     "TIERS:static.cloudflareinsights.com" "$_HTML_BEACON" "$_HOTES"
  #  🔴 LE CAS ZÉRO, et c'est le seul qui compte vraiment ici : le relevé légitime
  #  de ce contrôle est VIDE. Sans lui, une page qu'on n'a pas pu charger — WAN
  #  coupé, 502, redirection — rendrait OK, et on lirait « aucun tiers » là où il
  #  faut lire « je n'ai pas regardé » (`standards/04` §1).
  vt "aucune page reçue"                   INCONNU     "" "$_HOTES"
  #  Le standby ne sert rien : ni vert ni rouge, sans objet.
  vt "standby"                             SANS_OBJET  "$_HTML_BEACON" "$_HOTES" standby
  #  Une URL absolue LÉGITIME ne doit pas crier : la CSP autorise les polices.
  vt "polices Google, déclarées"           OK          '<link href="https://fonts.googleapis.com/css2?family=X">' "$_HOTES"


  #  Les épreuves du VERROU vivent dans `lib-verrou-selftest.sh` : ce
  #  fichier a dépassé son plafond en les recevant (12/09/2026). La coupe suit
  #  la nature de l'objet — même geste que `sudo_selftest`, appelé ici aussi.
  verrou_selftest || st_fail=1

  [ $st_fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  # ── C27 — auto-deploy a-t-il réussi son build ? ──────────────────────
  ba() {  # $1 = libellé, $2 = attendu, $3 = dernière ligne du deploy.log
    local got; got=$(verdict_build_autodeploy "$3")
    if [ "$got" = "$2" ]; then echo "PASS  $1  → $got"
    else echo "FAIL  $1  attendu=$2 obtenu=$got"; st_fail=1; fi
  }
  ba "build reussi"        OK      "[2026-09-21 07:48:01] Deploye: f4398e9"
  ba "rien a deployer"     OK      "[2026-09-21 07:53:01] Aucun changement (f4398e9)"
  ba "build en echec"      FAIL    "[2026-09-21 07:48:01] Aligne: f4398e9c (standby - ECHEC du build, images NON reconstruites)."
  #  L'accent ne survit pas toujours à SSH : le motif est ASCII exprès.
  ba "accent perdu en SSH" FAIL    "[2026-09-21 07:48:01] Aligne (standby - ?CHEC du build)."
  #  Cas zéro : sans ligne, on ne SAIT pas — et INCONNU n'est pas OK.
  ba "ligne absente"       INCONNU ""
  #  #1587 : ces sorties sont DATÉES, donc C14 les voit vivantes ; C27 dit
  #  qu'elles n'ont rien déployé. Sans ces cas, elles rendraient OK.
  ba "fetch en echec (#1587)" REPORTE "[2026-09-29 16:48:01] ⚠ git fetch impossible (fatal: Could not read from remote repository.) — déploiement reporté au prochain passage."
  ba "sortie imprevue (#1587)" INTERROMPU "[2026-10-02 09:10:30] ⚠ ÉCHEC inattendu (code 1, dernière commande : docker compose up -d api) — auto-deploy interrompu sans ligne de sortie."

  return $st_fail
}
