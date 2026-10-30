#!/bin/bash
# =============================================================================
#  lib-audit-securite.sh — QUAND l'audit de sécurité nocturne se lance, et C40 :
#  a-t-il tourné, et jusqu'au bout ?
#
#  Module SOURCÉ (mode 100644) par `check-reliability.sh` (qui le lance et pose
#  C40) et par `audit-securite.sh` (qui pose la marque). Jamais exécuté par un
#  cron. Autotest : bash scripts/lib/lib-audit-securite.sh --selftest
#
#  ── POURQUOI PAS UN CRON DE PLUS ─────────────────────────────────────────────
#
#  Un cron root se pose à la main sur chaque nœud (`infra/points-entree/
#  cron-root.crontab` : « geste explicite, jamais automatique »), et C22 crie
#  l'écart jusqu'à ce que les deux nœuds l'aient. `check-reliability.sh`, lui,
#  tourne DÉJÀ en root, toutes les quinze minutes, sur les deux nœuds : il lance
#  l'audit au premier passage après `AUDIT_SECURITE_HEURE`, une fois par jour
#  civil, et le juge aux passages suivants. Rien à poser, rien à comparer.
#
#  La MARQUE (`AUDIT_SECURITE_MARQUE`, chez root, hors de l'arbre déployé) porte
#  trois mots : « <epoch> <jour> <état> ». Le lanceur l'écrit AVANT de lancer
#  (« lance ») : un audit qui meurt n'est pas relancé toutes les quinze minutes
#  (96 essais par jour, c'est le mode de panne de `check-stack.sh`) — il est
#  dit, une fois, par C40. L'audit la réécrit à sa fin avec son code (« 0 »,
#  « 2 »…). C40 lit l'âge et l'état :
#    OK       — l'audit s'est terminé il y a moins de AUDIT_SECURITE_RETARD_H ;
#    RETARD   — la dernière fin date de plus ; ou jamais aucune (nœud neuf) ;
#    INCOMPLET — lancé, jamais terminé (mort sous `set -e`, tué, poste figé) ;
#    INCONNU  — la marque est illisible.
#  Les FAIL de l'audit lui-même partent par SON courriel ; C40 ne redit pas
#  son contenu, il dit qu'il a eu lieu (`standards/04` §4, le battement).
#
#  Fonctions PURES, sauf `audit_securite_lancer_si_du`, isolée en bas.
# =============================================================================

#: La marque, chez root. Le dossier est celui de la référence de S3.
AUDIT_SECURITE_DIR="${AUDIT_SECURITE_DIR:-/var/lib/hostachy/audit-securite}"
AUDIT_SECURITE_MARQUE="${AUDIT_SECURITE_MARQUE:-$AUDIT_SECURITE_DIR/dernier}"
#: À partir de quelle heure LOCALE du jour l'audit se lance (04 : après la
#: bascule de 02:00 et le redémarrage éventuel du standby, avant 06:00 où
#: l'API envoie son contrôle de santé — le digest de l'audit l'y rejoint).
AUDIT_SECURITE_HEURE="${AUDIT_SECURITE_HEURE:-4}"
#: Au-delà, C40 dit RETARD : 24 h de régime, plus deux heures de marge.
AUDIT_SECURITE_RETARD_H="${AUDIT_SECURITE_RETARD_H:-26}"
#: Le journal de l'audit (roté par `maintenance.sh`, glob hostachy-*.log).
AUDIT_SECURITE_JOURNAL="${AUDIT_SECURITE_JOURNAL:-/var/log/hostachy-audit-securite.log}"
#: Un audit ne dure pas plus que cela (secondes) : au-delà, il est tué, et C40
#: le dira INCOMPLET.
AUDIT_SECURITE_DELAI_S="${AUDIT_SECURITE_DELAI_S:-900}"

# ── Décisions PURES ──────────────────────────────────────────────────────────

#  $1 = la marque (« epoch jour état », vide si absente) · $2 = le jour (AAAA-MM-JJ)
#  $3 = l'heure locale (0-23) → oui | non
audit_securite_du() {
    local marque=${1:-} jour=${2:-} heure=${3:-} m_jour
    case "$heure" in ''|*[!0-9]*) echo non; return 0 ;; esac
    [ "${heure#0}" -ge "$AUDIT_SECURITE_HEURE" ] || { echo non; return 0; }
    [ -n "$jour" ] || { echo non; return 0; }
    read -r _ m_jour _ <<< "$marque"
    [ "$m_jour" != "$jour" ] && echo oui || echo non
}

