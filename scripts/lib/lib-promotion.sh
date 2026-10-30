#!/bin/bash
# =============================================================================
#  lib-promotion.sh — Le rôle d'une base PostgreSQL, et le geste qui le change :
#  la PROMOTION d'une réplique en primaire (module à sourcer, DI-7b, #1781)
#
#  Le standby porte une réplique en continu de la base (D16). Changer d'actif —
#  bascule de nuit, failover, garde au démarrage — se fait en PROMOUVANT cette
#  réplique. Trois scripts le font ; la règle et les
#  gestes s'écrivent ICI, une fois.
#
#  🔴 LA RÈGLE QUI PRIME : on ne démarre JAMAIS une base absente sur un nœud qui
#  prend la main. L'image PostgreSQL initialiserait un primaire VIDE, et le site
#  servirait une copropriété sans données. D'où `decider_prise_de_main` : une
#  réplique se promeut, un primaire se garde, l'absence fait ABSTENIR — et un
#  nœud qui s'abstient ne démarre RIEN : l'application n'a pas d'autre base.
#
#  🔴 Une promotion est IRRÉVERSIBLE : l'ancien primaire ne se relance pas tel
#  quel (deux primaires, deux histoires qui divergent). Il se reconstruit en
#  réplique : `scripts/exploitation/reconstruire-replique.sh`.
#
#  Les requêtes passent par l'ENTRÉE de psql (`docker exec -i`) : la même chaîne
#  vaut en local et chez le pair par SSH, guillemets SQL compris.
#
#  Test : bash lib-promotion.sh --selftest   (aucun effet de bord)
# =============================================================================

# ── Le rôle d'une base : UN script, exécuté tel quel en local ou chez le pair ──
#  Passé à SSH comme une seule chaîne : ses guillemets arrivent intacts (des mots
#  séparés perdraient ceux de `pg_is_in_recovery()`, que le shell distant lirait).
#  → primaire | replique_ok | replique_ko | absente | illisible
ROLE_BASE_SH='present=$(docker ps --format "{{.Names}}" 2>/dev/null | grep -cx hostachy_postgres)
if [ "$present" != 1 ]; then echo absente; exit 0; fi
q() { docker exec hostachy_postgres psql -U coprofirst -d coprofirst -Atqc "$1" 2>/dev/null; }
case "$(q "select pg_is_in_recovery()")" in
  f) echo primaire ;;
  t) [ "$(q "select status from pg_stat_wal_receiver")" = streaming ] && echo replique_ok || echo replique_ko ;;
  *) echo illisible ;;
esac'

#: psql sur l'entrée standard — la requête ne traverse aucun shell.
PSQL_ENTREE="docker exec -i hostachy_postgres psql -U coprofirst -d coprofirst -Atq"

role_base_locale() { bash -c "$ROLE_BASE_SH"; }
role_base_pair()   { $SSH_CMD ptressard@"$PEER_IP" "$ROLE_BASE_SH" 2>/dev/null || echo illisible; }
pgq_local()        { $PSQL_ENTREE <<< "$1" 2>/dev/null; }
pgq_pair()         { $SSH_CMD ptressard@"$PEER_IP" "$PSQL_ENTREE" <<< "$1" 2>/dev/null; }

# ── PURE : un nœud prend la main — que fait-on de SA base ? ───────────────────
#  $1 rôle de la base locale (primaire|replique_ok|replique_ko|absente|illisible)
#  → PROMOUVOIR | GARDER | ABSTENIR:<raison>
decider_prise_de_main() {
    case "${1:-}" in
        replique_ok) echo PROMOUVOIR ;;
        #  Déconnectée : elle a peut-être du retard, mais un site servi sur la
        #  dernière donnée reçue vaut mieux qu'un site coupé — on promeut, et on le DIT.
        replique_ko) echo PROMOUVOIR ;;
        primaire)    echo GARDER ;;
        absente)     echo "ABSTENIR:aucune base ici — la démarrer créerait un primaire VIDE" ;;
        *)           echo "ABSTENIR:base illisible — on ne promeut pas ce qu'on n'a pas lu" ;;
    esac
}

