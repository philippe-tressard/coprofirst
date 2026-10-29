#!/bin/bash
# =============================================================================
#  lib-mises-a-jour.sh — ce qui se met à jour HORS des dépendances applicatives
#
#  Les dépendances Python et npm ont leur veille (Dependabot, pip-audit, npm
#  audit). Deux couches n'en avaient AUCUNE (audit du 27/09/2026) :
#
#  1. le SYSTÈME des deux RPi (#1378). Le fichier `20auto-upgrades` de rpi2 était
#     mal formé depuis le 18/04/2026 : `apt-daily` échouait chaque jour, systemd
#     le comptait comme réussi, et `apt list --upgradable` rendait 0 — sur des
#     listes vieilles de cinq mois (#1377). Cinq mois sans correctif de
#     sécurité, et vingt-neuf contrôles au vert à chaque quart d'heure ;
#  2. les IMAGES DE BASE des conteneurs (#1379). `docker compose build` ne
#     re-télécharge jamais une image déjà présente, et Dependabot ne change que
#     l'étiquette : les correctifs publiés sous `python:3.12-slim` n'entraient
#     dans aucun conteneur.
#  3. le NOYAU (#1395). `unattended-upgrades` ne le pose pas (le dépôt Raspberry
#     n'est pas dans ses origines), et personne ne redémarre. Le 27/09/2026,
#     rpi1 tournait en 6.12.62 et rpi2 en 6.12.75 (#1393). Désormais, le nœud
#     qui vient de devenir standby pose la dernière RÉVISION de sa série puis
#     redémarre (`noyau-standby.sh`, appelé par la bascule). Un changement de
#     SÉRIE reste un geste humain : C30 le signale, avec la commande.
#
#  4. les AUTRES paquets des dépôts tiers (#2198) : Docker, containerd,
#     cloudflared, Node.js. Le standby les pose avec le noyau
#     (`noyau-standby.sh`, décision dans `lib-maj-paquets.sh`), sans jamais
#     ramener un paquet retiré par l'allègement (C35).
#
#  Ce module porte les trois premiers, parce qu'ils répondent à la même question — « ce
#  nœud reçoit-il ses correctifs ? » — et qu'aucun n'a d'autre maison.
#  La couche apt (1.) a sa collecte et sa décision dans `lib-apt.sh` depuis le
#  28/09/2026 (#1441) ; ses messages restent ici, dans la boucle par nœud.
#
#  Il est SOURCÉ (mode 100644) par `lib-collecte.sh` (le snippet `COLLECT_MAJ`),
#  `lib-conformite.sh` (les verdicts de C30), `check-reliability.sh` (le pair
#  injoignable), `maintenance.sh` (les images) et `noyau-standby.sh` (le noyau).
#  Autotest : bash scripts/lib/lib-mises-a-jour.sh --selftest
# =============================================================================

#  La couche apt (listes, configuration, correctifs de sécurité) : ses
#  collectes et sa décision, que les messages de C30 ci-dessous emploient.
. "$(dirname "${BASH_SOURCE[0]}")/lib-apt.sh"

#  Les paquets HORS sécurité (en attente, retenus) et la parité de docker,
#  containerd et cloudflared entre les nœuds (#1591) : même question que C30,
#  autre module — celui-ci approchait le plafond de 500 lignes.
. "$(dirname "${BASH_SOURCE[0]}")/lib-paquets.sh"

