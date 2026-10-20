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
#  Le retard se compte en versions MINEURES (16/10/2026, décision de l'auteur) :
#  les `X.Y` distinctes des tags `vX.Y.Z` de `main` publiés après celui que porte
#  `replica`, celle de `replica` exclue. Un correctif (X.Y.1, X.Y.2…) ne compte
#  pas : compter chaque tag annonçait 19 versions pour 11 mineures, et la tranche
#  suivante tombait dès le lendemain. C'est la mesure de l'alerte du registre
#  (`api/app/registre/alertes.py`, `RETARD_MINEURES`) : les deux disent le même écart.
#
#  Lancé chaque nuit par le workflow « Promotion » (déclenchement `schedule`).
#  Test : bash scripts/ci/rappel-replica.sh --selftest
# =============================================================================
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib-replica.sh"

LABEL=retard-replica
PAS=10

# ── Les décisions (PURES) ─────────────────────────────────────────────────────
#  $1 version de replica (X.Y.Z) · entrée : les tags vX.Y.Z publiés après elle,
#  un par ligne. Sortie : le nombre de mineures X.Y distinctes, la sienne exclue.
mineures_de_retard() {
    local propre="${1%.*}"
    sed -n 's/^v\([0-9]*\.[0-9]*\)\.[0-9]*$/\1/p' | grep -vxF -- "$propre" | sort -u | grep -c . || true
}
tranche_retard() {  # $1 mineures de retard → la tranche atteinte (0 : aucune)
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
#  $1 commit de replica · $2 sa version → ses mineures de retard sur `origin/main`.
#  Lit le dépôt git courant (le self-test lui en bâtit un). Le tag de replica est
#  dans la liste, et `mineures_de_retard` l'exclut avec sa mineure : un filtre en
#  amont vidait le tube quand replica porte la dernière version, et un `grep`
#  qui ne trouve rien sort en 1 — sous `pipefail` + `set -e`, le script mourait
#  sans un mot (nuits du 19 et du 20/10/2026, replica sur v3.1.0).
retard_de_replica() {
    git tag -l 'v[0-9]*' --merged origin/main --contains "$1" | mineures_de_retard "$2"
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    egal() {  # $1 libellé · $2 attendu · $3 obtenu
        if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 — attendu « $2 », obtenu « $3 »"; fail=1; fi
    }
    echo "== self-test : rappel de retard de replica =="
    egal "correctifs non comptés"          2  "$(printf 'v2.151.0
v2.151.1
v2.151.2
v2.152.0
' | mineures_de_retard 2.150.0)"
    egal "correctif de la mineure de replica non compté" 1 "$(printf 'v2.150.1
v2.151.0
' | mineures_de_retard 2.150.0)"
    egal "une majeure compte"              1  "$(printf 'v3.0.0
v3.0.1
' | mineures_de_retard 2.161.4)"
    egal "aucun tag → 0"                   0  "$(printf '' | mineures_de_retard 2.150.0)"
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
    #  Le retard lu dans un vrai dépôt : replica sur la DERNIÈRE version, puis en
    #  retard. Le code de retour compte autant que la valeur : l'écriture fautive
    #  rendait bien « 0 », mais en échec — et l'affectation tuait le script.
    depot=$(mktemp -d)
    commit() { git -c user.email=t@t -c user.name=t commit -q --allow-empty -m "$1"; }
    (cd "$depot" && git init -q && commit a && git tag v3.1.0 && git update-ref refs/remotes/origin/main HEAD)
    r=$(cd "$depot" && retard_de_replica HEAD 3.1.0) || r="échec (code $?)"
    egal "replica sur la dernière version → 0, sans échec" 0 "$r"
    (cd "$depot" && commit b && git tag v3.2.0 && commit c && git tag v3.2.1 && git update-ref refs/remotes/origin/main HEAD)
    r=$(cd "$depot" && retard_de_replica v3.1.0 3.1.0) || r="échec (code $?)"
    egal "une mineure et son correctif → 1"   1 "$r"
    rm -rf "$depot"
    exit "$fail"
fi

#  Un échec se nomme : sous `set -e`, le run ne disait que « exit code 1 ».
trap 'echo "::error::rappel-replica.sh, ligne $LINENO : « $BASH_COMMAND » a échoué"' ERR

DEPOT="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY manquant}"
git fetch --quiet origin main replica 2>/dev/null || true
replica=$(git rev-parse --verify origin/replica)
replica_version=$(version_du_commit "$replica")
[ -n "$replica_version" ] || { echo "::error::replica ($replica) ne porte aucun tag de version"; exit 1; }
derniere=$(git tag -l 'v[0-9]*' --merged origin/main --sort=-v:refname | sed -n 1p)
retard=$(retard_de_replica "$replica" "$replica_version")
tranche=$(tranche_retard "$retard")
titre=""
[ "$tranche" -gt 0 ] && titre=$(titre_rappel "$replica_version" "$tranche")

echo "replica : v$replica_version · dernière version : $derniere · retard : $retard mineure(s) · tranche : $tranche" \
    | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"

gh issue list --repo "$DEPOT" --label "$LABEL" --state open --limit 100 \
    --json number,title --jq '.[] | "\(.number)\t\(.title)"' \
    | rappels_perimes "$titre" | while read -r numero; do
        gh issue close "$numero" --repo "$DEPOT" \
            --comment "Ce rappel ne correspond plus : \`replica\` porte v$replica_version, avec $retard mineure(s) de retard."
    done

if [ "$(gh issue list --repo "$DEPOT" --label "$LABEL" --state all --limit 500 \
        --json title --jq '.[].title' | decider_rappel "$titre")" = creer ]; then
    gh label create "$LABEL" --repo "$DEPOT" --force \
        --color FBCA04 --description "Rappel : replica en retard sur la référence" >/dev/null
    corps=$(mktemp)
    cat > "$corps" <<CORPS
Les répliques sont sur **v$replica_version**, la référence sur **$derniere** : **$retard versions mineures** d'écart (les correctifs X.Y.1, X.Y.2… ne comptent pas).

Rien n'oblige à promouvoir — ce rappel n'est qu'un rappel, et le prochain ne viendra qu'à $(( tranche + PAS )) mineures. Pour promouvoir une version rodée (7 jours sur la référence) :

\`\`\`bash
gh workflow run promotion.yml -f version=X.Y.Z
\`\`\`

ou GitHub › Actions › Promotion › Run workflow. Ce rappel se ferme de lui-même quand \`replica\` avance.
CORPS
    gh issue create --repo "$DEPOT" --title "$titre" --label "$LABEL" \
        --assignee "${GITHUB_REPOSITORY_OWNER:-${GITHUB_REPOSITORY%%/*}}" --body-file "$corps"
fi
