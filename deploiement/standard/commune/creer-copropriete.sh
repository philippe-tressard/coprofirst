#!/bin/bash
# =============================================================================
#  creer-copropriete.sh — Ajouter une copropriété à une installation COMMUNE
#  (#2053, spec `specs/architecture/multi-coproprietes.md` §4.3, §4.1 bis)
#
#  Depuis le dossier de l'installation :
#
#      bash deploiement/standard/commune/creer-copropriete.sh tilleuls \
#          --code-postal 75015 --nom "Les Tilleuls" --expediteur contact@exemple.fr \
#          [--hote residence-tilleuls.fr]
#
#  ## Le déroulé — rien n'est écrit tant que tout n'est pas validé
#
#   1. l'API valide la copropriété projetée contre la déclaration EN SERVICE (alias,
#      hôtes, identifiant uniques) et rend les noms qui en dérivent — rôle, base,
#      variables, dossier (`app/installation_commune/creer.py noms`, seule écriture) ;
#   2. décider (fonction PURE `decider_nouvelle`) : variables déjà dans `.env`, rôle
#      ou base déjà là → REFUS ; jamais une réutilisation silencieuse ;
#   3. créer le rôle et la base PostgreSQL, fermée aux autres rôles (`lib-bases.sh`) ;
#   4. écrire l'URL de la base et un secret neuf dans `.env` (jamais affichés) ;
#   5. recréer l'API, qui lit ces variables ; attendre sa santé ;
#   6. l'API prépare la base, y pose les données de démarrage, crée le dossier des
#      fichiers, PUIS écrit la déclaration (`creer.py ajouter`) — relue sans
#      redémarrage, la copropriété est servie ;
#   7. vérifier la déclaration (`installation_commune.verifier`).
#
#  L'administrateur initial de la copropriété et son mot de passe temporaire sont
#  affichés à l'étape 6 (le seed) : à transmettre à son administrateur.
#
#  Test : bash deploiement/standard/commune/creer-copropriete.sh --selftest
# =============================================================================
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib-bases.sh
. "$ICI/../lib-bases.sh"

# ── PURE : que faire ? ────────────────────────────────────────────────────────
#  $1 rôle · $2 base · $3 variable de base dans .env (oui|non) · $4 variable de
#  secret dans .env (oui|non) · $5 rôle existe (oui|non) · $6 base existe (oui|non)
#  →  CREER | REFUS:<raison>
decider_nouvelle() {
    [ -n "$1" ] && [ -n "$2" ] || { echo "REFUS:noms illisibles"; return; }
    case "$1$2" in *[!a-z0-9_]*) echo "REFUS:rôle ou base hors de [a-z0-9_]"; return ;; esac
    [ "$1" != coprofirst ] && [ "$2" != coprofirst ] && [ "$2" != plateforme ] \
        || { echo "REFUS:une copropriété ne partage ni le rôle ni la base de l'installation"; return; }
    [ "$3" = non ] && [ "$4" = non ] \
        || { echo "REFUS:ses variables sont déjà dans .env — une copropriété déjà créée, ou à moitié"; return; }
    [ "$5" = non ] && [ "$6" = non ] \
        || { echo "REFUS:son rôle ou sa base existe déjà dans PostgreSQL"; return; }
    echo CREER
}

#  $1 sortie de `creer.py noms` · $2 clé → la valeur
lire_nom() { printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -1; }

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    attendu() {
        local lib="$1" voulu="$2" got; shift 2
        got=$(decider_nouvelle "$@")
        if [ "$got" = "$voulu" ]; then echo "PASS  $lib"; else echo "FAIL  $lib — « $got »"; fail=1; fi
    }
    echo "== self-test : créer une copropriété =="
    attendu "neuve → créer"                         CREER copro_t copro_t non non non non
    attendu "nom vide → refus"                      "REFUS:noms illisibles" "" copro_t non non non non
    attendu "nom hors alphabet → refus"             "REFUS:rôle ou base hors de [a-z0-9_]" "copro_t;x" copro_t non non non non
    attendu "rôle de l'installation → refus"        "REFUS:une copropriété ne partage ni le rôle ni la base de l'installation" coprofirst copro_t non non non non
    attendu "base du registre → refus"              "REFUS:une copropriété ne partage ni le rôle ni la base de l'installation" copro_t plateforme non non non non
    attendu "variable déjà dans .env → refus"       "REFUS:ses variables sont déjà dans .env — une copropriété déjà créée, ou à moitié" copro_t copro_t oui non non non
    attendu "secret déjà dans .env → refus"         "REFUS:ses variables sont déjà dans .env — une copropriété déjà créée, ou à moitié" copro_t copro_t non oui non non
    attendu "rôle existant → refus"                 "REFUS:son rôle ou sa base existe déjà dans PostgreSQL" copro_t copro_t non non oui non
    attendu "base existante → refus"                "REFUS:son rôle ou sa base existe déjà dans PostgreSQL" copro_t copro_t non non non oui
    sortie=$'ROLE=copro_t\nBASE=copro_t\nVAR_BASE=T_DATABASE_URL'
    [ "$(lire_nom "$sortie" VAR_BASE)" = T_DATABASE_URL ] && echo "PASS  lire_nom" || { echo "FAIL  lire_nom"; fail=1; }
    [ -z "$(lire_nom "$sortie" ABSENT)" ] && echo "PASS  lire_nom, clé absente" || { echo "FAIL  lire_nom, clé absente"; fail=1; }
    exit "$fail"
