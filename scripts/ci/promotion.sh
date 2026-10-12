#!/bin/bash
# =============================================================================
#  promotion.sh — Promouvoir une version de `main` sur la branche `replica`
#  (#1754, 08/10/2026)
#
#  Lot DI-2 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
#  §4.10, règles 1 et 5, D11). Les répliques CoproFirst suivent `replica` ;
#  la référence suit `main`. Une version passe de l'un à l'autre par ce geste,
#  décidé par l'auteur et lancé à la main (workflow « Promotion »).
#
#  ## Ce que le geste refuse (fonction PURE, testée par --selftest)
#
#  | Situation                                         | Verdict                 |
#  |---------------------------------------------------|-------------------------|
#  | version illisible                                 | `refus-version`         |
#  | aucun tag `vX.Y.Z`                                | `refus-sans-tag`        |
#  | le tag n'est pas sur `main`                       | `refus-hors-main`       |
#  | `replica` n'existe pas encore                     | `creer`                 |
#  | `replica` porte déjà ce commit                    | `deja`                  |
#  | le tag ne descend pas de `replica` (retour arrière, branche parallèle) | `refus-pas-en-avant` |
#  | sinon                                             | `avancer`               |
#
#  🔴 `replica` est un POINTEUR, jamais une branche de travail : elle n'avance
#  qu'en avance rapide, vers un tag de `main`, et ne porte aucun commit propre.
#  Un correctif urgent passe par `main`, reçoit sa version, puis se promeut.
#  Le jour où un commit naîtrait sur `replica`, il y aurait deux produits.
#
#  ## Ce que le geste AFFICHE, sans décider
#
#  Les critères de la spec — CI verte, version servie par la référence depuis N
#  jours sans incident, post-check vert — sont ceux de l'auteur : le geste en
#  montre les faits mesurables (âge du tag, état des contrôles du commit,
#  images publiées), et c'est l'auteur qui a décidé en le lançant. La durée de
#  rodage N reste une question ouverte (spec §9, question 8).
#
#  Usage : VERSION=X.Y.Z bash scripts/ci/promotion.sh   (clone aux tags lus)
#  Test  : bash scripts/ci/promotion.sh --selftest
# =============================================================================
set -euo pipefail

# ── La décision (PURE) ────────────────────────────────────────────────────────
#  $1 version · $2 commit du tag (vide : pas de tag) · $3 tag sur main (1 | 0)
#  · $4 commit de replica (vide : pas de branche) · $5 replica ancêtre du tag (1 | 0)
decider_promotion() {
    local version="$1" commit="$2" sur_main="$3" replica="$4" en_avant="$5"
    if ! printf '%s' "$version" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then echo refus-version; return; fi
    if [ -z "$commit" ]; then echo refus-sans-tag; return; fi
    if [ "$sur_main" != 1 ]; then echo refus-hors-main; return; fi
    if [ -z "$replica" ]; then echo creer; return; fi
    if [ "$replica" = "$commit" ]; then echo deja; return; fi
    if [ "$en_avant" != 1 ]; then echo refus-pas-en-avant; return; fi
    echo avancer
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    attendu() {  # $1 libellé · $2 verdict attendu · $3… arguments
        local lib="$1" voulu="$2" got; shift 2
        got=$(decider_promotion "$@")
        if [ "$got" = "$voulu" ]; then echo "PASS  $lib"; else echo "FAIL  $lib — « $got »"; fail=1; fi
    }
    echo "== self-test : promotion vers replica =="
    attendu "première promotion → créer replica"         creer               2.120.0 c2 1 ""  0
    attendu "version suivante → avancer"                  avancer             2.121.0 c3 1 c2  1
    attendu "même version, relancée → déjà"               deja                2.121.0 c3 1 c3  1
    attendu "version ANTÉRIEURE → refus (pas de retour)"  refus-pas-en-avant  2.119.0 c1 1 c3  0
    attendu "tag hors de main → refus"                    refus-hors-main     2.121.0 c9 0 c3  1
    attendu "aucun tag → refus"                           refus-sans-tag      2.121.0 ""  1 c3 1
    attendu "version illisible → refus"                   refus-version       "v2.1"  c3 1 c3  1
    attendu "injection dans la version → refus"           refus-version       '1.2.3;rm' c3 1 c3 1
    exit "$fail"
fi

version="${VERSION:-}"
tag="v$version"
git fetch --quiet origin main 2>/dev/null || true
commit=$(git rev-list -n 1 "refs/tags/$tag" 2>/dev/null || true)
sur_main=0
[ -n "$commit" ] && git merge-base --is-ancestor "$commit" origin/main 2>/dev/null && sur_main=1
replica=$(git rev-parse --verify --quiet origin/replica 2>/dev/null || true)
en_avant=0
[ -n "$commit" ] && [ -n "$replica" ] && git merge-base --is-ancestor "$replica" "$commit" 2>/dev/null && en_avant=1
verdict=$(decider_promotion "$version" "$commit" "$sur_main" "$replica" "$en_avant")

# ── Les faits, affichés pour l'auteur ─────────────────────────────────────────
resume="${GITHUB_STEP_SUMMARY:-/dev/null}"
{
    echo "## Promotion de $tag sur \`replica\`"
    echo
    echo "| Fait | Valeur |"
    echo "|---|---|"
    echo "| Verdict | \`$verdict\` |"
    echo "| Commit du tag | \`${commit:-absent}\` |"
    echo "| \`replica\` avant | \`${replica:-absente}\` |"
    if [ -n "$commit" ]; then
        jours=$(( ( $(date +%s) - $(git log -1 --format=%ct "$commit") ) / 86400 ))
        echo "| Rodage sur la référence | $jours jour(s) depuis la fusion — durée attendue : question 8 de la spec |"
        if [ -n "${GH_TOKEN:-}" ] && [ -n "${GITHUB_REPOSITORY:-}" ]; then
            ci=$(gh api "repos/${GITHUB_REPOSITORY:-}/commits/$commit/check-runs" \
                --jq '[.check_runs[].conclusion] | group_by(.) | map("\(.[0] // "en cours") : \(length)") | join(", ")' 2>/dev/null || echo "illisible")
            echo "| Contrôles du commit | ${ci:-aucun} |"
        fi
    fi
} | tee -a "$resume"

case "$verdict" in
    creer|avancer)
        #  Avance rapide par construction : le verdict l'a vérifié. Un push
        #  sans `--force` le revérifie côté serveur, et la règle de la branche
        #  refuse tout le reste.
        git push origin "$commit:refs/heads/replica"
        echo "✓ replica → $tag ($commit)" | tee -a "$resume" ;;
    deja)
        echo "✓ replica porte déjà $tag : rien à faire." | tee -a "$resume" ;;
    *)
        echo "::error::promotion refusée : $verdict"
        exit 1 ;;
esac
[ -n "${GITHUB_OUTPUT:-}" ] && {
    echo "commit=$commit"
    echo "precedent=$replica"
    echo "verdict=$verdict"
} >> "${GITHUB_OUTPUT:-/dev/null}"
exit 0
