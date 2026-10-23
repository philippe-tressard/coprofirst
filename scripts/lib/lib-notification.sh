#!/bin/bash
# =============================================================================
#  lib-notification.sh — À qui rend compte une exécution de contrôles ?
#                        (module à sourcer)
#
#  POURQUOI ce module existe (#449, mesuré le 19/08/2026) :
#    `check-reliability.sh` n'alertait que `si [ "$FAILS" -gt 0 ]`. Or CINQ de
#    ses contrôles rendent WARN par choix assumé — C16 (cache de build), C17
#    (maintenance en retard), C19 (journal ⇆ base), C20 (sudo), C22 (points
#    d'entrée) — au motif, écrit dans le script, que « cela ne coupe pas la
#    production, et un FAIL à */15 enverrait un mail par heure jusqu'à
#    correction ».
#
#    Le raisonnement était juste sur la FRÉQUENCE et faux sur la CONCLUSION :
#    on en a déduit « pas de mail » là où il fallait « pas ce mail-là ». Ces
#    cinq contrôles n'avaient donc AUCUN destinataire — `standards/04` §7 — et
#    leur verdict finissait dans un journal que personne n'ouvre.
#
#  🔴 CE QUE ÇA A COÛTÉ, et ce n'est pas théorique. Le 16/08/2026 à 03:02, le
#    rapport de la maintenance hebdomadaire a été refusé par l'API (HTTP 422).
#    C19 l'a VU au passage suivant — « elle a TOURNÉ (journal) mais son rapport
#    n'est pas arrivé en base » — et a rendu WARN. Personne n'a été prévenu.
#    Le défaut a été trouvé le 18 à l'œil, sur l'écran d'administration, par
#    l'utilisateur. La détection marchait ; la NOTIFICATION, encore une fois,
#    non — exactement l'incident du 26/07/2026 qui avait fait naître
#    `lib-alert.sh`, un cran plus loin.
#
#  Deux canaux, deux rythmes : l'échec critique alerte dans l'heure, le point de
#  vigilance se résume une fois par jour. La fréquence se règle par le COOLDOWN,
#  jamais en coupant le canal.
#
#  Usage :
#    source /opt/5hostachy/scripts/lib/lib-notification.sh
#    notifier_verdicts "$REPO" "$SELF" "$FAIL_LINES" "$WARN_LINES"
#
#  La DÉCISION (`verdict_notification`) est pure et vit dans `lib-verdicts.sh`,
#  avec son contrat dans `verdicts_selftest`. Ce module-ci ne porte que l'envoi.
#
#  Ce module est SOURCÉ, jamais exécuté par cron → mode 100644 (le job CI
#  `test-scripts` le vérifie ; un bit d'exécution ici serait trompeur).
# =============================================================================

# Journalisation : réutilise le log() de l'appelant s'il en définit un.
if ! declare -f log >/dev/null 2>&1; then
    log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fi

