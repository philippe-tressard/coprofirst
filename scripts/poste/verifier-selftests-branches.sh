#!/usr/bin/env bash
# =============================================================================
#  Tout script versionné qui expose `--selftest` doit être LANCÉ par le job
#  `test-scripts` de la CI (#1574).
#
#  POURQUOI. `CLAUDE.md` (« Scripts d'infra ») pose : toute logique de décision
#  d'infra s'isole en fonction pure, expose `--selftest`, « et l'ajoute au job ».
#  Le troisième verbe ne manque à personne tant qu'on n'y pense pas :
#  `durcir-sudoers.sh --selftest` passait au vert, déclarait « TOUS OK » et
#  n'était appelé par aucun job — alors que la décision qu'il éprouve écrit dans
#  `/etc/sudoers.d` (la règle NOPASSWD retirée du dépôt qui était restée
#  installée 24 h, 01/09/2026). C'est la famille de #409, #410, #411 et #561 :
#  un contrôle qui existe, qui est juste, et que rien n'exécute. Ce script est
#  `front/scripts/check-ci-complete.mjs` transposé aux scripts d'infra, et il
#  se juge lui-même : son propre `--selftest` est dans le job.
#
#  CE QU'IL MESURE. Les exposeurs sont lus à la FORME du geste — une ligne non
#  commentée `… = "--selftest"` — et non à la mention du mot : un script qui
#  cite `--selftest` dans un commentaire ne l'expose pas, et celui qui le cite
#  dans le job en commentaire ne le lance pas. Le job est découpé dans
#  `.github/workflows/ci.yml` (de `  test-scripts:` au job suivant) : un
#  self-test lancé dans un AUTRE job ne compte pas, c'est le sens du ticket.
#
#  EXCEPTIONS. `EXCEPTIONS` (plus bas) déclare un script exposant `--selftest`
#  qu'on ne lance délibérément pas en CI, avec SA RAISON. ⚠️ Une exception qui ne
#  sert plus — le script ne l'expose plus, ou le job le lance désormais — FAIT
#  ÉCHOUER : sinon la liste couvrirait le prochain oubli sous un nom qui a déjà
#  servi. Elle est vide aujourd'hui : un seul manque existait, et il est câblé.
#
#  CAS ZÉRO. Moins de 20 exposeurs lus, ou un job introuvable, ne veut pas dire
#  « tout va bien » : la lecture est cassée → INCONNU, code 1, jamais OK.
#
#  Usage : bash scripts/poste/verifier-selftests-branches.sh
#          bash scripts/poste/verifier-selftests-branches.sh --selftest
# =============================================================================
set -uo pipefail
# shellcheck source=../lib/lib-poste-gnu.sh
. "$(dirname "$0")/../lib/lib-poste-gnu.sh"
poste_gnu_poser "$@"   # macOS : les outils GNU en tête du PATH, comme Git Bash et la CI (#2419)

RACINE_DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORKFLOW="$RACINE_DEPOT/.github/workflows/ci.yml"
JOB="test-scripts"
MIN_EXPOSEURS=20

#  « chemin|raison » — voir l'en-tête. Vide : tout self-test exposé est lancé.
EXCEPTIONS=()

# ── Fonctions de décision PURES ──────────────────────────────────────────────

#  Les fichiers (arguments) qui EXPOSENT `--selftest` : une ligne non commentée
#  où l'on compare un argument à « --selftest » (`[ "$1" = "--selftest" ]`) ou
#  qui en fait l'étiquette d'un `case` (`--selftest) …`). Lit les fichiers, n'écrit rien.
exposeurs_selftest() {
  local f
  for f in "$@"; do
    [ -f "$f" ] || continue
    grep -qE '^[^#]*(= *"--selftest"|--selftest\))' "$f" && printf '%s\n' "$f"
  done
  return 0
}

#  Le texte du job `$2` dans le workflow `$1` (stdin possible via fichier) :
#  de sa ligne d'ouverture au job suivant (clé à deux espaces d'indentation).
#  Les lignes de commentaire en sont retirées — citer un self-test n'est pas le
#  lancer. Vide si le job n'existe pas.
texte_du_job() {  # $1 = texte du workflow, $2 = nom du job
  printf '%s\n' "$1" | awk -v job="$2" '
    $0 ~ "^  " job ":[[:space:]]*$" { dedans = 1; next }
    dedans && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ { exit }
    dedans && $0 !~ /^[[:space:]]*#/ { print }
  '
}

