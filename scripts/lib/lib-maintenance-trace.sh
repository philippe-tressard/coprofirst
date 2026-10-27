#!/usr/bin/env bash
# =============================================================================
#  lib-maintenance-trace.sh — C17 : la maintenance hebdomadaire a-t-elle tourné ?
#
#  Né du faux constat du 05/10/2026. Admin › Maintenance affichait sur les DEUX
#  nœuds « Maintenance hebdomadaire en retard : dernière exécution il y a 8 j
#  (attendu ≤ 8 j) », alors que maintenance.sh avait tourné le 04/10 à 03:00 et
#  rendu « statut: succes » sur chacun.
#
#  La collecte reconnaissait un passage à la ligne « [Hygiène] Garde-fou :
#  plafond 10 Go », un détail de la purge du cache de build. #1524 (v2.90.3) a
#  fondu les deux passes de cette purge en une ligne « Cache de build : X → Y » :
#  plus aucun « Garde-fou » n'était écrit, et la collecte ne trouvait que le
#  dernier de l'ancien format (27/09). Huit jours et six minutes plus tard, le
#  contrôle déclarait un retard. Le contrat entre ce que le script ÉCRIT et ce
#  que la collecte LIT n'était écrit nulle part — et `8 j (attendu ≤ 8 j)`, un
#  âge arrondi au jour inférieur, rendait le message contradictoire en prime.
#
#  Même forme que `lib-health-watch.sh` (C31) : trois morceaux d'une notion,
#  ensemble pour qu'un changement de l'un casse les épreuves de l'autre :
#    ligne_fin_hygiene     ce que maintenance.sh ÉCRIT, à la FIN de l'hygiène
#                          locale — une marque dédiée, et non plus un détail
#                          d'une étape qu'on réécrira ;
#    collecte_maintenance  ce que la collecte en LIT sur chaque nœud ;
#    maintenance_verdicts  ce que check-reliability en CONCLUT (C17).
#
#  WARN et non FAIL : une maintenance en retard ne coupe pas la production, elle
#  la laisse se dégrader ; ce qui coupe, C9 et C10 le voient déjà. Sur les DEUX
#  nœuds : le défaut du 31/07/2026 était une maintenance limitée à l'actif.
#
#  SOURCÉ (mode 100644) par `maintenance.sh` (la ligne) et `lib-collecte.sh`
#  (la collecte, puis les verdicts appelés par `check-reliability.sh`).
#  ⚠️ `maintenance_verdicts` emploie `ok`, `warn`, `$SELF`, `$PEER`, `$PEER_OK`,
#  `$MAINT_LOG` et les champs S_*/P_* de son appelant.
#  Autotest : bash scripts/lib/lib-maintenance-trace.sh --selftest
# =============================================================================

#  8 jours : un dimanche manqué toléré (cron hebdomadaire, horaire dans
#  `infra/points-entree/cron-root.crontab`).
MAINT_MAX_AGE_MIN=11520
#  La marque, UNE fois. ASCII seulement : le motif voyage par SSH, et
#  « Hygiène » y dépendrait de la locale des deux bouts.
MAINT_MARQUE='HYGIENE-FAITE'
#  La transition (la ligne de purge de #1524 valait trace tant qu'aucun journal ne
#  portait la marque) a pris fin le 25/10/2026 : la marque est lue sur les deux
#  nœuds depuis le 18/10, et l'alternative est retirée.
MAINT_MOTIF_FIN="$MAINT_MARQUE"

# ── La ligne de fin d'hygiène (PURE) ─────────────────────────────────────────
ligne_fin_hygiene() {
    echo "[Hygiène] Passage complet — $MAINT_MARQUE (marque lue par C17)"
}

# ── La collecte : la date de la dernière marque, sur chaque nœud ─────────────
#  Rend un fragment de COLLECT (une ligne `maint_last=…`) pour le journal $1 —
#  paramétré pour que l'autotest l'EXÉCUTE sur un journal témoin. Journal absent
#  ou sans marque : valeur vide, que `beat_age_min` traduit en INCONNU.
collecte_maintenance() { # $1 = journal de maintenance
    printf '\necho "maint_last=$(grep -E "%s" %s 2>/dev/null | tail -1 | cut -c2-20)"\n' \
        "$MAINT_MOTIF_FIN" "$1"
}

