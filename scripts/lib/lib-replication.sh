#!/bin/bash
# =============================================================================
#  lib-replication.sh — C37 : la base PostgreSQL est-elle répliquée vers le
#  standby ? (module à sourcer, DI-7b, #1781)
#
#  Sous PostgreSQL (D16), un primaire tourne sur l'actif et une RÉPLIQUE en
#  continu sur le standby. Ce que ce contrôle protège :
#    • deux primaires à la fois — le split-brain des données, celui qu'aucun
#      compte de conteneurs ne voit ;
#    • une réplique arrêtée, déconnectée ou en retard — le failover promouvrait
#      une base périmée sans que rien ne l'ait dit ;
#    • un actif qui porterait une réplique (rôles inversés après un incident).
#
#  Aucune base sur AUCUN des deux nœuds est un échec : l'application n'a pas
#  d'autre base que PostgreSQL.
#
#  Collecte, décision PURE et constats vivent ensemble, comme C31 et C36.
#  La collecte ne lit la base QUE par `docker exec hostachy_postgres psql` :
#  PostgreSQL sert ses lecteurs.
#
#  Test : bash lib-replication.sh --selftest   (aucun effet de bord)
# =============================================================================

#: Retard toléré de la réplique, en octets de journal (au-delà : WARN).
REPLICATION_RETARD_MAX=67108864   # 64 Mio

# ── PURE : le moteur que `.env` désigne — par l'URL de sa base ───────────────
#  → postgresql|inconnu. `deploiement/standard/lib-installation.sh` en porte une
#  COPIE DÉCLARÉE (`test_deploiement_standard` exige deux corps identiques).
moteur_de_url() {
    case "${1:-}" in
        postgresql:*|postgresql+*)  echo postgresql ;;
        *)                          echo inconnu ;;
    esac
}


# ── PURE : `.env` désigne-t-il la base de l'application ? ────────────────────
#  Les scripts qui touchent la base, la promeuvent ou la restaurent posent CETTE
#  question avant tout geste : une URL qui ne désigne pas PostgreSQL est une
#  configuration que l'application ne sait pas servir — on REFUSE, on ne devine pas.
#  $1 DATABASE_URL → OK | REFUS:<raison>
verdict_base_configuree() {
    [ "$(moteur_de_url "${1:-}")" = postgresql ] \
        || { echo "REFUS:DATABASE_URL ne désigne pas PostgreSQL dans .env"; return; }
    echo OK
}

#  Une clé d'un fichier `.env`, sans guillemets ni retour chariot.
#  $1 = le fichier · $2 = clé
cle_env_fichier() {
    grep -m1 "^$2=" "$1" 2>/dev/null | cut -d= -f2- | tr -d "\"'\r"
}

#  Le verdict d'un fichier `.env` ($1, en général `$REPO/.env`). L'URL porte un
#  mot de passe : elle ne sort jamais de cette fonction, seul le verdict en sort.
base_configuree() {
    verdict_base_configuree "$(cle_env_fichier "$1" DATABASE_URL)"
}

#  Point 4 du pré-check : le verdict relevé sur l'actif → OK | FAIL | INCONNU
#  (rien de relevé : SSH muet, jamais un vert).
verdict_precheck_base() {
    case "${1:-}" in
        OK)      echo OK ;;
        REFUS:*) echo FAIL ;;
        *)       echo INCONNU ;;
    esac
}

# ── Collecte (insérée dans COLLECT : SANS apostrophe) ────────────────────────
#  pg_present  1 si le conteneur de la base tourne, 0 sinon
#  pg_recovery t (réplique) | f (primaire) | vide (illisible)
#  pg_flux     primaire : nombre de répliques qui rejouent son journal
#  pg_retard   primaire : retard maximal, en octets (-1 sans réplique)
#  pg_recepteur réplique : état de la réception (streaming attendu)
#  Une requête SQL sur la base de CE nœud → sa valeur brute, vide si illisible.
#  Définie ICI, une fois, et pour les deux usages : appelée telle quelle par un
#  script qui source ce module (`creer-base-plateforme.sh`), et recopiée par
#  `declare -f` dans la collecte, qui s'exécute sur le nœud distant. Jusqu'au
#  13/10/2026 elle n'existait QUE dans la chaîne : le script qui l'appelait
#  rendait « pgq: command not found » et refusait à tort (#1892).
pgq() { docker exec hostachy_postgres psql -U coprofirst -d coprofirst -Atqc "$1" 2>/dev/null; }

