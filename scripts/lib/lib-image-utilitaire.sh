#!/bin/bash
# =============================================================================
#  lib-image-utilitaire.sh — L'image des conteneurs jetables, et sa présence (#2962)
#
#  Module IMPORTÉ, jamais exécuté par un cron : pas de bit x, versionné en 100644.
#
#  L'image se DÉCLARE dans `infra/Dockerfile.utilitaire` (son seul `FROM`) : ce
#  fichier est ce que le re-tirage du dimanche et Dependabot lisent. Les scripts la
#  demandent ici, jamais en recopiant son étiquette.
#
#    image_utilitaire [fichier]   l'image, ou rien et le code 1 quand le fichier
#                                 ne se lit pas ou ne porte pas d'étiquette
#                                 explicite (absente ou `latest`) — PURE ;
#    assurer_image_utilitaire     présente sur CE nœud, tirée seulement si elle
#                                 manque (code 1 si ni l'une ni l'autre).
#
#  Autotest : bash scripts/lib/lib-image-utilitaire.sh --selftest
# =============================================================================

#  Dans le dépôt, ou à côté de ce module quand un banc l'a déposé en /tmp par scp
#  (`banc-volumes.sh`) : le premier qui existe.
_ICI_IMAGE_UTILITAIRE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DOCKERFILE_UTILITAIRE="$_ICI_IMAGE_UTILITAIRE/../../infra/Dockerfile.utilitaire"
[ -f "$DOCKERFILE_UTILITAIRE" ] || DOCKERFILE_UTILITAIRE="$_ICI_IMAGE_UTILITAIRE/Dockerfile.utilitaire"

image_utilitaire() {
    local fichier="${1:-$DOCKERFILE_UTILITAIRE}" image
    #  `sub(/\r$/…)` : un fichier passé en CRLF garderait son `\r` dans l'étiquette.
    image=$(awk '{ sub(/\r$/, "") } toupper($1) == "FROM" { print $2; exit }' "$fichier" 2>/dev/null) || return 1
    case "$image" in
        *:latest|*:) return 1 ;;
        ?*:?*) printf '%s\n' "$image" ;;
        *) return 1 ;;
    esac
}

assurer_image_utilitaire() {
    local image
    image=$(image_utilitaire) || return 1
    docker image inspect "$image" >/dev/null 2>&1 && return 0
    docker pull -q "$image" >/dev/null 2>&1
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    fail=0
    t() {  # $1 libellé · $2 attendu · $3 contenu du fichier (vide : fichier absent)
        local f rendu
        f=$(mktemp)
        if [ -n "$3" ]; then printf '%b' "$3" > "$f"; else rm -f "$f"; fi
        rendu=$(image_utilitaire "$f") || rendu="REFUS"
        rm -f "$f"
        if [ "$rendu" = "$2" ]; then echo "PASS  $1 → $rendu"
        else echo "FAIL  $1 : « $rendu » au lieu de « $2 »"; fail=1; fi
    }
    t "l'étiquette du FROM"                  "alpine:3.24" '# commentaire\nFROM alpine:3.24\n'
    t "un fichier en CRLF"                   "alpine:3.24" 'FROM alpine:3.24\r\n'
    t "sans étiquette : refusée"             "REFUS"       'FROM alpine\n'
    t "latest : refusée (flottante)"         "REFUS"       'FROM alpine:latest\n'
    t "aucun FROM : refusé"                  "REFUS"       '# rien\n'
    t "fichier absent : refusé"              "REFUS"       ''
    #  Le fichier du dépôt lui-même : une étiquette explicite.
    if image_utilitaire >/dev/null; then echo "PASS  le fichier du dépôt porte $(image_utilitaire)"
    else echo "FAIL  le fichier du dépôt ne donne aucune image"; fail=1; fi
    #  Sans image lisible, rien n'est tiré : code 1, aucune commande docker.
    if DOCKERFILE_UTILITAIRE=/nulle/part assurer_image_utilitaire 2>/dev/null; then
        echo "FAIL  une image illisible passe pour présente"; fail=1
    else echo "PASS  une image illisible n'est ni présente ni tirée"; fi
    [ "$fail" -eq 0 ] && echo "lib-image-utilitaire : tous les cas passent."
    exit "$fail"
fi