# ── La collecte, exécutée sur CHAQUE nœud (ajoutée à COLLECT) ────────────────
#  Même contrainte que `lib-collecte.sh` : chaîne entre guillemets SIMPLES, donc
#  AUCUNE apostrophe en dessous, même en commentaire. Tout ce qui s'explique
#  s'explique ici :
#   - apt_* : `COLLECT_APT`, dans `lib-apt.sh`.
#   - noyau_actif / noyau_installe : le noyau qui tourne, et le plus récent
#     installé de la MÊME saveur (`+rpt-rpi-2712`) — lu dans /lib/modules, donc
#     sans dépendre du nom du paquet, qui change d une image Raspberry à l autre.
#   - noyau_candidat : la version que le dépôt propose pour le méta-paquet de
#     cette saveur (`linux-image-rpi-2712`) — ce qui dit RÉVISION ou SÉRIE.
COLLECT_MAJ="$COLLECT_APT"'
_k=$(uname -r)
echo "noyau_actif=$_k"
echo "noyau_installe=$(ls -1 /lib/modules 2>/dev/null | grep -F -- "+${_k#*+}" | sort -V | tail -1)"
echo "noyau_candidat=$(apt-cache policy "linux-image-${_k#*+rpt-}" 2>/dev/null | awk "/Candidate:/{print \$2}")"
'

#: Les conteneurs d'un AUTRE projet que le redémarrage du standby va arrêter
#: (List-dons vit sur rpi2). `noyau-standby.sh` les relève juste avant de
#: redémarrer — l'epoch en première ligne, un nom par ligne ensuite — et C30
#: vérifie qu'ils tournent de nouveau. Hors du dépôt, comme `noyau-tente` : le
#: relevé doit survivre au redémarrage (28/09/2026, arbitrage de Philippe :
#: « tu peux arrêter List-dons, mais vérifie qu'il redémarre »).
CONTENEURS_ETRANGERS="${CONTENEURS_ETRANGERS:-/var/lib/hostachy/conteneurs-etrangers}"

#  La collecte du retour, pour un relevé donné (paramétrée pour l'autotest).
#  Même contrainte que COLLECT_MAJ : aucune apostrophe dans la chaîne.
#   - etrangers_age / etrangers_attendus : l'âge du relevé, et ce qu'il nomme —
#     émis seulement si un relevé existe ;
#   - etrangers_lu / etrangers_manquants : émis seulement si `docker ps` a
#     répondu. Est REVENU un conteneur qui tourne et que son healthcheck ne dit
#     ni malade ni en cours de démarrage : on mesure le service, pas le process.
collecte_etrangers() {
    printf '%s' '
_f='"$1"'
if [ -r "$_f" ]; then
_e=$(head -1 "$_f")
case "$_e" in ""|*[!0-9]*) echo "etrangers_age=illisible" ;; *) echo "etrangers_age=$(( $(date +%s) - _e ))" ;; esac
echo "etrangers_attendus=$(tail -n +2 "$_f" | paste -sd, -)"
if _v=$(docker ps --format "{{.Names}} {{.Status}}" 2>/dev/null); then
echo "etrangers_lu=1"
_m=""
for _c in $(tail -n +2 "$_f"); do
_w=$(printf "%s\n" "$_v" | grep -v -e "unhealthy" -e "health: starting")
grep -q "^$_c " <<<"$_w" || _m="$_m${_m:+,}$_c"
done
echo "etrangers_manquants=$_m"
fi
fi
'
}
COLLECT_MAJ="$COLLECT_MAJ$(collecte_etrangers "$CONTENEURS_ETRANGERS")"
COLLECT_MAJ="$COLLECT_MAJ$COLLECT_PAQUETS"

# ── Décisions PURES (aucun effet de bord) ────────────────────────────────────

#  $1 noyau qui tourne · $2 plus récent installé de la même saveur
#  → OK | REDEMARRAGE | INCONNU
#  `unattended-upgrades` installe, il ne redémarre pas : un noyau corrigé qui
#  attend un redémarrage ne protège de rien.
verdict_noyau() {
    local actif=$1 installe=$2
    [ -n "$actif" ] && [ -n "$installe" ] || { echo INCONNU; return; }
    [ "$actif" = "$installe" ] && echo OK || echo REDEMARRAGE
}

#  $1 et $2 : les noyaux qui tournent sur les deux nœuds → OK | DIVERGENCE | INCONNU
#  Deux nœuds qui se relaient chaque nuit doivent se comporter pareil ; le
#  27/09/2026, rpi1 tournait en 6.12.62 et rpi2 en 6.12.75.
verdict_noyaux_parite() {
    [ -n "$1" ] && [ -n "$2" ] || { echo INCONNU; return; }
    [ "${1%%+*}" = "${2%%+*}" ] && echo OK || echo DIVERGENCE
}

#  $1 le noyau de l'ACTIF · $2 celui du STANDBY → OK | STANDBY_EN_AVANCE |
#  DIVERGENCE | INCONNU. Une RÉVISION que le standby a posée après la bascule
#  (#1395) le met en avance d'un jour : l'actif la prend à la suivante — la même
#  règle que les paquets (`verdict_versions_parite_roles`, lib-paquets.sh). Une
#  autre SÉRIE ne se pose qu'à la main : elle reste un écart.
verdict_noyaux_parite_roles() {
    local v a b
    v=$(verdict_noyaux_parite "${1:-}" "${2:-}")
    [ "$v" = DIVERGENCE ] || { echo "$v"; return; }
    a=$(version_noyau "$1"); b=$(version_noyau "$2")
    [ "${a%.*}" = "${b%.*}" ] || { echo DIVERGENCE; return; }
    verdict_versions_parite_roles "$a" "$b"
}