# ── PURE : un nœud se RETIRE — que fait-on de SA base ? (#2000) ──────────────
#  $1 rôle de la base locale · → RECONSTRUIRE:<raison> | GARDER | ATTENDRE
#  `boot-role-guard` ne reconstruisait qu'un ancien primaire EN MARCHE. Or le
#  failover ARRÊTE la base de l'ancien actif (`docker compose stop`, et
#  `restart: unless-stopped` la laisse arrêtée au redémarrage) : elle se lit
#  `absente`, rien ne la reconstruisait, et le nouvel actif servait sans
#  réplique jusqu'à une intervention (15/10/2026, réparé à la main à 20:50).
#  `illisible` peut être une base qui démarre : on ATTEND (l'appelant borne),
#  on ne reconstruit pas ce qu'on n'a pas lu.
decider_base_au_retrait() {
    case "${1:-}" in
        primaire)                echo "RECONSTRUIRE:ancien primaire — le relancer ferait deux primaires" ;;
        absente)                 echo "RECONSTRUIRE:base arrêtée ou absente — l'actif servirait sans réplique" ;;
        replique_ok|replique_ko) echo GARDER ;;
        *)                       echo ATTENDRE ;;
    esac
}

# ── PURE : le retour arrière de la bascule relance-t-il la base LOCALE ? (#2318)
#  $1 PROMU (true|false) · $2 rôle de la base du pair, relu APRÈS son isolement
#  → DEMARRER | ABSTENIR:<raison>
#  Le primaire local (arrêté en phase 3) ne reprend que si le pair ne porte plus
#  de primaire. L'isolement ne rend pas son échec (`|| true`) : c'est la relecture
#  qui le dit. Un pair illisible n'est pas un pair isolé — le site reste coupé,
#  ce qui se répare ; deux primaires, non.
decider_base_au_rollback() {
    [ "${1:-false}" = true ] || { echo DEMARRER; return; }
    case "${2:-}" in
        absente|replique_ok|replique_ko) echo DEMARRER ;;
        primaire) echo "ABSTENIR:la base promue du pair sert encore — relancer la locale ferait deux primaires" ;;
        *)        echo "ABSTENIR:base du pair illisible après son isolement — on ne relance pas un primaire sans l'avoir lue" ;;
    esac
}

# ── PURE : la réplique a-t-elle rejoué tout le journal du primaire ? ──────────
#  $1 position du primaire, $2 position rejouée par la réplique (octets)
#  → oui | non | inconnu
decider_rattrapage() {
    local v
    for v in "${1:-}" "${2:-}"; do
        case "$v" in ''|*[!0-9]*) echo inconnu; return ;; esac
    done
    [ "$2" -ge "$1" ] && echo oui || echo non
}

# ── Les gestes ────────────────────────────────────────────────────────────────
#  Promouvoir la réplique LOCALE ; attend la fin (60 s). Rend 0 si elle est primaire.
promouvoir_local() {
    [ "$(pgq_local "select pg_promote(true, 60)")" = t ] || return 1
    [ "$(pgq_local "select pg_is_in_recovery()")" = f ]
}

#  Promouvoir la réplique du PAIR.
promouvoir_pair() {
    [ "$(pgq_pair "select pg_promote(true, 60)")" = t ] || return 1
    [ "$(pgq_pair "select pg_is_in_recovery()")" = f ]
}

#  Attendre que la réplique du pair ait rejoué TOUT le journal du primaire local
#  ($1 = délai en secondes). Les écrivains doivent être arrêtés : sinon la
#  position avance pendant qu'on l'attend.
attendre_rattrapage_pair() {
    local delai=${1:-60} cible fait t0=$SECONDS
    cible=$(pgq_local "select pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')::bigint")
    while [ $((SECONDS - t0)) -lt "$delai" ]; do
        fait=$(pgq_pair "select pg_wal_lsn_diff(pg_last_wal_replay_lsn(), '0/0')::bigint")
        case "$(decider_rattrapage "$cible" "$fait")" in
            oui) return 0 ;;
            inconnu) return 2 ;;
        esac
        sleep 2
    done
    return 1
}

