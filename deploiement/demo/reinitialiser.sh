#!/bin/bash
# =============================================================================
#  reinitialiser.sh — La remise à zéro nocturne de la DÉMO PUBLIQUE de CoproFirst
#  (spec `specs/architecture/mode-demo.md` §7, lot D5 #1905)
#
#  Rien de ce qu'un visiteur saisit ne survit à la nuit (§1, exigence 3) : la
#  base et les fichiers sont vidés, puis la résidence fictive est FABRIQUÉE de
#  nouveau par le code de la version installée (`python -m app.demo.charger`).
#
#  ## Le déroulé
#
#   1. décider (fonction PURE `decider_remise`) : seulement si `.env` pose
#      `MODE_DEMO` — sur une installation ordinaire, ce script ne fait RIEN —,
#      et seulement pour un moteur connu, SQLite ou PostgreSQL (§11, question 4) ;
#   2. arrêter l'API (règle d'or : aucun processus tiers sur une base ouverte) ;
#   3. vider la base (fonction PURE `commande_vidage`) et le volume des fichiers :
#      - SQLite : supprimer le FICHIER de la base et son journal WAL — jamais le
#        volume `app_data` entier : l'inscription de l'installation au registre y
#        vit (`INSTALLATION_DIR`), et la démo la perdrait chaque nuit ;
#      - PostgreSQL : supprimer et recréer le SCHÉMA `public`, dans le serveur qui
#        tourne — jamais le volume `pg_data`, jamais la base elle-même ;
#   4. poser le schéma puis charger le jeu, dans un conteneur ponctuel ;
#   5. redémarrer, sonder `/api/health`, rendre compte (`remise_a_zero_demo`) ;
#   6. en échec du chargement, l'API RESTE ARRÊTÉE (fonction PURE
#      `decider_issue`) : une démo à moitié chargée ne se sert pas.
#
#  Le verrou est CELUI de la mise à jour nocturne (`mise-a-jour.sh`) : les deux
#  ne tournent jamais ensemble. La crontab les espace (04:30 puis 05:15) ; si la
#  mise à jour déborde, la remise à zéro l'attend.
#
#  Test : bash deploiement/demo/reinitialiser.sh --selftest
# =============================================================================
set -euo pipefail

VERROU=/tmp/coprofirst-maj.lock
ATTENTE_VERROU_S=3600

# ── Décisions PURES ───────────────────────────────────────────────────────────

#  `MODE_DEMO` allume-t-il la démo ? Mêmes valeurs que `utils/demo.est_demo`.
est_oui() {  # $1 valeur brute → oui|non
    case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')" in
        oui|1|true|yes|on) echo oui ;;
        *)                 echo non ;;
    esac
}

#  $1 MODE_DEMO brut · $2 moteur (sqlite|postgresql|inconnu)
#  → remettre | pas-demo | moteur-non-gere
decider_remise() {
    if [ "$(est_oui "$1")" != oui ]; then echo pas-demo; return; fi
    case "${2:-}" in
        sqlite|postgresql) echo remettre ;;
        *)                 echo moteur-non-gere ;;
    esac
}

#  Ce qui vide la base, selon le moteur : `$1` moteur · `$2` chemin du fichier
#  SQLite (vu du conteneur de l'API). Rend `<service> <commande sh>` : le service
#  Compose où la jouer, puis la commande. PostgreSQL se vide dans SON conteneur,
#  qui tourne, par le superutilisateur de l'image (`POSTGRES_USER`).
commande_vidage() {
    case "$1" in
        sqlite) printf "api rm -f '%s' '%s-wal' '%s-shm'\n" "$2" "$2" "$2" ;;
        postgresql) printf '%s\n' 'postgres psql -v ON_ERROR_STOP=1 -U coprofirst -d coprofirst -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"' ;;
    esac
}

#  Le chemin du fichier de la base, vu du conteneur, depuis son URL SQLite.
chemin_sqlite() {  # $1 sqlite:////app/data/app.db → /app/data/app.db
    printf '%s\n' "${1#sqlite:///}"
}

