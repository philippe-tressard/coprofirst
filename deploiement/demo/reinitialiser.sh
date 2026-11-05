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
#      et seulement si `DATABASE_URL` désigne PostgreSQL (§11, question 4) ;
#   2. arrêter l'API : aucun écrivain pendant le vidage ;
#   3. vider la base (`VIDAGE`) et le volume des fichiers : supprimer et recréer
#      le SCHÉMA `public`, dans le serveur qui tourne — jamais le volume
#      `pg_data`, jamais la base elle-même, jamais le volume `app_data` :
#      l'inscription de l'installation au registre y vit (`INSTALLATION_DIR`) ;
#   4. poser le schéma puis charger le jeu, dans un conteneur ponctuel, sous le
#      compte `app` (`PONCTUEL`, voir plus bas : jamais en root) ;
#   5. redémarrer, sonder `/api/health`, rendre compte (`remise_a_zero_demo`) ;
#   6. en échec du chargement (fonction PURE `decider_issue`), la base est VIDÉE de
#      nouveau, puis l'API RELANCÉE quand même — une démo à moitié chargée ne se
#      sert pas, une démo arrêtée non plus (#2546) ;
#   7. quoi qu'il arrive après l'arrêt de l'API, un piège (`EXIT`) la relance et
#      rend compte de l'étape qui a échoué.
#
#  🔴 POURQUOI L'API EST TOUJOURS RELANCÉE (incident du 05/11/2026, #2546) : le
#  vidage des fichiers a échoué, `set -e` a arrêté le script, et la démo est restée
#  sans API (502) et sans base jusqu'à un geste à la main. Une API arrêtée sert une
#  erreur aux visiteurs et à l'app iOS, et ne peut même pas recevoir le rapport :
#  l'échec n'était connu que de ce journal. Relancée sur une base vide, elle sert
#  le site (connexion, bandeau, textes légaux), reçoit le rapport d'échec, et la
#  nuit suivante recharge le jeu. On ne RECHARGE pas une seconde fois : un
#  chargement qui échoue échoue de la même façon — c'est le code de la version.
#
#  Le verrou est CELUI de la mise à jour nocturne (`mise-a-jour.sh`) : les deux
#  ne tournent jamais ensemble. La crontab les espace (04:30 puis 05:15) ; si la
#  mise à jour déborde, la remise à zéro l'attend.
#
#  Test : bash deploiement/demo/reinitialiser.sh --selftest      (décisions pures)
#         bash scripts/ci/essai-reinitialiser-demo.sh --selftest (le script entier,
#         contre un docker factice : l'API relancée dans chaque échec)
# =============================================================================
set -euo pipefail

#  COPROFIRST_ESSAI_VERROU : l'autotest de comportement (`scripts/ci/essai-reinitialiser-demo.sh`)
#  pose son verrou dans son dossier jetable — jamais celui d'une installation.
VERROU=${COPROFIRST_ESSAI_VERROU:-/tmp/coprofirst-maj.lock}
ATTENTE_VERROU_S=3600

# ── Décisions PURES ───────────────────────────────────────────────────────────

#  `MODE_DEMO` allume-t-il la démo ? Mêmes valeurs que `utils/demo.est_demo`.
est_oui() {  # $1 valeur brute → oui|non
    case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')" in
        oui|1|true|yes|on) echo oui ;;
        *)                 echo non ;;
    esac
}

#  $1 MODE_DEMO brut · $2 moteur (postgresql|inconnu) → remettre | pas-demo | moteur-non-gere
decider_remise() {
    if [ "$(est_oui "$1")" != oui ]; then echo pas-demo; return; fi
    if [ "${2:-}" = postgresql ]; then echo remettre; else echo moteur-non-gere; fi
}

#  Ce qui vide la base : dans le conteneur `postgres`, qui tourne, par le
#  superutilisateur de l'image (`POSTGRES_USER`).
VIDAGE='psql -v ON_ERROR_STOP=1 -U coprofirst -d coprofirst -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'

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
    attendu "MODE_DEMO=oui, PostgreSQL → remettre"       remettre        decider_remise oui postgresql
    attendu "MODE_DEMO=OUI (casse) → remettre"           remettre        decider_remise OUI postgresql
    attendu "MODE_DEMO absent → rien (pas une démo)"     pas-demo        decider_remise "" postgresql
    attendu "MODE_DEMO=non → rien"                       pas-demo        decider_remise non postgresql
    attendu "MODE_DEMO mal écrit → rien, jamais vider"   pas-demo        decider_remise ouii postgresql
    attendu "moteur inconnu → non géré, jamais vider"    moteur-non-gere decider_remise oui inconnu
    attendu "MODE_DEMO absent, moteur inconnu → rien"    pas-demo        decider_remise "" inconnu
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
        journal "⚠ La remise à zéro ne connaît que PostgreSQL (DATABASE_URL : $(moteur_de_url "$URL"))."
        rendre_compte_tache remise_a_zero_demo erreur "moteur de base non géré" "{}"
        exit 1 ;;
