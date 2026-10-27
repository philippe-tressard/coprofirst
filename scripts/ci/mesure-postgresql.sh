#!/bin/bash
# =============================================================================
#  mesure-postgresql.sh — La suite pytest sur PostgreSQL (#1747)
#
#  Lancé dans `api/`, avec `TESTS_BASE_URL`, par les deux jobs qui jouent la
#  suite — « Tests Python (pytest) » (`ci.yml`, vers `dev`) et « Suite pytest sur
#  PostgreSQL » (`postgresql.yml`, vers `main`) — et par le rejeu du poste. Il
#  rejoue TOUTE la suite, en parallèle, et écrit le bilan au résumé du run —
#  tests verts, en échec, en erreur, et les fichiers qui échouent. Un test qui
#  échoue bloque la fusion.
#
#  Code de sortie (fonction PURE `issue_suite`, testée par --selftest) :
#    pytest à 0 → 0 ; un test en échec (1) → 1 ;
#    toute autre fin (interrompu, erreur interne, usage, rien collecté) → ce
#    code, parce qu'alors la suite n'a PAS tourné — INCONNU, jamais un vert.
#
#  Parallèle par pytest-xdist (#2223), et non plus par tranches de fichiers : une
#  tranche lente fixait la durée de toute l'étape, et la répartition changeait à
#  chaque fichier ajouté — c'est ainsi qu'une dépendance à l'ordre est sortie
#  sur le lot d'un autre (24/10/2026). Les workers se répartissent les tests au
#  fil de l'eau ; chacun a son schéma d'application (`tests/conftest.py`), et
#  chaque test le sien (`tests/aides_base`).
#
#  Workers : `PYTEST_WORKERS`, sinon `workers_suite` (PURE) — les cœurs du poste,
#  bornés par ce que le serveur admet de connexions.
#  Ordre : ALÉATOIRE (pytest-randomly), graine affichée et écrite au résumé ;
#  `PYTEST_GRAINE=<n>` rejoue le même ordre.
#
#  Test : bash scripts/ci/mesure-postgresql.sh --selftest
# =============================================================================
set -uo pipefail

#: Connexions qu'un worker tient en même temps : trois au plus relevées (#2223 —
#: 35 pour 11 workers, 48 pour 16), une de marge.
CONNEXIONS_PAR_WORKER=4
#: Laissées aux autres : le rejeu d'une autre session, un psql, la supervision.
CONNEXIONS_RESERVEES=30
#: Au-delà, un worker de plus ne fait plus gagner de temps : 401 s à 11 workers,
#: 431 s à 16 sur le poste de 28 cœurs — la base y sature (#2223).
WORKERS_PLAFOND=12

# ── PURE : le code de sortie de pytest → le code de sortie de la suite ───────
#  Le plus grand l'emporte : une fin interrompue (≥ 2) dit que la suite n'a pas
#  tourné, plus grave qu'un échec (1). Un code illisible compte pour 3, et
#  aucun code aussi — rien n'a tourné.
issue_suite() {
    [ $# -gt 0 ] || { echo 3; return; }
    local pire=0 rc
    for rc in "$@"; do
        case "$rc" in ''|*[!0-9]*) rc=3 ;; esac
        [ "$rc" -gt "$pire" ] && pire=$rc
    done
    echo "$pire"
}

# ── PURE : cœurs, connexions admises par le serveur → nombre de workers ──────
#  Le plus petit de : les cœurs, ce que le serveur admet une fois la réserve
#  ôtée, le plafond mesuré. Jamais moins d'un. Une donnée illisible compte pour
#  un cœur, ou pour le défaut de PostgreSQL (100 connexions).
workers_suite() {
    local coeurs=${1:-1} connexions=${2:-100} n par_connexions
    case "$coeurs" in ''|*[!0-9]*) coeurs=1 ;; esac
    case "$connexions" in ''|*[!0-9]*) connexions=100 ;; esac
    n=$coeurs
    par_connexions=$(( (connexions - CONNEXIONS_RESERVEES) / CONNEXIONS_PAR_WORKER ))
    [ "$par_connexions" -lt "$n" ] && n=$par_connexions
    [ "$WORKERS_PLAFOND" -lt "$n" ] && n=$WORKERS_PLAFOND
    [ "$n" -lt 1 ] && n=1
    echo "$n"
}

