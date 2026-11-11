#!/usr/bin/env bash
# =============================================================================
#  lib-precheck-exception.sh — l'exception DATÉE d'un point du pré-check (#2631)
#
#  POURQUOI. Le point 9 sortait FAIL depuis le 04/11/2026 pour 26 courriels d'un
#  incident clos (#2528) : le pré-check concluait « MEP non autorisée », n'écrivait
#  pas sa trace, et chaque MEP refaisait la même vérification à la main — aucun
#  échec plus récent — avant de la déclarer dans la PR. Un écart connu qu'on
#  redéclare à la main finit par couvrir le suivant, qu'on ne regarde plus.
#
#  CE QU'ELLE EST. Une ligne du fichier `exceptions-precheck` du répertoire git
#  COMMUN (le poste entier, tous les worktrees — `dossier_git_commun`) :
#
#      # point|ticket|borne : aucun fait après|échéance|motif
#      9|#2528|2026-11-04 21:30 +0100|2026-11-11 21:00 +0100|26 courriels de l'incident clos
#
#  Le point la VÉRIFIE lui-même, avec le fait le plus récent qu'il mesure (pour le
#  point 9 : `dernier`, rendu par la route des échecs) :
#    - point FAIL, échéance non passée, aucun fait après la borne → OK « déclaré » ;
#    - échéance passée, ou un fait PLUS RÉCENT que la borne → FAIL : l'exception ne
#      couvre que ce qu'elle a nommé, et seulement jusqu'à sa date ;
#    - fait illisible → INCONNU : une exception qu'on ne peut pas vérifier n'excuse rien ;
#    - point OK et exception encore là → ÉCART « sans objet, à retirer » — elle ne
#      sert plus, et une exception qui ne sert plus couvrirait le prochain défaut.
#
#  Lancer : bash scripts/lib/lib-precheck-exception.sh --selftest   (job `test-scripts`)
# =============================================================================

# ligne_exception fichier point → « ticket|borne|échéance|motif » (la dernière déclarée), vide sinon
ligne_exception() {
  [ -f "${1:-}" ] || return 0
  tr -d '\r' < "$1" | grep -vE '^[[:space:]]*(#|$)' | awk -F'|' -v p="${2:-}" '$1 == p' | tail -1 | cut -d'|' -f2-
}

# epoch_de « date lisible par GNU date » → secondes, vide si illisible. La route de
# l'API rend un instant UTC NAÏF (`2026-11-04T20:31:12.345`) : sans fuseau, il est lu en UTC.
epoch_de() {
  local d="${1:-}"
  [ -n "$d" ] && [ "$d" != null ] || { echo ""; return; }
  case "$d" in
    *[+-][0-9][0-9][0-9][0-9]|*[+-][0-9][0-9]:[0-9][0-9]|*Z|*UTC) date -d "$d" +%s 2>/dev/null ;;
    *) date -u -d "${d/T/ } UTC" +%s 2>/dev/null ;;
  esac
}

# verdict_exception brut fait borne echeance maintenant (epochs ; borne et échéance
# vides = pas d'exception) → « VERDICT raison »
verdict_exception() {
  local brut="${1:-}" fait="${2:-}" borne="${3:-}" ech="${4:-}" now="${5:-}"
  [ -z "$borne$ech" ] && { echo "$brut sans"; return; }
  case "$borne$ech$now" in ""|*[!0-9]*)
    [ "$brut" = FAIL ] && echo "FAIL illisible" || echo "$brut illisible"; return ;; esac
  case "$brut" in
    OK)   [ "$now" -gt "$ech" ] && echo "ECART echue" || echo "ECART sans_objet" ;;
    FAIL) if [ "$now" -gt "$ech" ]; then echo "FAIL echue"
          else case "$fait" in ""|*[!0-9]*) echo "INCONNU fait_illisible" ;;
                 *) [ "$fait" -gt "$borne" ] && echo "FAIL posterieur" || echo "OK declaree" ;;
               esac; fi ;;
    *)    echo "$brut mesure" ;;
  esac
}