# ── La bascule de nuit (`bascule.sh`) ─────────────────────────────────────────
#  Appelées par la bascule, qui fournit `log`, `drylog`, `DRY_RUN`, `rollback`,
#  `PEER`, `PEER_IP`, `SSH_CMD`, `SELF` et `REPO`. Une étape qui échoue pose le
#  libellé de son retour arrière (`trap … ERR`, global au shell) et rend 1 :
#  l'appelant écrit `phases_base_postgresql || false`, qui le déclenche.

#  Phases 3 et 4 : la réplique du pair rattrape, le primaire local s'arrête
#  PROPREMENT (plus aucun écrivain : phase 2), le pair est PROMU.
phases_base_postgresql() {
    log "[3/7] Base PostgreSQL : la réplique de $PEER rattrape le primaire local..."
    trap 'rollback "3-rattrapage-postgresql"' ERR
    local role_pair
    role_pair=$(role_base_pair)
    if [ "$role_pair" != replique_ok ]; then
        log "ERREUR: la base de $PEER n'est pas une réplique qui reçoit le journal ($role_pair) — bascule annulée."
        return 1
    fi
    if $DRY_RUN; then
        drylog "rattrapage de la réplique de $PEER, docker compose stop postgres, pg_promote() sur $PEER"
        return 0
    fi
    if ! attendre_rattrapage_pair 90; then
        log "ERREUR: la réplique de $PEER n'a pas rattrapé le primaire en 90 s — bascule annulée."
        return 1
    fi
    log "  → Réplique à jour : tout le journal est rejoué."
    #  Ce primaire ne le sera plus jamais : il se reconstruira en réplique (phase 7).
    ( cd "$REPO" && docker compose stop postgres >/dev/null ) || return 1
    log "  → Primaire local arrêté."

    log "[4/7] Promotion de la réplique de $PEER..."
    trap 'rollback "4-promotion-postgresql"' ERR
    PROMU=true   # posé AVANT : un échec à mi-promotion doit aussi isoler le pair
    if ! promouvoir_pair; then
        log "ERREUR: la promotion de la base de $PEER a échoué — bascule annulée."
        return 1
    fi
    log "  → $PEER porte désormais le PRIMAIRE."
}

#  Retour arrière : une base PROMUE chez le pair ne se défait pas — on l'ARRÊTE
#  (deux primaires sinon). Elle n'a reçu d'écritures que de l'API démarrée en
#  phase 5 ; le primaire local reprend, et elle se reconstruit en réplique.
isoler_base_pair_si_promue() {
    "${PROMU:-false}" || return 0
    $SSH_CMD ptressard@"$PEER_IP" "cd /opt/5hostachy && docker compose stop postgres 2>/dev/null" 2>/dev/null || true
    log "  → Base promue du peer ARRÊTÉE (isolée) — la reconstruire en réplique : sudo bash /opt/5hostachy/scripts/exploitation/reconstruire-replique.sh --oui sur $PEER."
}

#  Phase 7 : l'ancien primaire (ce nœud) redevient RÉPLIQUE du nouveau. Après
#  `trap - ERR` : un échec ne défait rien — le site est servi par le pair, et C37
#  dit qu'il n'a plus de réplique tant que celle-ci n'est pas refaite.
reconstruire_apres_bascule() {
    if bash "$REPO/scripts/exploitation/reconstruire-replique.sh" --oui; then
        log "  → $SELF reconstruit en réplique de $PEER."
    else
        log "  ⚠ Reconstruction de la réplique sur $SELF ÉCHOUÉE — $PEER sert sans réplique : relancer sudo bash /opt/5hostachy/scripts/exploitation/reconstruire-replique.sh --oui."
    fi
}