notifier_verdicts() { # repo self fail_lines warn_lines
    local repo="${1:-}" self="${2:-}"
    local decision sujet corps fails warns fail_lines warn_lines

    #  Ce que CE nœud dit — à l'écran comme au courriel (#1396, #1402). Les
    #  lignes reçues portent sur tout ce qu'il a VU, les deux nœuds compris :
    #  les réutiliser enverrait deux fois le même fait, une fois par nœud.
    repartir_constats "$repo" "$self" "${3:-}${4:-}"
    fails=$REP_NF warns=$REP_NW fail_lines=$REP_FAIL_LINES warn_lines=$REP_WARN_LINES

    #  L'écran d'abord : il ne dépend ni du cooldown ni de la configuration SMTP.
    rapporter_verdicts "$repo" "$self"

    decision=$(verdict_notification "$fails" "$warns")
    [ "$decision" = "silence" ] && return 0

    if [ ! -r "$repo/scripts/lib/lib-alert.sh" ]; then
        echo "[WARN] lib-alert.sh introuvable dans $repo — aucune notification envoyée."
        return 0
    fi

    if [ "$decision" = "critique" ]; then
        # 1 h : à */15, un FAIL persistant ferait 96 e-mails par jour.
        ALERT_COOLDOWN_FILE=/tmp/check-reliability-cooldown
        ALERT_COOLDOWN_SECONDS=3600
        sujet="[5Hostachy] ❌ $fails contrôle(s) de fiabilité en échec sur $self"
        corps=$(printf 'check-reliability.sh sur %s a relevé %s FAIL et %s WARN à %s.\n\nDétail (cette exécution) :\n%s\nLog complet : /var/log/hostachy-reliability.log\n' \
            "$self" "$fails" "$warns" "$(date '+%d/%m/%Y %H:%M')" "$fail_lines")
    else
        # 24 h : un point de vigilance qui dure est une dette, pas une urgence.
        ALERT_COOLDOWN_FILE=/tmp/check-reliability-digest-cooldown
        ALERT_COOLDOWN_SECONDS=86400
        sujet="[5Hostachy] ⚠️ $warns point(s) de vigilance sur $self"
        corps=$(printf 'check-reliability.sh sur %s a relevé %s WARN et aucun FAIL à %s.\n\nAucun ne coupe la production ; laissés sans suite, ils rendent la surveillance aveugle — un rapport de maintenance perdu le 16/08/2026 y a passé deux jours.\n\nDétail (cette exécution) :\n%s\nCe résumé part au plus une fois par 24 h.\nLog complet : /var/log/hostachy-reliability.log\n' \
            "$self" "$warns" "$(date '+%d/%m/%Y %H:%M')" "$warn_lines")
    fi

    ALERT_REPO="$repo"
    # shellcheck source=/dev/null
    source "$repo/scripts/lib/lib-alert.sh"
    alert_if_not_in_cooldown "$sujet" "$corps"
}

# ── L'écran d'administration, troisième destinataire (27/09/2026) ────────────
#  Les verdicts de C1 à C30 n'allaient qu'au journal et au courriel : l'écran
#  « Maintenance » ne pouvait montrer ni ce qui était en vigilance, ni si ce
#  contrôleur tournait encore. Ils y sont remontés comme un rapport de tâche
#  (`reliability`), sur le canal des autres scripts (`lib-rapport.sh`).
#
#  ⚠️ PAS à chaque passage : 96 lignes par jour et par nœud dans la table la plus
#  lue de l'écran, dont la rétention est de 20 lignes par tâche — un jour de
#  constats aurait chassé tout le reste. On rend compte quand l'ENSEMBLE des
#  constats change, ou au moins une fois par jour : ce battement est ce qui
#  permet à l'écran de dire « Exécution manquante » d'un contrôleur mort.
#
#  La signature ignore les CHIFFRES : « disque à 61 % » puis « à 62 % » est le
#  même constat, et le compter comme un changement ramènerait un rapport par
#  passage.

#: Au-delà, on renvoie même sans changement. 23 h et non 24 : la synthèse
#: attend un rapport par 24 h (`sante_taches`), et un passage à 23 h 55 raté
#: repousserait le suivant au-delà.
RAPPORT_ECRAN_BATTEMENT_S=82800

#  PURE. $1 signature courante · $2 signature envoyée · $3 âge de l'envoi (s)
#  → envoyer | taire
decision_rapport_ecran() {
    local sig=$1 prec=$2 age=$3
    case "$age" in ''|*[!0-9]*) echo envoyer; return ;; esac
    [ -n "$prec" ] && [ "$sig" = "$prec" ] && [ "$age" -lt "$RAPPORT_ECRAN_BATTEMENT_S" ] \
        && echo taire || echo envoyer
}

#  PURE. Les lignes « [FAIL] … » et « [WARN] … » → un tableau JSON de chaînes.
constats_json() {
    local ligne sortie="" sep=""
    while IFS= read -r ligne; do
        [ -n "$ligne" ] || continue
        sortie="$sortie$sep\"$(rapport_echapper "$ligne")\""
        sep=","
    done <<< "$1"
    printf '[%s]' "$sortie"
}

