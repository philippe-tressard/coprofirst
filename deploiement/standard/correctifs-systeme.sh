#!/bin/bash
# =============================================================================
#  correctifs-systeme.sh — Les correctifs du SYSTÈME d'une installation
#  CoproFirst : posés seuls chaque nuit, et contrôlés chaque matin
#
#  Usage, sur le serveur de l'installation :
#    bash correctifs-systeme.sh --selftest            # éprouve les décisions, ne touche rien
#    sudo deploiement/standard/correctifs-systeme.sh --appliquer   # pose (idempotent)
#    sudo deploiement/standard/correctifs-systeme.sh --etat        # LECTURE SEULE
#    sudo deploiement/standard/correctifs-systeme.sh --retirer     # retire ce qui a été posé
#    (--rapport : lancé par le minuteur `coprofirst-correctifs.timer`, jamais à la main)
#
#  Ce qui est posé (mode d'emploi : `deploiement/standard/LISEZMOI.md`, « Les
#  correctifs du système ») — tout vient de `deploiement/standard/systeme/` :
#   - `unattended-upgrades` pose, en plus des correctifs de sécurité du système,
#     les mises à jour de la distribution, de Docker et de `cloudflared` ;
#   - son passage tourne entre 03:00 et 03:20, et redémarre la machine juste
#     après s'il l'exige — loin de la mise à jour de CoproFirst (04:30) ;
#   - chaque matin à 07:30, `--rapport` juge la nuit et rend compte à
#     l'administration (tâche `correctifs_systeme`) : le contrôle de 06:00 en
#     fait un courriel, et le rapport nocturne au registre le dit à la référence.
#
#  🔒 Le minuteur exécute une COPIE que root seul peut réécrire
#  (`/usr/local/lib/coprofirst-correctifs`), jamais le dossier de l'installation,
#  que l'utilisateur de Docker et la mise à jour nocturne réécrivent : un script
#  lancé en root depuis là serait un accès root pour qui tient ce compte
#  (`standards/03` §8 bis). `--appliquer` rafraîchit la copie.
#
#  La DÉCISION sur apt (configuration lisible, listes fraîches, paquet vu par un
#  passage sans être posé) est celle des nœuds de la référence (C30) :
#  `scripts/lib/lib-apt.sh`, qui part dans l'archive de déploiement. Ici, ce que
#  seule une installation standard demande : ce qu'`unattended-upgrades` posera
#  (son simulateur), la
#  configuration POSÉE et SERVIE, le redémarrage en attente.
# =============================================================================
set -uo pipefail

ICI=$(cd "$(dirname "$0")" && pwd)
#: La copie exécutée par le minuteur, et ce qu'elle emporte.
COPIE=/usr/local/lib/coprofirst-correctifs
REGLAGES=/etc/default/coprofirst-correctifs
ETAT_DIR=/var/lib/coprofirst-correctifs
APT_CONF=/etc/apt/apt.conf.d/52coprofirst-correctifs
UNITES=/etc/systemd/system
DROP_INS="apt-daily.timer apt-daily-upgrade.timer"
REDEMARRAGE_REQUIS=/var/run/reboot-required

#  Un fichier compagnon : à côté (la copie installée), sinon à sa place dans le
#  dépôt ou dans le dossier de l'installation.
voisin() {
    local c
    for c in "$ICI/$1" "$ICI/systeme/$1" "$ICI/../../scripts/lib/$1"; do
        [ -f "$c" ] && { echo "$c"; return 0; }
    done
    echo "$1 introuvable à côté de $0" >&2; return 1
}
# shellcheck source=../../scripts/lib/lib-apt.sh
. "$(voisin lib-apt.sh)" || exit 2
# shellcheck source=lib-installation.sh
. "$(voisin lib-installation.sh)" || exit 2
CONF_SOURCE=$(voisin 52coprofirst-correctifs) || exit 2

# ── Décisions PURES ───────────────────────────────────────────────────────────

#  Les origines que la configuration versionnée ajoute (une par ligne), lues
#  dans le fichier lui-même : source UNIQUE du fichier posé et du jugement.
origines_voulues() {
    sed -n 's/^[[:space:]]*"\(origin=[^"]*\)";.*/\1/p' "${1:-$CONF_SOURCE}"
}

