#!/bin/bash
# =============================================================================
#  notes-de-version.sh — Les notes d'une version publiée, pour les exploitants
#  des répliques (#1754, 08/10/2026 ; chaque version taguée depuis #2210)
#
#  Appelé par `publier-version.sh` (workflow « Images », chaque version taguée)
#  et par le workflow « Promotion », après l'avance de `replica`. Publie une
#  release GitHub sur le tag `vX.Y.Z`, qui dit ce qu'un exploitant doit savoir
#  AVANT la mise à jour nocturne de son installation :
#  - les lots livrés depuis la version précédente (titres des fusions) ;
#  - les migrations de base ajoutées ;
#  - les réglages ajoutés ou retirés dans `.env.example`.
#
#  Elle joint l'archive du DÉPLOIEMENT STANDARD de la version (#1755) :
#  `coprofirst-deploiement-X.Y.Z.tar.gz`, tirée du commit promu par
#  `git archive` — les fichiers exacts de cette version, rien du poste.
#
#  Entrées (environnement) : VERSION, COMMIT, PRECEDENT (vide pour la première
#  version), MODE (`urgence`, `automatique` ou vide, #1934), GH_TOKEN. Une release déjà publiée n'est pas réécrite.
#
#  Test : bash scripts/ci/notes-de-version.sh --selftest
# =============================================================================
set -euo pipefail

# ── L'archive du déploiement standard : `lib-archive-deploiement.sh` ─────────
#  (la liste de ses fichiers et sa fabrication), partagée avec l'essai de la
#  mise à jour nocturne (`essai-mise-a-jour.sh`).
source "$(dirname "${BASH_SOURCE[0]}")/lib-archive-deploiement.sh"

# ── La composition (PURE sur un dépôt git) ────────────────────────────────────
#  $1 précédent (vide : première promotion) · $2 commit promu · $3 version
#  · $4 mode de la promotion (`urgence`, `automatique` ou vide)
composer_notes() {
    local precedent="$1" commit="$2" version="$3" mode="${4:-}" plage migrations reglages
    echo "# CoproFirst $version"
    echo
    case "$mode" in
        urgence)     echo "> ⚡ **Correctif urgent** : promue sans les 7 jours de rodage sur la référence."; echo ;;
        automatique) echo "> Version majeure promue automatiquement après 7 jours de rodage sur la référence."; echo ;;
    esac
    if [ -z "$precedent" ]; then
        echo "Première version publiée."
        return
    fi
    plage="$precedent..$commit"
    echo "## Ce qui change depuis la version précédente"
    echo
    git log --format='- %s' "$plage"
    echo
    migrations=$(git diff --name-only --diff-filter=A "$plage" -- api/alembic/versions | sed 's|.*/|- |')
    echo "## Migrations de base"
    echo
    echo "${migrations:-Aucune.}"
    echo
    reglages=$(git diff "$plage" -- .env.example | grep -E '^[+-][A-Z_]+=' | sed -E -e 's/^[+](.*)/- ajouté : \1/' -e t -e 's/^-(.*)/- retiré : \1/' || true)
    echo "## Réglages (\`.env.example\`)"
    echo
    echo "${reglages:-Aucun changement.}"
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    DEPOT=$(mktemp -d)
    (
        cd "$DEPOT" && git init -q && git config user.name t && git config user.email t@example.org
        mkdir -p api/alembic/versions && printf 'A=1\nC=3\n' > .env.example && git add -A && git commit -qm "v1 — départ"
        echo x > api/alembic/versions/0272_neuve.py && printf 'A=1\nB=2\n' > .env.example
        git add -A && git commit -qm "v2 — ajoute B"
    )
    p=$(git -C "$DEPOT" rev-parse HEAD~1); c=$(git -C "$DEPOT" rev-parse HEAD)
    notes=$(cd "$DEPOT" && composer_notes "$p" "$c" 2.0.0)
    for attendu in "# CoproFirst 2.0.0" "- v2 — ajoute B" "- 0272_neuve.py" "- ajouté : B=2" "- retiré : C=3"; do
        if printf '%s\n' "$notes" | grep -qxF -- "$attendu"; then echo "PASS  « $attendu »"
        else echo "FAIL  « $attendu » absent"; fail=1; fi
    done
    if printf '%s\n' "$notes" | grep -q "v1 — départ"; then echo "FAIL  la version précédente est recopiée"; fail=1
    else echo "PASS  la version précédente n'est pas recopiée"; fi
    #  L'archive : un fichier manquant au commit fait échouer `git archive`.
    (cd "$DEPOT" && for f in "${FICHIERS_DEPLOIEMENT[@]}"; do mkdir -p "$(dirname "$f")"; echo x > "$f"; done
        git add -A && git commit -qm "v3 — déploiement")
    c3=$(git -C "$DEPOT" rev-parse HEAD)
    SORTIE=$(mktemp -d)
    archive=$(cd "$DEPOT" && archiver_deploiement "$c3" 3.0.0 "$SORTIE")
    n=$(tar -tzf "$archive" | grep -cv '/$' || true)
    if [ "$n" -eq "${#FICHIERS_DEPLOIEMENT[@]}" ]; then echo "PASS  archive : $n fichiers, préfixe coprofirst-3.0.0/"
    else echo "FAIL  archive : $n fichier(s) pour ${#FICHIERS_DEPLOIEMENT[@]}"; fail=1; fi
    if (cd "$DEPOT" && archiver_deploiement "$c" 2.0.0 "$SORTIE") >/dev/null 2>&1; then
        echo "FAIL  archive d'un commit où il manque des fichiers : acceptée"; fail=1
    else echo "PASS  archive d'un commit incomplet : refusée"; fi
    rm -rf "$SORTIE"
    urgente=$(cd "$DEPOT" && composer_notes "$p" "$c" 2.0.1 urgence)
    if printf '%s' "$urgente" | grep -q "Correctif urgent"; then echo "PASS  l'urgence est dite"
    else echo "FAIL  l'urgence n'est pas dite"; fail=1; fi
    if printf '%s' "$notes" | grep -q "Correctif urgent\|automatiquement"; then echo "FAIL  une promotion manuelle se dit urgente"; fail=1
    else echo "PASS  une promotion manuelle ne dit rien de plus"; fi
    premiere=$(cd "$DEPOT" && composer_notes "" "$c" 1.0.0)
    if printf '%s' "$premiere" | grep -q "Première version publiée"; then echo "PASS  première promotion"
    else echo "FAIL  première promotion : « $premiere »"; fail=1; fi
    rm -rf "$DEPOT"
    exit "$fail"
fi

VERSION="${VERSION:?VERSION manquante}"
COMMIT="${COMMIT:?COMMIT manquant}"
if gh release view "v$VERSION" >/dev/null 2>&1; then
    echo "Release v$VERSION déjà publiée : laissée telle quelle."
    exit 0
fi
notes=$(mktemp)
composer_notes "${PRECEDENT:-}" "$COMMIT" "$VERSION" "${MODE:-}" > "$notes"
archive=$(archiver_deploiement "$COMMIT" "$VERSION" "$(mktemp -d)")
gh release create "v$VERSION" --verify-tag --title "CoproFirst $VERSION" --notes-file "$notes" "$archive"
