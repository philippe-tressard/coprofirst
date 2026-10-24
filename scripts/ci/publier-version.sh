#!/bin/bash
# =============================================================================
#  publier-version.sh — PUBLIER une version taguée : sa release, ses notes et
#  l'archive du déploiement standard (#2210, 24/10/2026)
#
#  Une installation suit le canal Urgence — la dernière version publiée de `main` —
#  ou une version choisie ; la référence ne propose que les versions qui ont leur
#  release, puisque la mise à jour nocturne y télécharge l'archive de déploiement
#  (`deploiement/standard/mise-a-jour.sh`). Chaque version taguée est donc publiée,
#  et plus seulement les versions promues sur `replica`.
#
#  Appelé par le workflow « Images », une fois les images de la version publiées ;
#  à la main pour une version déjà taguée (rattrapage) :
#      VERSION=X.Y.Z GH_TOKEN=… bash scripts/ci/publier-version.sh
#
#  Les notes comparent la version au tag de version qui la précède
#  (`notes-de-version.sh`, qui ne réécrit jamais une release déjà publiée).
#
#  Test : bash scripts/ci/publier-version.sh --selftest
# =============================================================================
set -euo pipefail

# ── Le tag qui précède (PUR sur un dépôt git) ─────────────────────────────────
#  $1 commit de la version → le tag de version qui le précède, vide s'il n'y en a pas
tag_precedent() {
    git describe --tags --abbrev=0 --match 'v[0-9]*.[0-9]*.[0-9]*' "$1^" 2>/dev/null || true
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    DEPOT=$(mktemp -d)
    (
        cd "$DEPOT" && git init -q && git config user.name t && git config user.email t@example.org
        git commit -q --allow-empty -m un && git tag -a v1.0.0 -m v1
        git commit -q --allow-empty -m deux && git tag -a essai -m essai
        git commit -q --allow-empty -m trois && git tag -a v1.1.0 -m v11
    )
    attendu() {  # $1 libellé · $2 attendu · $3 tag dont on cherche le précédent
        local got; got=$(cd "$DEPOT" && tag_precedent "$(git rev-list -n 1 "$3")")
        if [ "$got" = "$2" ]; then echo "PASS  $1"; else echo "FAIL  $1 — « $got »"; fail=1; fi
    }
    echo "== self-test : le tag de version qui précède =="
    attendu "v1.1.0 → v1.0.0 (un tag qui n'est pas une version est sauté)" v1.0.0 v1.1.0
    attendu "la première version n'a pas de précédent"                     ""     v1.0.0
    rm -rf "$DEPOT"
    exit "$fail"
fi

VERSION="${VERSION:?VERSION manquante (X.Y.Z)}"
if ! printf '%s' "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "::error::version illisible : « $VERSION »"; exit 1
fi
COMMIT=$(git rev-list -n 1 "refs/tags/v$VERSION" 2>/dev/null) \
    || { echo "::error::tag v$VERSION absent"; exit 1; }
PRECEDENT=$(tag_precedent "$COMMIT")
export VERSION COMMIT PRECEDENT
bash "$(dirname "${BASH_SOURCE[0]}")/notes-de-version.sh"