#  $1 code de `apt-config dump` · $2 sa sortie · $3 calendrier du minuteur du
#  passage (`TimersCalendar`) → OUI | ECART:<ce qui manque> | INCONNU:<pourquoi>.
#  Juge la configuration SERVIE, jamais le fichier posé (`standards/03` §8 ter).
verdict_pose() {
    local rc=${1:-} dump=${2:-} cal=${3:-} o ecarts=""
    [ "$rc" = 0 ] || { echo "ECART:configuration apt illisible (apt-config dump rend ${rc:-?})"; return; }
    [ -n "$dump" ] || { echo "INCONNU:apt-config dump muet"; return; }
    while IFS= read -r o; do
        [ -n "$o" ] || continue
        grep -qF -- "Unattended-Upgrade::Origins-Pattern:: \"$o\";" <<< "$dump" || ecarts="$ecarts origine($o)"
    done < <(origines_voulues)
    for o in 'APT::Periodic::Unattended-Upgrade "1";' 'Unattended-Upgrade::Automatic-Reboot "true";'; do
        grep -qxF -- "$o" <<< "$dump" || ecarts="$ecarts ${o%% *}"
    done
    case "$cal" in
        '') ecarts="$ecarts minuteur(illisible)" ;;
        *"03:00"*) ;;
        *) ecarts="$ecarts minuteur(pas à 03:00)" ;;
    esac
    if [ -n "$ecarts" ]; then echo "ECART:${ecarts# }"; else echo OUI; fi
}

#  $1 verdict de `verdict_apt` · $2 verdict de `verdict_pose` · $3 depuis combien
#  de secondes un redémarrage est requis (vide : aucun)
#  → OK | ATTENTE | EN_COURS | NON_POSE | ILLISIBLE | PERIMEES | SECURITE |
#    SANS_PASSAGE | REDEMARRAGE | INCONNU
#  L'ordre est celui de `verdict_apt` (le symptôme le plus profond d'abord) ;
#  une configuration qui n'est pas en service passe avant ce qu'elle produirait.
#  Le redémarrage suit le passage (Automatic-Reboot-Time "now") : requis depuis
#  plus que le régime d'un passage (APT_SECU_DELAI_S), il n'a pas eu lieu.
verdict_correctifs() {
    local apt=$1 pose=$2 redem=${3:-}
    [ "$apt" = ILLISIBLE ] && { echo ILLISIBLE; return; }
    case "$pose" in ECART:*) echo NON_POSE; return ;; OUI) ;; *) echo INCONNU; return ;; esac
    case "$apt" in PERIMEES|SECURITE|SANS_PASSAGE|INCONNU) echo "$apt"; return ;; esac
    case "$redem" in *[!0-9]*) echo INCONNU; return ;; esac
    if [ -n "$redem" ] && [ "$redem" -gt "$APT_SECU_DELAI_S" ]; then echo REDEMARRAGE; return; fi
    echo "$apt"
}

#  $1 verdict → succes | erreur (le statut que l'administration retient).
#  INCONNU est une erreur : un contrôle qui ne sait pas n'est pas vert.
statut_de() { case "$1" in OK|ATTENTE|EN_COURS) echo succes ;; *) echo erreur ;; esac; }

#  $1 verdict · $2 détail → la phrase rendue (l'erreur du rapport, le courriel)
message_de() {
    case "$1" in
        OK)           echo "à jour" ;;
        ATTENTE)      echo "des correctifs attendent le passage de cette nuit ($2)" ;;
        EN_COURS)     echo "un passage d'unattended-upgrades est en cours" ;;
        NON_POSE)     echo "la configuration des mises à jour automatiques n'est pas en service ($2) : relancer correctifs-systeme.sh --appliquer" ;;
        ILLISIBLE)    echo "la configuration apt est illisible : aucune mise à jour ne passe" ;;
        PERIMEES)     echo "les listes de paquets ont plus de $APT_LISTES_MAX_J jours : le serveur n'apprend plus rien" ;;
        SECURITE)     echo "des correctifs vus par le dernier passage n'ont pas été posés ($2) : sudo unattended-upgrade -v dit pourquoi" ;;
        SANS_PASSAGE) echo "des correctifs attendent depuis plus de 30 h sans passage ($2)" ;;
        REDEMARRAGE)  echo "un redémarrage est requis depuis plus de 30 h et n'a pas eu lieu" ;;
        *)            echo "état des correctifs illisible ($2)" ;;
    esac
}

