#!/usr/bin/env bash
# =============================================================================
#  lib-journal.sh — la ligne DATÉE des scripts d'exploitation, et ses sorties
#
#  Né de #1587 (02/10/2026). `auto-deploy.sh` datait son journal par une
#  variable calculée AU DÉMARRAGE (`LOG_DATE`) : « Changements détectés » et
#  « Déployé » portaient la même seconde, 09:08:01, pour un déploiement fini
#  vers 09:11. La date que lit P1 mentait de trois minutes, et la durée d'un
#  build n'était lisible nulle part. Et un `git fetch` en échec le tuait sous
#  `set -e` sans une seule ligne datée — quatre fois en un mois sur les deux
#  nœuds, chaque fois invisible à un tri par date.
#
#  `log` date CHAQUE ligne au moment où elle est écrite. Elle existait déjà,
#  à l'identique, dans neuf scripts et modules : ce module en devient la
#  source, et les copies restantes s'y rangent au fil de l'eau — pas en bloc
#  dans un lot qui ne touche pas ces scripts (rang 1, `standards/02` §6).
#  Les modules qui gardent un repli (`lib-alert`, `lib-notification`,
#  `lib-rapport`) le testent par `declare -f log` : ils prennent celle-ci.
#
#  Il porte aussi le CONTRAT DE BATTEMENT d'auto-deploy sous une forme qui
#  s'éprouve : C14 lit la date de la dernière ligne datée, donc un chemin muet
#  fait passer le script pour mort — ou, pire depuis #1587, une sortie
#  imprévue qui laisse la ligne précédente fait passer le script pour sain.
#    sortir                   une sortie prévue : sa ligne datée, puis `exit` ;
#    journal_sortie_imprevue  le filet : toute AUTRE sortie en échec (un
#                             `set -e` au fond d'une fonction) écrit la sienne,
#                             que C27 lit comme un échec ;
#    contrat_journal          le contrôle statique de ces deux règles, lancé
#                             sur `auto-deploy.sh` par l'autotest (job CI
#                             `test-scripts`). Il remplace l'awk qui vivait
#                             dans `ci.yml` : une seule écriture du contrat.
#
#  SOURCÉ (mode 100644). Autotest : bash scripts/lib/lib-journal.sh --selftest
# =============================================================================

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ── Une sortie PRÉVUE : sa ligne datée, puis le code ─────────────────────────
#  Appelée au niveau du script, jamais dans un `$(…)` : `exit` n'y quitterait
#  que le sous-shell.
sortir() { # $1 = code de sortie, $2… = la ligne qui la date
    local code=$1; shift
    log "$*"
    JOURNAL_SORTIE_DATEE=oui
    exit "$code"
}

# ── Le filet : une sortie IMPRÉVUE écrit quand même sa ligne datée ───────────
#  Sous `set -e`, une commande en échec tue le script et ne laisse que son
#  erreur brute, sans date : c'est le 26/07/2026 (7 h 30 de lignes git non
#  horodatées) et le `git fetch` de #1587. Le piège EXIT voit toutes les
#  sorties, y compris au fond d'une fonction ; le piège ERR retient la
#  dernière commande en échec et sa ligne, pour les nommer.
#  ⚠️ Motif « CHEC inattendu » SANS accent : C27 le lit à travers SSH
#  (`verdict_build_autodeploy`, même raison que « CHEC du build »).
#  Un script qui pose son propre piège EXIT ne peut pas l'employer.
#
#  $2 (facultatif) : une fonction appelée APRÈS la ligne, la cause en argument —
#  pour un script qui doit aussi la dire AILLEURS que dans son journal. Né de
#  #1826 : `maintenance.sh`, mort sous `set -e`, laissait à l'écran un battement
#  « en cours » sans cause ; il y envoie désormais un rapport en erreur. Son
#  échec est ignoré : le filet ne change jamais le code de sortie.
#
#  `errtrace` : sans lui, le piège ERR ne voit pas l'intérieur des fonctions, et
#  une commande morte au fond de l'une d'elles se nommait « ? ». Le piège ne fait
#  que retenir la commande ; il ne décide de rien.
journal_sortie_imprevue() { # $1 = nom du script, cité dans la ligne ; $2 = fonction (facultative)
    JOURNAL_SORTIE_DATEE=non
    _JOURNAL_NOM=$1
    _JOURNAL_RAPPEL=${2:-}
    _JOURNAL_CMD=""
    set -o errtrace
    trap '_JOURNAL_CMD="$BASH_COMMAND (ligne $LINENO)"' ERR
    trap '_journal_filet $?' EXIT
}

