#!/bin/bash
# =============================================================================
#  lib-installation.sh — Les gestes communs des scripts d'une INSTALLATION
#  CoproFirst : lire `.env`, journaliser, sonder la santé, rendre compte.
#
#  Sourcée par `mise-a-jour.sh` (la mise à jour nocturne d'une réplique, #1756)
#  et par `deploiement/demo/reinitialiser.sh` (la remise à zéro nocturne de la
#  démo publique, #1905). Elle les avait en ligne dans le premier ; le second
#  en aurait été la copie (rang 1 : factorisation).
#
#  ⚠️ Elle part dans l'ARCHIVE de déploiement (`scripts/ci/lib-archive-deploiement.sh`) :
#  une réplique n'emporte pas `scripts/lib`. Rien ici ne lit autre chose que le
#  dossier de l'installation, où les scripts se placent (`cd`) avant de la sourcer.
#
#  Attend du script qui la source : être dans le dossier de l'installation, et
#  `DEBUT` (date +%s du lancement) pour la durée rendue.
# =============================================================================

SANTE_MAX_S=${SANTE_MAX_S:-180}

journal() { echo "$(date '+%F %T') $*"; }

lire_env() { sed -n "s/^$1=//p" .env 2>/dev/null | tail -1 | tr -d '"'"'"'\r'; }

#  Le moteur que `.env` désigne, par l'URL de sa base → sqlite|postgresql|inconnu.
#  🔒 COPIE DÉCLARÉE de `scripts/lib/lib-replication.sh` : l'archive d'une
#  réplique n'emporte pas les scripts des RPi (#1755). `test_deploiement_standard`
#  exige que les deux corps restent identiques.
moteur_de_url() {
    case "${1:-}" in
        sqlite:*)                   echo sqlite ;;
        postgresql:*|postgresql+*)  echo postgresql ;;
        *)                          echo inconnu ;;
    esac
}

sante() {  # → ok | ko, en sondant jusqu'à SANTE_MAX_S
    local fin=$(( $(date +%s) + SANTE_MAX_S ))
    while [ "$(date +%s)" -lt "$fin" ]; do
        [ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' http://localhost/api/health || true)" = 200 ] && { echo ok; return; }
        sleep 5
    done
    echo ko
}

#  $1 tâche (`TachePlanifiee`) · $2 statut (succes|erreur) · $3 erreur (vide si
#  succès) · $4 détails, objet JSON déjà formé (`{}` à défaut)
rendre_compte_tache() {
    local cle erreur message corps details="${4:-}"
    [ -n "$details" ] || details='{}'
    cle=$(lire_env MAINTENANCE_KEY)
    [ -n "$cle" ] || { journal "(MAINTENANCE_KEY absente : rien rendu à l'administration)"; return 0; }
    #  Le message ne porte que des versions et des chemins : on retire les
    #  guillemets plutôt que d'échapper du JSON à la main. En deux temps : un
    #  guillemet dans une substitution elle-même entre guillemets égare
    #  `verifier-variables-shell.py`, qui perdait alors la suite du script.
    erreur=null
    if [ -n "$3" ]; then
        message=$(printf '%s' "$3" | tr -d '"\\')
        erreur="\"$message\""
    fi
    corps=$(printf '{"tache":"%s","statut":"%s","erreur":%s,"duree_secondes":%d,"details":%s}' \
        "$1" "$2" "$erreur" "$(( $(date +%s) - DEBUT ))" "$details")
    curl -fsS -m 20 -o /dev/null -X POST http://localhost/api/admin/maintenance/rapport \
        -H "x-maintenance-key: $cle" -H "Content-Type: application/json" -d "$corps" \
        || journal "⚠ Rapport non transmis à l'administration."
}