if [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }
    pr() { local r; r=$("${@:3}"); [ "${r%%:*}" = "$2" ] && echo "PASS  $1 → ${r%%:*}" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }
    #  La sortie RÉELLE d'`apt-config dump` sur l'instance de la démo (23/10/2026),
    #  complétée de ce que le fichier versionné ajoute.
    DUMP='APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
Unattended-Upgrade::Allowed-Origins:: "${distro_id}:${distro_codename}-security";'
    while IFS= read -r o; do DUMP="$DUMP
Unattended-Upgrade::Origins-Pattern:: \"$o\";"; done < <(origines_voulues)
    DUMP="$DUMP
Unattended-Upgrade::Automatic-Reboot \"true\";"
    CAL='{ OnCalendar=*-*-* 03:00:00 ; next_elapse=Sat 2026-10-24 03:12:41 CEST }'
    t  "les origines se lisent dans le fichier versionné" 4 eval 'origines_voulues | grep -c .'
    t  "Docker et cloudflared en font partie" 2 eval 'origines_voulues | grep -cE "origin=(Docker|cloudflared),"'
    pr "posée et servie" OUI verdict_pose 0 "$DUMP" "$CAL"
    pr "relevé du 23/10 : origines du système seules" ECART verdict_pose 0 "${DUMP%%Unattended-Upgrade::Origins-Pattern*}" "$CAL"
    pr "origine Docker manquante" ECART verdict_pose 0 "$(grep -v Docker <<< "$DUMP")" "$CAL"
    pr "redémarrage automatique coupé" ECART verdict_pose 0 "${DUMP/Automatic-Reboot \"true\"/Automatic-Reboot \"false\"}" "$CAL"
    pr "minuteur resté au défaut (06:00)" ECART verdict_pose 0 "$DUMP" "{ OnCalendar=*-*-* 6,18:00:00 ; }"
    pr "minuteur illisible" ECART verdict_pose 0 "$DUMP" ""
    pr "fichier apt mal formé" ECART verdict_pose 100 "" "$CAL"
    pr "dump muet → INCONNU, jamais OUI" INCONNU verdict_pose 0 "" "$CAL"
    t "tout va bien" OK verdict_correctifs OK OUI ""
    t "correctif publié après le passage" ATTENTE verdict_correctifs ATTENTE OUI ""
    t "configuration absente l'emporte" NON_POSE verdict_correctifs OK "ECART:origine" ""
    t "illisible l'emporte sur l'absence" ILLISIBLE verdict_correctifs ILLISIBLE "ECART:x" ""
    t "pose illisible → INCONNU" INCONNU verdict_correctifs OK "INCONNU:muet" ""
    t "vu sans être posé" SECURITE verdict_correctifs SECURITE OUI ""
    t "listes périmées" PERIMEES verdict_correctifs PERIMEES OUI ""
    t "apt illisible → INCONNU" INCONNU verdict_correctifs INCONNU OUI ""
    t "redémarrage requis depuis 31 h" REDEMARRAGE verdict_correctifs OK OUI 111600
    t "redémarrage requis depuis 1 h → rien à dire" OK verdict_correctifs OK OUI 3600
    t "âge du redémarrage illisible → INCONNU" INCONNU verdict_correctifs OK OUI "x"
    t "le retard l'emporte sur le redémarrage" SECURITE verdict_correctifs SECURITE OUI 111600
    t "OK → succès" succes statut_de OK
    t "ATTENTE → succès" succes statut_de ATTENTE
    t "INCONNU → erreur, jamais succès" erreur statut_de INCONNU
    t "NON_POSE → erreur" erreur statut_de NON_POSE
    [ "$st" -eq 0 ] && echo "correctifs-systeme : tous les cas passent."
    exit "$st"
fi

# ── Lectures (vides si impossibles : le verdict dit INCONNU) ───────────────────