# ── Autotest (job CI `test-scripts`) ──────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); r=${r%%:*}
          [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }
    echo "== prise de main =="
    t "réplique qui reçoit"                PROMOUVOIR decider_prise_de_main replique_ok
    t "réplique déconnectée : on promeut"  PROMOUVOIR decider_prise_de_main replique_ko
    t "déjà primaire"                      GARDER     decider_prise_de_main primaire
    t "AUCUNE base → abstention"           ABSTENIR   decider_prise_de_main absente
    t "illisible → abstention"             ABSTENIR   decider_prise_de_main illisible
    t "rien lu → abstention"               ABSTENIR   decider_prise_de_main ""
    echo "== un nœud se retire : que faire de sa base (#2000) =="
    t "ancien primaire relancé par Docker"     RECONSTRUIRE decider_base_au_retrait primaire
    t "base ARRÊTÉE par le failover (15/10)"   RECONSTRUIRE decider_base_au_retrait absente
    t "réplique qui reçoit : rien à faire"     GARDER       decider_base_au_retrait replique_ok
    t "réplique déconnectée : elle se rattrape" GARDER      decider_base_au_retrait replique_ko
    t "illisible (elle démarre ?) → attendre"  ATTENDRE     decider_base_au_retrait illisible
    t "rien lu → attendre, jamais effacer"     ATTENDRE     decider_base_au_retrait ""
    echo "== retour arrière de la bascule : la base locale reprend-elle ? (#2318) =="
    t "rien promu : le primaire local reprend"     DEMARRER decider_base_au_rollback false ""
    t "pair promu puis isolé (arrêté)"             DEMARRER decider_base_au_rollback true absente
    t "promotion avortée : le pair est réplique"   DEMARRER decider_base_au_rollback true replique_ok
    t "pair promu ET encore primaire"              ABSTENIR decider_base_au_rollback true primaire
    t "pair illisible après l'isolement"           ABSTENIR decider_base_au_rollback true illisible
    t "rien lu chez le pair promu"                 ABSTENIR decider_base_au_rollback true ""
    echo "== rattrapage =="
    t "rejouée jusqu'au bout"              oui     decider_rattrapage 1000 1000
    t "rejouée au-delà (point final)"      oui     decider_rattrapage 1000 1040
    t "en retard"                          non     decider_rattrapage 1000 960
    t "position illisible"                 inconnu decider_rattrapage 1000 ""
    t "réponse non numérique"              inconnu decider_rattrapage 1000 "ERROR"
    echo "== le script de rôle, exécuté avec un docker simulé =="
    r() {  # $1 libellé · $2 attendu · $3 noms de docker ps · $4 recovery · $5 récepteur
        local got
        got=$(DOCKER_PS="$3" REC="$4" RECEP="$5" bash -c '
            docker() { case "$1" in ps) printf "%b" "$DOCKER_PS" ;;
                                    exec) case "$*" in *recovery*) echo "$REC" ;; *receiver*) echo "$RECEP" ;; esac ;; esac; }
            '"$ROLE_BASE_SH")
        [ "$got" = "$2" ] && echo "PASS  $1 → $got" || { echo "FAIL  $1  attendu=$2 obtenu=$got"; st=1; }
    }
    r "primaire"                     primaire    "hostachy_postgres" f ""
    r "réplique qui reçoit"          replique_ok "hostachy_postgres" t streaming
    r "réplique qui ne reçoit plus"  replique_ko "hostachy_postgres" t ""
    r "pas de conteneur"             absente     "hostachy_api"      f ""
    r "psql muet → illisible"        illisible   "hostachy_postgres" "" ""
    echo "== la requête passe par l'entrée de psql, guillemets intacts =="
    docker() { cat; }
    got=$(pgq_local "select pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')")
    [ "$got" = "select pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')" ] \
        && echo "PASS  la requête arrive entière" || { echo "FAIL  requête reçue : $got"; st=1; }
    unset -f docker
    [ "$st" -eq 0 ] && echo "lib-promotion : tous les cas passent."
    exit "$st"
fi