#  $1 = la marque · $2 = l'instant (epoch) → OK | RETARD:<heures> | INCOMPLET:<heures> | INCONNU
audit_securite_verdict() {
    local marque=${1:-} now=${2:-} epoch jour etat age_h
    [ -n "$marque" ] || { echo "RETARD:jamais"; return 0; }
    read -r epoch jour etat <<< "$marque"
    case "$epoch" in ''|*[!0-9]*) echo INCONNU; return 0 ;; esac
    case "$now" in ''|*[!0-9]*) echo INCONNU; return 0 ;; esac
    age_h=$(( (now - epoch) / 3600 ))
    [ "$age_h" -ge 0 ] || { echo INCONNU; return 0; }
    case "$etat" in
        lance) echo "INCOMPLET:$age_h" ;;
        [0-9]*) [ "$age_h" -le "$AUDIT_SECURITE_RETARD_H" ] && echo OK || echo "RETARD:$age_h" ;;
        *) echo INCONNU ;;
    esac
}

#  La marque à écrire. $1 = epoch · $2 = jour · $3 = état
audit_securite_marque() { printf '%s %s %s\n' "${1:-}" "${2:-}" "${3:-}"; }

# ── C40 (constats : emploie `ok`, `warn` et `$SELF` de l'appelant) ───────────
audit_securite_verdicts() {
    local marque="" v
    [ -r "$AUDIT_SECURITE_MARQUE" ] && marque=$(head -1 "$AUDIT_SECURITE_MARQUE")
    v=$(audit_securite_verdict "$marque" "$(date +%s)")
    case "$v" in
        OK)            ok   "Audit de sécurité nocturne sur $SELF : terminé il y a $(( ($(date +%s) - ${marque%% *}) / 3600 )) h (S1–S6, journal $AUDIT_SECURITE_JOURNAL)" ;;
        RETARD:jamais) warn "Audit de sécurité nocturne sur $SELF : jamais exécuté — il se lance au premier passage de check-reliability après ${AUDIT_SECURITE_HEURE}h ; sa référence S3 se pose ensuite par 'sudo bash /opt/5hostachy/scripts/exploitation/audit-securite.sh --accepter'" ;;
        RETARD:*)      warn "Audit de sécurité nocturne sur $SELF : dernier passage il y a ${v#RETARD:} h (> $AUDIT_SECURITE_RETARD_H) — check-reliability ne l'a pas lancé, ou la marque n'est plus écrite ($AUDIT_SECURITE_MARQUE)" ;;
        INCOMPLET:*)   warn "Audit de sécurité nocturne sur $SELF : lancé il y a ${v#INCOMPLET:} h et JAMAIS terminé — mort en route, lire $AUDIT_SECURITE_JOURNAL ; il se relancera demain" ;;
        *)             warn "Audit de sécurité nocturne sur $SELF : marque illisible ('$marque') — ni vert ni rouge" ;;
    esac
}