#  Ce qu'`unattended-upgrades` poserait maintenant, « <paquet>=<version> » par
#  ligne, dans $1. Son simulateur, et non `apt list --upgradable` : il ne compte
#  que les origines admises, et ce qu'il annonce est ce que son passage posera —
#  un paquet annoncé puis resté en attente est bien un défaut (SECURITE). Il ne
#  suit pas le déploiement progressif d'Ubuntu : le 23/10/2026, il annonçait le
#  `cloud-init` phasé à 10 %, qu'`apt upgrade` retenait. Rend 1 si la simulation
#  n'a rien dit de lisible (verrou pris, outil absent).
lister_attente() {
    local sortie p
    sortie=$(unattended-upgrade --dry-run -v 2>&1) || true
    if grep -q "No packages found that can be upgraded unattended" <<< "$sortie"; then
        : > "$1"; return 0
    fi
    grep -q "Packages that will be upgraded:" <<< "$sortie" || return 1
    for p in $(sed -n 's/.*Packages that will be upgraded: //p' <<< "$sortie" | head -1); do
        echo "$p=$(apt-cache policy "$p" 2>/dev/null | awk '/Candidate:/ {print $2}')"
    done > "$1"
}

#  → « VERDICT|détail »
mesurer() {
    local attente releve dump rc cal pose apt redem="" n ecart=""
    install -d -m 0755 "$ETAT_DIR" 2>/dev/null
    attente="$ETAT_DIR/attente"
    if lister_attente "$attente"; then
        releve=$(eval "$COLLECT_APT_LISTES$(collecte_secu "$ETAT_DIR/vus" "cat $attente")$(collecte_apt_en_cours)")
    else
        releve=$(eval "$COLLECT_APT_LISTES$(collecte_apt_en_cours)")
    fi
    champ() { sed -n "s/^$1=//p" <<< "$releve" | tail -1; }
    apt=$(verdict_apt "$(champ apt_erreurs)" "$(champ apt_listes_j)" "$(champ apt_secu)" \
        "$(champ apt_secu_vu_s)" "$(champ apt_passage_s)" "$(champ apt_en_cours)")
    dump=$(apt-config dump 2>/dev/null); rc=$?
    cal=$(systemctl show -p TimersCalendar --value apt-daily-upgrade.timer 2>/dev/null)
    pose=$(verdict_pose "$rc" "$dump" "$cal")
    [ -e "$REDEMARRAGE_REQUIS" ] && redem=$(( $(date +%s) - $(stat -c %Y "$REDEMARRAGE_REQUIS") ))
    n=$(champ apt_secu)
    [ "$pose" = OUI ] || ecart=" — ${pose#*:}"
    echo "$(verdict_correctifs "$apt" "$pose" "$redem")|${n:-?} paquet(s) en attente : $(tr '\n' ' ' < "$attente" 2>/dev/null)$ecart"
}

#  La copie installée est-elle celle du dossier de l'installation ? Une version
#  plus récente arrive avec chaque mise à jour de CoproFirst, et ne s'exécute
#  qu'après un `--appliquer`.
copie_a_jour() {
    local dossier=$1 f
    #  Une installation d'avant ce script n'a rien à comparer.
    [ -f "$dossier/deploiement/standard/correctifs-systeme.sh" ] || { echo oui; return; }
    for f in deploiement/standard/correctifs-systeme.sh scripts/lib/lib-apt.sh \
             deploiement/standard/lib-installation.sh deploiement/standard/systeme/52coprofirst-correctifs; do
        [ -f "$dossier/$f" ] || continue
        cmp -s "$dossier/$f" "$COPIE/$(basename "$f")" || { echo non; return; }
    done
    echo oui
}

# ── Les gestes ───────────────────────────────────────────────────────────────

etat() {
    local m v
    [ "$(id -u)" -eq 0 ] || echo "⚠️  Pas root : la simulation d'unattended-upgrades l'exige → INCONNU."
    m=$(mesurer); v=${m%%|*}
    echo "Correctifs du système de $(hostname) : $v — $(message_de "$v" "${m#*|}")"
    echo "  prochain passage : $(systemctl show -p NextElapseUSecRealtime --value apt-daily-upgrade.timer 2>/dev/null)"
    [ -f "$REGLAGES" ] && [ "$(copie_a_jour "$(sed -n 's/^COPROFIRST_DOSSIER=//p' "$REGLAGES")")" = non ] \
        && echo "  ⚠️  la copie de $COPIE n'est pas celle de l'installation : relancer --appliquer"
    case "$(statut_de "$v")" in succes) return 0 ;; esac
    [ "$v" = INCONNU ] && return 3
    return 1
}

