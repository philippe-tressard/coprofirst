#!/bin/bash
# =============================================================================
#  essai-mise-a-jour.sh — La mise à jour nocturne d'une réplique, éprouvée de
#  bout en bout sur une machine JETABLE (DI-4 sous PostgreSQL, #1756)
#
#  Lancé par le workflow « Essai de mise à jour » (`essai-mise-a-jour.yml`), sur
#  un runner GitHub : jamais sur les RPi, dont les noms de conteneurs sont ceux
#  de la production. Rien n'est promu, `replica` n'est pas lue.
#
#    bash scripts/ci/essai-mise-a-jour.sh <de X.Y.Z> <vers X.Y.Z>
#
#  Le déroulé, celui d'un exploitant :
#    1. l'archive de déploiement des DEUX versions, tirée de leurs tags
#       (`lib-archive-deploiement.sh`, la fabrication de la release) ;
#    2. l'installation de <de> selon le mode d'emploi, sa base PostgreSQL ;
#    3. un témoin : le compte administrateur initial, qui se connecte ;
#    4. `mise-a-jour.sh` de l'INSTALLATION (celui de <de>), cible imposée par
#       `COPROFIRST_ESSAI_CIBLE` et archive par `COPROFIRST_ESSAI_ARCHIVE` ;
#    5. le verdict (fonction PURE `verdict_essai`) : journal « réussie », version
#       posée dans `.env` ET servie par le site, sauvegarde des volumes et
#       export de la base présents, et le témoin qui se connecte toujours.
#
#  ⚠️ <de> doit porter cet outillage (archive avec `postgresql/pg_hba.conf`,
#  commande `verifier`) : la première version qui le permet est celle de ce lot.
#
#  Test : bash scripts/ci/essai-mise-a-jour.sh --selftest
# =============================================================================
set -euo pipefail