COLLECT_REPLICATION="
$(declare -f pgq)"'
echo "pg_present=$(docker ps --format "{{.Names}}" 2>/dev/null | grep -cx hostachy_postgres)"
echo "pg_recovery=$(pgq "select pg_is_in_recovery()")"
echo "pg_flux=$(pgq "select count(*) from pg_stat_replication where replay_lsn is not null")"
echo "pg_retard=$(pgq "select coalesce(max(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)), -1)::bigint from pg_stat_replication")"
echo "pg_recepteur=$(pgq "select status from pg_stat_wal_receiver")"
'

# ── PURE : l'état d'UN nœud → son verdict ────────────────────────────────────
#  $1 rôle attendu (actif|standby) · $2 pg_present · $3 pg_recovery · $4 pg_flux
#  · $5 pg_retard · $6 pg_recepteur · $7 seuil de retard
#  → ABSENT | ILLISIBLE | PRIMAIRE_OK | SANS_REPLIQUE | RETARD | REPLIQUE_OK
#    | DECONNECTEE | INVERSE
verdict_noeud_replication() {
    local role=$1 present=$2 rec=$3 flux=$4 retard=$5 recepteur=$6 seuil=$7
    [ "$present" = 1 ] || { echo ABSENT; return; }
    case "$rec" in t|f) ;; *) echo ILLISIBLE; return ;; esac
    if [ "$role" = actif ]; then
        [ "$rec" = f ] || { echo INVERSE; return; }
        case "$flux" in ''|*[!0-9]*) echo ILLISIBLE; return ;; esac
        [ "$flux" -ge 1 ] || { echo SANS_REPLIQUE; return; }
        case "$retard" in ''|*[!0-9-]*) echo ILLISIBLE; return ;; esac
        [ "$retard" -le "$seuil" ] && echo PRIMAIRE_OK || echo RETARD
    else
        [ "$rec" = t ] || { echo INVERSE; return; }
        [ "$recepteur" = streaming ] && echo REPLIQUE_OK || echo DECONNECTEE
    fi
}

# ── PURE : les deux nœuds → la réplication est-elle activée, et cohérente ? ──
#  $1 pg_present actif · $2 pg_present standby · $3 recovery actif · $4 recovery standby
#  → AUCUNE | PARTIELLE | DEUX_PRIMAIRES | NOEUDS
verdict_paire_replication() {
    local pa=$1 ps=$2 ra=$3 rs=$4
    [ "$pa" = 1 ] || [ "$ps" = 1 ] || { echo AUCUNE; return; }
    [ "$pa" = 1 ] && [ "$ps" = 1 ] && [ "$ra" = f ] && [ "$rs" = f ] && { echo DEUX_PRIMAIRES; return; }
    [ "$pa" = 1 ] && [ "$ps" = 1 ] || { echo PARTIELLE; return; }
    echo NOEUDS
}

# ── PURE : le point 22 du pré-check de MEP ───────────────────────────────────
#  Les champs collectés sur l'actif puis sur le standby (mêmes noms que C37) :
#  $1-$5 actif (present recovery flux retard recepteur) · $6-$10 standby (idem)
#  → OK | FAIL | INCONNU
verdict_precheck_replication() {
    local pa=$1 ra=$2 fa=$3 da=$4 ca=$5 ps=$6 rs=$7 fs=$8 ds=$9 cs=${10} va vs
    [ -n "$pa" ] && [ -n "$ps" ] || { echo INCONNU; return; }
    case "$(verdict_paire_replication "$pa" "$ps" "$ra" "$rs")" in
        AUCUNE|DEUX_PRIMAIRES|PARTIELLE) echo FAIL; return ;;
    esac
    va=$(verdict_noeud_replication actif "$pa" "$ra" "$fa" "$da" "$ca" "$REPLICATION_RETARD_MAX")
    vs=$(verdict_noeud_replication standby "$ps" "$rs" "$fs" "$ds" "$cs" "$REPLICATION_RETARD_MAX")
    [ "$va" = ILLISIBLE ] || [ "$vs" = ILLISIBLE ] && { echo INCONNU; return; }
    [ "$va" = PRIMAIRE_OK ] && [ "$vs" = REPLIQUE_OK ] && { echo OK; return; }
    echo FAIL
}