rapport() {
    local m v statut detail
    #  Posé par l'unité (`EnvironmentFile`), jamais par l'appelant : absent, rien ne se mesure.
    local dossier=${COPROFIRST_DOSSIER:-}
    DEBUT=$(date +%s)
    [ -n "$dossier" ] || { journal "⚠ COPROFIRST_DOSSIER absent de $REGLAGES : relancer --appliquer."; exit 2; }
    cd "$dossier" || exit 2
    m=$(mesurer); v=${m%%|*}; detail=$(printf '%s' "${m#*|}" | tr -d '"\\')
    statut=$(statut_de "$v")
    journal "Correctifs du système : $v — $(message_de "$v" "$detail")"
    [ "$(copie_a_jour "$dossier")" = oui ] \
        || journal "⚠ La copie exécutée diffère de celle de l'installation (mise à jour de CoproFirst) : relancer --appliquer."
    rendre_compte_tache correctifs_systeme "$statut" \
        "$([ "$statut" = erreur ] && message_de "$v" "$detail" | tr -d '"\\')" \
        "$(printf '{"verdict":"%s","detail":"%s"}' "$v" "$detail")"
}

appliquer() {
    local dossier=${1:-$ICI/../..} f unite
    [ "$(id -u)" -eq 0 ] || { echo "--appliquer s'exécute en root (sudo $0 --appliquer)."; exit 2; }
    dossier=$(cd "$dossier" && pwd) || exit 2
    [ -f "$dossier/.env" ] && [ -f "$dossier/docker-compose.yml" ] \
        || { echo "$dossier n'est pas le dossier d'une installation (.env, docker-compose.yml)."; exit 2; }
    dpkg -s unattended-upgrades >/dev/null 2>&1 || apt-get install -y -q unattended-upgrades >/dev/null \
        || { echo "ÉCHEC de l'installation d'unattended-upgrades"; exit 1; }
    install -d -o root -g root -m 0755 "$COPIE" "$ETAT_DIR"
    install -o root -g root -m 0755 "$0" "$COPIE/correctifs-systeme.sh"
    for f in lib-apt.sh lib-installation.sh 52coprofirst-correctifs; do
        install -o root -g root -m 0644 "$(voisin "$f")" "$COPIE/$f"
    done
    poser "$APT_CONF" 0644 < "$CONF_SOURCE"; [ $? -le 1 ] || { echo "ÉCHEC d'écriture de $APT_CONF"; exit 1; }
    #  `apt-config` est le seul juge d'un fichier apt : refusé, on le retire.
    apt-config dump >/dev/null 2>&1 || { rm -f "$APT_CONF"; echo "🔴 apt refuse $APT_CONF : retiré."; exit 1; }
    for unite in $DROP_INS; do
        install -d -m 0755 "$UNITES/$unite.d"
        poser "$UNITES/$unite.d/coprofirst.conf" 0644 < "$(voisin "$unite.conf")"
    done
    for f in coprofirst-correctifs.service coprofirst-correctifs.timer; do
        poser "$UNITES/$f" 0644 < "$(voisin "$f")"
    done
    printf 'COPROFIRST_DOSSIER=%s\n' "$dossier" | poser "$REGLAGES" 0644
    systemctl daemon-reload
    systemctl enable --now apt-daily.timer apt-daily-upgrade.timer coprofirst-correctifs.timer >/dev/null 2>&1
    systemctl restart apt-daily.timer apt-daily-upgrade.timer
    echo "Posé pour $dossier."
    etat
}

retirer() {
    local unite
    [ "$(id -u)" -eq 0 ] || { echo "--retirer s'exécute en root."; exit 2; }
    systemctl disable --now coprofirst-correctifs.timer >/dev/null 2>&1
    rm -f "$APT_CONF" "$REGLAGES" "$UNITES/coprofirst-correctifs.service" "$UNITES/coprofirst-correctifs.timer"
    for unite in $DROP_INS; do rm -f "$UNITES/$unite.d/coprofirst.conf"; rmdir "$UNITES/$unite.d" 2>/dev/null; done
    rm -rf "$COPIE" "$ETAT_DIR"
    systemctl daemon-reload
    systemctl restart apt-daily.timer apt-daily-upgrade.timer
    echo "Retiré : unattended-upgrades revient à la configuration du système (sécurité seule, 06:00–07:00, sans redémarrage)."
}

case "${1:-}" in
    --etat)      etat ;;
    --rapport)   rapport ;;
    --appliquer) appliquer "${2:-}" ;;
    --retirer)   retirer ;;
    *)           sed -n '5,11p' "$0"; exit 2 ;;
esac