# ── PURE : l'essai a-t-il réussi ? ────────────────────────────────────────────
#  $1 « réussie » au journal (oui|non) · $2 version de .env · $3 version
#  servie · $4 version attendue · $5 archive des volumes (oui|non) · $6 export
#  de la base (oui|non) · $7 le témoin se connecte (oui|non)
#  → OK | ECHEC:<raisons>
verdict_essai() {
    local fautes=()
    [ "$1" = oui ] || fautes+=("le journal ne dit pas « Mise à jour réussie »")
    [ "$2" = "$4" ] || fautes+=(".env porte ${2:-rien}, attendu $4")
    [ "$3" = "$4" ] || fautes+=("le site sert ${3:-rien}, attendu $4")
    [ "$5" = oui ] || fautes+=("pas d'archive des volumes")
    [ "$6" = oui ] || fautes+=("pas d'export de la base")
    [ "$7" = oui ] || fautes+=("le compte témoin ne se connecte plus")
    if [ ${#fautes[@]} -eq 0 ]; then echo OK; else local IFS=';'; echo "ECHEC:${fautes[*]}"; fi
}

if [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$(verdict_essai "${@:3}"); r=${r%%:*}
          [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }
    t "tout est là"                         OK     oui 2.1.0 2.1.0 2.1.0 oui oui oui
    t "sans export de la base"              ECHEC  oui 2.1.0 2.1.0 2.1.0 oui non oui
    t "sans archive des volumes"            ECHEC  oui 2.1.0 2.1.0 2.1.0 non oui oui
    t "le site sert l'ancienne version"     ECHEC  oui 2.1.0 2.0.0 2.1.0 oui oui oui
    t "version servie illisible"            ECHEC  oui 2.1.0 ""    2.1.0 oui oui oui
    t "revenue en arrière"                  ECHEC  non 2.0.0 2.0.0 2.1.0 oui oui oui
    t "le témoin a disparu"                 ECHEC  oui 2.1.0 2.1.0 2.1.0 oui oui non
    [ "$st" -eq 0 ] && echo "essai-mise-a-jour : tous les cas passent."
    exit "$st"
fi

DE="${1:?version de départ manquante}"
VERS="${2:?version cible manquante}"
RACINE=$(git rev-parse --show-toplevel)
# shellcheck source=lib-archive-deploiement.sh
source "$RACINE/scripts/ci/lib-archive-deploiement.sh"

TRAVAIL=$(mktemp -d)
INST="$TRAVAIL/coprofirst"
SAUV="$TRAVAIL/sauvegardes"
mkdir -p "$INST" "$SAUV"
echo "== 1. Archives de $DE et $VERS"
ARCHIVE_DE=$(archiver_deploiement "v$DE" "$DE" "$TRAVAIL")
ARCHIVE_VERS=$(archiver_deploiement "v$VERS" "$VERS" "$TRAVAIL")

echo "== 2. Installation de $DE"
tar -xzf "$ARCHIVE_DE" -C "$INST" --strip-components=1
cd "$INST"
cp .env.example .env
poser() { sed -i "/^$1=/d" .env; printf '%s=%s\n' "$1" "$2" >> .env; }
poser SECRET_KEY "$(openssl rand -hex 32)"
poser WHATSAPP_API_KEY "$(openssl rand -hex 16)"
poser ORIGIN http://localhost
poser COOKIE_SECURE false
poser COPROFIRST_VERSION "$DE"
poser COPROFIRST_SAUVEGARDES "$SAUV"
poser MAINTENANCE_KEY "$(openssl rand -hex 24)"
MDP=$(openssl rand -hex 32)
#  Une <de> qui portait PostgreSQL derrière un profil ne le démarre que par lui ;
#  sans profil, la variable n'allume rien de plus.
poser COMPOSE_PROFILES postgresql
poser POSTGRES_PASSWORD "$MDP"
poser DATABASE_URL "postgresql+psycopg://coprofirst:$MDP@postgres:5432/coprofirst"
COMPOSE=(docker compose -f docker-compose.yml -f deploiement/standard/compose.images.yml)
"${COMPOSE[@]}" up -d --quiet-pull
attendre_sante() {
    for _ in $(seq 1 60); do
        [ "$(curl -s -m 5 -o /dev/null -w '%{http_code}' http://localhost/api/health || true)" = 200 ] && return 0
        sleep 5
    done
    "${COMPOSE[@]}" logs --tail 80 api
    return 1
}
attendre_sante || { echo "::error::$DE ne démarre pas"; exit 1; }

echo "== 3. Le témoin : le compte administrateur initial"
MDP_ADMIN=$("${COMPOSE[@]}" logs api 2>&1 | sed -n 's/.*Mot de passe temporaire : *//p' | tail -1 | tr -d '\r ')
[ -n "$MDP_ADMIN" ] || { echo "::error::mot de passe initial introuvable dans les journaux"; exit 1; }
#  → le code HTTP de la connexion (200 attendu). Le code, pas oui/non : un 403
#  disait « adresse non vérifiée », et l'essai ne le montrait pas (10/10/2026).
connexion() {
    curl -s -m 10 -o "$TRAVAIL/connexion.json" -w '%{http_code}' -X POST http://localhost/api/auth/login \
        -H 'Content-Type: application/json' \
        -d "{\"email\":\"admin@localhost\",\"password\":\"$MDP_ADMIN\"}" || true
}
se_connecte() { [ "$(connexion)" = 200 ] && echo oui || echo non; }
CODE=$(connexion)
[ "$CODE" = 200 ] || {
    echo "::error::le témoin ne se connecte pas AVANT la mise à jour (HTTP $CODE : $(head -c 200 "$TRAVAIL/connexion.json"))"
    exit 1
}

echo "== 4. La mise à jour $DE → $VERS"
COPROFIRST_ESSAI_CIBLE="$VERS" COPROFIRST_ESSAI_ARCHIVE="$ARCHIVE_VERS" \
    bash deploiement/standard/mise-a-jour.sh | tee "$TRAVAIL/maj.log" || true

echo "== 5. Le verdict"
attendre_sante || true
REUSSIE=$(grep -q "Mise à jour réussie : $VERS" "$TRAVAIL/maj.log" && echo oui || echo non)
ENV_VERSION=$(sed -n 's/^COPROFIRST_VERSION=//p' .env | tail -1)
SERVIE=$(node "$RACINE/front/scripts/check-version-servie.mjs" --site http://localhost 2>/dev/null | tail -1 || true)
VOLUMES=$(ls "$SAUV"/coprofirst_*_vers_"$VERS"_*.tar.gz 2>/dev/null | grep -v -- '-base\.tar\.gz$' | grep . >/dev/null && echo oui || echo non)
BASE=$(ls "$SAUV"/*-base.tar.gz >/dev/null 2>&1 && echo oui || echo non)
TEMOIN=$(se_connecte)
ls -la "$SAUV"
VERDICT=$(verdict_essai "$REUSSIE" "$ENV_VERSION" "$SERVIE" "$VERS" "$VOLUMES" "$BASE" "$TEMOIN")
echo "Essai $DE → $VERS : $VERDICT"
"${COMPOSE[@]}" down -v >/dev/null 2>&1 || true
[ "$VERDICT" = OK ] || { echo "::error::$VERDICT"; exit 1; }