#  Un chemin est-il lancé (`<chemin> --selftest`) dans le texte du job ?
est_lance() {  # $1 = texte du job, $2 = chemin
  local motif
  #  ⚠️ `[` ne s'écrit qu'EN DERNIER dans la classe : placé avant `.`, il ouvre « [. »
  #  (symbole de collation), `sed` proteste et le motif reste vide — or un motif vide
  #  reconnaît tout : un vert. Vu en l'écrivant ; d'où le garde-fou ci-dessous.
  motif=$(printf '%s' "$2" | sed 's|[].*^$\\[]|\\&|g')
  [ -n "$motif" ] || return 1
  grep -qE "(^|[[:space:]])${motif}[[:space:]]+--selftest" <<<"$1"
}

#  Le verdict. $1 = texte du job · $2 = exposeurs (un par ligne) · $3 = exceptions
#  (« chemin|raison », une par ligne). Écrit les anomalies, une par ligne ; rend 0
#  si aucune, 1 sinon.
verdict_selftests() {
  local job="$1" exposeurs="$2" exceptions="$3" f ligne chemin anomalies=""
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    est_lance "$job" "$f" && continue
    if grep -qF "${f}|" <<<"$exceptions"; then continue; fi
    anomalies+="MANQUE $f : expose --selftest, aucune ligne « bash $f --selftest » dans le job $JOB"$'\n'
  done <<< "$exposeurs"
  while IFS= read -r ligne; do
    [ -z "$ligne" ] && continue
    chemin="${ligne%%|*}"
    if ! grep -qxF "$chemin" <<<"$exposeurs"; then
      anomalies+="EXCEPTION PÉRIMÉE $chemin : n'expose plus --selftest — retirer l'entrée"$'\n'
    elif est_lance "$job" "$chemin"; then
      anomalies+="EXCEPTION PÉRIMÉE $chemin : le job $JOB le lance désormais — retirer l'entrée"$'\n'
    fi
  done <<< "$exceptions"
  [ -z "$anomalies" ] && return 0
  printf '%s' "$anomalies"
  return 1
}

# ── Self-test ────────────────────────────────────────────────────────────────
verifier_selftests_selftest() {
  local ok=0 ko=0 tmp
  _attend() {  # _attend <libellé> <attendu> <obtenu>
    if [ "$2" = "$3" ]; then echo "  OK    $1"; ok=$((ok+1)); else echo "  ÉCHEC $1 (attendu $2, obtenu $3)"; ko=$((ko+1)); fi
  }
  _code() { "$@" >/dev/null 2>&1; echo $?; }

  tmp=$(mktemp -d 2>/dev/null) || { echo "INCONNU : mktemp indisponible — self-test non exécuté." >&2; return 3; }
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" RETURN

  echo "== Lecture des exposeurs =="
  printf '#!/bin/bash\nif [ "${1:-}" = "--selftest" ]; then exit 0; fi\n'      > "$tmp/expose.sh"
  printf '#!/bin/bash\n# bash x.sh --selftest : un commentaire n expose rien\n'  > "$tmp/commente.sh"
  printf '#!/bin/bash\necho rien\n'                                              > "$tmp/aucun.sh"
  printf '#!/bin/bash\n[ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ] && exit 0\n' > "$tmp/garde.sh"
  printf '#!/bin/bash\ncase "${1:-}" in\n  --selftest) exit 0 ;;\nesac\n'            > "$tmp/etiquette.sh"
  _attend "un « = \"--selftest\" » non commenté est un exposeur" "2" \
    "$(exposeurs_selftest "$tmp/expose.sh" "$tmp/garde.sh" | wc -l | tr -d ' ')"
  _attend "une étiquette « --selftest) » de case en est un aussi (banc-volumes.sh)" "1" \
    "$(exposeurs_selftest "$tmp/etiquette.sh" | wc -l | tr -d ' ')"
  _attend "une mention en commentaire n'expose rien" "0" \
    "$(exposeurs_selftest "$tmp/commente.sh" "$tmp/aucun.sh" "$tmp/absent.sh" | wc -l | tr -d ' ')"

  echo "== Découpe du job =="
  local wf job
  wf=$'jobs:\n  autre:\n    steps:\n      - run: bash scripts/a.sh --selftest\n  test-scripts:\n    steps:\n      # bash scripts/c.sh --selftest\n      - run: |\n          bash scripts/b.sh   --selftest\n  suivant:\n    steps:\n      - run: bash scripts/d.sh --selftest\n'
  job=$(texte_du_job "$wf" "$JOB")
  _attend "ce que le job lance est lu" "0" "$(est_lance "$job" scripts/b.sh; echo $?)"
  _attend "un self-test lancé dans un AUTRE job (avant) ne compte pas" "1" "$(est_lance "$job" scripts/a.sh; echo $?)"
  _attend "un self-test lancé dans un AUTRE job (après) ne compte pas" "1" "$(est_lance "$job" scripts/d.sh; echo $?)"
  _attend "un self-test cité en commentaire n'est pas lancé" "1" "$(est_lance "$job" scripts/c.sh; echo $?)"
  _attend "cas zéro : un job inexistant donne un texte vide" "" "$(texte_du_job "$wf" "inexistant")"
  _attend "le point d'un chemin n'est pas un joker" "1" "$(est_lance "bash scripts/bXsh --selftest" scripts/b.sh; echo $?)"

  echo "== Verdict =="
  local expo=$'scripts/b.sh\nscripts/z.sh'
  _attend "un exposeur absent du job est refusé (le cas de #1574)" "1" "$(_code verdict_selftests "$job" "$expo" "")"
  _attend "…et le message le nomme" "oui" \
    "$(m=$(verdict_selftests "$job" "$expo" ""); case "$m" in *"MANQUE scripts/z.sh"*) echo oui ;; *) echo non ;; esac)"
  _attend "tous lancés : accepté" "0" "$(_code verdict_selftests "$job" "scripts/b.sh" "")"
  _attend "un manque déclaré en exception est toléré" "0" \
    "$(_code verdict_selftests "$job" "$expo" "scripts/z.sh|besoin d'un nœud réel")"
  _attend "une exception dont le script n'expose plus rien échoue" "1" \
    "$(_code verdict_selftests "$job" "scripts/b.sh" "scripts/z.sh|raison")"
  _attend "une exception que le job lance désormais échoue" "1" \
    "$(_code verdict_selftests "$job" "scripts/b.sh" "scripts/b.sh|raison")"

  echo "== Le dépôt réel =="
  local reel
  reel=$(cd "$RACINE_DEPOT" && git ls-files -- '*.sh' '.githooks/*' 2>/dev/null)
  if [ -z "$reel" ]; then
    echo "  INCONNU : git ne liste aucun script (hors dépôt ?) — contrôle du dépôt réel non exécuté" >&2
    ko=$((ko+1))
  else
    local n
    n=$(cd "$RACINE_DEPOT" && exposeurs_selftest $reel | wc -l | tr -d ' ')
    [ "$n" -ge "$MIN_EXPOSEURS" ] \
      && { echo "  OK    cas zéro : $n exposeurs lus (au moins $MIN_EXPOSEURS attendus)"; ok=$((ok+1)); } \
      || { echo "  ÉCHEC cas zéro : $n exposeur(s) lu(s), au moins $MIN_EXPOSEURS attendus — le motif ne correspond plus aux scripts"; ko=$((ko+1)); }
  fi

  echo
  if [ "$ko" -eq 0 ]; then echo "== TOUS OK ($ok contrôles) =="; return 0; fi
  echo "== $ko ÉCHEC(S) sur $((ok+ko)) =="
  return 1
}

