#!/bin/bash
# =============================================================================
#  mesure-postgresql.sh — La suite pytest sur PostgreSQL (#1747)
#
#  Lancé dans `api/`, avec `TESTS_BASE_URL`, par les deux jobs qui jouent la
#  suite — « Tests Python (pytest) » (`ci.yml`, vers `dev`) et « Suite pytest sur
#  PostgreSQL » (`postgresql.yml`, vers `main`) — et par le rejeu du poste. Il
#  rejoue TOUTE la suite, en tranches parallèles, et écrit le bilan au résumé du
#  run — tests verts, en échec, en erreur, et les fichiers qui échouent. Un test
#  qui échoue bloque la fusion.
#
#  Code de sortie (fonction PURE `issue_suite`, testée par --selftest) :
#    toutes les tranches à 0 → 0 ;
#    une tranche en échec (1) → 1 : un test casse sur PostgreSQL ;
#    toute autre fin (interrompu, erreur interne, usage, rien collecté) → ce
#    code, parce qu'alors la suite n'a PAS tourné — INCONNU, jamais un vert.
#
#  Tranches : `TRANCHES` (défaut 4, les cœurs d'un exécuteur GitHub). Chaque test
#  a son schéma (`tests/aides_base`), les tranches ne se voient pas.
#
#  Test : bash scripts/ci/mesure-postgresql.sh --selftest
# =============================================================================
set -uo pipefail

# ── PURE : codes de sortie des tranches → code de sortie de la suite ─────────
#  Le plus grand l'emporte : une tranche interrompue (≥ 2) dit que la suite n'a
#  pas tourné, plus grave qu'un échec (1). Un code illisible compte pour 3, et
#  aucune tranche aussi — rien n'a tourné.
issue_suite() {
    [ $# -gt 0 ] || { echo 3; return; }
    local pire=0 rc
    for rc in "$@"; do
        case "$rc" in ''|*[!0-9]*) rc=3 ;; esac
        [ "$rc" -gt "$pire" ] && pire=$rc
    done
    echo "$pire"
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    for cas in "0 0 0:0" "0 1 0:1" "1 1:1" "0 2:2" "1 4:4" "5 2:5" "0 x:3" ":3"; do
        entree=${cas%%:*}; voulu=${cas##*:}
        # shellcheck disable=SC2086 # découpage voulu : une tranche par mot
        got=$(issue_suite $entree)
        if [ "$got" = "$voulu" ]; then echo "PASS  tranches [$entree] → $got"; else echo "FAIL  tranches [$entree] → $got (attendu $voulu)"; fail=1; fi
    done
    exit "$fail"
fi

[ -n "${TESTS_BASE_URL:-}" ] || { echo "::error::TESTS_BASE_URL absent : la suite ne peut pas tourner."; exit 3; }

TRANCHES=${TRANCHES:-4}
dossier=$(mktemp -d)
mapfile -t fichiers < <(ls tests/test_*.py)
[ "${#fichiers[@]}" -gt 0 ] || { echo "::error::aucun fichier de test trouvé dans $(pwd)/tests"; exit 3; }

pids=()
for i in $(seq 0 $((TRANCHES - 1))); do
    tranche=()
    for j in "${!fichiers[@]}"; do
        [ $((j % TRANCHES)) -eq "$i" ] && tranche+=("${fichiers[$j]}")
    done
    [ "${#tranche[@]}" -gt 0 ] || continue
    python -m pytest "${tranche[@]}" -q -p no:cacheprovider --tb=short -rfE > "$dossier/$i.log" 2>&1 &
    pids+=("$!")
done
codes=()
for pid in "${pids[@]}"; do
    wait "$pid"; codes+=("$?")
done

journal="$dossier/tout.log"
cat "$dossier"/[0-9]*.log > "$journal"
grep -hE "^[0-9]+ (passed|failed)|[0-9]+ (passed|failed|error)" "$dossier"/[0-9]*.log

issue=$(issue_suite "${codes[@]}")
resume="${GITHUB_STEP_SUMMARY:-/dev/null}"
{
    echo "## La suite pytest sur PostgreSQL (#1747)"
    echo
    echo "**Tranches** : ${#codes[@]} — codes pytest ${codes[*]} → issue $issue"
    echo
    grep -hE "^[0-9]+ (passed|failed)|[0-9]+ (passed|failed|error)" "$dossier"/[0-9]*.log | sed 's/^/- /'
    echo
    echo "### Les fichiers qui échouent"
    echo
    echo "| Échecs | Fichier |"
    echo "|---|---|"
    grep -E "^(FAILED|ERROR) " "$journal" | sed -E 's/^(FAILED|ERROR) ([^:]+)::.*/\2/' \
        | sort | uniq -c | sort -rn | head -40 | awk '{printf "| %s | `%s` |\n", $1, $2}'
} >> "$resume"

grep -E "^(FAILED|ERROR) " "$journal" | head -60
exit "$issue"