# ── C37. Les constats ────────────────────────────────────────────────────────
#  Variables de la collecte : S_* (ce nœud), P_* (le pair), S_active, SELF,
#  PEER, PEER_OK. Le pair muet : on ne parle que de ce nœud.
replication_verdicts() {
    local actif standby A Sb pa ps ra rs n role v p
    if [ "${S_active:-}" = "$SELF" ]; then actif=$SELF; standby=$PEER; A=S; Sb=P
    else actif=$PEER; standby=$SELF; A=P; Sb=S; fi
    #  Pair muet : la paire ne se juge pas ; ce nœud seul, par la boucle ci-dessous.
    if [ "${PEER_OK:-1}" -eq 0 ]; then
        eval "pa=\${${A}_pg_present:-0} ps=\${${Sb}_pg_present:-0} ra=\${${A}_pg_recovery:-} rs=\${${Sb}_pg_recovery:-}"
        case "$(verdict_paire_replication "$pa" "$ps" "$ra" "$rs")" in
            AUCUNE)         fail "AUCUNE base PostgreSQL sur $actif ni sur $standby — l'application n'a pas de base : docker ps ; docker logs hostachy_postgres --tail 30"; return ;;
            DEUX_PRIMAIRES) fail "DEUX PRIMAIRES PostgreSQL ($actif et $standby) : les données divergent — isoler $standby (docker compose stop postgres) puis le reconstruire en réplique (sudo bash /opt/5hostachy/scripts/exploitation/reconstruire-replique.sh --oui)"; return ;;
            PARTIELLE)      warn "Réplication PostgreSQL PARTIELLE : la base tourne sur $([ "$pa" = 1 ] && echo "$actif" || echo "$standby") seulement — l'autre nœud n'a pas de base ; reconstruire la réplique sur le standby" ;;
        esac
    fi
    for n in "$actif" "$standby"; do
        [ "$n" = "$SELF" ] && p=S || p=P
        [ "$p" = P ] && [ "${PEER_OK:-1}" -ne 0 ] && continue
        role=$([ "$n" = "$actif" ] && echo actif || echo standby)
        eval "v=\$(verdict_noeud_replication $role \"\${${p}_pg_present:-0}\" \"\${${p}_pg_recovery:-}\" \"\${${p}_pg_flux:-}\" \"\${${p}_pg_retard:-}\" \"\${${p}_pg_recepteur:-}\" $REPLICATION_RETARD_MAX)"
        case "$v" in
            PRIMAIRE_OK)   ok   "Base PostgreSQL de $n : primaire, sa réplique rejoue le journal" ;;
            REPLIQUE_OK)   ok   "Base PostgreSQL de $n : réplique, réception en continu" ;;
            ABSENT)        warn "Base PostgreSQL absente sur $n ($role) — conteneur hostachy_postgres arrêté" ;;
            SANS_REPLIQUE) fail "Base PostgreSQL de $n : primaire SANS réplique — un failover promouvrait une base périmée ; vérifier la réplique du standby" ;;
            RETARD)        warn "Base PostgreSQL de $n : la réplique a plus de $((REPLICATION_RETARD_MAX / 1048576)) Mio de retard" ;;
            DECONNECTEE)   fail "Base PostgreSQL de $n : réplique DÉCONNECTÉE du primaire — elle ne reçoit plus le journal" ;;
            INVERSE)       fail "Base PostgreSQL de $n : rôle INVERSÉ ($role mais $([ "$role" = actif ] && echo réplique || echo primaire)) — à corriger avant tout failover" ;;
            *)             warn "Base PostgreSQL de $n INCONNUE (psql illisible) — ni vert ni rouge" ;;
        esac
    done
}

