#!/bin/bash
# =============================================================================
#  lib-plateforme.sh — la base `plateforme` du registre : ses DÉCISIONS et ses
#  GESTES de création (module à sourcer, #1877, #1972)
#
#  POURQUOI ce module existe (15/10/2026, #1972) : la base du registre se crée à
#  DEUX moments — à l'allumage du registre (`creer-base-plateforme.sh`) et quand
#  la référence renaît de la copie hors site (`restaurer-copie-hors-site.sh`, et
#  son banc). Le second ne peut pas appeler le premier : celui-ci redémarre l'API,
#  qui inscrit aussitôt la référence — et la base n'est plus neuve pour l'import.
#  Les gestes vivent donc ici, une fois : la règle de nommage, la lecture de
#  l'URL, la création du rôle et de la base fermée aux autres.
#
#  Éprouvé par les self-tests de ses deux appelants (même raison que
#  `lib-export-hors-site.sh` : un self-test vide ici rendrait 0 sans rien mesurer).
# =============================================================================

# ── PURE : que faire ? ────────────────────────────────────────────────────────
#  $1 actif (oui|non) · $2 PostgreSQL primaire (oui|non) · $3 utilisateur de l'URL
#  · $4 base de l'URL · $5 mot de passe présent (oui|non) · $6 rôle existe (oui|non)
#  · $7 base existe (oui|non)  →  CREER | DEJA_FAIT | REFUS:<raison>
decider_creation() {
    [ "$1" = oui ] || { echo "REFUS:ce nœud n'est pas l'actif"; return; }
    [ "$2" = oui ] || { echo "REFUS:le PostgreSQL de ce nœud n'est pas le primaire"; return; }
    [ -n "$3" ] && [ -n "$4" ] || { echo "REFUS:PLATEFORME_DATABASE_URL absente ou illisible dans .env"; return; }
    case "$3$4" in *[!a-z0-9_]*) echo "REFUS:utilisateur ou base hors de [a-z0-9_]"; return ;; esac
    [ "$3" != coprofirst ] && [ "$4" != coprofirst ] \
        || { echo "REFUS:la plateforme ne partage ni le rôle ni la base de la résidence"; return; }
    [ "$5" = oui ] || { echo "REFUS:mot de passe absent de PLATEFORME_DATABASE_URL"; return; }
    [ "$6" = oui ] && [ "$7" = oui ] && { echo DEJA_FAIT; return; }
    echo CREER
}

# ── PURE : la copie hors site emporte-t-elle le registre ? (#1972) ────────────
#  $1 le `.env` déclare le registre (oui|non) · $2 une archive du registre est
#  fournie (oui|non)  →  AVEC | SANS | REFUS:<raison>
#  🔴 Registre déclaré SANS son archive : refus. L'API démarrerait, migrerait une
#  base vide et y inscrirait la seule référence — le registre renaîtrait VIDE, en
#  silence, et les installations inscrites seraient perdues.
decider_registre() {
    case "$1$2" in
        ouioui)   echo AVEC ;;
        nonnon)   echo SANS ;;
        ouinon)   echo "REFUS:le .env déclare le registre (PLATEFORME_DATABASE_URL) : fournir son archive par --registre, sinon il renaîtrait vide" ;;
        nonoui)   echo "REFUS:archive du registre fournie, mais PLATEFORME_DATABASE_URL est absente du .env" ;;
        *)        echo "REFUS:arguments non compris" ;;
    esac
}

# ── Les gestes communs à toute base d'une installation — lire une URL, savoir si
#  le rôle et la base existent, les créer fermés aux autres — vivent dans
#  `deploiement/standard/lib-bases.sh` depuis #2053 : une installation commune crée
#  ainsi la base de chaque copropriété (`commune/creer-copropriete.sh`).
# shellcheck source=../../deploiement/standard/lib-bases.sh
source "$(dirname "${BASH_SOURCE[0]}")/../../deploiement/standard/lib-bases.sh"

# ── psql sur le PostgreSQL de la PRODUCTION (en root, sur le nœud qui sert) ───
plateforme_psql_ref() { docker exec -i hostachy_postgres psql -v ON_ERROR_STOP=1 -U coprofirst -d coprofirst "$@"; }