_journal_filet() { # $1 = code de sortie du script
    local cause
    { [ "$1" -eq 0 ] || [ "$JOURNAL_SORTIE_DATEE" = oui ]; } && return 0
    cause="code $1, dernière commande : ${_JOURNAL_CMD:-?}"
    log "⚠ ÉCHEC inattendu ($cause) — $_JOURNAL_NOM interrompu sans ligne de sortie." || true
    [ -z "$_JOURNAL_RAPPEL" ] || "$_JOURNAL_RAPPEL" "$cause" || true
}

# ── Le contrat, vérifié sur le TEXTE d'un script (PURE) ──────────────────────
#  Une ligne par écart, rien si le script est conforme :
#    - un `exit N` sans ligne datée dans les quatre lignes qui le précèdent
#      (C14 conclurait que le script est mort — la règle du 31/07/2026) ;
#    - un `exit` EN ÉCHEC hors de `sortir` : le filet le daterait une seconde
#      fois, et la dernière ligne ne dirait plus la vraie cause ;
#    - un `git fetch` sans repli (`||` ou `if`) : sous `set -e`, son échec
#      sortait sans rien dire de la cause (#1587).
#  Le bloc `--selftest` est ignoré : il ne tourne pas en production.
contrat_journal() { # $1 = fichier
    awk '
        /--selftest/ && /then/           { st = 1 }
        st && /^fi/                      { st = 0; next }
        st || /^[[:space:]]*#/           { next }
        /(^|[;{([:space:]])(log|sortir)[[:space:]]/ { last = NR }
        /(^|[;{[:space:]])exit [0-9]/ {
            if (NR - last > 4) printf "l.%d : sortie sans ligne datée\n", NR
            if (/(^|[;{[:space:]])exit [1-9]/) printf "l.%d : sortie en échec hors de sortir\n", NR
        }
        #  En position de COMMANDE seulement : un message qui cite le geste
        #  (« git fetch impossible ») n en est pas un.
        /(^|[;&|(!])[[:space:]]*git fetch/ && !/\|\|/ && !/^[[:space:]]*if[[:space:]]/ {
            printf "l.%d : git fetch sans repli\n", NR
        }
    ' "$1"
}

#  PURE pour l'appelant. La fonction $1 date-t-elle à l'ÉCRITURE ? On lui
#  fait écrire deux lignes avec une horloge qui avance d'un cran à chaque
#  lecture : deux dates différentes → OUI ; la même → NON (horodatage figé).
horodatage_a_l_ecriture() { # $1 = nom de la fonction de journal → OUI | NON
    local f l1 l2
    f=$(mktemp)
    echo 1 > "$f"
    l1=$( date() { local c; c=$(cat "$f"); echo $((c + 1)) > "$f"; echo "T$c"; }; "$1" a )
    l2=$( date() { local c; c=$(cat "$f"); echo $((c + 1)) > "$f"; echo "T$c"; }; "$1" b )
    rm -f "$f"
    [ "${l1%% *}" != "${l2%% *}" ] && echo OUI || echo NON
}

# ── Autotest (job CI `test-scripts`) ──────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { if [ "$3" = "$2" ]; then echo "PASS  $1 → ${3:-(rien)}"
          else echo "FAIL  $1  attendu=${2:-(rien)} obtenu=${3:-(rien)}"; st=1; fi; }
    ICI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    tmp=$(mktemp -d)

    echo "== lib-journal : la ligne datée =="
    t "format [AAAA-MM-JJ HH:MM:SS] message" OUI \
      "$(grep -qE '^\[[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\] Déployé: abc1234$' <<<"$(log "Déployé: abc1234")" && echo OUI || echo NON)"
    t "log date chaque ligne à l'écriture" OUI "$(horodatage_a_l_ecriture log)"
    #  La faute de #1587, reconstituée : la date calculée UNE fois, au démarrage.
    D_FIGEE="[$(date '+%Y-%m-%d %H:%M:%S')]"
    log_fige() { echo "$D_FIGEE $*"; }
    t "faute injectée : horodatage figé au démarrage → refusé" NON "$(horodatage_a_l_ecriture log_fige)"

    echo "== lib-journal : les sorties =="
    #  Le filet, dans un vrai `set -e` : une commande en échec au fond d'une
    #  fonction, sans ligne prévue.
    sortie=$(bash -c 'set -euo pipefail; . "$1"; journal_sortie_imprevue essai; f() { false; }; f; echo jamais' _ "$ICI/lib-journal.sh" 2>&1)
    t "set -e au fond d'une fonction → une ligne datée « CHEC inattendu »" 1 \
      "$(printf '%s\n' "$sortie" | grep -cE '^\[[0-9-]{10} [0-9:]{8}\] .*CHEC inattendu \(code 1.*essai interrompu')"
    #  §46 : le même script SANS le filet ne laisse aucune ligne datée — c'est
    #  donc bien le filet que le cas précédent éprouve.
    sortie=$(bash -c 'set -euo pipefail; . "$1"; f() { false; }; f' _ "$ICI/lib-journal.sh" 2>&1)
    t "faute injectée : sans le filet, aucune ligne datée" 0 "$(printf '%s\n' "$sortie" | grep -c '^\[')"
    sortie=$(bash -c 'set -euo pipefail; . "$1"; journal_sortie_imprevue essai; false' _ "$ICI/lib-journal.sh" 2>&1)
    t "échec au niveau du script : la commande est nommée" 1 "$(printf '%s\n' "$sortie" | grep -c 'dernière commande : false')"
    #  #1826 : la commande morte AU FOND d'une fonction se nomme, avec sa ligne.
    sortie=$(bash -c 'set -euo pipefail; . "$1"; journal_sortie_imprevue essai; f() { inspect_absent; }; f' _ "$ICI/lib-journal.sh" 2>&1)
    t "échec au fond d'une fonction : la commande et sa ligne sont nommées" 1 \
      "$(printf '%s\n' "$sortie" | grep -cE 'dernière commande : inspect_absent \(ligne [0-9]+\)')"
    #  #1826 : la fonction de l'appelant reçoit la cause ; le code reste le sien.
    sortie=$(bash -c 'set -euo pipefail; . "$1"; dire() { echo "DIT: $1"; false; }; journal_sortie_imprevue essai dire; f() { return 4; }; f' _ "$ICI/lib-journal.sh" 2>&1); rc=$?
    t "la fonction de l'appelant reçoit la cause" 1 "$(printf '%s\n' "$sortie" | grep -c '^DIT: code 4, dernière commande : ')"
    t "…APRÈS la ligne datée" "CHEC|DIT" "$(printf '%s\n' "$sortie" | grep -oE 'CHEC|^DIT' | paste -sd'|' -)"
    t "…et son propre échec ne change pas le code de sortie" 4 "$rc"
    sortie=$(bash -c 'set -euo pipefail; . "$1"; dire() { echo "DIT"; }; journal_sortie_imprevue essai dire; sortir 0 "rien à faire"' _ "$ICI/lib-journal.sh" 2>&1)
    t "sortie prévue : la fonction n'est pas appelée" 0 "$(printf '%s\n' "$sortie" | grep -c '^DIT')"
    sortie=$(bash -c 'set -euo pipefail; . "$1"; dire() { echo "DIT"; }; journal_sortie_imprevue essai dire; true' _ "$ICI/lib-journal.sh" 2>&1)
    t "fin normale : la fonction n'est pas appelée" "" "$sortie"
    sortie=$(bash -c 'set -euo pipefail; . "$1"; journal_sortie_imprevue essai; sortir 3 "fetch impossible"' _ "$ICI/lib-journal.sh" 2>&1); rc=$?
    t "sortir : son code" 3 "$rc"
    t "sortir : UNE ligne, la sienne (le filet se tait)" "1|1" \
      "$(printf '%s\n' "$sortie" | grep -c '^\[')|$(printf '%s\n' "$sortie" | grep -c 'fetch impossible')"
    sortie=$(bash -c 'set -euo pipefail; . "$1"; journal_sortie_imprevue essai; true' _ "$ICI/lib-journal.sh" 2>&1)
    t "fin normale : le filet se tait" "" "$sortie"

    echo "== lib-journal : le contrat statique =="
    printf '%s\n' 'log "Bascule en cours"; exit 0' 'sortir 1 "build KO"' > "$tmp/ok.sh"
    t "texte conforme → aucun écart" "" "$(contrat_journal "$tmp/ok.sh")"
    #  La ligne d'auto-deploy.sh avant #1587, telle quelle.
    printf '%s\n' 'git fetch origin main --quiet' > "$tmp/fetch.sh"
    t "faute injectée : git fetch nu (#1587) → refusé" "l.1 : git fetch sans repli" "$(contrat_journal "$tmp/fetch.sh")"
    printf '%s\n' 'if ! E=$(git fetch origin main 2>&1); then' 'git fetch origin || sortir 0 "x"' > "$tmp/fetch-ok.sh"
    t "git fetch testé ou suivi d'un repli → admis" "" "$(contrat_journal "$tmp/fetch-ok.sh")"
    printf '%s\n' '    sortir 0 "⚠ git fetch impossible — reporté."' > "$tmp/fetch-cite.sh"
    t "un message qui CITE git fetch n'est pas un geste" "" "$(contrat_journal "$tmp/fetch-cite.sh")"
    printf '%s\n' 'log "a"' ':' ':' ':' ':' 'exit 0' > "$tmp/loin.sh"
    t "faute injectée : exit à 5 lignes de sa date → refusé" "l.6 : sortie sans ligne datée" "$(contrat_journal "$tmp/loin.sh")"
    printf '%s\n' 'log "build KO"' 'exit 1' > "$tmp/nu.sh"
    t "faute injectée : exit 1 hors de sortir → refusé" "l.2 : sortie en échec hors de sortir" "$(contrat_journal "$tmp/nu.sh")"
    printf '%s\n' 'if [ "${1:-}" = "--selftest" ]; then' 'exit 1' 'fi' > "$tmp/st.sh"
    t "le bloc --selftest est ignoré" "" "$(contrat_journal "$tmp/st.sh")"
    #  Le contrat appliqué pour de vrai : le script dont C14 lit le battement.
    t "auto-deploy.sh respecte le contrat" "" "$(contrat_journal "$ICI/../exploitation/auto-deploy.sh")"
    #  #1826 : la maintenance arme le filet, et lui confie son rapport d'erreur.
    t "maintenance.sh arme le filet avec son rapport" 1 \
      "$(grep -cE '^journal_sortie_imprevue maintenance\.sh rapport_arret_inattendu$' "$ICI/../exploitation/maintenance.sh")"

    rm -rf "$tmp"
    [ "$st" -eq 0 ] && echo "lib-journal : tous les cas passent."
    exit "$st"
fi