# ── L'âge lisible : jours ET heures ──────────────────────────────────────────
#  « 8 j (attendu ≤ 8 j) » se lisait comme une contradiction : l'âge était
#  arrondi au jour inférieur, le dépassement tenait dans les six minutes.
age_jours_heures() { # $1 = âge en minutes
    echo "$(( $1 / 1440 )) j $(( ($1 % 1440) / 60 )) h"
}

# ── C17. La maintenance hebdomadaire a-t-elle tourné, sur les DEUX nœuds ? ───
maintenance_verdicts() {
    local n v age
    for n in "$SELF" "$PEER"; do
        if [ "$n" = "$SELF" ]; then v=${S_maint_last:-}
        else [ "$PEER_OK" -eq 0 ] || continue; v=${P_maint_last:-}; fi
        age=$(beat_age_min "$v")
        case "$(beat_verdict "$age" "$MAINT_MAX_AGE_MIN")" in
            ok)     ok   "Maintenance hebdomadaire sur $n : dernière exécution il y a $(age_jours_heures "$age")" ;;
            absent) warn "Maintenance hebdomadaire en retard sur $n : dernière exécution il y a $(age_jours_heures "$age") (attendu ≤ $(( MAINT_MAX_AGE_MIN / 1440 )) j) → cron root perdu, bit x, ou script en erreur avant la fin de l'hygiène" ;;
            *)      warn "Maintenance hebdomadaire INCONNUE sur $n : aucune marque $MAINT_MARQUE datée dans $MAINT_LOG (jamais exécutée, log illisible, ou format changé)" ;;
        esac
    done
}

# ── Le contrôle statique : maintenance.sh écrit la marque en FIN d'hygiène ───
#  PURE (lit un texte). OK si `ligne_fin_hygiene` est appelée dans
#  `hygiene_locale`, après la rotation des journaux — sa dernière étape.
#  → OK | ABSENT | AVANT
marque_en_fin_hygiene() { # $1 = fichier
    awk '
        /^[[:space:]]*#/ { next }
        /^hygiene_locale\(\)/ { dans = 1 }
        dans && /roter_log/ { r = NR }
        dans && /ligne_fin_hygiene/ { m = NR }
        dans && /^}/ { dans = 0 }
        END { if (!m) print "ABSENT"; else if (r && m < r) print "AVANT"; else print "OK" }
    ' "$1"
}