# ── PURE : le journal de pytest → ce qui explique un échec ───────────────────
#  Les sections « FAILURES » et « ERRORS » : l'assertion et la trace de chaque test (`--tb=short`).
#  Le rejeu ne gardait que le nom du test (#2242) : `test_l_archive_porte_l_export…` est tombé une
#  fois sous charge, et le rejeu repris est resté vert sans que rien n'explique le premier rouge.
#  Bornée (400 lignes) : une suite cassée de bout en bout ne noie pas le journal. Rien à dire sur
#  une suite verte — la sortie est vide, jamais un « aucun échec » qui se lirait comme une mesure.
LIGNES_ECHECS_MAX=400
sections_echecs() {         # stdin = journal de pytest → stdout
    awk -v max="$LIGNES_ECHECS_MAX" '
        /^=+ (FAILURES|ERRORS) =+$/ { dedans = 1 }
        /^=+ (warnings summary|short test summary info|[0-9]+ (passed|failed|error)).*=+$/ { dedans = 0 }
        dedans { if (n < max) print; else if (n == max) print "… (journal tronqué à " max " lignes)"; n++ }
    '
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    t() { if [ "$2" = "$3" ]; then echo "PASS  $1 → $2"; else echo "FAIL  $1 → $2 (attendu $3)"; fail=1; fi; }
    for cas in "0:0" "1:1" "2:2" "4:4" "5:5" "x:3" ":3" "0 1:1"; do
        entree=${cas%%:*}; voulu=${cas##*:}
        # shellcheck disable=SC2086 # découpage voulu : un code par mot
        t "codes [$entree]" "$(issue_suite $entree)" "$voulu"
    done
    t "4 cœurs (exécuteur GitHub), 100 connexions"     "$(workers_suite 4 100)"   4
    t "28 cœurs, 100 connexions : le plafond borne"    "$(workers_suite 28 100)"  12
    t "28 cœurs, 60 connexions : le serveur borne"     "$(workers_suite 28 60)"   7
    t "1 cœur"                                          "$(workers_suite 1 100)"   1
    t "serveur saturé : jamais moins d'un worker"       "$(workers_suite 28 20)"   1
    t "cœurs illisibles, serveur muet : un worker"      "$(workers_suite "" "")"   1
    t "données illisibles : un cœur"                    "$(workers_suite x y)"     1
    #  #2242 : l'assertion et la trace d'un test en échec sont gardées, pas son seul nom.
    rouge=$'.F.
=========== FAILURES ===========
___ test_archive ___
tests/t.py:12: in test_archive
    assert n == 3
E   assert 2 == 3
=========== warnings summary ===========
ignoré
=========== short test summary info ===========
FAILED tests/t.py::test_archive
=========== 1 failed, 2 passed in 3.2s ==========='
    garde=$(printf '%s
' "$rouge" | sections_echecs)
    t "échec : l'assertion est gardée"        "$(printf '%s
' "$garde" | grep -c 'E   assert 2 == 3')" 1
    t "échec : la trace est gardée"           "$(printf '%s
' "$garde" | grep -c 'tests/t.py:12')" 1
    t "échec : l'avertissement est écarté"    "$(printf '%s
' "$garde" | grep -c 'ignoré')" 0
    t "échec : le résumé n'est pas répété"    "$(printf '%s
' "$garde" | grep -c '^FAILED')" 0
    t "suite verte : rien à dire"             "$(printf '.....
=========== 5 passed in 1s ===========
' | sections_echecs | wc -l | tr -d ' ')" 0
    erreur=$'=========== ERRORS ===========
___ ERROR collecting tests/t.py ___
E   ImportError: x
=========== short test summary info ==========='
    t "erreur de collecte : gardée"           "$(printf '%s
' "$erreur" | sections_echecs | grep -c 'ImportError')" 1
    LIGNES_ECHECS_MAX=3
    t "journal borné"                         "$( (echo '=========== FAILURES ==========='; seq 1 50) | sections_echecs | wc -l | tr -d ' ')" 4
    LIGNES_ECHECS_MAX=400
    exit "$fail"
fi

[ -n "${TESTS_BASE_URL:-}" ] || { echo "::error::TESTS_BASE_URL absent : la suite ne peut pas tourner."; exit 3; }

#  `max_connections` du serveur des tests ; vide s'il ne répond pas — la suite
#  le dira alors elle-même, test par test.
connexions=$(python - <<'EOF' 2>/dev/null
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
moteur = create_engine(os.environ["TESTS_BASE_URL"], poolclass=NullPool)
with moteur.connect() as c:
    print(c.execute(text("SHOW max_connections")).scalar())
EOF
)
WORKERS=${PYTEST_WORKERS:-$(workers_suite "$(nproc 2>/dev/null)" "$connexions")}
GRAINE=${PYTEST_GRAINE:-$(( (RANDOM << 15) | RANDOM ))}
echo "Suite : $WORKERS worker(s) ; ordre aléatoire, graine $GRAINE — rejouer cet ordre : PYTEST_GRAINE=$GRAINE"

dossier=$(mktemp -d)
journal="$dossier/suite.log"
#  `--randomly-dont-reset-seed` : l'ordre change, pas le hasard des tests —
#  `random` réamorcé à chaque test rendrait le même numéro d'affaire à tous.
python -m pytest tests -n "$WORKERS" --dist load \
    --randomly-seed="$GRAINE" --randomly-dont-reset-seed \
    -q -p no:cacheprovider --tb=short -rfE > "$journal" 2>&1
code=$?

bilan=$(grep -hE "^[0-9]+ (passed|failed)|[0-9]+ (passed|failed|error)" "$journal" | tail -1)
echo "$bilan"

issue=$(issue_suite "$code")
resume="${GITHUB_STEP_SUMMARY:-/dev/null}"
{
    echo "## La suite pytest sur PostgreSQL (#1747)"
    echo
    echo "**Workers** : $WORKERS — **graine** de l'ordre : \`$GRAINE\` (\`PYTEST_GRAINE=$GRAINE\` le rejoue) — code pytest $code → issue $issue"
    echo
    echo "- $bilan"
    echo
    echo "### Les fichiers qui échouent"
    echo
    echo "| Échecs | Fichier |"
    echo "|---|---|"
    grep -E "^(FAILED|ERROR) " "$journal" | sed -E 's/^(FAILED|ERROR) ([^:]+)::.*/\2/' \
        | sort | uniq -c | sort -rn | head -40 | awk '{printf "| %s | `%s` |\n", $1, $2}'
} >> "$resume"

#  L'explication AVANT les noms : le rejeu garde cette sortie dans `rejeu-ci-echecs/` (#2242).
[ "$code" -ne 0 ] && sections_echecs < "$journal"
grep -E "^(FAILED|ERROR) " "$journal" | head -60
#  Une suite qui n'a pas tourné montre sa fin : l'erreur de collecte ou
#  d'interruption y est, et nulle part ailleurs.
[ "$issue" -ge 2 ] && tail -40 "$journal"
exit "$issue"
