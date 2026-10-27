#!/bin/bash
# =============================================================================
#  lib-relecture.sh — relire UNE fois une lecture vide avant de conclure INCONNU
#
#  Module SOURCÉ (mode 100644), jamais exécuté directement.
#
#  POURQUOI. Le 25/10/2026 à 02 h 06, check-reliability a écrit quatre FAIL
#  « INCONNU » sur les deux nœuds : les journaux étaient intacts (lignes datées
#  de 02 h 02 à 02 h 37), et un autre passage, une seconde plus tôt, les lisait
#  sans peine. Une lecture vide ponctuelle devient donc une panne annoncée. Un
#  INCONNU doit rester la réponse à une lecture qui ÉCHOUE deux fois, pas à une
#  lecture qui a échoué une fois.
#
#  Une seule relecture, après une courte pause. Une valeur qui revient au second
#  passage est celle qui compte ; une valeur encore vide reste vide, et le
#  verdict en aval rend INCONNU comme avant.
#
#  Autotest : bash scripts/lib/lib-relecture.sh --selftest (job CI `test-scripts`).
# =============================================================================

# ── La lecture, relue une fois si elle rend vide ─────────────────────────────
# $@ = la commande de lecture (sa sortie est capturée). Pause : RELECTURE_PAUSE_S
# (défaut 5 s). Rend la sortie du second passage si le premier était vide.
relire_si_vide() {
    local v
    v=$("$@" 2>/dev/null)
    if [ -z "$v" ]; then
        sleep "${RELECTURE_PAUSE_S:-5}"
        v=$("$@" 2>/dev/null)
    fi
    printf '%s' "$v"
}

# ── Autotest ─────────────────────────────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    export RELECTURE_PAUSE_S=0

    # Lecteur témoin : renvoie vide jusqu'à la lecture n° $FAUX_JUSQU_A, compte ses appels.
    lecteur() {
        local n=$(( $(cat "$tmp/n" 2>/dev/null || echo 0) + 1 ))
        echo "$n" > "$tmp/n"
        [ "$n" -ge "${FAUX_JUSQU_A:-1}" ] && echo "2026-10-25 02:03:02"
        return 0
    }
    compte() { cat "$tmp/n" 2>/dev/null || echo 0; }
    reset() { rm -f "$tmp/n"; }

    echo "== relecture : une lecture vide ponctuelle est rattrapée =="
    reset; FAUX_JUSQU_A=2
    v=$(relire_si_vide lecteur)
    if [ "$v" = "2026-10-25 02:03:02" ] && [ "$(compte)" = 2 ]; then
        echo "PASS  vide puis présent → valeur rendue après 2 lectures"
    else echo "FAIL  attendu=2026-10-25 02:03:02 après 2 lectures, obtenu='$v' ($(compte) lecture(s))"; st=1; fi

    echo "== relecture : une lecture présente n'est pas relue =="
    reset; FAUX_JUSQU_A=1
    v=$(relire_si_vide lecteur)
    if [ "$v" = "2026-10-25 02:03:02" ] && [ "$(compte)" = 1 ]; then
        echo "PASS  présent d'emblée → une seule lecture"
    else echo "FAIL  attendu 1 lecture, obtenu $(compte) ('$v')"; st=1; fi

    echo "== relecture : un vide persistant reste vide (INCONNU en aval) =="
    reset; FAUX_JUSQU_A=99
    v=$(relire_si_vide lecteur)
    if [ -z "$v" ] && [ "$(compte)" = 2 ]; then
        echo "PASS  vide aux deux passages → vide, 2 lectures"
    else echo "FAIL  attendu vide après 2 lectures, obtenu '$v' ($(compte))"; st=1; fi

    exit $st
fi