# ── Autotest (job CI `test-scripts`) ──────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { if [ "$3" = "$2" ]; then echo "PASS  $1 → ${3:-(rien)}"
          else echo "FAIL  $1  attendu=${2:-(rien)} obtenu=${3:-(rien)}"; st=1; fi; }
    ICI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    # shellcheck source=lib-verdicts.sh
    . "$ICI/lib-verdicts.sh"     # beat_age_min, beat_verdict
    tmp=$(mktemp -d)
    il_y_a() { date -d "@$(( $(date +%s) - $1 * 60 ))" '+%Y-%m-%d %H:%M:%S'; }

    echo "== C17 : la ligne écrite répond au motif lu =="
    t "la marque de fin est reconnue" 1 "$(ligne_fin_hygiene | grep -cE "$MAINT_MOTIF_FIN")"
    t "une ligne d'étape ne l'est pas" 0 \
      "$(echo "[Hygiène] Rotation des logs host (20000 lignes max)..." | grep -cE "$MAINT_MOTIF_FIN")"

    echo "== C17 : la collecte, exécutée sur un journal témoin =="
    #  Le cas du 05/10/2026 : l'ancien format (27/09), puis le passage du 04/10
    #  sans « Garde-fou ». La collecte d'avant rendait le 27/09.
    {
        echo "[2026-09-27 03:00:08] [Hygiène] Garde-fou : plafond 10 Go..."
        echo "[2026-09-27 03:00:09] ===== Maintenance terminée (11s, statut: succes) ====="
        echo "[2026-10-04 03:00:17] [Hygiène] Purge du cache de build (inutilisé depuis > 168 h, plafond 10 Go)..."
        echo "[2026-10-04 03:00:20]   → Cache de build : 11.52GB → 11.24GB."
        echo "[2026-10-04 03:00:30] ===== Maintenance terminée (27s, statut: succes) ====="
    } > "$tmp/transition.log"
    t "un journal sans marque (ancien format) n'est plus lu : INCONNU" "maint_last=" \
      "$(bash -c "$(collecte_maintenance "$tmp/transition.log")")"
    {
        cat "$tmp/transition.log"
        echo "[2026-10-11 03:00:21] $(ligne_fin_hygiene)"
        echo "[2026-10-11 03:00:22] ===== Hygiène locale terminée (standby) ====="
    } > "$tmp/marque.log"
    t "la dernière MARQUE, pas la dernière ligne datée" "maint_last=2026-10-11 03:00:21" \
      "$(bash -c "$(collecte_maintenance "$tmp/marque.log")")"
    t "journal absent → valeur vide (INCONNU)" "maint_last=" \
      "$(bash -c "$(collecte_maintenance "$tmp/absent.log")")"
    if bash -n <(printf '%s' "$(collecte_maintenance /var/log/hostachy-maintenance.log)") 2>/dev/null; then
        echo "PASS  le fragment de collecte est du shell valide"
    else echo "FAIL  le fragment de collecte est du shell INVALIDE"; st=1; fi

    echo "== C17 : les verdicts, sur les DEUX nœuds =="
    ok()   { echo "[ OK ] $*"; }
    warn() { echo "[WARN] $*"; }
    SELF=rpi1 PEER=rpi2 PEER_OK=0 MAINT_LOG=/var/log/hostachy-maintenance.log
    S_maint_last=$(il_y_a 1440) P_maint_last=$(il_y_a 1440)
    sortie=$(maintenance_verdicts)
    t "deux passages d'hier → deux OK" "2|0" "$(grep -c '^\[ OK \]' <<< "$sortie")|$(grep -c '^\[WARN\]' <<< "$sortie")"
    P_maint_last=$(il_y_a 11526)
    sortie=$(maintenance_verdicts)
    t "8 j 0 h 6 min sur rpi2 → WARN" 1 "$(grep -c '^\[WARN\] Maintenance hebdomadaire en retard sur rpi2' <<< "$sortie")"
    t "…l'âge dit les heures (plus de « 8 j, attendu ≤ 8 j »)" 1 "$(grep -c 'il y a 8 j 0 h (attendu ≤ 8 j)' <<< "$sortie")"
    t "…et ce constat ne nomme pas rpi1" 0 "$(grep '^\[WARN\]' <<< "$sortie" | grep -c rpi1)"
    P_maint_last=$(il_y_a 11519)
    t "une minute sous le seuil → OK" 0 "$(maintenance_verdicts | grep -c '^\[WARN\]')"
    P_maint_last=""
    t "aucune marque lue sur rpi2 → INCONNU, jamais OK" 1 \
      "$(maintenance_verdicts | grep -c '^\[WARN\] Maintenance hebdomadaire INCONNUE sur rpi2')"
    PEER_OK=255
    t "pair injoignable : rien sur rpi2" 0 "$(maintenance_verdicts | grep -c rpi2)"

    echo "== C17 : maintenance.sh écrit la marque en fin d'hygiène =="
    t "maintenance.sh : marque après la rotation" OK \
      "$(marque_en_fin_hygiene "$ICI/../exploitation/maintenance.sh")"
    printf '%s\n' 'hygiene_locale() {' '    log "x"' '    for f in a; do roter_log "$f" 1; done' '}' > "$tmp/sans.sh"
    t "faute injectée : hygiène sans marque → refusée" ABSENT "$(marque_en_fin_hygiene "$tmp/sans.sh")"
    printf '%s\n' 'hygiene_locale() {' '    log "$(ligne_fin_hygiene)"' '    roter_log a 1' '}' > "$tmp/avant.sh"
    t "faute injectée : marque AVANT la rotation → refusée" AVANT "$(marque_en_fin_hygiene "$tmp/avant.sh")"

    rm -rf "$tmp"
    [ "$st" -eq 0 ] && echo "lib-maintenance-trace : tous les cas passent."
    exit "$st"
fi
