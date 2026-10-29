#!/bin/bash
# =============================================================================
#  tag-version.sh — Poser le tag `vX.Y.Z` d'une version, et dire si les
#  images du commit reçoivent l'étiquette de version (#1753, 08/10/2026)
#
#  Lot DI-1 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
#  §4.10, D12) : chaque version bumpée sur `main` reçoit UN tag, posé par la CI,
#  sur le commit qui porte le bump — jamais à la main. Appelé par le workflow
#  `images.yml`, après chaque push sur `main`.
#
#  ## La décision (fonction PURE, testée par --selftest)
#
#  | Le tag `vX.Y.Z`…               | Verdict   | Images de ce commit étiquetées…              |
#  |--------------------------------|-----------|----------------------------------------------|
#  | n'existe pas                   | `creer`   | `sha-<commit>` ET `X.Y.Z` ; le tag est posé   |
#  | existe, sur CE commit          | `deja`    | idem (relance du même run : idempotent)       |
#  | existe, sur un AUTRE commit    | `ignorer` | `sha-<commit>` seulement : lot sans bump      |
#  | version illisible              | `erreur`  | le run échoue                                 |
#
#  « ignorer » n'est pas une erreur : un lot sans bump se déploie quand même
#  (`mep-precheck`, point 0d), et la référence en tire l'image par `sha-<commit>`
#  (arbitrage du 08/10/2026). Il n'a simplement pas de VERSION à lui : une image
#  étiquetée `2.119.1` doit être celle du commit qui a posé 2.119.1, pas son
#  successeur sans numéro.
#
#  Usage : bash scripts/ci/tag-version.sh <version>   (dans un clone aux tags lus)
#  Test  : bash scripts/ci/tag-version.sh --selftest
# =============================================================================
set -euo pipefail

# ── La décision (PURE) ────────────────────────────────────────────────────────
#  $1 version (« 2.119.1 ») · $2 commit que porte le tag (vide s'il n'existe
#  pas) · $3 commit courant
decider_tag() {
    local version="$1" commit_du_tag="$2" head="$3"
    if ! grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$' <<<"$version"; then
        echo erreur
    elif [ -z "$commit_du_tag" ]; then
        echo creer
    elif [ "$commit_du_tag" = "$head" ]; then
        echo deja
    else
        echo ignorer
    fi
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    attendu() {  # $1 libellé · $2 verdict attendu · $3… arguments
        local lib="$1" voulu="$2" got; shift 2
        got=$(decider_tag "$@")
        if [ "$got" = "$voulu" ]; then echo "PASS  $lib"; else echo "FAIL  $lib — « $got »"; fail=1; fi
    }
    echo "== self-test : tag d'une version =="
    attendu "version neuve → créer"                  creer   2.119.1 ""      abc123
    attendu "relance sur le même commit → déjà"      deja    2.119.1 abc123  abc123
    attendu "lot sans bump → ignorer (sha seul)"     ignorer 2.119.1 abc123  def456
    attendu "version illisible → erreur"             erreur  "2.119" ""      abc123
    attendu "préfixe v refusé (le tag l'ajoute)"     erreur  v2.119.1 ""     abc123
    attendu "version vide → erreur"                  erreur  ""      ""      abc123
    exit "$fail"
fi

version="${1:?usage : tag-version.sh <version>}"
tag="v$version"
head=$(git rev-parse HEAD)
commit_du_tag=$(git rev-list -n 1 "refs/tags/$tag" 2>/dev/null || true)
verdict=$(decider_tag "$version" "$commit_du_tag" "$head")

case "$verdict" in
    creer)
        git -c user.name="github-actions[bot]" \
            -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
            tag -a "$tag" -m "CoproFirst $tag" "$head"
        git push origin "refs/tags/$tag"
        echo "Tag $tag posé sur $head."
        versionner=true ;;
    deja)
        echo "Tag $tag déjà posé sur ce commit : publication relancée."
        versionner=true ;;
    ignorer)
        echo "::notice::$tag porte déjà le commit $commit_du_tag : ce lot n'a pas de bump, ses images ne sont étiquetées que par leur commit."
        versionner=false ;;
    *)
        echo "::error::version illisible dans front/package.json : « $version »"
        exit 1 ;;
esac

[ -n "${GITHUB_OUTPUT:-}" ] && echo "versionner=$versionner" >> "${GITHUB_OUTPUT:-/dev/null}"
exit 0