# juger_exception fichier point brut fait_lisible → pose EXC_V (verdict) et EXC_D (à ajouter au détail)
#  L'instant présent s'injecte (`MAINTENANT_EPOCH`) : un autotest ne lit pas l'horloge (#2261).
juger_exception() {
  local l ticket borne ech motif r
  l=$(ligne_exception "$1" "$2")
  IFS='|' read -r ticket borne ech motif <<<"$l"
  r=$(verdict_exception "$3" "$(epoch_de "${4:-}")" "$(epoch_de "${borne:-}")" "$(epoch_de "${ech:-}")" "${MAINTENANT_EPOCH:-$(date +%s)}")
  EXC_V=${r%% *}
  case "${r#* }" in
    sans)           EXC_D="" ;;
    declaree)       EXC_D=" — déclaré : $ticket, aucun fait après $borne (dernier : ${4:-?}), jusqu'au $ech — $motif" ;;
    echue)          EXC_D=" — exception $ticket ÉCHUE le $ech : la retirer ($1)" ;;
    sans_objet)     EXC_D=" — exception $ticket sans objet (le point est vert) : la retirer ($1)" ;;
    posterieur)     EXC_D=" — fait du ${4:-?} POSTÉRIEUR à la borne de $ticket ($borne) : un nouvel échec" ;;
    fait_illisible) EXC_D=" — exception $ticket non vérifiable : fait le plus récent illisible" ;;
    illisible)      EXC_D=" — exception du point $2 illisible (borne ou échéance) dans $1" ;;
    *)              EXC_D="" ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  echecs=0
  t() {
    local libelle="$1" att="$2" obtenu; shift 2
    obtenu=$("$@")
    if [ "$obtenu" = "$att" ]; then echo "PASS  $libelle → $obtenu"
    else echo "FAIL  $libelle — attendu « $att », obtenu « $obtenu »"; echecs=$((echecs + 1)); fi
  }
  #  Instants fixes : borne 1000, échéance 2000.
  t "aucune exception : le verdict brut"        "FAIL sans"            verdict_exception FAIL 900 "" "" 1500
  t "incident déclaré, rien après la borne"     "OK declaree"          verdict_exception FAIL 900 1000 2000 1500
  t "fait exactement à la borne"                "OK declaree"          verdict_exception FAIL 1000 1000 2000 1500
  t "🔴 un nouvel échec après la borne"          "FAIL posterieur"      verdict_exception FAIL 1001 1000 2000 1500
  t "🔴 échéance passée"                         "FAIL echue"           verdict_exception FAIL 900 1000 2000 2001
  t "fait illisible : rien n'est excusé"        "INCONNU fait_illisible" verdict_exception FAIL "" 1000 2000 1500
  t "exception mal écrite : FAIL reste FAIL"    "FAIL illisible"       verdict_exception FAIL 900 "x" 2000 1500
  t "point vert, exception encore là"           "ECART sans_objet"     verdict_exception OK 900 1000 2000 1500
  t "point vert, exception échue"               "ECART echue"          verdict_exception OK 900 1000 2000 2001
  t "point non mesuré : INCONNU reste INCONNU"  "INCONNU mesure"       verdict_exception INCONNU 900 1000 2000 1500
  TMPX=$(mktemp -d); trap 'rm -rf "$TMPX"' EXIT
  printf '# point|ticket|borne|échéance|motif\r\n9|#1|2026-11-01 10:00 +0100|2026-11-02 10:00 +0100|ancien\r\n9|#2528|2026-11-04 21:30 +0100|2026-11-11 21:00 +0100|incident clos\r\n\r\n12|#9|a|b|c\r\n' > "$TMPX/exc"
  t "la DERNIÈRE ligne du point, CRLF retiré"   "#2528|2026-11-04 21:30 +0100|2026-11-11 21:00 +0100|incident clos" ligne_exception "$TMPX/exc" 9
  t "point sans ligne"                          ""                     ligne_exception "$TMPX/exc" 6
  t "fichier absent"                            ""                     ligne_exception "$TMPX/absent" 9
  t "instant naïf de l'API lu en UTC"           1793824272             epoch_de "2026-11-04T20:31:12.345678"
  t "instant avec fuseau"                       1793824272             epoch_de "2026-11-04 21:31:12 +0100"
  t "null de l'API"                             ""                     epoch_de null
  t "date illisible"                            ""                     epoch_de "pas une date"
  MAINTENANT_EPOCH=$(epoch_de "2026-11-08 12:00 +0100")
  juger_exception "$TMPX/exc" 9 FAIL "2026-11-04T20:00:00"
  t "bout à bout : courriel d'avant la borne, dans l'échéance" OK echo "$EXC_V"
  juger_exception "$TMPX/exc" 9 FAIL "2026-11-05T08:00:00"
  t "bout à bout : un courriel du lendemain"    FAIL                   echo "$EXC_V"
  MAINTENANT_EPOCH=$(epoch_de "2026-11-12 08:00 +0100")
  juger_exception "$TMPX/exc" 9 FAIL "2026-11-04T20:00:00"
  t "bout à bout : échéance passée"             FAIL                   echo "$EXC_V"
  juger_exception "$TMPX/exc" 6 FAIL "2026-11-04T20:00:00"
  t "bout à bout : point sans exception"        "FAIL|"                echo "$EXC_V|$EXC_D"
  if [ "$echecs" -eq 0 ]; then
    echo "✓ exception datée : déclarée, échue, dépassée, sans objet, et les cas zéro."
    exit 0
  fi
  echo "✗ $echecs cas de l'exception datée en défaut."
  exit 1
fi