esac

COMPOSE=(docker compose -f docker-compose.yml -f deploiement/standard/compose.images.yml)
#  🔴 `-u app` (#2546) : `--entrypoint` remplace `start.sh`, donc aussi sa descente
#  vers `app` (`setpriv`). Le conteneur de l'API est DURCI (#2368) : resté root, il
#  n'aurait ni DAC_OVERRIDE ni FOWNER, et ne pourrait supprimer AUCUN fichier de
#  `app` dans des dossiers en 755 — c'est l'incident du 05/11/2026. Le compte de
#  l'API possède ses fichiers : c'est lui qui les vide et qui recharge.
#  🔒 `scripts/ci/commandes_ponctuelles.py` refuse un `run|exec` sans compte.
PONCTUEL=("${COMPOSE[@]}" run --rm --no-deps -T -u app --entrypoint sh api -c)
UPLOADS=$(lire_env UPLOADS_DIR); UPLOADS=${UPLOADS:-/app/uploads}

#  L'étape en cours, et l'API arrêtée ou non : ce que le piège lit.
ETAPE="" API_ARRETEE=non
relancer_l_api() {
    "${COMPOSE[@]}" up -d api >/dev/null 2>&1 || journal "⚠ La relance de l'API (up -d api) a échoué."
    API_ARRETEE=non
}
#  Le piège : toute sortie, l'API encore arrêtée, la relance et rend compte. Le
#  rapport part APRÈS la relance — il passe par l'API (#1820).
au_depart() {
    local code=$? s
    [ "$API_ARRETEE" = oui ] || return 0
    journal "🔴 Remise à zéro interrompue : $ETAPE (code $code). L'API est relancée."
    relancer_l_api
    s=$(sante)
    journal "Santé après la relance : $s."
    rendre_compte_tache remise_a_zero_demo erreur "remise à zéro interrompue : $ETAPE (code $code) — API relancée, santé $s" "{}"
    exit "$code"
}
trap au_depart EXIT

journal "Remise à zéro de la démo : base PostgreSQL, fichiers $UPLOADS."
ETAPE="arrêt de l'API"; API_ARRETEE=oui
"${COMPOSE[@]}" stop api >/dev/null
ETAPE="vidage de la base"
"${COMPOSE[@]}" exec -T postgres sh -c "$VIDAGE" >/dev/null
ETAPE="vidage des fichiers"
"${PONCTUEL[@]}" "find '$UPLOADS' -mindepth 1 -delete"
ETAPE="chargement du jeu"
if "${PONCTUEL[@]}" "python -m app.utils.schema_initial && python -m app.demo.charger"; then
    CODE=0
else
    CODE=$?
fi
if [ "$CODE" != 0 ]; then
    #  Refusé ou échoué : la base est peut-être À MOITIÉ chargée. Elle se vide de
    #  nouveau ; l'API, relancée ensuite, y pose le schéma courant (`start.sh`).
    ETAPE="second vidage de la base, après l'échec du chargement (code $CODE)"
    "${COMPOSE[@]}" exec -T postgres sh -c "$VIDAGE" >/dev/null
fi
ETAPE="redémarrage de l'API"
relancer_l_api
SANTE=$(sante)

case "$(decider_issue "$CODE" "$SANTE")" in
    reussie)
        journal "Démo remise à zéro (en $(( $(date +%s) - DEBUT )) s)."
        rendre_compte_tache remise_a_zero_demo succes "" "{}" ;;
    sante-ko)
        journal "⚠ Démo rechargée, mais l'API ne répond pas."
        rendre_compte_tache remise_a_zero_demo erreur "santé KO après le rechargement" "{}"
        exit 1 ;;
    refusee|chargement-echoue)
        journal "🔴 Chargement de la démo refusé ou échoué (code $CODE) : base vidée, API relancée SANS le jeu (santé $SANTE)."
        rendre_compte_tache remise_a_zero_demo erreur "chargement refusé ou échoué (code $CODE) — démo servie vide, santé $SANTE" "{}"
        exit 1 ;;
esac
