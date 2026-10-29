#!/bin/bash
# =============================================================================
#  lib-replica.sh — Ce que la promotion lit de `replica`
#  (#1934, 14/10/2026). Sourcé par `promotion.sh`.
# =============================================================================

#  $1 commit → la version X.Y.Z dont il porte le tag (vide : aucun tag de version)
version_du_commit() {
    git tag --points-at "$1" -l 'v[0-9]*' | head -n 1 | sed 's/^v//'
}
