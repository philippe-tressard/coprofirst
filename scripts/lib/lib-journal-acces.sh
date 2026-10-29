#!/bin/bash
# =============================================================================
#  lib-journal-acces.sh — C36 : le journal d'accès de Caddy est-il écrit, et que
#                         dit-il des erreurs serveur des dernières 24 h ?
#
#  Né de #1588 (audit du 02/10/2026) : le journal d'accès vivait sur la sortie
#  standard du conteneur, recréé à chaque déploiement (70 lignes au moment de
#  l'audit) — aucun 5xx de la veille n'était observable. Il est désormais un
#  fichier du volume `caddy_logs` (`Caddyfile`, bloc `log journal`), anonyme et
#  roulé sur 7 jours au plus. Un journal que personne ne lit ne sert à rien
#  (`standards/04` §7) : ce contrôle est son destinataire.
#
#  Ce que C36 mesure, sur le nœud ACTIF seulement (le standby ne sert rien) :
#    1. le journal est-il écrit ? La dernière ligne date de moins d'une heure
#       (la sonde LAN de health-watch passe par Caddy toutes les quelques
#       minutes : un site vivant écrit en permanence) ;
#    2. combien d'erreurs serveur INATTENDUES (500, 504) sur 24 h ? Un 500 est
#       une exception non gérée de l'API. Les 502/503 sont comptés à part : ce
#       sont les redémarrages des conteneurs d'un déploiement, pas des défauts.
#
#  Lecture seule : `docker exec hostachy_caddy tail` sur un fichier de LOG de
#  Caddy — jamais la base. Tout en WARN (digest quotidien).
#
#  SOURCÉ (mode 100644) par `lib-collecte.sh` (`COLLECT_ACCES`, repris dans
#  COLLECT) ; `acces_caddy_verdicts` est appelé par `lib-conformite.sh`.
#  ⚠️ `acces_caddy_verdicts` emploie `ok`, `warn`, `$SELF` et `$S_active`.
#  Autotest : bash scripts/lib/lib-journal-acces.sh --selftest
# =============================================================================

#: Au-delà, le journal est dit « plus écrit » — secondes.
ACCES_CADDY_PERIME_S="${ACCES_CADDY_PERIME_S:-3600}"

# ── La collecte, exécutée sur CHAQUE nœud (reprise par COLLECT) ──────────────
#  Même contrainte que `lib-collecte.sh` : chaîne entre guillemets SIMPLES, donc
#  AUCUNE apostrophe dans le fragment, même en commentaire. Le programme awk est
#  donc entre guillemets doubles (`\$0`, `\"` échappés). Tout s'explique ici :
#   - acces_caddy : « ok:<âge>:<requêtes>:<500+504>:<autres 5xx> » ; VIDE si
#     Caddy ne tourne pas, si le fichier est absent ou sans ligne datée — cas
#     zéro : sans le marqueur « ok: », « aucune erreur » et « rien mesuré »
#     seraient indiscernables ;
#   - `tail -n 50000` borne la lecture (un fichier roulé à 10 Mo en tient ~50 000) ;
#   - la fenêtre de 24 h se juge sur le `ts` de chaque ligne, jamais sur sa
#     position : le fichier roule par taille, pas par jour.
COLLECT_ACCES='
if [ -n "$(docker ps -q -f name=hostachy_caddy 2>/dev/null)" ]; then
echo "acces_caddy=$(docker exec hostachy_caddy tail -n 50000 /var/log/caddy/access.log 2>/dev/null | awk -v m=$(date +%s) "BEGIN{n=0;a=0;b=0;t=0} { if (match(\$0, /\"ts\":[0-9]+/)) { ts=substr(\$0, RSTART+5, RLENGTH-5)+0; if (ts>t) t=ts; if (ts>=m-86400) { n++; if (match(\$0, /\"status\":[0-9]+/)) { s=substr(\$0, RSTART+9, RLENGTH-9)+0; if (s==500||s==504) a++; else if (s>=500) b++ } } } } END{ if (t==0) print \"\"; else print \"ok:\" (m-t) \":\" n \":\" a \":\" b }")"
else
echo "acces_caddy="
fi
'

# ── Décisions PURES (aucun effet de bord) ────────────────────────────────────

#  $1 le relevé « ok:100:5:2:1 » → « 100 5 2 1 » (âge, requêtes, 500/504, autres
#  5xx) ; échoue sans le marqueur « ok: » ou si un champ n'est pas un entier.
acces_champs() {
    local v a n e o
    case "${1:-}" in ok:*) v="${1#ok:}" ;; *) return 1 ;; esac
    IFS=: read -r a n e o <<< "$v"
    for x in "$a" "$n" "$e" "$o"; do
        case "$x" in ''|*[!0-9]*) return 1 ;; esac
    done
    printf '%s %s %s %s' "$a" "$n" "$e" "$o"
}