# ── Le noyau du standby (#1395) ──────────────────────────────────────────────

#: Les paquets d'une montée de noyau : le méta-paquet des deux saveurs, leurs
#: en-têtes, et le micrologiciel qui copie le noyau dans /boot/firmware. Une
#: seule liste, pour le geste automatique ET pour la commande que C30 affiche.
NOYAU_PAQUETS="linux-image-rpi-2712 linux-image-rpi-v8 linux-headers-rpi-2712 linux-headers-rpi-v8 raspi-firmware"

#: La marque que le standby pose sur l'ACTIF juste avant de redémarrer
#: (« <epoch> <noyau visé> »). Tant qu'elle a moins de REDEMARRAGE_PAIR_MAX_S,
#: un pair injoignable est un redémarrage prévu ; au-delà, un noyau qui ne
#: repart pas — donc un FAIL. Un Pi 5 redémarre en 1 à 2 min.
MARQUE_REDEMARRAGE="${MARQUE_REDEMARRAGE:-/opt/5hostachy/.redemarrage-noyau}"
REDEMARRAGE_PAIR_MAX_S=${REDEMARRAGE_PAIR_MAX_S:-600}
#: Au-delà, une marque ou un relevé ne dit plus rien du moment : ce qui arrive
#: trois jours après un redémarrage réussi a une autre cause.
REDEMARRAGE_PERTINENT_S=${REDEMARRAGE_PERTINENT_S:-21600}

#  « 6.18.50+rpt-rpi-2712 » (uname -r) ou « 1:6.18.50-1+rpt1 » (dpkg) → 6.18.50
version_noyau() { local v=${1#*:}; v=${v%%+*}; echo "${v%%-*}"; }

#  La commande de montée MANUELLE, pour un nœud — celle de #1393.
commande_montee_noyau() {
    echo "ssh -t ptressard@$1 'sudo apt-get update && sudo apt-get install --only-upgrade $NOYAU_PAQUETS && sudo reboot'"
}

#  $1 noyau qui tourne · $2 version candidate du méta-paquet
#  → RIEN | REVISION | SERIE | INCONNU
#  RÉVISION = même série majeur.mineur, plus récente : elle se pose seule sur le
#  standby. SÉRIE = autre série : geste humain (un pilote ou Docker peuvent
#  casser, on regarde le standby avant de lui confier la production).
decision_noyau_candidat() {
    local a c re='^[0-9]+\.[0-9]+\.[0-9]+$'
    a=$(version_noyau "$1"); c=$(version_noyau "$2")
    [[ $a =~ $re && $c =~ $re ]] || { echo INCONNU; return; }
    [ "$(printf '%s\n%s\n' "$a" "$c" | sort -V | tail -1)" = "$a" ] && { echo RIEN; return; }
    [ "${a%.*}" = "${c%.*}" ] && echo REVISION || echo SERIE
}

#  $1 noyau qui tourne · $2 plus récent installé · $3 noyau déjà tenté (vide sinon)
#  → RIEN | REDEMARRER | DEJA_TENTE | SERIE | INCONNU
#  DEJA_TENTE : on a redémarré pour ce noyau et il ne tourne toujours pas — le
#  firmware est revenu sur l'ancien, ou il ne démarre pas. On ne boucle pas : on
#  alerte. SERIE : une autre série installée à la main se redémarre à la main.
decision_redemarrage_standby() {
    case "$(verdict_noyau "$1" "$2")" in
        OK) echo RIEN ;;
        REDEMARRAGE)
            if [ "$(decision_noyau_candidat "$1" "$2")" = SERIE ]; then echo SERIE
            elif [ "$3" = "$2" ]; then echo DEJA_TENTE
            else echo REDEMARRER; fi ;;
        *) echo INCONNU ;;
    esac
}

#  $1 âge (s) de la marque de redémarrage, vide si aucune
#  → REDEMARRAGE | NE_REPART_PAS | INJOIGNABLE
#  Au-delà de REDEMARRAGE_PERTINENT_S, la marque ne dit plus rien de la panne
#  du moment.
verdict_pair_injoignable() {
    case "$1" in ''|*[!0-9]*) echo INJOIGNABLE; return ;; esac
    if   [ "$1" -le "$REDEMARRAGE_PAIR_MAX_S" ]; then echo REDEMARRAGE
    elif [ "$1" -le "$REDEMARRAGE_PERTINENT_S" ]; then echo NE_REPART_PAS
    else echo INJOIGNABLE; fi
}