fi

[ -n "${1:-}" ] || { echo "usage : $0 <identifiant> --code-postal <cp> --nom <nom> --expediteur <adresse> [--hote <domaine>]"; exit 2; }
cd "$ICI/../../.."
. deploiement/standard/lib-installation.sh
DEBUT=$(date +%s)
[ -f .env ] || { journal "✗ .env introuvable : lancer depuis le dossier de l'installation."; exit 1; }
[ -n "$(lire_env COPROPRIETES_FICHIER)" ] || { journal "✗ COPROPRIETES_FICHIER absent de .env : ce n'est pas une installation commune."; exit 1; }

COMPOSE=(docker compose -f docker-compose.yml -f deploiement/standard/compose.images.yml
         -f deploiement/standard/commune/compose.commune.yml)
psql_installation() { "${COMPOSE[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U coprofirst -d coprofirst "$@"; }
pgq() { psql_installation -Atc "$1" 2>/dev/null; }

# ── 1. Valider et nommer ──────────────────────────────────────────────────────
NOMS=$("${COMPOSE[@]}" exec -T -u app api python -m app.installation_commune.creer noms "$@") \
    || { journal "✗ $NOMS"; exit 1; }
ROLE=$(lire_nom "$NOMS" ROLE); BASE=$(lire_nom "$NOMS" BASE)
VAR_BASE=$(lire_nom "$NOMS" VAR_BASE); VAR_SECRET=$(lire_nom "$NOMS" VAR_SECRET)
journal "Copropriété projetée : $(lire_nom "$NOMS" ALIAS) → $(lire_nom "$NOMS" ADRESSE)"

# ── 2. Décider ────────────────────────────────────────────────────────────────
dans_env() { grep -q "^$1=" .env && echo oui || echo non; }
read -r ROLE_LA BASE_LA <<< "$(base_existants pgq "$ROLE" "$BASE")"
DECISION=$(decider_nouvelle "$ROLE" "$BASE" "$(dans_env "$VAR_BASE")" "$(dans_env "$VAR_SECRET")" "$ROLE_LA" "$BASE_LA")
[ "$DECISION" = CREER ] || { journal "✗ ${DECISION#REFUS:} — rien n'est fait."; exit 1; }

# ── 3–4. La base, le rôle, les secrets ────────────────────────────────────────
MDP=$(openssl rand -hex 32); SECRET=$(openssl rand -hex 32)
RAISON=$(base_creer psql_installation "$ROLE" "$BASE" "$MDP" non non) \
    || { journal "✗ PostgreSQL : $RAISON — .env et déclaration inchangés."; exit 1; }
journal "Rôle et base $BASE créés, fermés aux autres rôles."
umask 077
{
    printf '\n# Copropriété %s (creer-copropriete.sh, %s)\n' "$1" "$(date '+%F')"
    printf '%s=postgresql+psycopg://%s:%s@postgres:5432/%s\n' "$VAR_BASE" "$ROLE" "$MDP" "$BASE"
    printf '%s=%s\n' "$VAR_SECRET" "$SECRET"
} >> .env
unset MDP SECRET

# ── 5. L'API lit les nouvelles variables ──────────────────────────────────────
"${COMPOSE[@]}" up -d api >/dev/null
[ "$(sante)" = ok ] || { journal "✗ L'API ne répond pas après sa recréation : déclaration NON écrite. Lire : docker compose logs api"; exit 1; }

# ── 6–7. Préparer, semer, déclarer, vérifier ──────────────────────────────────
"${COMPOSE[@]}" exec -T -u app api python -m app.installation_commune.creer ajouter "$@" \
    || { journal "✗ Copropriété non déclarée (base créée, variables dans .env) : corriger puis relancer « creer.py ajouter »."; exit 1; }
"${COMPOSE[@]}" exec -T -u app api python -m app.installation_commune.verifier
journal "Copropriété $1 créée en $(( $(date +%s) - DEBUT )) s."
