#!/bin/bash
# =============================================================================
#  lib-constats.sh — les trois verdicts d'un passage de contrôles, écrits UNE fois
#
#  Module SOURCÉ (mode 100644) par `check-reliability.sh` (C1 à C40) et par
#  `audit-securite.sh` (S1 à S6). Jamais exécuté par un cron.
#
#  POURQUOI ce module (30/10/2026). `ok`, `warn` et `fail` vivaient dans
#  `check-reliability.sh`, avec leurs compteurs et leurs lignes mémorisées. L'audit
#  de sécurité nocturne rend compte par le même canal (`lib-notification.sh`, qui
#  lit `FAIL_LINES`, `WARN_LINES` et `OKS`) : recopier ces trois fonctions aurait
#  figé deux formes de constat destinées à diverger — et `repartir_constats`,
#  `constats_json` et l'écran lisent cette forme au caractère près.
#
#  Ce que chaque ligne mémorise, et pourquoi :
#   - OKS : ce que l'écran dit des passages sans constat. « fail 0 · warn 0 » se
#     lit pareil quand 74 points sont verts et quand rien n'a été mesuré
#     (23/10/2026) — seul un compte de contrôles réussis les distingue (#2199) ;
#   - WARN_LINES : depuis #449 les WARN ont un destinataire (le digest quotidien).
#     Sans cette mémoire, il aurait dû relire le journal — donc reprendre
#     l'historique de toutes les exécutions passées, le défaut déjà corrigé pour
#     `fail()` ;
#   - FAIL_LINES : l'alerte reprenait les FAIL du LOG (`grep '^\[FAIL\]' … | tail`),
#     donc l'historique. Le 30/07/2026 le mail « 1 contrôle en échec » détaillait
#     SIX lignes, dont cinq d'une panne réseau résorbée une heure plus tôt : sujet
#     et corps se contredisaient. Une alerte décrit l'exécution qui la déclenche,
#     rien d'autre (`standards/07` §4).
#
#  Les compteurs sont (ré)initialisés par `constats_init`, que l'appelant invoque
#  AVANT son premier verdict ; `lib-notification.sh` lit ensuite les variables.
# =============================================================================

constats_init() { FAILS=0; WARNS=0; OKS=0; FAIL_LINES=""; WARN_LINES=""; }

ok()   { echo "[ OK ] $*"; OKS=$((OKS+1)); }
warn() { echo "[WARN] $*"; WARN_LINES+="[WARN] $*"$'\n'; WARNS=$((WARNS+1)); }
fail() { echo "[FAIL] $*"; FAIL_LINES+="[FAIL] $*"$'\n'; FAILS=$((FAILS+1)); }

#  La ligne de résumé, identique pour les deux lecteurs.
constats_resume() { # $1 = le nom de ce qu'on a contrôlé (« contrôles critiques », « points de l'audit »)
    echo "─────────────────────────────────────────────────────────────"
    echo "Résumé : $FAILS FAIL, $WARNS WARN, $OKS OK"
    if [ "$FAILS" -eq 0 ]; then echo "✅ Tous les ${1:-contrôles} sont verts."
    else echo "❌ $FAILS ${1:-contrôle(s)} en échec — intervention requise."; fi
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; }; }
    constats_init
    s=$(ok "un"; warn "deux"; fail "trois"; warn "quatre")
    t "les trois formes, au caractère près" $'[ OK ] un\n[WARN] deux\n[FAIL] trois\n[WARN] quatre' "$s"
    ok "un" >/dev/null; warn "deux" >/dev/null; fail "trois" >/dev/null; warn "quatre" >/dev/null
    t "les compteurs" "1|2|1" "$OKS|$WARNS|$FAILS"
    t "les WARN mémorisés, une ligne chacun" $'[WARN] deux\n[WARN] quatre' "${WARN_LINES%$'\n'}"
    t "les FAIL mémorisés" "[FAIL] trois" "${FAIL_LINES%$'\n'}"
    constats_init
    t "init remet tout à zéro" "0|0|0||" "$OKS|$WARNS|$FAILS|$FAIL_LINES|$WARN_LINES"
    t "résumé vert" 1 "$(constats_resume "points" | grep -c '^✅ Tous les points sont verts')"
    fail "x" >/dev/null
    t "résumé rouge compte les FAIL" 1 "$(constats_resume "point(s)" | grep -c '^❌ 1 point(s) en échec')"
    [ "$st" -eq 0 ] && echo "lib-constats : tous les cas passent."
    exit "$st"
fi
