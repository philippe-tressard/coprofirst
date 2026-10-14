#!/bin/bash
# =============================================================================
#  rappel-replica.sh — Rappeler à l'auteur que `replica` prend du retard
#  (#1934, 14/10/2026)
#
#  Les répliques ne reçoivent que les versions que l'auteur promeut (workflow
#  « Promotion », `scripts/ci/promotion.sh`). Rien ne l'y oblige — c'est voulu,
#  le choix de la version est aussi commercial —, mais un oubli laisserait les
#  installations sur une version de plus en plus ancienne sans que personne le
#  voie. D'où ce rappel, une décision de l'auteur :
#
#  - à 10 versions de retard sur la référence, UNE issue lui est assignée
#    (GitHub en envoie le courriel), puis UNE nouvelle à 20, à 30… ;
#  - jamais deux pour une même tranche : le titre porte la version de `replica`
#    et la tranche, et une issue de ce titre, ouverte ou fermée, suffit ;
#  - une issue de rappel qui ne correspond plus (replica a avancé, ou la
#    tranche suivante est ouverte) se ferme d'elle-même.
#
#  Les versions se comptent sur les tags `vX.Y.Z` de `main` publiés après celui
#  que porte `replica`.
#
#  Lancé chaque nuit par le workflow « Promotion » (déclenchement `schedule`).
#  Test : bash scripts/ci/rappel-replica.sh --selftest
# =============================================================================
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib-replica.sh"

LABEL=retard-replica
PAS=10

# ── Les décisions (PURES) ─────────────────────────────────────────────────────
tranche_retard() {  # $1 versions de retard → la tranche atteinte (0 : aucune)
    echo $(( $1 / PAS * PAS ))
}
titre_rappel() {  # $1 version de replica · $2 tranche
    echo "Promotion : replica (v$1) a $2 versions de retard sur la référence"
}
#  $1 titre de la tranche courante (vide : aucune) · entrée : les titres des
#  issues de rappel, une par ligne. Sortie : « creer » ou rien.
decider_rappel() {
    local titre="$1"
    if [ -n "$titre" ] && ! grep -qxF -- "$titre"; then echo creer; else cat >/dev/null; fi
}
#  $1 titre de la tranche courante · entrée : « numéro<TAB>titre » des issues de
#  rappel OUVERTES. Sortie : les numéros à fermer.
rappels_perimes() {
    awk -F '\t' -v t="$1" '$2 != t { print $1 }'
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    egal() {  # $1 libellé · $2 attendu · $3 obtenu
        if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 — attendu « $2 », obtenu « $3 »"; fail=1; fi
    }
    echo "== self-test : rappel de retard de replica =="
    egal "0 version → aucune tranche"   0  "$(tranche_retard 0)"
    egal "9 versions → aucune tranche"  0  "$(tranche_retard 9)"
    egal "10 versions → tranche 10"     10 "$(tranche_retard 10)"
    egal "19 versions → tranche 10"     10 "$(tranche_retard 19)"
    egal "20 versions → tranche 20"     20 "$(tranche_retard 20)"
    egal "35 versions → tranche 30"     30 "$(tranche_retard 35)"
    t10=$(titre_rappel 2.145.0 10); t20=$(titre_rappel 2.145.0 20)
    egal "première fois à 10 → créer"            creer "$(printf '' | decider_rappel "$t10")"
    egal "déjà rappelé à 10 → rien"              ""    "$(printf '%s\n' "$t10" | decider_rappel "$t10")"
    egal "tranche 20 après 10 → créer"           creer "$(printf '%s\n' "$t10" | decider_rappel "$t20")"
    egal "aucune tranche → rien"                 ""    "$(printf '%s\n' "$t10" | decider_rappel "")"
    egal "même tranche, replica a avancé → créer" creer "$(printf '%s\n' "$t10" | decider_rappel "$(titre_rappel 2.150.0 10)")"
    egal "rappel 10 périmé quand 20 s'ouvre"     12    "$(printf '12\t%s\n15\t%s\n' "$t10" "$t20" | rappels_perimes "$t20")"
    egal "tout se ferme quand replica rattrape"  "12"  "$(printf '12\t%s\n' "$t10" | rappels_perimes "")"
    exit "$fail"
fi

DEPOT="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY manquant}"
git fetch --quiet origin main replica 2>/dev/null || true
replica=$(git rev-parse --verify origin/replica)
replica_version=$(version_du_commit "$replica")
[ -n "$replica_version" ] || { echo "::error::replica ($replica) ne porte aucun tag de version"; exit 1; }
derniere=$(git tag -l 'v[0-9]*' --merged origin/main --sort=-v:refname | head -n 1)
retard=$(git tag -l 'v[0-9]*' --merged origin/main --contains "$replica" | grep -cvxF "v$replica_version" || true)
tranche=$(tranche_retard "$retard")
titre=""
[ "$tranche" -gt 0 ] && titre=$(titre_rappel "$replica_version" "$tranche")

echo "replica : v$replica_version · dernière version : $derniere · retard : $retard version(s) · tranche : $tranche" \
    | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"

gh issue list --repo "$DEPOT" --label "$LABEL" --state open --limit 100 \
    --json number,title --jq '.[] | "\(.number)\t\(.title)"' \
    | rappels_perimes "$titre" | while read -r numero; do
        gh issue close "$numero" --repo "$DEPOT" \
            --comment "Ce rappel ne correspond plus : \`replica\` porte v$replica_version, avec $retard version(s) de retard."
    done

if [ "$(gh issue list --repo "$DEPOT" --label "$LABEL" --state all --limit 500 \
        --json title --jq '.[].title' | decider_rappel "$titre")" = creer ]; then
    gh label create "$LABEL" --repo "$DEPOT" --force \
        --color FBCA04 --description "Rappel : replica en retard sur la référence" >/dev/null
    corps=$(mktemp)
    cat > "$corps" <<CORPS
Les répliques sont sur **v$replica_version**, la référence sur **$derniere** : **$retard versions** d'écart.

Rien n'oblige à promouvoir — ce rappel n'est qu'un rappel, et le prochain ne viendra qu'à $(( tranche + PAS )) versions. Pour promouvoir une version rodée (7 jours sur la référence) :

\`\`\`bash
gh workflow run promotion.yml -f version=X.Y.Z
\`\`\`

ou GitHub › Actions › Promotion › Run workflow. Ce rappel se ferme de lui-même quand \`replica\` avance.
CORPS
    gh issue create --repo "$DEPOT" --title "$titre" --label "$LABEL" \
        --assignee "${GITHUB_REPOSITORY_OWNER:-${GITHUB_REPOSITORY%%/*}}" --body-file "$corps"
fi