#  $1 âge (s) du relevé des conteneurs étrangers, vide si aucun · $2 ceux qu'il
#  nomme · $3 ceux qui ne sont pas revenus · $4 « 1 » si `docker ps` a répondu
#  → SANS_OBJET | REVENUS | EN_COURS | ABSENTS | INCONNU
#  Même fenêtre que le pair injoignable : un Pi 5 et ses conteneurs repartent
#  en deux minutes ; au-delà de dix, un autre projet est à l'arrêt.
verdict_etrangers_revenus() {
    local age=$1 attendus=$2 manquants=$3 lu=$4
    [ -n "$age" ] || { echo SANS_OBJET; return; }
    case "$age" in *[!0-9]*) echo INCONNU; return ;; esac
    [ "$age" -le "$REDEMARRAGE_PERTINENT_S" ] && [ -n "$attendus" ] || { echo SANS_OBJET; return; }
    [ "$lu" = 1 ] || { echo INCONNU; return; }
    if   [ -z "$manquants" ]; then echo REVENUS
    elif [ "$age" -le "$REDEMARRAGE_PAIR_MAX_S" ]; then echo EN_COURS
    else echo ABSENTS; fi
}

#  Émis par check-reliability quand le pair ne répond pas en SSH. Dépend de
#  l'appelant : warn/fail, PEER, PEER_IP. $1 (facultatif) : la cause dite par
#  `ssh_noeud_diagnostic` — une clé d'hôte non épinglée n'est pas un nœud figé (#1598).
pair_injoignable_emettre() {
    local m age='' cible=''
    m=$(cat "$MARQUE_REDEMARRAGE" 2>/dev/null)
    case "${m%% *}" in ''|*[!0-9]*) ;; *) age=$(( $(date +%s) - ${m%% *} )); cible=${m#* } ;; esac
    case "$(verdict_pair_injoignable "$age")" in
        REDEMARRAGE)   warn "Peer $PEER ($PEER_IP) en redémarrage prévu depuis ${age} s (noyau $cible, #1395) — revérifié au prochain passage" ;;
        NE_REPART_PAS) fail "Peer $PEER ($PEER_IP) injoignable $(( age / 60 )) min après avoir redémarré pour le noyau $cible — il ne repart pas (accès physique : le Pi n'a pas de menu de démarrage)" ;;
        *)             fail "Peer $PEER ($PEER_IP) injoignable en SSH — impossible d'auditer les 2 nœuds.${1:+ $1}" ;;
    esac
}

