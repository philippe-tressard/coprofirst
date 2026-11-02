#!/bin/bash
# =============================================================================
#  lib-contrat-version.sh — Le CONTRAT D'API d'une version, joint à sa release
#  (#2456) : ce qu'il emporte, et comment il se fabrique (module à sourcer)
#
#  L'app iOS (`philippe-tressard/coprofirst-ios`) génère son client depuis ces
#  fichiers, jamais d'une copie à la main :
#    · openapi.json       — le schéma de l'API, exporté DE L'IMAGE PUBLIÉE de la
#                           version, sans réseau (`docker run --network none`) :
#                           c'est le contrat de ce qui est servi ;
#    · pages.ts           — les onglets du site, sa parité d'écrans ;
#    · socle.css, palette-sombre.css — les jetons de couleur et de taille, que
#                           l'app génère au lieu de les recopier.
#  `/api/openapi.json` reste fermé en production (`ENABLE_API_DOCS=false`) : le
#  schéma part ici, jamais sur le site.
#
#  Lecteur : `publier-version.sh`. Test : bash scripts/ci/lib-contrat-version.sh --selftest
# =============================================================================

# ── Ce que la release emporte, en plus du schéma ──────────────────────────────
FICHIERS_CONTRAT=(
    front/src/lib/pages.ts
    front/src/styles/socle.css
    front/src/styles/palette-sombre.css
)

#: La référence du contrat : elle porte la version que le schéma doit annoncer.
REFERENCE_CONTRAT=api/app/contrat/reference.json

#  $1 image · $2 dossier qui porte exporter_openapi.py · $3 dossier de sortie (inscriptible)
#  Le geste qui touche docker — l'autotest le remplace.
exporter_dans_image() {
    docker run --rm --network none --platform linux/amd64 -u app \
        -v "$2:/ci:ro" -v "$3:/sortie" "$1" \
        python /ci/exporter_openapi.py --api /app --sortie /sortie/openapi.json
}

#  $1 commit · $2 image de l'API de ce commit · $3 dossier de sortie
#  → les fichiers du contrat dans $3 ; échoue si l'un manque, ou si le schéma
#  exporté n'annonce pas la version de la référence du commit.
preparer_contrat() {
    local commit="$1" image="$2" sortie="$3" f outils schema attendu
    if ! git cat-file -e "$commit:$REFERENCE_CONTRAT" 2>/dev/null; then
        echo "Contrat d'API : aucun avant #2456 à ce commit — rien à joindre."
        return 0
    fi
    for f in "${FICHIERS_CONTRAT[@]}"; do
        git show "$commit:$f" > "$sortie/$(basename "$f")" \
            || { echo "::error::$f absent de $commit" >&2; return 1; }
    done
    #  L'exportateur DU COMMIT, pas celui du dépôt courant (rattrapage d'une version).
    outils=$(mktemp -d)
    git show "$commit:scripts/ci/exporter_openapi.py" > "$outils/exporter_openapi.py" || return 1
    schema=$(mktemp -d) && chmod 0777 "$schema"   # l'image écrit sous `app`
    exporter_dans_image "$image" "$outils" "$schema" \
        || { echo "::error::export du schéma depuis $image impossible" >&2; return 1; }
    attendu=$(git show "$commit:$REFERENCE_CONTRAT" | jq -r .version)
    if ! jq -e --arg v "$attendu" \
        '.info.version == $v and .servers[0].url == "/api" and (.paths | length) > 0' \
        "$schema/openapi.json" >/dev/null 2>&1; then
        echo "::error::le schéma exporté n'est pas le contrat $attendu du commit $commit" >&2
        return 1
    fi
    cp "$schema/openapi.json" "$sortie/openapi.json"
    echo "Contrat d'API $attendu : openapi.json et ${#FICHIERS_CONTRAT[@]} fichiers joints."
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    set -euo pipefail
    fail=0
    DEPOT=$(mktemp -d)
    (
        cd "$DEPOT" && git init -q && git config user.name t && git config user.email t@example.org
        git commit -q --allow-empty -m avant
        mkdir -p front/src/lib front/src/styles api/app/contrat scripts/ci
        for f in "${FICHIERS_CONTRAT[@]}"; do echo "// $f" > "$f"; done
        echo '{"version": "1.2.0"}' > "$REFERENCE_CONTRAT"
        echo 'exportateur' > scripts/ci/exporter_openapi.py
        git add -A && git commit -q -m contrat
        git rm -q front/src/styles/socle.css && git commit -q -m incomplet
    )
    commit() { (cd "$DEPOT" && git rev-parse "HEAD~$1"); }
    #  L'image simulée : elle écrit le schéma qu'on lui demande d'écrire.
    SCHEMA_SIMULE='{"info": {"version": "1.2.0"}, "servers": [{"url": "/api"}], "paths": {"/x": {}}}'
    exporter_dans_image() { echo "$SCHEMA_SIMULE" > "$3/openapi.json"; }
    essai() {  # $1 libellé · $2 attendu (ok|refus) · $3 commit
        local s; s=$(mktemp -d)
        if (cd "$DEPOT" && preparer_contrat "$3" image "$s") >/dev/null 2>&1; then r=ok; else r=refus; fi
        n=$(find "$s" -type f | wc -l | tr -d ' ')
        if [ "$r" = "$2" ]; then echo "PASS  $1 ($n fichier(s))"; else echo "FAIL  $1 — $r"; fail=1; fi
        rm -rf "$s"
    }
    echo "== self-test : le contrat d'API joint à une version =="
    essai "contrat complet : quatre fichiers"                 ok    "$(commit 1)"
    essai "un fichier manque au commit : refusé"              refus "$(commit 0)"
    essai "commit d'avant le contrat : rien à joindre"        ok    "$(commit 2)"
    SCHEMA_SIMULE='{"info": {"version": "1.1.0"}, "servers": [{"url": "/api"}], "paths": {"/x": {}}}'
    essai "schéma d'une autre version que la référence : refusé" refus "$(commit 1)"
    SCHEMA_SIMULE='{"info": {"version": "1.2.0"}, "paths": {"/x": {}}}'
    essai "schéma sans le préfixe servi : refusé"             refus "$(commit 1)"
    exporter_dans_image() { return 1; }
    essai "l'image ne s'exécute pas : refusé"                 refus "$(commit 1)"
    s=$(mktemp -d); exporter_dans_image() { echo "$SCHEMA_SIMULE" > "$3/openapi.json"; }
    SCHEMA_SIMULE='{"info": {"version": "1.2.0"}, "servers": [{"url": "/api"}], "paths": {"/x": {}}}'
    (cd "$DEPOT" && preparer_contrat "$(commit 1)" image "$s") >/dev/null
    if [ "$(cd "$s" && ls | sort | tr '\n' ' ')" = "openapi.json pages.ts palette-sombre.css socle.css " ]; then
        echo "PASS  les noms joints : openapi.json pages.ts palette-sombre.css socle.css"
    else echo "FAIL  noms joints : $(ls "$s")"; fail=1; fi
    rm -rf "$DEPOT" "$s"
    exit "$fail"
fi