# ── Qui DIT quoi — à l'écran ET au courriel (#1396, #1402) ────────────────────
#  Chaque nœud contrôle les deux : le 27/09/2026, « apt illisible sur rpi2 » et
#  « noyaux divergents » s'affichaient sous RPI1 ET sous RPI2 — et partaient
#  deux fois par courriel, rpi1 et rpi2 envoyant la même alerte à 16:36:06.
#  Chaque constat est désormais dit UNE fois, par un seul nœud :
#    propre  → il ne nomme que ce nœud : sous ce nœud ;
#    pair    → il ne nomme que l'autre : l'autre le dit lui-même ;
#    commun  → les deux, ou aucun (site, split-brain, parité) : dit par l'ACTIF.
#  Si le pair ne répond pas, il ne dira rien : ce nœud porte alors tout. C'est
#  ce qui garde la promesse du courriel — un nœud mort a toujours quelqu'un pour
#  parler de lui. Un nœud VIVANT dont le contrôleur ne tourne plus, lui, se voit
#  à l'écran (« Exécution manquante », par nœud) et au courriel de 06:00.

#  PURE. $1 ce nœud · $2 le pair · $3 une ligne → propre | pair | commun
portee_constat() {
    local l=${3,,} s=0 p=0 b='(^|[^a-z0-9])' f='([^a-z0-9]|$)'
    [[ $l =~ $b${1,,}$f ]] && s=1
    [[ $l =~ $b${2,,}$f ]] && p=1
    if   [ "$s" -eq 1 ] && [ "$p" -eq 0 ]; then echo propre
    elif [ "$p" -eq 1 ] && [ "$s" -eq 0 ]; then echo pair
    else echo commun; fi
}

#  PURE. Ce nœud porte-t-il les constats communs ?
#  $1 ce nœud · $2 le nœud actif (.active) · $3 PEER_OK (0 = le pair répond) → oui | non
#  Un rôle illisible les fait porter : un doublon vaut mieux qu'une perte.
porte_communs() {
    if [ "${3:-0}" != 0 ] || [ -z "$2" ] || [ "$1" = "$2" ]; then echo oui; else echo non; fi
}

#  PURE. $1 ce nœud · $2 le pair · $3 porte les communs (oui|non)
#        $4 le pair est muet (oui|non) · $5 les lignes
#  → une ligne par constat retenu, préfixée « P: » (propre) ou « C: » (commun).
#  Un constat sur le PAIR n'est repris que s'il est muet : sinon il le dit lui-même.
constats_retenus() {
    local ligne
    while IFS= read -r ligne; do
        [ -n "$ligne" ] || continue
        case "$(portee_constat "$1" "$2" "$ligne")" in
            propre) echo "P:$ligne" ;;
            pair)   [ "$4" = oui ] && echo "C:$ligne" ;;
            *)      [ "$3" = oui ] && echo "C:$ligne" ;;
        esac
    done <<< "$5"
    return 0
}

#  $1 dépôt · $2 ce nœud · $3 toutes les lignes vues. Pose les REP_* que lisent
#  le courriel et l'écran : les deux disent la même chose, calculée une fois.
repartir_constats() {
    local repo="${1:-}" self="${2:-}"
    REP_ACTIF=$(tr -d '[:space:]' < "$repo/.active" 2>/dev/null)
    REP_PORTE=$(porte_communs "$self" "$REP_ACTIF" "${PEER_OK:-0}")
    REP_RETENUS=$(constats_retenus "$self" "$(role_peer "$self" 2>/dev/null)" "$REP_PORTE" \
        "$([ "${PEER_OK:-0}" != 0 ] && echo oui || echo non)" "${3:-}")
    REP_PROPRES=$(printf '%s\n' "$REP_RETENUS" | sed -n 's/^P://p')
    REP_COMMUNS=$(printf '%s\n' "$REP_RETENUS" | sed -n 's/^C://p')
    REP_FAIL_LINES=$(printf '%s\n' "$REP_RETENUS" | sed -n 's/^[PC]:\(\[FAIL\]\)/\1/p')
    REP_WARN_LINES=$(printf '%s\n' "$REP_RETENUS" | sed -n 's/^[PC]:\(\[WARN\]\)/\1/p')
    REP_NF=$(printf '%s\n' "$REP_RETENUS" | grep -c '^[PC]:\[FAIL\]')
    REP_NW=$(printf '%s\n' "$REP_RETENUS" | grep -c '^[PC]:\[WARN\]')
    [ -z "$REP_FAIL_LINES" ] || REP_FAIL_LINES+=$'\n'
    [ -z "$REP_WARN_LINES" ] || REP_WARN_LINES+=$'\n'
    return 0
}