if [ "${1:-}" = "--selftest" ]; then verifier_selftests_selftest; exit $?; fi
if [ "$#" -gt 0 ]; then
  echo "Usage : $0 [--selftest]" >&2
  exit 2
fi

# ── Exécution sur le dépôt ───────────────────────────────────────────────────
cd "$RACINE_DEPOT" || exit 1
if [ ! -f "$WORKFLOW" ]; then
  echo "INCONNU : $WORKFLOW introuvable — rien à vérifier, et se taire vaudrait un vert." >&2
  exit 1
fi
job=$(texte_du_job "$(cat "$WORKFLOW")" "$JOB")
if [ -z "$job" ]; then
  echo "INCONNU : le job « $JOB » est introuvable dans ci.yml — la lecture ne correspond plus au fichier." >&2
  exit 1
fi
# shellcheck disable=SC2046
exposeurs=$(exposeurs_selftest $(git ls-files -- '*.sh' '.githooks/*'))
n=$(printf '%s\n' "$exposeurs" | grep -c .)
if [ "$n" -lt "$MIN_EXPOSEURS" ]; then
  echo "INCONNU : $n exposeur(s) de --selftest lu(s), au moins $MIN_EXPOSEURS attendus — le motif de lecture ne correspond plus aux scripts." >&2
  exit 1
fi
exceptions=$(printf '%s\n' "${EXCEPTIONS[@]+"${EXCEPTIONS[@]}"}")
if anomalies=$(verdict_selftests "$job" "$exposeurs" "$exceptions"); then
  echo "✓ $n scripts exposent --selftest, tous lancés par le job $JOB (${#EXCEPTIONS[@]} exception(s) nommée(s))."
  exit 0
fi
{
  echo
  echo "✗ self-tests exposés mais non lancés par le job $JOB :"
  echo
  printf '%s' "$anomalies" | sed 's/^/  /'
  echo
  echo "  Un contrôle qui existe et que rien n'exécute est le pire des faux verts :"
  echo "  il passe quand on le tape, la CI est verte, et la décision n'est plus gardée."
  echo "  Ajouter « bash <script> --selftest » à l'étape des self-tests de ci.yml — ou,"
  echo "  si c'est délibéré, déclarer le script dans EXCEPTIONS avec sa raison."
  echo
} >&2
exit 1