#  $1 code de sortie du chargement · $2 santé après le redémarrage (ok|ko|vide)
#  → reussie | refusee | chargement-echoue | sante-ko
decider_issue() {
    case "$1" in
        0) ;;
        2|3) echo refusee; return ;;
        *) echo chargement-echoue; return ;;
    esac
    if [ "${2:-}" = ok ]; then echo reussie; else echo sante-ko; fi
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    attendu() {  # $1 libellé · $2 attendu · $3 fonction · $4… arguments
        local lib="$1" voulu="$2" f="$3" got; shift 3
        got=$("$f" "$@")
        if [ "$got" = "$voulu" ]; then echo "PASS  $lib"; else echo "FAIL  $lib — « $got »"; fail=1; fi
    }
    echo "== self-test : faut-il remettre à zéro =="
    attendu "MODE_DEMO=oui, SQLite → remettre"           remettre        decider_remise oui sqlite
    attendu "MODE_DEMO=OUI (casse) → remettre"           remettre        decider_remise OUI sqlite
    attendu "MODE_DEMO absent → rien (pas une démo)"     pas-demo        decider_remise "" sqlite
    attendu "MODE_DEMO=non → rien"                       pas-demo        decider_remise non sqlite
    attendu "MODE_DEMO mal écrit → rien, jamais vider"   pas-demo        decider_remise ouii sqlite
    attendu "MODE_DEMO=oui, PostgreSQL → remettre"       remettre        decider_remise oui postgresql
    attendu "moteur inconnu → non géré, jamais SQLite"   moteur-non-gere decider_remise oui inconnu
    echo "== self-test : le fichier de la base =="
    attendu "URL SQLite absolue"                         /app/data/app.db chemin_sqlite "sqlite:////app/data/app.db"
    echo "== self-test : vider la base =="
    attendu "SQLite : le fichier et son journal, par l'API" \
        "api rm -f '/app/data/app.db' '/app/data/app.db-wal' '/app/data/app.db-shm'" \
        commande_vidage sqlite /app/data/app.db
    attendu "PostgreSQL : le schéma, dans son conteneur" \
        'postgres psql -v ON_ERROR_STOP=1 -U coprofirst -d coprofirst -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"' \
        commande_vidage postgresql ""
    attendu "moteur inconnu : rien à jouer"              ""              commande_vidage inconnu ""
    echo "== self-test : l'issue =="
    attendu "chargée, santé OK → réussie"                reussie           decider_issue 0 ok
    attendu "chargée, santé KO → santé KO"               sante-ko          decider_issue 0 ko
    attendu "pas en démo (2) → refusée"                  refusee           decider_issue 2 ""
    attendu "base non vierge (3) → refusée"              refusee           decider_issue 3 ""
    attendu "erreur (1) → chargement échoué"             chargement-echoue decider_issue 1 ""
    exit "$fail"
fi

DOSSIER="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$DOSSIER"
. deploiement/standard/lib-installation.sh
DEBUT=$(date +%s)

exec 9>"$VERROU"
flock -w "$ATTENTE_VERROU_S" 9 || { journal "⚠ La mise à jour tient le verrou depuis une heure : remise à zéro sautée cette nuit."; exit 1; }

URL=$(lire_env DATABASE_URL)
case "$(decider_remise "$(lire_env MODE_DEMO)" "$(moteur_de_url "$URL")")" in
    pas-demo) journal "MODE_DEMO n'est pas posé : ce n'est pas la démo, rien n'est remis à zéro."; exit 0 ;;
    moteur-non-gere)
        journal "⚠ La remise à zéro ne connaît que SQLite et PostgreSQL (DATABASE_URL : $(moteur_de_url "$URL"))."
        rendre_compte_tache remise_a_zero_demo erreur "moteur de base non géré" "{}"
        exit 1 ;;
esac

COMPOSE=(docker compose -f docker-compose.yml -f deploiement/standard/compose.images.yml)
PONCTUEL=("${COMPOSE[@]}" run --rm --no-deps -T --entrypoint sh api -c)
MOTEUR=$(moteur_de_url "$URL")
BASE=$(chemin_sqlite "$URL")
UPLOADS=$(lire_env UPLOADS_DIR); UPLOADS=${UPLOADS:-/app/uploads}
read -r SERVICE_VIDAGE VIDAGE <<<"$(commande_vidage "$MOTEUR" "$BASE")"

journal "Remise à zéro de la démo : base $MOTEUR, fichiers $UPLOADS."
"${COMPOSE[@]}" stop api >/dev/null
if [ "$SERVICE_VIDAGE" = postgres ]; then
    "${COMPOSE[@]}" exec -T postgres sh -c "$VIDAGE" >/dev/null
    "${PONCTUEL[@]}" "find '$UPLOADS' -mindepth 1 -delete"
else
    "${PONCTUEL[@]}" "$VIDAGE && find '$UPLOADS' -mindepth 1 -delete"
fi
if "${PONCTUEL[@]}" "python -m app.utils.schema_initial && python -m app.demo.charger"; then
    CODE=0
else
    CODE=$?
fi
SANTE=""
if [ "$CODE" = 0 ]; then
    "${COMPOSE[@]}" up -d >/dev/null 2>&1 || true
    SANTE=$(sante)
fi

case "$(decider_issue "$CODE" "$SANTE")" in
    reussie)
        journal "Démo remise à zéro (en $(( $(date +%s) - DEBUT )) s)."
        rendre_compte_tache remise_a_zero_demo succes "" "{}" ;;
    sante-ko)
        journal "⚠ Démo rechargée, mais l'API ne répond pas."
        rendre_compte_tache remise_a_zero_demo erreur "santé KO après le rechargement" "{}"
        exit 1 ;;
    refusee|chargement-echoue)
        #  L'API reste arrêtée : elle ne peut donc pas recevoir le rapport. Le
        #  journal de ce script est la trace, et la démo, injoignable, le dit.
        journal "🔴 Chargement de la démo refusé ou échoué (code $CODE) : l'API reste ARRÊTÉE."
        exit 1 ;;
esac
