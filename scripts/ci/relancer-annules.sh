#!/usr/bin/env bash
# =============================================================================
#  relancer-annules.sh — Relancer les jobs ANNULÉS d'une PR (#2225, 24/10/2026)
#
#  POURQUOI. Ce jour-là, GitHub a annulé deux checks requis d'une PR (conclusion
#  CANCELLED) : ni verts ni rouges, ils bloquaient la fusion, et rien ne le
#  signalait — on attendait une CI qui ne tournait plus. Ce script trouve les
#  exécutions de la PR dont un check est annulé et les relance
#  (`gh run rerun --failed`, qui reprend les jobs échoués ET annulés).
#
#  ## La décision (fonction PURE, testée par --selftest)
#
#  Par exécution (`…/actions/runs/<id>/…` dans le lien du check) :
#  | Ses checks…                         | Verdict    |
#  |-------------------------------------|------------|
#  | l'un encore en cours                | `en_cours` — on ne relance pas ce qui tourne |
#  | aucun en cours, l'un annulé         | `relancer` |
#  | aucun annulé                        | rien       |
#  Un check sans lien d'exécution (statut externe) est ignoré. Aucun check lu
#  (gh muet, PR inconnue) : INCONNU, code 2 — jamais « rien à relancer ».
#
#  Usage : bash scripts/ci/relancer-annules.sh <n° de PR> [--voir]
#  Test  : bash scripts/ci/relancer-annules.sh --selftest
#  Codes : 0 rien d'annulé ou relance faite · 1 une relance a échoué · 2 INCONNU / usage
# =============================================================================
set -uo pipefail

#  stdin « bucket<TAB>nom<TAB>lien » (gh pr checks) → « id<TAB>verdict<TAB>noms annulés » (PURE)
runs_a_relancer() {
  awk -F'\t' '
    match($3, /\/actions\/runs\/[0-9]+/) {
      id = substr($3, RSTART + 14, RLENGTH - 14)
      if (!(id in vu)) { vu[id] = 1; ordre[++n] = id }
      if ($1 == "pending") enc[id] = 1
      if ($1 == "cancel")  ann[id] = ann[id] (ann[id] == "" ? "" : ", ") $2
    }
    END {
      for (i = 1; i <= n; i++) {
        id = ordre[i]
        if (id in enc)      { if (id in ann) printf "%s\ten_cours\t%s\n", id, ann[id] }
        else if (id in ann) printf "%s\trelancer\t%s\n", id, ann[id]
      }
    }'
}

if [ "${1:-}" = "--selftest" ]; then
  st=0
  t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$3] obtenu=[$2]"; st=1; }; }
  L="https://github.com/o/d/actions/runs"
  t "rien d'annulé : rien" "$(printf 'pass\tA\t%s/1/job/9\nfail\tB\t%s/1/job/8\n' "$L" "$L" | runs_a_relancer)" ""
  t "un annulé : relancer, nommé" \
    "$(printf 'pass\tA\t%s/1/job/9\ncancel\tB\t%s/1/job/8\ncancel\tC\t%s/1/job/7\n' "$L" "$L" "$L" | runs_a_relancer)" \
    "$(printf '1\trelancer\tB, C')"
  t "annulé mais exécution en cours : attendre" \
    "$(printf 'cancel\tB\t%s/2/job/8\npending\tD\t%s/2/job/6\n' "$L" "$L" | runs_a_relancer)" "$(printf '2\ten_cours\tB')"
  t "deux exécutions, une seule annulée" \
    "$(printf 'cancel\tB\t%s/3/job/8\npass\tE\t%s/4/job/5\n' "$L" "$L" | runs_a_relancer | cut -f1,2)" "$(printf '3\trelancer')"
  t "statut externe sans exécution : ignoré" "$(printf 'cancel\tX\thttps://exemple.test/statut\n' | runs_a_relancer)" ""
  t "cas zéro : aucune ligne, aucune décision" "$(printf '' | runs_a_relancer)" ""
  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $st
fi

PR="${1:-}"; VOIR="${2:-}"
case "$PR" in ''|*[!0-9]*) sed -n '/^#  Usage/,/^#  Codes/p' "$0"; exit 2 ;; esac

#  `gh pr checks` sort en code non nul dès qu'un check échoue ou tourne : on juge sa SORTIE.
CHECKS=$(gh pr checks "$PR" --json bucket,name,link --jq '.[] | [.bucket, .name, .link] | @tsv' 2>/dev/null)
if [ -z "$CHECKS" ]; then
  echo "? Aucun check lu pour la PR $PR (gh muet, PR inconnue ou sans CI) — INCONNU, rien n'est relancé."
  exit 2
fi
DECISIONS=$(printf '%s\n' "$CHECKS" | runs_a_relancer)
if [ -z "$DECISIONS" ]; then
  echo "✓ PR $PR : $(printf '%s\n' "$CHECKS" | grep -c .) check(s) lus, aucun annulé."
  exit 0
fi
code=0
while IFS=$'\t' read -r id verdict noms; do
  case "$verdict" in
    en_cours) echo "· exécution $id : annulé(s) [$noms], mais elle tourne encore — relancer après sa fin." ;;
    relancer)
      if [ "$VOIR" = --voir ]; then
        echo "· exécution $id : annulé(s) [$noms] — à relancer : gh run rerun $id --failed"
      elif gh run rerun "$id" --failed; then
        echo "✓ exécution $id relancée — annulé(s) : $noms"
      else
        echo "✗ exécution $id : la relance a échoué — annulé(s) : $noms"; code=1
      fi ;;
  esac
done <<< "$DECISIONS"
exit $code