# ── Le lancement (effet de bord : écrit la marque, exécute l'audit) ──────────
#  $1 = le dépôt. Appelé par check-reliability.sh en root, après ses propres
#  constats : la durée de l'audit n'entre pas dans celle du passage, et un
#  audit qui meurt ne prive pas le passage de sa notification.
audit_securite_lancer_si_du() {
    local repo=${1:-/opt/5hostachy} marque="" jour heure
    [ "$(id -u)" -eq 0 ] || return 0
    [ -r "$AUDIT_SECURITE_MARQUE" ] && marque=$(head -1 "$AUDIT_SECURITE_MARQUE")
    jour=$(date +%F); heure=$(date +%H)
    [ "$(audit_securite_du "$marque" "$jour" "$heure")" = oui ] || return 0
    #  Rien ici ne peut arrêter l'appelant, même sous `set -e` : une marque qu'on
    #  ne peut pas écrire → pas de lancement (sinon un lancement par quart
    #  d'heure) ; un script absent, mort ou figé → son code, dit, et C40 le lit.
    mkdir -p -m 700 "$AUDIT_SECURITE_DIR" 2>/dev/null || true
    if ! audit_securite_marque "$(date +%s)" "$jour" lance > "$AUDIT_SECURITE_MARQUE" 2>/dev/null; then
        echo "[INFO] Audit de sécurité nocturne : marque non inscriptible ($AUDIT_SECURITE_MARQUE) — non lancé"
        return 0
    fi
    echo "[INFO] Audit de sécurité nocturne : lancé (journal $AUDIT_SECURITE_JOURNAL)"
    local rc=0
    timeout "$AUDIT_SECURITE_DELAI_S" bash "$repo/scripts/exploitation/audit-securite.sh" >> "$AUDIT_SECURITE_JOURNAL" 2>&1 || rc=$?
    echo "[INFO] Audit de sécurité nocturne : terminé (code $rc)"
    return 0
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
audit_securite_selftest() {
    local st=0
    t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; }; }
    echo "== self-test lib-audit-securite (lancement, C40) =="
    t "jamais lancé, 04:06 → dû" oui "$(audit_securite_du "" 2026-10-30 04)"
    t "jamais lancé, 03:51 → pas encore" non "$(audit_securite_du "" 2026-10-30 03)"
    t "déjà fait aujourd'hui → non" non "$(audit_securite_du "1761800000 2026-10-30 0" 2026-10-30 09)"
    t "fait hier → dû" oui "$(audit_securite_du "1761700000 2026-10-29 0" 2026-10-30 04)"
    t "lancé aujourd'hui et mort → pas relancé (une fois par jour)" non "$(audit_securite_du "1761800000 2026-10-30 lance" 2026-10-30 12)"
    t "heure « 23 » (sans zéro) → dû" oui "$(audit_securite_du "" 2026-10-30 23)"
    t "heure illisible → non" non "$(audit_securite_du "" 2026-10-30 "")"
    t "jour illisible → non" non "$(audit_securite_du "" "" 05)"
    local N=1761800000
    t "C40 : terminé il y a 3 h" OK "$(audit_securite_verdict "$((N - 3*3600)) 2026-10-30 0" "$N")"
    t "C40 : terminé en échec il y a 3 h reste OK (il a eu lieu ; ses FAIL ont leur courriel)" OK \
      "$(audit_securite_verdict "$((N - 3*3600)) 2026-10-30 2" "$N")"
    t "C40 : à 26 h, encore OK" OK "$(audit_securite_verdict "$((N - 26*3600)) 2026-10-29 0" "$N")"
    t "C40 : 27 h → RETARD" "RETARD:27" "$(audit_securite_verdict "$((N - 27*3600)) 2026-10-29 0" "$N")"
    t "C40 : lancé il y a 2 h, jamais fini → INCOMPLET" "INCOMPLET:2" "$(audit_securite_verdict "$((N - 7200)) 2026-10-30 lance" "$N")"
    t "C40 : jamais → RETARD:jamais" "RETARD:jamais" "$(audit_securite_verdict "" "$N")"
    #  LE CAS ZÉRO : une marque illisible n'est jamais OK.
    t "C40 : marque corrompue" INCONNU "$(audit_securite_verdict "abc 2026-10-30 0" "$N")"
    t "C40 : état inconnu" INCONNU "$(audit_securite_verdict "$N 2026-10-30 x" "$N")"
    t "C40 : marque dans le futur" INCONNU "$(audit_securite_verdict "$((N + 7200)) 2026-10-30 0" "$N")"
    t "marque : trois mots" "1 2026-10-30 lance" "$(audit_securite_marque 1 2026-10-30 lance)"
    #  Les constats, par un lecteur simulé.
    ok() { echo "OK $*"; }; warn() { echo "WARN $*"; }
    local d; d=$(mktemp -d); SELF=rpi1
    AUDIT_SECURITE_MARQUE="$d/m"
    t "constat : jamais exécuté → WARN qui donne la commande d'acceptation" 1 \
      "$(audit_securite_verdicts | grep -c '^WARN Audit de sécurité nocturne sur rpi1 : jamais exécuté.*--accepter')"
    audit_securite_marque "$(( $(date +%s) - 7200 ))" x 0 > "$d/m"
    t "constat : fini il y a 2 h → OK" 1 "$(audit_securite_verdicts | grep -c '^OK Audit de sécurité nocturne sur rpi1 : terminé il y a 2 h')"
    audit_securite_marque "$(( $(date +%s) - 7200 ))" x lance > "$d/m"
    t "constat : lancé et jamais fini → WARN INCOMPLET" 1 "$(audit_securite_verdicts | grep -c '^WARN .*JAMAIS terminé')"
    #  Le lancement : l'audit est un témoin ; la marque est posée AVANT, à « lance ».
    local repo="$d/repo"; mkdir -p "$repo/scripts/exploitation"
    printf '#!/bin/bash\ncat "%s"\n' "$d/m" > "$repo/scripts/exploitation/audit-securite.sh"
    AUDIT_SECURITE_JOURNAL="$d/journal" AUDIT_SECURITE_DIR="$d" AUDIT_SECURITE_HEURE=0
    id() { echo 0; }
    rm -f "$d/m"
    audit_securite_lancer_si_du "$repo" >/dev/null
    t "lancement : l'audit a vu la marque « lance » du jour" "$(date +%F) lance" "$(cut -d' ' -f2,3 "$d/journal")"
    local avant; avant=$(cat "$d/journal")
    audit_securite_lancer_si_du "$repo" >/dev/null
    t "lancement : pas deux fois le même jour" "$avant" "$(cat "$d/journal")"
    unset -f id ok warn
    rm -rf "$d"
    [ "$st" -eq 0 ] && echo "lib-audit-securite : tous les cas passent."
    return "$st"
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    audit_securite_selftest; exit $?
fi