# ── Autotest (job CI `test-scripts`) ──────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=${r:-(rien)}"; st=1; }; }
    M=$REPLICATION_RETARD_MAX
    echo "== un nœud =="
    t "actif primaire, une réplique à jour"       PRIMAIRE_OK   verdict_noeud_replication actif 1 f 1 0 "" "$M"
    t "actif primaire, aucune réplique"           SANS_REPLIQUE verdict_noeud_replication actif 1 f 0 -1 "" "$M"
    t "actif primaire, réplique en retard"        RETARD        verdict_noeud_replication actif 1 f 1 $((M + 1)) "" "$M"
    t "exactement au seuil : encore à jour"       PRIMAIRE_OK   verdict_noeud_replication actif 1 f 1 "$M" "" "$M"
    t "actif qui porte une RÉPLIQUE"              INVERSE       verdict_noeud_replication actif 1 t 0 -1 "" "$M"
    t "standby réplique en continu"               REPLIQUE_OK   verdict_noeud_replication standby 1 t "" "" streaming "$M"
    t "standby réplique déconnectée"              DECONNECTEE   verdict_noeud_replication standby 1 t "" "" "" "$M"
    t "standby qui s'est PROMU"                   INVERSE       verdict_noeud_replication standby 1 f 0 -1 "" "$M"
    t "conteneur arrêté"                          ABSENT        verdict_noeud_replication standby 0 "" "" "" "" "$M"
    t "psql illisible → INCONNU, jamais OK"       ILLISIBLE     verdict_noeud_replication actif 1 "" "" "" "" "$M"
    t "compte illisible → INCONNU"                ILLISIBLE     verdict_noeud_replication actif 1 f x 0 "" "$M"
    echo "== la paire =="
    t "aucune base sur les deux nœuds"            AUCUNE         verdict_paire_replication 0 0 "" ""
    t "deux primaires"                            DEUX_PRIMAIRES verdict_paire_replication 1 1 f f
    t "base sur un seul nœud"                     PARTIELLE      verdict_paire_replication 1 0 f ""
    t "primaire + réplique"                       NOEUDS         verdict_paire_replication 1 1 f t
    echo "== le moteur configuré =="
    t "une autre URL → inconnu"           inconnu    moteur_de_url "mysql://u:p@h/b"
    t "PostgreSQL par psycopg"            postgresql moteur_de_url "postgresql+psycopg://u:p@postgres:5432/coprofirst"
    t "PostgreSQL sans pilote nommé"      postgresql moteur_de_url "postgresql://u:p@h/b"
    t "variable absente → inconnu"        inconnu    moteur_de_url ""

    echo "== la base configurée =="
    prefixe() { local r; r=$("$@"); echo "${r%%:*}"; }   # REFUS:<raison> → REFUS
    U="postgresql+psycopg://u:p@postgres:5432/coprofirst"
    t "URL PostgreSQL"                    OK    verdict_base_configuree "$U"
    t "URL d'un autre moteur → refus"     REFUS prefixe verdict_base_configuree "mysql://u:p@h/b"
    t "URL absente → refus, jamais OK"    REFUS prefixe verdict_base_configuree ""
    st_env=$(mktemp -d)
    printf 'A=1\r\nDATABASE_URL="%s"\r\n' "$U" > "$st_env/env"
    t "fichier réel, guillemets et CRLF"  OK    base_configuree "$st_env/env"
    t "fichier absent → refus"            REFUS prefixe base_configuree "$st_env/absent"
    rm -rf "$st_env"
    t "point 4 : configuration juste"     OK      verdict_precheck_base OK
    t "point 4 : refus → FAIL"            FAIL    verdict_precheck_base "REFUS:URL d'un autre moteur"
    t "point 4 : rien relevé → INCONNU"   INCONNU verdict_precheck_base ""
    echo "== le point 22 du pré-check =="
    t "aucune base : échec, jamais OK"        FAIL       verdict_precheck_replication 0 "" "" "" "" 0 "" "" "" ""
    t "primaire + réplique saines"            OK         verdict_precheck_replication 1 f 1 0 "" 1 t "" "" streaming
    t "réplique déconnectée"                  FAIL       verdict_precheck_replication 1 f 0 -1 "" 1 t "" "" ""
    t "deux primaires"                        FAIL       verdict_precheck_replication 1 f 0 -1 "" 1 f 0 -1 ""
    t "standby muet (collecte vide)"          INCONNU    verdict_precheck_replication 1 f 1 0 "" "" "" "" "" ""
    t "psql illisible sur l'actif"            INCONNU    verdict_precheck_replication 1 "" "" "" "" 1 t "" "" streaming
    echo "== la collecte est du shell valide, sans apostrophe =="
    if bash -n <(printf '%s' "$COLLECT_REPLICATION") 2>/dev/null && ! grep -q "'" <<<"$COLLECT_REPLICATION"; then
        echo "PASS  COLLECT_REPLICATION"
    else echo "FAIL  COLLECT_REPLICATION invalide ou porte une apostrophe"; st=1; fi
    echo "== la collecte, exécutée avec un docker simulé =="
    docker() {
        case "$1" in
            ps) echo hostachy_postgres ;;
            exec) case "$*" in
                      *pg_is_in_recovery*) echo f ;;
                      *count*)             echo 1 ;;
                      *pg_wal_lsn_diff*)   echo 0 ;;
                      *wal_receiver*)      echo "" ;;
                  esac ;;
        esac
    }
    #  AVANT l'eval, qui la redéfinirait : c'est la fonction du MODULE qu'on éprouve,
    #  celle qu'appelle un script qui le source (#1892).
    t "pgq, fonction du module (pas seulement de la collecte)" f pgq "select pg_is_in_recovery()"
    sortie=$(eval "$COLLECT_REPLICATION")
    t "primaire simulé : présent, f, 1, 0" "1|f|1|0" \
      bash -c "printf '%s' \"$sortie\" | sed -n 's/^pg_present=//p;s/^pg_recovery=//p;s/^pg_flux=//p;s/^pg_retard=//p' | paste -sd'|'"
    unset -f docker
    echo "== les constats =="
    ok() { echo "[ OK ] $*"; }; warn() { echo "[WARN] $*"; }; fail() { echo "[FAIL] $*"; }
    SELF=rpi2 PEER=rpi1 PEER_OK=0 S_active=rpi2
    S_pg_present=0 P_pg_present=0
    t "aucune base : un seul constat, en échec" "0|1" bash -c "$(declare -f replication_verdicts verdict_paire_replication verdict_noeud_replication ok warn fail); SELF=$SELF PEER=$PEER PEER_OK=0 S_active=$S_active S_pg_present=0 P_pg_present=0; REPLICATION_RETARD_MAX=$M; r=\$(replication_verdicts); printf '%s|%s' \"\$(grep -c '^\[ OK \]' <<< \"\$r\")\" \"\$(grep -c '^\[FAIL\]' <<< \"\$r\")\""
    t "primaire + réplique saines : deux OK" "2|0" bash -c "$(declare -f replication_verdicts verdict_paire_replication verdict_noeud_replication ok warn fail); SELF=rpi2 PEER=rpi1 PEER_OK=0 S_active=rpi2 S_pg_present=1 S_pg_recovery=f S_pg_flux=1 S_pg_retard=0 P_pg_present=1 P_pg_recovery=t P_pg_recepteur=streaming; REPLICATION_RETARD_MAX=$M; r=\$(replication_verdicts); printf '%s|%s' \"\$(grep -c '^\[ OK \]' <<< \"\$r\")\" \"\$(grep -c '^\[FAIL\]' <<< \"\$r\")\""
    t "faute injectée : deux primaires → un FAIL" "0|1" bash -c "$(declare -f replication_verdicts verdict_paire_replication verdict_noeud_replication ok warn fail); SELF=rpi2 PEER=rpi1 PEER_OK=0 S_active=rpi2 S_pg_present=1 S_pg_recovery=f P_pg_present=1 P_pg_recovery=f; REPLICATION_RETARD_MAX=$M; r=\$(replication_verdicts); printf '%s|%s' \"\$(grep -c '^\[ OK \]' <<< \"\$r\")\" \"\$(grep -c '^\[FAIL\]' <<< \"\$r\")\""
    t "faute injectée : réplique déconnectée → un FAIL" "1|1" bash -c "$(declare -f replication_verdicts verdict_paire_replication verdict_noeud_replication ok warn fail); SELF=rpi2 PEER=rpi1 PEER_OK=0 S_active=rpi2 S_pg_present=1 S_pg_recovery=f S_pg_flux=1 S_pg_retard=0 P_pg_present=1 P_pg_recovery=t P_pg_recepteur=; REPLICATION_RETARD_MAX=$M; r=\$(replication_verdicts); printf '%s|%s' \"\$(grep -c '^\[ OK \]' <<< \"\$r\")\" \"\$(grep -c '^\[FAIL\]' <<< \"\$r\")\""
    [ "$st" -eq 0 ] && echo "lib-replication : tous les cas passent."
    exit "$st"
fi