rapporter_verdicts() { # repo self — après repartir_constats
    local repo="${1:-}" self="${2:-}"
    local etat=${RAPPORT_ECRAN_ETAT:-/var/tmp/hostachy-reliability-rapport} sig prec="" prec_t=0
    local statut=succes actif=$REP_ACTIF cible="http://localhost" ip cle details erreur maintenant
    local porte=$REP_PORTE retenus=$REP_RETENUS propres=$REP_PROPRES communs=$REP_COMMUNS
    local nf=$REP_NF nw=$REP_NW
    #  La durée du PASSAGE (#2199) : `$SECONDS` compte depuis le lancement de
    #  check-reliability, qui appelle ce rapport en dernier. Elle s'écrivait `0`.
    local duree=$SECONDS
    command -v rapport_payload >/dev/null 2>&1 \
        || source "$repo/scripts/lib/lib-rapport.sh" 2>/dev/null || return 0

    #  Le standby n'a pas d'API : il rend compte à celle de l'ACTIF, comme la
    #  maintenance (`envoyer_rapport`). Pas de table d'adresses ici.
    if [ -n "$actif" ] && [ "$actif" != "$self" ]; then
        ip=$(role_ip "$actif" 2>/dev/null) || ip=""
        [ -n "$ip" ] || { log "  ⚠ Rapport des contrôles non envoyé : IP de l'actif ($actif) inconnue"; return 0; }
        cible="http://$ip"
    fi
    cle=$(rapport_cle "$repo") || { log "  ⚠ Rapport des contrôles non envoyé : MAINTENANCE_KEY absente"; return 0; }

    #  On signe ce que l'écran montrera de CE nœud : un constat que le pair
    #  rapporte lui-même ne doit pas relancer notre rapport.
    sig=$(printf '%s|%s' "$porte" "$retenus" | tr -d '0-9' | md5sum | cut -c1-32)
    #  Ce que l'écran montrera, calculé une fois pour le rapport ET le battement.
    #  Les FAIL vont AUSSI dans `erreur` : c'est ce que liste « Anomalies
    #  récentes », et un échec critique doit y figurer comme ceux des autres tâches.
    details=$(printf '{"fail":%d,"warn":%d,"constats":%s,"communs":%s,"porte_communs":%s}' \
        "$nf" "$nw" "$(constats_json "$propres")" "$(constats_json "$communs")" \
        "$([ "$porte" = oui ] && echo true || echo false)")
    erreur=$(printf '%s\n%s\n' "$propres" "$communs" | sed -n 's/^\[FAIL\] //p' | paste -sd'|' - | sed 's/|/ | /g')
    [ -r "$etat" ] && read -r prec prec_t < "$etat"
    if [ "$(decision_rapport_ecran "$sig" "$prec" "$(( $(date +%s) - ${prec_t:-0} ))")" = taire ]; then
        #  Rien de neuf : on dit qu'on a tourné (« dernier contrôle »). Sans ce
        #  battement, l'écran affichait l'heure du dernier CHANGEMENT, et on a cru
        #  le contrôleur mort (27/09/2026). Il porte aussi les constats du passage
        #  (#1805) : la signature ignore les chiffres, et l'écran gardait ceux du
        #  premier relevé jusqu'à 23 h. Un 404 = plus de ligne à prolonger : on
        #  oublie, et le passage suivant renvoie un rapport complet.
        rapport_battement "$cible" "$cle" reliability "$self" "$details" "$erreur" "$duree"
        [ "$RAPPORT_HTTP" = 404 ] && rm -f "$etat"
        return 0
    fi

    [ "$nw" -gt 0 ] && statut=avertissement
    [ "$nf" -gt 0 ] && statut=erreur
    maintenant=$(date -u +%Y-%m-%dT%H:%M:%S)
    RAPPORT_HTTP=""
    rapport_envoyer "$cible" "$cle" \
        "$(rapport_payload reliability "$self" applicative "$statut" "$duree" "$details" "$erreur" \
            "$maintenant" "$maintenant")" \
        "Rapport des contrôles"
    #  Mémorisé seulement s'il a ABOUTI : un envoi perdu se retente au passage
    #  suivant, au lieu d'attendre le rapport quotidien.
    [ "$RAPPORT_HTTP" = "201" ] && printf '%s %s\n' "$sig" "$(date +%s)" > "$etat"
    return 0
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    . "$(dirname "$0")/lib-rapport.sh"
    st=0
    t() { [ "$2" = "$3" ] && echo "PASS  $1 → $3" || { echo "FAIL  $1  attendu=$2 obtenu=$3"; st=1; }; }
    t "premier passage"                   envoyer "$(decision_rapport_ecran a "" 0)"
    t "mêmes constats, 15 min après"      taire   "$(decision_rapport_ecran a a 900)"
    t "constats changés"                  envoyer "$(decision_rapport_ecran b a 900)"
    t "mêmes constats, battement dû"      envoyer "$(decision_rapport_ecran a a 82800)"
    t "âge illisible → on envoie"         envoyer "$(decision_rapport_ecran a a "")"
    t "aucun constat"                     "[]"    "$(constats_json "")"
    t "deux constats, guillemets échappés" \
      '["[WARN] Disque \"rpi1\"","[FAIL] Site KO"]' \
      "$(constats_json $'[WARN] Disque "rpi1"\n[FAIL] Site KO\n')"
    #  La signature ignore les chiffres : 61 % puis 62 % n'est pas un changement.
    s1=$(printf '[WARN] Disque à 61%%' | tr -d '0-9' | md5sum | cut -c1-32)
    s2=$(printf '[WARN] Disque à 62%%' | tr -d '0-9' | md5sum | cut -c1-32)
    t "les chiffres ne font pas un changement" taire "$(decision_rapport_ecran "$s2" "$s1" 900)"

    #  #1396 — qui dit quoi. Les phrases RÉELLES de l'écran du 27/09/2026.
    t "apt illisible sur rpi2, vu de rpi2 → propre" propre \
      "$(portee_constat rpi2 rpi1 "[WARN] Configuration apt ILLISIBLE sur rpi2 (1 erreur(s))")"
    t "le même, vu de rpi1 → pair (rpi2 le dit)" pair \
      "$(portee_constat rpi1 rpi2 "[WARN] Configuration apt ILLISIBLE sur rpi2 (1 erreur(s))")"
    t "noyaux divergents : les deux → commun" commun \
      "$(portee_constat rpi1 rpi2 "[WARN] Noyaux DIVERGENTS — rpi1 en 6.12.62, rpi2 en 6.12.75")"
    t "site public : aucun nœud → commun" commun "$(portee_constat rpi1 rpi2 "[FAIL] Site public KO (HTTP 503)")"
    t "casse et bord de mot (RPI1, rpi12 n'est pas rpi1)" propre \
      "$(portee_constat rpi1 rpi2 "[WARN] Disque RPI1 à 81 % · rpi12 inconnu")"
    t "actif → porte les communs"           oui "$(porte_communs rpi1 rpi1 0)"
    t "standby, pair joignable → non"       non "$(porte_communs rpi2 rpi1 0)"
    t "standby, pair MUET → porte tout"     oui "$(porte_communs rpi2 rpi1 255)"
    t "rôle illisible → porte (doublon > perte)" oui "$(porte_communs rpi2 "" 0)"
    lignes=$'[WARN] apt ILLISIBLE sur rpi2\n[WARN] Noyaux DIVERGENTS — rpi1 en A, rpi2 en B\n[WARN] Disque rpi1 à 81 %\n'
    t "l'actif rpi1 : le sien + le commun, pas celui de rpi2" \
      "C:[WARN] Noyaux DIVERGENTS — rpi1 en A, rpi2 en B|P:[WARN] Disque rpi1 à 81 %" \
      "$(constats_retenus rpi1 rpi2 oui non "$lignes" | sort | paste -sd'|' -)"
    t "le standby rpi2 : le sien seulement" "P:[WARN] apt ILLISIBLE sur rpi2" \
      "$(constats_retenus rpi2 rpi1 non non "$lignes" | paste -sd'|' -)"
    t "rpi1 dont le pair est muet : son constat sur rpi2 en commun" \
      "C:[FAIL] Peer rpi2 (192.168.1.223) injoignable" \
      "$(constats_retenus rpi1 rpi2 oui oui "[FAIL] Peer rpi2 (192.168.1.223) injoignable" | paste -sd'|' -)"
    t "aucune ligne → rien" "" "$(constats_retenus rpi1 rpi2 oui non "")"

    #  #1402 — le COURRIEL suit la même répartition : réunis, les deux nœuds
    #  disent chaque fait UNE fois. Chacun a vu les mêmes lignes, plus les siennes
    #  que l'autre ne voit pas (git, NTP, sudo : mesurés en local seulement).
    vu1=$'[WARN] apt ILLISIBLE sur rpi2\n[WARN] Noyaux DIVERGENTS — rpi1 en A, rpi2 en B\n[FAIL] Site public KO\n[WARN] NTP non synchronisé sur rpi1\n'
    vu2=$'[WARN] apt ILLISIBLE sur rpi2\n[WARN] Noyaux DIVERGENTS — rpi2 en B, rpi1 en A\n[FAIL] Site public KO\n[WARN] Surface sudo de rpi2 non mesurable\n'
    dits=$( { constats_retenus rpi1 rpi2 oui non "$vu1"; constats_retenus rpi2 rpi1 non non "$vu2"; } | sed 's/^[PC]://')
    t "deux nœuds joignables : les cinq faits dits" 5 "$(printf '%s\n' "$dits" | grep -c .)"
    t "…et aucun deux fois" "" "$(printf '%s\n' "$dits" | sort | uniq -d)"
    t "…le fait du standby, par le standby" "P:[WARN] apt ILLISIBLE sur rpi2" \
      "$(constats_retenus rpi2 rpi1 non non "$vu2" | grep apt)"
    t "…le fait commun, par l'actif seul" "" "$(constats_retenus rpi2 rpi1 non non "$vu2" | grep 'Site public')"
    t "actif muet : le standby dit TOUT ce qu'il a vu" 4 \
      "$(constats_retenus rpi2 rpi1 "$(porte_communs rpi2 rpi1 255)" oui "$vu2" | grep -c .)"
    t "rôle illisible : les deux portent le commun (doublon > perte)" 2 \
      "$( { constats_retenus rpi1 rpi2 "$(porte_communs rpi1 "" 0)" non "$vu1"; constats_retenus rpi2 rpi1 "$(porte_communs rpi2 "" 0)" non "$vu2"; } | grep -c 'Site public')"
    #  La faute injectée — le pair repris même joignable, c'est-à-dire l'ancien
    #  comportement du courriel — est bien vue comme un doublon.
    faux=$( { constats_retenus rpi1 rpi2 oui oui "$vu1"; constats_retenus rpi2 rpi1 non non "$vu2"; } | sed 's/^[PC]://' | sort | uniq -d)
    t "faute injectée (pair repris) → doublon détecté" "[WARN] apt ILLISIBLE sur rpi2" "$faux"

    #  repartir_constats : les lignes du courriel gardent leur préfixe et leur fin.
    tmp=$(mktemp -d); echo rpi1 > "$tmp/.active"
    role_peer() { [ "$1" = rpi1 ] && echo rpi2 || echo rpi1; }
    PEER_OK=0 repartir_constats "$tmp" rpi2 "$vu2"
    t "standby rpi2 : ses deux WARN, rien du commun" "0|2|[WARN] apt ILLISIBLE sur rpi2" \
      "$REP_NF|$REP_NW|$(printf '%s' "$REP_WARN_LINES" | head -1)"
    PEER_OK=0 repartir_constats "$tmp" rpi1 "$vu1"
    t "actif rpi1 : le FAIL commun, son WARN et la parité" "1|2" "$REP_NF|$REP_NW"
    t "…ligne du courriel intacte" "[FAIL] Site public KO" "$(printf '%s' "$REP_FAIL_LINES" | head -1)"
    rm -rf "$tmp"
    #  #1805 — le battement porte les constats du passage. Le 10/10/2026, l'écran
    #  disait « 1 erreur sur 965 requêtes » sous « dernier contrôle 13:21 », quand
    #  le contrôle en comptait 3 sur 1904 : seuls les CHIFFRES avaient changé, la
    #  signature les ignore, et le battement ne portait que l'heure.
    tmp=$(mktemp -d)
    rapport_cle() { echo k; }
    rapport_envoyer() { ENVOIS=$((ENVOIS + 1)); RAPPORT_HTTP=201; }
    rapport_battement() { BATTEMENT_DETAILS="${5:-}"; BATTEMENT_ERREUR="${6-absent}"; RAPPORT_HTTP=200; }
    ENVOIS=0 BATTEMENT_DETAILS="" BATTEMENT_ERREUR=jamais
    passage() {
        REP_ACTIF=rpi1 REP_PORTE=oui REP_RETENUS="P:$1" REP_PROPRES="$1" REP_COMMUNS=""         REP_NF=$2 REP_NW=$3 RAPPORT_ECRAN_ETAT="$tmp/etat" rapporter_verdicts "$tmp" rpi1
    }
    passage "[WARN] 1 erreur(s) sur 965 requêtes" 0 1
    passage "[WARN] 3 erreur(s) sur 1904 requêtes" 0 1
    t "chiffres seuls changés : pas de second rapport" 1 "$ENVOIS"
    t "…mais le battement porte le relevé du passage" 1       "$(printf '%s' "$BATTEMENT_DETAILS" | grep -c '3 erreur(s) sur 1904')"
    t "…sans erreur, le battement dit « aucune » (vide), pas « inconnue »" "" "$BATTEMENT_ERREUR"
    passage "[FAIL] Site public KO (HTTP 503)" 1 0
    passage "[FAIL] Site public KO (HTTP 502)" 1 0
    t "un FAIL dont seul le code change → l'erreur suit" "Site public KO (HTTP 502)" "$BATTEMENT_ERREUR"
    unset -f rapport_cle rapport_envoyer rapport_battement passage
    rm -rf "$tmp"

    #  La charge complète est du JSON valide — le 422 du 16/08 venait de là.
    ch=$(rapport_payload reliability rpi1 applicative avertissement 0 \
        "$(printf '{"fail":%d,"warn":%d,"constats":%s}' 0 1 "$(constats_json $'[WARN] l\'actif\tvu')")" "" x x)
    if printf '%s' "$ch" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null \
       || printf '%s' "$ch" | python -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
        echo "PASS  charge utile JSON valide (apostrophe, tabulation)"
    else echo "FAIL  charge utile JSON INVALIDE : $ch"; st=1; fi
    [ "$st" -eq 0 ] && echo "lib-notification : tous les cas passent."
    exit "$st"
fi