# ── Les verdicts de C30, émis par check-reliability (via lib-conformite) ─────
#  Dépend de l'appelant : ok/warn/fail, SELF/PEER/PEER_OK et les champs S_*/P_*.
#  Tout sort en WARN, donc au digest quotidien : aucune de ces situations
#  n'arrête le site, et un redémarrage reste un geste manuel, le standby
#  d'abord. Un FAIL à */15 serait une alerte par heure qu'on apprendrait à
#  ignorer. UNE exception : un autre projet que notre redémarrage a arrêté et
#  qui ne revient pas — c'est une panne, que nous avons causée, et elle ne
#  dure que la fenêtre du relevé (REDEMARRAGE_PERTINENT_S).
mises_a_jour_verdicts() {
    local n p v
    for n in "$SELF" "$PEER"; do
        if [ "$n" = "$SELF" ]; then p=S; else [ "$PEER_OK" -eq 0 ] || continue; p=P; fi
        local err age secu vu pas proch actif inst cand enc
        eval "err=\${${p}_apt_erreurs:-} age=\${${p}_apt_listes_j:-} secu=\${${p}_apt_secu:-}"
        eval "vu=\${${p}_apt_secu_vu_s:-} pas=\${${p}_apt_passage_s:-} proch=\${${p}_apt_prochain:-} enc=\${${p}_apt_en_cours:-}"
        eval "actif=\${${p}_noyau_actif:-} inst=\${${p}_noyau_installe:-} cand=\${${p}_noyau_candidat:-}"
        v=$(verdict_apt "$err" "$age" "$secu" "$vu" "$pas" "$enc")
        case "$v" in
            OK)        ok   "Mises à jour système sur $n : listes apt de ${age} j, aucun correctif de sécurité en attente" ;;
            ATTENTE)   ok   "Mises à jour système sur $n : $secu correctif(s) de sécurité publié(s) depuis le dernier passage d'installation, posé(s) au prochain (${proch:-heure illisible})" ;;
            #  EN_COURS : INCONNU par nature (le relevé va changer), dit en `ok` PARCE QUE
            #  tout `warn` part au digest quotidien — et c'est ce digest, pour un fait
            #  résolu vingt secondes plus tard, que #1610 supprime. Jamais un vert qui
            #  masque : la borne `APT_EN_COURS_MAX_S` rend la main au verdict habituel.
            EN_COURS)  ok   "Mises à jour système sur $n : un passage d'installation apt est EN COURS ($secu correctif(s) de sécurité en attente) — INCONNU, revérifié au prochain passage (#1610)" ;;
            ILLISIBLE) warn "Configuration apt ILLISIBLE sur $n ($err erreur(s)) — apt-daily échoue chaque jour en silence, AUCUNE mise à jour n'arrive (#1377) : 'apt-config dump' pour voir la ligne fautive" ;;
            PERIMEES)  warn "Listes apt périmées sur $n : ${age} j (seuil ${APT_LISTES_MAX_J} j) — le nœud ne voit plus les correctifs ; vérifier 'systemctl status apt-daily' et /etc/apt/apt.conf.d/20auto-upgrades" ;;
            SECURITE)  warn "$secu correctif(s) de sécurité en attente sur $n, vus par le passage d'installation d'il y a $(( pas / 3600 )) h sans être posés — 'sudo unattended-upgrade -v' dit pourquoi (fichier de configuration modifié, paquet retenu)" ;;
            SANS_PASSAGE) warn "$secu correctif(s) de sécurité en attente sur $n depuis $(( vu / 3600 )) h, au-delà des 25 h entre deux passages d'installation — 'systemctl status apt-daily-upgrade.timer', puis 'sudo unattended-upgrade -v'" ;;
            *)         warn "Mises à jour système INCONNUES sur $n (erreurs='${err:-vide}' âge='${age:-vide}' sécurité='${secu:-vide}' attente='${vu:-vide}' s passage='${pas:-vide}' s) — ni vert ni rouge" ;;
        esac
        case "$(verdict_noyau "$actif" "$inst")" in
            OK)          ok   "Noyau de $n à jour ($actif)" ;;
            REDEMARRAGE) warn "Redémarrage requis sur $n : tourne en $actif, $inst est installé — redémarrer le STANDBY d'abord, l'actif après une bascule" ;;
            *)           warn "Noyau de $n INCONNU (tourne='${actif:-vide}' installé='${inst:-vide}') — ni vert ni rouge" ;;
        esac
        local e_age e_att e_man e_lu
        eval "e_age=\${${p}_etrangers_age:-} e_att=\${${p}_etrangers_attendus:-} e_man=\${${p}_etrangers_manquants:-} e_lu=\${${p}_etrangers_lu:-}"
        case "$(verdict_etrangers_revenus "$e_age" "$e_att" "$e_man" "$e_lu")" in
            SANS_OBJET) ;;
            REVENUS)  ok   "Conteneurs hors 5Hostachy revenus sur $n après son redémarrage (noyau ou moteur de conteneurs) : ${e_att//,/, }" ;;
            EN_COURS) warn "Redémarrage de noyau de $n il y a ${e_age} s : ${e_man//,/, } pas encore revenu(s) — revérifié au prochain passage (#1395)" ;;
            ABSENTS)  fail "Conteneur(s) ${e_man//,/, } NON revenu(s) sur $n, $(( e_age / 60 )) min après son redémarrage — noyau ou moteur de conteneurs (#1395, #2198) — un autre projet est à l'arrêt : 'docker ps -a' sur $n, puis 'docker compose up -d <ses services>' dans son répertoire" ;;
            *)        warn "Retour des conteneurs hors 5Hostachy sur $n INCONNU (relevé de '${e_age:-vide}' s, docker lu='${e_lu:-non}') — ni vert ni rouge" ;;
        esac
        case "$(decision_noyau_candidat "$actif" "$cand")" in
            RIEN)     ok   "Aucun noyau plus récent pour $n dans le dépôt" ;;
            REVISION) ok   "Révision de noyau $(version_noyau "$cand") disponible pour $n — posée seule quand il sera standby, après la bascule (#1395)" ;;
            SERIE)    warn "Nouvelle SÉRIE de noyau pour $n : $(version_noyau "$actif") → $(version_noyau "$cand"). Elle ne se pose pas seule — le STANDBY d'abord, l'actif après une bascule : $(commande_montee_noyau "$(role_ip "$n")")" ;;
            *)        warn "Noyau candidat de $n INCONNU (tourne='${actif:-vide}' dépôt='${cand:-vide}') — ni vert ni rouge" ;;
        esac
    done
    paquets_verdicts   # lib-paquets.sh : hors sécurité, retenus, parité docker/containerd/cloudflared (#1591)
    [ "$PEER_OK" -eq 0 ] || return 0
    local v
    case "$(cote_actif "${S_active:-}" "${P_active:-}" "$SELF" "$PEER")" in
        S) v=$(verdict_noyaux_parite_roles "${S_noyau_actif:-}" "${P_noyau_actif:-}") ;;
        P) v=$(verdict_noyaux_parite_roles "${P_noyau_actif:-}" "${S_noyau_actif:-}") ;;
        *) v=$(verdict_noyaux_parite "${S_noyau_actif:-}" "${P_noyau_actif:-}") ;;
    esac
    case "$v" in
        OK)         ok   "Même noyau sur les 2 nœuds (${S_noyau_actif%%+*})" ;;
        STANDBY_EN_AVANCE) ok "Noyau du standby en avance sur l'actif ($S_active) — $SELF en ${S_noyau_actif%%+*}, $PEER en ${P_noyau_actif%%+*} : révision posée après la bascule (#1395), l'actif la prend à la suivante" ;;
        DIVERGENCE) warn "Noyaux DIVERGENTS — $SELF en ${S_noyau_actif%%+*}, $PEER en ${P_noyau_actif%%+*} : les deux nœuds se relaient chaque nuit et ne se comportent pas pareil. Une révision se résorbe seule en 48 h (le standby la pose après la bascule) ; un écart de SÉRIE se résorbe à la main (voir « Nouvelle SÉRIE »)" ;;
        *)          warn "Parité des noyaux INCONNUE ($SELF='${S_noyau_actif:-vide}' $PEER='${P_noyau_actif:-vide}')" ;;
    esac
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }

    t "noyau à jour"            OK          verdict_noyau 6.12.75+rpt-rpi-2712 6.12.75+rpt-rpi-2712
    t "noyau en attente"        REDEMARRAGE verdict_noyau 6.12.62+rpt-rpi-2712 6.12.75+rpt-rpi-2712
    t "rien d'installé lu"      INCONNU     verdict_noyau 6.12.62+rpt-rpi-2712 ""

    t "noyaux identiques"       OK          verdict_noyaux_parite 6.12.75+rpt-rpi-2712 6.12.75+rpt-rpi-2712
    t "rpi1 / rpi2 le 27/09"    DIVERGENCE  verdict_noyaux_parite 6.12.62+rpt-rpi-2712 6.12.75+rpt-rpi-2712
    t "peer muet"               INCONNU     verdict_noyaux_parite 6.12.62+rpt-rpi-2712 ""
    #  Selon le rôle : le standby pose la révision après la bascule, l'actif suit.
    t "révision : standby en avance"   STANDBY_EN_AVANCE verdict_noyaux_parite_roles 6.18.50+rpt-rpi-2712 6.18.52+rpt-rpi-2712
    t "révision : tri numérique"       STANDBY_EN_AVANCE verdict_noyaux_parite_roles 6.18.9+rpt-rpi-2712 6.18.10+rpt-rpi-2712
    t "révision : l'ACTIF en avance"   DIVERGENCE  verdict_noyaux_parite_roles 6.18.52+rpt-rpi-2712 6.18.50+rpt-rpi-2712
    t "SÉRIE, même au standby → écart" DIVERGENCE  verdict_noyaux_parite_roles 6.12.75+rpt-rpi-2712 6.18.50+rpt-rpi-2712
    t "mêmes noyaux → OK"              OK          verdict_noyaux_parite_roles 6.18.50+rpt-rpi-2712 6.18.50+rpt-rpi-2712
    t "un côté muet → INCONNU"         INCONNU     verdict_noyaux_parite_roles 6.18.50+rpt-rpi-2712 ""

    #  #1395 — le noyau du standby. Les formes RÉELLES : uname -r et dpkg.
    t "version : uname -r"      6.18.50     version_noyau 6.18.50+rpt-rpi-2712
    t "version : dpkg (époque)" 6.18.50     version_noyau 1:6.18.50-1+rpt1
    t "candidat = en service"   RIEN        decision_noyau_candidat 6.18.50+rpt-rpi-2712 1:6.18.50-1+rpt1
    t "révision de la série"    REVISION    decision_noyau_candidat 6.18.50+rpt-rpi-2712 1:6.18.52-1+rpt1
    t "rpi1 le 27/09 : série"   SERIE       decision_noyau_candidat 6.12.62+rpt-rpi-2712 1:6.18.50-1+rpt1
    t "tri NUMÉRIQUE (6.18.9 < 6.18.10)" REVISION decision_noyau_candidat 6.18.9+rpt-rpi-2712 1:6.18.10-1+rpt1
    t "dépôt plus ancien → rien" RIEN       decision_noyau_candidat 6.12.75+rpt-rpi-2712 1:6.12.62-1+rpt1
    t "candidat illisible"      INCONNU     decision_noyau_candidat 6.18.50+rpt-rpi-2712 ""
    t "candidat (none) d'apt"   INCONNU     decision_noyau_candidat 6.18.50+rpt-rpi-2712 "(none)"

    t "à jour → rien"           RIEN        decision_redemarrage_standby 6.18.50+rpt-rpi-2712 6.18.50+rpt-rpi-2712 ""
    t "révision posée → redémarrer" REDEMARRER decision_redemarrage_standby 6.18.50+rpt-rpi-2712 6.18.52+rpt-rpi-2712 ""
    t "déjà tentée → on ne boucle pas" DEJA_TENTE decision_redemarrage_standby 6.18.50+rpt-rpi-2712 6.18.52+rpt-rpi-2712 6.18.52+rpt-rpi-2712
    t "tentative d'une AUTRE révision" REDEMARRER decision_redemarrage_standby 6.18.50+rpt-rpi-2712 6.18.53+rpt-rpi-2712 6.18.52+rpt-rpi-2712
    t "série posée à la main → main" SERIE  decision_redemarrage_standby 6.12.62+rpt-rpi-2712 6.18.50+rpt-rpi-2712 ""
    t "installé illisible"      INCONNU     decision_redemarrage_standby 6.18.50+rpt-rpi-2712 "" ""

    t "pas de marque → injoignable"   INJOIGNABLE   verdict_pair_injoignable ""
    t "marque de 90 s → redémarrage"  REDEMARRAGE   verdict_pair_injoignable 90
    t "marque à la limite (600 s)"    REDEMARRAGE   verdict_pair_injoignable 600
    t "marque de 11 min → ne repart pas" NE_REPART_PAS verdict_pair_injoignable 660
    t "marque de 3 jours → autre cause"  INJOIGNABLE verdict_pair_injoignable 259200
    t "marque illisible → injoignable"   INJOIGNABLE verdict_pair_injoignable "abc"

    #  Les conteneurs d'un AUTRE projet arrêtés par le redémarrage (28/09/2026) :
    #  rpi2 porte List-dons, et redémarrer ne vaut que si on constate son retour.
    t "aucun relevé → sans objet"          SANS_OBJET verdict_etrangers_revenus "" "" "" ""
    t "relevé sans conteneur → sans objet" SANS_OBJET verdict_etrangers_revenus 90 "" "" 1
    t "tous revenus"                       REVENUS    verdict_etrangers_revenus 90 listdons_app "" 1
    t "absent à 2 min → en cours"          EN_COURS   verdict_etrangers_revenus 120 listdons_app listdons_app 1
    t "absent à 11 min → ABSENTS"          ABSENTS    verdict_etrangers_revenus 660 listdons_app listdons_app 1
    t "relevé de 3 jours → sans objet"     SANS_OBJET verdict_etrangers_revenus 259200 listdons_app listdons_app 1
    t "docker illisible → INCONNU, jamais REVENUS" INCONNU verdict_etrangers_revenus 660 listdons_app "" ""
    t "horodatage illisible → INCONNU"     INCONNU    verdict_etrangers_revenus illisible listdons_app "" 1

    #  La collecte elle-même, sur un relevé et un `docker ps` simulés : c'est
    #  elle qui dit « revenu » — un conteneur en route ou malade ne l'est pas.
    tmpe=$(mktemp)
    printf '%s\nlistdons_app\nautre_app\n' "$(( $(date +%s) - 700 ))" > "$tmpe"
    docker() { printf 'listdons_app Up 2 minutes (healthy)\nautre_app Up 1 minute (health: starting)\nhostachy_api Up 3 hours\n'; }
    t "collecte : sain revenu, « starting » manquant" "autre_app" \
      eval 'eval "$(collecte_etrangers "$tmpe")" | sed -n "s/^etrangers_manquants=//p"'
    docker() { printf 'listdons_app Up 2 minutes (unhealthy)\n'; }
    t "collecte : « unhealthy » n'est pas revenu" "listdons_app,autre_app" \
      eval 'eval "$(collecte_etrangers "$tmpe")" | sed -n "s/^etrangers_manquants=//p"'
    docker() { return 1; }
    t "collecte : docker en échec → aucun verdict de retour" "" \
      eval 'eval "$(collecte_etrangers "$tmpe")" | grep -E "^etrangers_(lu|manquants)="'
    unset -f docker; rm -f "$tmpe"
    t "collecte : pas de relevé → rien" "" eval 'eval "$(collecte_etrangers "$tmpe")"'


    #  L'émission : jamais un vert, et le bon canal pour chaque cas.
    tmpm=$(mktemp); PEER=rpi2; PEER_IP=192.168.1.223
    warn() { echo "WARN $*"; }; fail() { echo "FAIL $*"; }
    MARQUE_REDEMARRAGE=$tmpm
    echo "$(( $(date +%s) - 60 )) 6.18.52+rpt-rpi-2712" > "$tmpm"
    t "marque fraîche → WARN" WARN eval 'pair_injoignable_emettre | cut -d" " -f1'
    echo "$(( $(date +%s) - 1200 )) 6.18.52+rpt-rpi-2712" > "$tmpm"
    t "marque de 20 min → FAIL" FAIL eval 'pair_injoignable_emettre | cut -d" " -f1'
    rm -f "$tmpm"
    t "sans marque → FAIL" FAIL eval 'pair_injoignable_emettre | cut -d" " -f1'
    #  #1598 : la cause dite par lib-ssh-noeuds termine le message ; muette, rien.
    t "la cause SSH termine le message" "nœuds. (clé non épinglée)" \
      eval 'pair_injoignable_emettre "(clé non épinglée)" | grep -o "nœuds\..*"'
    t "sans cause : le message s'arrête" "nœuds." eval 'pair_injoignable_emettre "" | grep -o "nœuds\..*"'
    #  #1610 — le constat de C30 pendant un passage d'installation : la boucle par
    #  nœud, exécutée sur les champs S_* de rpi1 (le relevé du 01/10 à 06:21).
    ok() { echo "OK $*"; }
    SELF=rpi1 PEER=rpi2 PEER_OK=1
    S_apt_erreurs=0 S_apt_listes_j=0 S_apt_secu=3 S_apt_secu_vu_s=86400 S_apt_passage_s=6
    S_noyau_actif=6.12.75+rpt-rpi-2712 S_noyau_installe=6.12.75+rpt-rpi-2712 S_noyau_candidat=1:6.12.75-1+rpt1
    S_apt_en_cours=non
    t "#1610 : le relevé du 01/10 sans passage en cours → WARN (le défaut reste vu)" 1 \
      eval 'mises_a_jour_verdicts | grep -c "^WARN 3 correctif(s) de sécurité en attente sur rpi1"'
    S_apt_en_cours=oui
    t "#1610 : passage en cours → AUCUN WARN (donc pas de digest)" 0 \
      eval 'mises_a_jour_verdicts | grep -c "^WARN"'
    t "#1610 : …dit INCONNU et nomme son nœud" 1 \
      eval 'mises_a_jour_verdicts | grep -c "^OK Mises à jour système sur rpi1 : un passage .*EN COURS.*INCONNU, revérifié au prochain passage"'
    S_apt_passage_s=10800
    t "#1610 : « en cours » depuis 3 h → le WARN revient (pas de masque permanent)" 1 \
      eval 'mises_a_jour_verdicts | grep -c "^WARN 3 correctif(s) de sécurité en attente sur rpi1"'
    unset S_apt_erreurs S_apt_listes_j S_apt_secu S_apt_secu_vu_s S_apt_passage_s S_apt_en_cours S_noyau_actif S_noyau_installe S_noyau_candidat SELF PEER PEER_OK

    t "commande manuelle : les paquets de la liste" \
      "ssh -t ptressard@192.168.1.223 'sudo apt-get update && sudo apt-get install --only-upgrade $NOYAU_PAQUETS && sudo reboot'" \
      commande_montee_noyau 192.168.1.223

    #  La collecte est du shell VALIDE une fois assemblée (même piège que COLLECT).
    if bash -n <(printf '%s' "$COLLECT_MAJ") 2>/dev/null; then echo "PASS  COLLECT_MAJ est du shell valide"
    else echo "FAIL  COLLECT_MAJ est du shell INVALIDE (apostrophe dans la chaîne ?)"; st=1; fi

    [ "$st" -eq 0 ] && echo "lib-mises-a-jour : tous les cas passent."
    exit "$st"
fi