#  $1 le relevé · $2 le seuil de péremption (s) → OK | ERREURS | PERIME | INCONNU
#  Un journal non écrit prime sur le compte d'erreurs : un fichier muet ne dit
#  rien des erreurs qui ont pu avoir lieu depuis.
verdict_acces_caddy() {
    local c a n e o
    c=$(acces_champs "${1:-}") || { echo INCONNU; return; }
    read -r a n e o <<< "$c"
    if [ "$a" -gt "${2:-$ACCES_CADDY_PERIME_S}" ]; then echo PERIME
    elif [ "$e" -gt 0 ]; then echo ERREURS
    else echo OK; fi
}

# ── C36. Le journal d'accès, sur le nœud actif ───────────────────────────────
acces_caddy_verdicts() {
    local c a n e o
    if [ "${S_active:-}" != "${SELF:-}" ]; then
        ok "Journal d'accès de Caddy : sans objet sur $SELF (standby — il ne sert pas le site)"
        return
    fi
    c=$(acces_champs "${S_acces_caddy:-}") || c=''
    [ -z "$c" ] || read -r a n e o <<< "$c"
    case "$(verdict_acces_caddy "${S_acces_caddy:-}" "$ACCES_CADDY_PERIME_S")" in
        OK)      ok   "Journal d'accès de Caddy sur $SELF : $n requêtes en 24 h, aucune erreur 500/504, $o réponse(s) 502/503 (redémarrages de conteneurs)" ;;
        ERREURS) warn "Journal d'accès de Caddy sur $SELF : $e erreur(s) serveur 500/504 en 24 h sur $n requêtes (+ $o réponse(s) 502/503) — une exception non gérée de l'API : 'docker exec hostachy_caddy grep -E \"\\\"status\\\":(500|504)\" /var/log/caddy/access.log' donne le chemin et l'heure (#1588)" ;;
        PERIME)  warn "Journal d'accès de Caddy sur $SELF : dernière ligne il y a $(( a / 60 )) min (> $(( ACCES_CADDY_PERIME_S / 60 ))) — il n'est plus écrit alors que le site est servi ; 'docker exec hostachy_caddy ls -l /var/log/caddy' et le volume caddy_logs (#1588)" ;;
        *)       warn "Journal d'accès de Caddy sur $SELF INCONNU (Caddy arrêté, fichier absent ou sans ligne datée : '${S_acces_caddy:-vide}') — ni vert ni rouge ; normal juste après le premier déploiement de #1588" ;;
    esac
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → ${r:-(rien)}" || { echo "FAIL  $1  attendu=${2:-(rien)} obtenu=${r:-(rien)}"; st=1; }; }

    echo "== la décision =="
    t "journal frais, aucune erreur"            OK       verdict_acces_caddy "ok:100:5:0:0" 3600
    t "…502/503 seuls : des redémarrages, OK"   OK       verdict_acces_caddy "ok:100:5:0:3" 3600
    t "un 500 en 24 h"                          ERREURS  verdict_acces_caddy "ok:100:5:1:0" 3600
    t "journal muet depuis 2 h"                 PERIME   verdict_acces_caddy "ok:7200:5:0:0" 3600
    t "muet ET des erreurs : PERIME prime"      PERIME   verdict_acces_caddy "ok:7200:5:4:0" 3600
    t "exactement au seuil : encore frais"      OK       verdict_acces_caddy "ok:3600:5:0:0" 3600
    t "relevé vide → INCONNU, jamais OK"        INCONNU  verdict_acces_caddy "" 3600
    t "sans marqueur « ok: » → INCONNU"         INCONNU  verdict_acces_caddy "100:5:0:0" 3600
    t "champ non entier → INCONNU"              INCONNU  verdict_acces_caddy "ok:100:x:0:0" 3600
    t "champ manquant → INCONNU"                INCONNU  verdict_acces_caddy "ok:100:5:0" 3600

    echo "== la collecte, exécutée sur un journal simulé aux formes RÉELLES (Caddy 2.11) =="
    #  now = 1791300000 ; la fenêtre commence à 1791213600.
    date() { echo 1791300000; }
    docker() {
        case "$1" in
            ps) echo abc123 ;;
            exec) cat <<'X'
{"level":"info","ts":1791200000.1,"logger":"http.log.access.journal","msg":"handled request","request":{"proto":"HTTP/1.1","method":"GET","host":"h","uri":"/a"},"bytes_read":0,"user_id":"","duration":0.01,"size":2,"status":500}
{"level":"info","ts":1791250000.5,"logger":"http.log.access.journal","msg":"handled request","request":{"proto":"HTTP/1.1","method":"GET","host":"h","uri":"/b"},"bytes_read":0,"user_id":"","duration":0.01,"size":2,"status":503}
{"level":"info","ts":1791280000.9,"logger":"http.log.access.journal","msg":"handled request","request":{"proto":"HTTP/1.1","method":"GET","host":"h","uri":"/c"},"bytes_read":0,"user_id":"","duration":0.01,"size":2,"status":504}
{"level":"info","ts":1791290000.2,"logger":"http.log.access.journal","msg":"handled request","request":{"proto":"HTTP/1.1","method":"POST","host":"h","uri":"/d"},"bytes_read":0,"user_id":"","duration":0.01,"size":2,"status":500}
{"level":"info","ts":1791299000.0,"logger":"http.log.access.journal","msg":"handled request","request":{"proto":"HTTP/1.1","method":"GET","host":"h","uri":"/e"},"bytes_read":0,"user_id":"","duration":0.01,"size":2,"status":200}
{"level":"info","ts":1791299900.7,"logger":"http.log.access.journal","msg":"handled request","request":{"proto":"HTTP/1.1","method":"GET","host":"h","uri":"/f"},"bytes_read":0,"user_id":"","duration":0.01,"size":2,"status":404}
X
            ;;
        esac
    }
    champ() { eval "$COLLECT_ACCES" | sed -n "s/^$1=//p"; }
    #  L'âge est celui de la dernière ligne (100 s) ; la ligne de 1791200000 (500) est HORS fenêtre ;
    #  500 + 504 = 2 erreurs ; un 503 ; cinq requêtes dans la fenêtre.
    t "collecte : âge, requêtes, 500/504, autres 5xx" "ok:100:5:2:1" champ acces_caddy
    docker() { case "$1" in ps) echo abc123 ;; exec) printf '' ;; esac; }
    t "collecte : fichier vide ou absent → VIDE (INCONNU)" "" champ acces_caddy
    docker() { case "$1" in ps) : ;; esac; }
    t "collecte : Caddy arrêté → VIDE, jamais « ok: »" "" champ acces_caddy
    docker() { case "$1" in ps) echo abc123 ;; exec) echo "pas du json" ;; esac; }
    t "collecte : lignes sans ts → VIDE" "" champ acces_caddy
    unset -f docker date champ
    if bash -n <(printf '%s' "$COLLECT_ACCES") 2>/dev/null; then echo "PASS  COLLECT_ACCES est du shell valide"
    else echo "FAIL  COLLECT_ACCES est du shell INVALIDE (apostrophe dans la chaîne ?)"; st=1; fi
    t "collecte : aucune apostrophe dans la chaîne" 0 eval 'printf "%s" "$COLLECT_ACCES" | grep -c "$(printf "\047")"'

    echo "== les constats =="
    ok()   { echo "OK $*"; }
    warn() { echo "WARN $*"; }
    SELF=rpi2 S_active=rpi2 ACCES_CADDY_PERIME_S=3600
    S_acces_caddy="ok:100:5:0:3"; sortie=$(acces_caddy_verdicts)
    t "actif sain → un OK qui nomme le nœud et compte les 502/503" "1|1" \
      eval 'echo "$(grep -c "^OK Journal d.accès de Caddy sur rpi2 : 5 requêtes en 24 h, aucune erreur 500/504, 3 réponse" <<< "$sortie")|$(grep -c "^OK" <<< "$sortie")"'
    S_acces_caddy="ok:100:5:2:0"; sortie=$(acces_caddy_verdicts)
    t "faute injectée : 2 erreurs 500/504 → UN WARN qui nomme rpi2" "1" \
      eval 'grep -c "^WARN Journal d.accès de Caddy sur rpi2 : 2 erreur(s) serveur 500/504" <<< "$sortie"'
    S_acces_caddy="ok:7200:5:0:0"; sortie=$(acces_caddy_verdicts)
    t "journal muet 120 min → WARN « plus écrit »" "1" \
      eval 'grep -c "^WARN .*dernière ligne il y a 120 min" <<< "$sortie"'
    S_acces_caddy=""; sortie=$(acces_caddy_verdicts)
    t "rien mesuré sur l'actif → WARN INCONNU, jamais OK" "1|0" \
      eval 'echo "$(grep -c "^WARN .* INCONNU" <<< "$sortie")|$(grep -c "^OK" <<< "$sortie")"'
    SELF=rpi1 S_active=rpi2 S_acces_caddy=""; sortie=$(acces_caddy_verdicts)
    t "standby : sans objet, ni WARN ni mesure" "1|0" \
      eval 'echo "$(grep -c "^OK .* sans objet sur rpi1" <<< "$sortie")|$(grep -c "^WARN" <<< "$sortie")"'
    unset -f ok warn

    [ "$st" -eq 0 ] && echo "lib-journal-acces : tous les cas passent."
    exit "$st"
fi
