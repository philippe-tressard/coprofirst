#!/bin/bash
# =============================================================================
#  lib-paquets.sh — ce que C30 ne voyait pas des paquets d'un nœud (#1591)
#
#  Audit du 02/10/2026 : C30 ne comptait que les correctifs de sécurité
#  (`apt list --upgradable | grep -- "-security"`, `lib-apt.sh`) et le noyau.
#  Le reste — 222 paquets en attente sur rpi1, 191 sur rpi2, Docker en 29.2.1
#  d'un côté et 29.4.0 de l'autre, un tunnel `cloudflared` vieux de sept mois,
#  `initramfs-tools-core` retenu — n'était mesuré par rien, et C30 disait « aucun
#  correctif en attente ». Le même argument qui fait comparer les noyaux (« les
#  deux nœuds se relaient chaque nuit ») vaut pour le moteur de conteneurs et
#  pour le tunnel, le composant exposé.
#
#  Quatre questions, toutes en WARN (digest quotidien — aucune n'arrête le site) :
#    1. combien de paquets HORS sécurité attendent-ils, au-delà d'un seuil ?
#    2. des paquets sont-ils RETENUS (« kept back ») — `apt upgrade` ne les
#       installe pas, et `unattended-upgrades` non plus ?
#    3. docker, containerd et cloudflared sont-ils à la MÊME version sur les
#       deux nœuds ?
#    4. `Unattended-Upgrade::Mail` a-t-il la même valeur EFFECTIVE sur les deux
#       nœuds (#1677, 04/10/2026 : posé sur rpi1 seul, une ERROR par passage) ?
#
#  ⚠️ Ce module MESURE et DIT. Il ne pose rien : le geste vit dans
#  `noyau-standby.sh`, qui pose tout ce qui attend sur le standby après chaque
#  bascule (#2198, décision dans `lib-maj-paquets.sh`).
#
#  Lecture seule : `apt list`, `apt-get -s` (SIMULATION, sans verrou ni écriture)
#  et `dpkg-query`. Rien ne touche à la base ni aux volumes.
#
#  SOURCÉ (mode 100644) par `lib-mises-a-jour.sh`, qui reprend `COLLECT_PAQUETS`
#  dans `COLLECT_MAJ` et appelle `paquets_verdicts` depuis `mises_a_jour_verdicts`
#  (C30). La liste des paquets du noyau, déjà écrite là-bas (`NOYAU_PAQUETS`),
#  n'est pas recopiée : `paquets_verdicts` la lit, car ces paquets-là se posent
#  par `noyau-standby.sh` et sont retenus PAR CONSTRUCTION.
#  Autotest : bash scripts/lib/lib-paquets.sh --selftest
# =============================================================================

#: Au-delà, trop de paquets hors sécurité attendent : `unattended-upgrades` ne
#: pose que les origines Debian (docker.com, cloudflare, Raspberry Pi n'y sont
#: pas), et c'est `noyau-standby.sh` qui pose le reste, sur le standby, après
#: chaque bascule (#2198). Chaque nœud est donc à jour en 48 h : 20 absorbe deux
#: jours de dépôts. Il valait 100 avant que le geste existe, et laissait passer
#: les 16 paquets du 23/10/2026 — Node.js vulnérable et le tunnel compris.
APT_HORS_SECU_MAX=${APT_HORS_SECU_MAX:-20}

#: Les paquets dont la version doit être la même sur les deux nœuds : le moteur
#: de conteneurs, son runtime, et le tunnel. UNE liste, pour la collecte ET pour
#: la décision.
PAQUETS_PARITE="docker-ce containerd.io cloudflared"

#  Le nom du champ de collecte d'un paquet : `containerd.io` → `ver_containerd_io`.
#  Un point ou un tiret ne passe pas dans un nom de variable (`parse` fait un eval).
cle_version() { echo "ver_${1//[^A-Za-z0-9]/_}"; }

# ── La collecte, exécutée sur CHAQUE nœud (reprise par COLLECT_MAJ) ──────────
#  Même contrainte que `lib-collecte.sh` : chaîne entre guillemets SIMPLES, donc
#  AUCUNE apostrophe dans le fragment, même en commentaire. Tout s'explique ici :
#   - apt_hors_secu : paquets en attente MOINS ceux d'un dépôt `*-security` (même
#     définition que `lib-apt.sh`) ; vide si apt manque ou échoue : INCONNU ;
#   - apt_retenus : « ok: » puis les paquets « kept back » de la simulation
#     `apt-get -s upgrade` (LC_ALL=C : le texte est celui de la locale), séparés
#     par des virgules. Le marqueur « ok: » distingue « aucun » de « simulation
#     impossible » (verrou pris, apt-get absent), qui rend VIDE — cas zéro ;
#   - ver_<paquet> : la version installée, « absent » si dpkg répond que le
#     paquet n est pas installé ET qu aucun binaire du même nom ne répond,
#     VIDE si dpkg-query manque. 🔴 Le binaire est interrogé quand dpkg ne
#     connaît pas le paquet : le 04/10/2026, rpi2 faisait tourner un cloudflared
#     2026.3.0 posé à la main (scripts/installation/install-cloudflared.sh, hors
#     apt) et le contrôle disait « absent » — comme si le tunnel n existait pas,
#     alors que c était lui qui portait la production. On mesure ce qui TOURNE,
#     pas ce que le gestionnaire de paquets en sait (standards/04 §3, §14).
collecte_paquets() {
    local p
    printf '%s' '
if command -v apt >/dev/null 2>&1 && _u=$(apt list --upgradable 2>/dev/null); then
_t=$(printf "%s\n" "$_u" | grep -c "\[upgradable")
_x=$(printf "%s\n" "$_u" | grep "\[upgradable" | grep -c -- "-security")
echo "apt_hors_secu=$(( _t - _x ))"
else
echo "apt_hors_secu="
fi
if command -v apt-get >/dev/null 2>&1 && _k=$(LC_ALL=C apt-get -s upgrade 2>/dev/null); then
echo "apt_retenus=ok:$(printf "%s\n" "$_k" | awk "/have been kept back/ { f = 1; next } f && /^  / { for (i = 1; i <= NF; i++) print \$i; next } { f = 0 }" | sort -u | paste -sd, -)"
else
echo "apt_retenus="
fi
if command -v dpkg-query >/dev/null 2>&1; then
_pv() { _s=$(dpkg-query -W -f "\${Status}|\${Version}" "$1" 2>/dev/null); case "$_s" in "install ok installed|"*) echo "${_s#*|}" ;; *) _b=$("$1" --version 2>/dev/null | head -1 | grep -oE "[0-9]+(\.[0-9]+)+" | head -1); echo "${_b:-absent}" ;; esac; }
'
    for p in $PAQUETS_PARITE; do printf 'echo "%s=$(_pv %s)"\n' "$(cle_version "$p")" "$p"; done
    printf '%s\n' 'else'
    for p in $PAQUETS_PARITE; do printf 'echo "%s="\n' "$(cle_version "$p")"; done
    printf '%s\n' 'fi'
    #  uu_mail : « ok: » puis la valeur EFFECTIVE de Unattended-Upgrade::Mail
    #  (vide après « ok: » si elle n est pas posée), lue par apt-config sans sudo ;
    #  VIDE si apt-config manque ou échoue — cas zéro (#1677).
    printf '%s' '
if command -v apt-config >/dev/null 2>&1 && _ac=$(apt-config dump 2>/dev/null); then
echo "uu_mail=ok:$(printf "%s\n" "$_ac" | sed -n "s/^Unattended-Upgrade::Mail \"\(.*\)\";\$/\1/p" | head -1)"
else
echo "uu_mail="
fi
'
}
COLLECT_PAQUETS=$(collecte_paquets)

# ── Décisions PURES (aucun effet de bord) ────────────────────────────────────

#  $1 nombre de paquets hors sécurité en attente → OK | TROP | INCONNU
verdict_hors_secu() {
    case "${1:-}" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    [ "$1" -gt "$APT_HORS_SECU_MAX" ] && echo TROP || echo OK
}

#  $1 le relevé « ok:a,b,c » · $2 les paquets à ne pas compter (séparés par des
#  espaces) → la liste « a,b » des paquets retenus qui comptent ; ne rend RIEN et
#  échoue si le relevé n'a pas le marqueur « ok: » (mesure impossible).
retenus_utiles() {
    local r=${1:-} x=${2:-} n out=''
    case "$r" in ok:*) r=${r#ok:} ;; *) return 1 ;; esac
    local IFS=,
    for n in $r; do
        case " $x " in *" $n "*) continue ;; esac
        out="$out${out:+,}$n"
    done
    printf '%s' "$out"
}

#  $1 le relevé · $2 les exclus → OK | RETENUS | INCONNU
#  Les paquets du noyau sont retenus par construction : le méta-paquet change de
#  dépendances à chaque révision, et `noyau-standby.sh` les pose. Les compter
#  ferait un WARN permanent sur un fait qui a déjà son propre geste.
verdict_retenus() {
    local u
    u=$(retenus_utiles "${1:-}" "${2:-}") || { echo INCONNU; return; }
    [ -n "$u" ] && echo RETENUS || echo OK
}

#  $1 et $2 : la version d'un paquet sur les deux nœuds → OK | DIVERGENCE | INCONNU
#  « absent » des deux côtés est un fait mesuré, identique (OK) ; une version vide
#  (dpkg-query illisible) n'est jamais une égalité — cas zéro.
verdict_versions_parite() {
    [ -n "${1:-}" ] && [ -n "${2:-}" ] || { echo INCONNU; return; }
    [ "$1" = "$2" ] && echo OK || echo DIVERGENCE
}

#  $1 la version de l'ACTIF, $2 celle du STANDBY → OK | STANDBY_EN_AVANCE |
#  DIVERGENCE | INCONNU. Seul le standby pose ces paquets, après chaque bascule
#  (`noyau-standby.sh`, #2198) : une version publiée entre deux nuits le met en
#  avance sur l'actif pour un jour, et l'actif la prend à la bascule suivante,
#  devenu standby à son tour. C'est le geste qui marche, pas un écart — le
#  28/10/2026, cloudflared 2026.10.5 sur rpi2, 2026.10.4 sur rpi1 : WARN au digest.
#  L'ACTIF en avance, lui, dit un standby qui n'a pas posé ce qu'il devait : écart.
#  « absent » d'un côté n'est jamais une avance (sort -V le rangerait après tout
#  chiffre) ; une version vide reste INCONNU.
verdict_versions_parite_roles() {
    local v
    v=$(verdict_versions_parite "${1:-}" "${2:-}")
    [ "$v" = DIVERGENCE ] || { echo "$v"; return; }
    case "$1|$2" in absent\|*|*\|absent) echo DIVERGENCE; return ;; esac
    [ "$(printf '%s
%s
' "$1" "$2" | sort -V | tail -1)" = "$2" ] && echo STANDBY_EN_AVANCE || echo DIVERGENCE
}

#  $1 `.active` lu sur ce nœud · $2 lu sur le pair · $3 ce nœud · $4 le pair
#  → S (ce nœud est l'actif) | P (le pair l'est) | rien. Le rôle ne compte que
#  si les deux `.active` le disent : sinon, aucune avance du standby n'est admise
#  (C3 dit déjà l'incohérence). Une source pour les paquets ET le noyau.
cote_actif() {
    [ -n "${1:-}" ] && [ "$1" = "${2:-}" ] || return 0
    case "$1" in "${3:-}") echo S ;; "${4:-}") echo P ;; esac
}

# ── Les verdicts de C30 pour ce module, appelés par `mises_a_jour_verdicts` ──
#  Dépend de l'appelant : ok/warn, SELF/PEER/PEER_OK et les champs S_*/P_*.
#  Tout sort en WARN (digest), jamais en FAIL. Un `apt-get -s` qui échoue PENDANT
#  un passage d'installation (verrou) n'est pas une panne : dit en `ok`, comme
#  C30 le fait pour `EN_COURS` (#1610) — un `warn` partirait au digest.
paquets_verdicts() {
    local n p hs rt enc k a b v act='' ecarts='' inconnus='' avances=''
    for n in "$SELF" "$PEER"; do
        if [ "$n" = "$SELF" ]; then p=S; else [ "$PEER_OK" -eq 0 ] || continue; p=P; fi
        eval "hs=\${${p}_apt_hors_secu:-} rt=\${${p}_apt_retenus:-} enc=\${${p}_apt_en_cours:-}"
        case "$(verdict_hors_secu "$hs")" in
            OK)   ok   "Paquets hors sécurité en attente sur $n : $hs (seuil ${APT_HORS_SECU_MAX})" ;;
            TROP) warn "$hs paquets hors sécurité en attente sur $n (seuil ${APT_HORS_SECU_MAX}) — le standby les pose après chaque bascule (noyau-standby.sh, #2198) : un reste au-delà du seuil dit un geste qui n'a pas abouti ou des paquets ÉCARTÉS (ils ramèneraient la pile de bureau) — lignes [noyau] de /var/log/hostachy-bascule.log" ;;
            *)    if [ "$enc" = oui ]; then ok "Paquets hors sécurité sur $n : un passage d'installation est EN COURS — INCONNU, revérifié au prochain passage (#1591)"
                  else warn "Paquets hors sécurité en attente sur $n INCONNUS (valeur='${hs:-vide}') — ni vert ni rouge"; fi ;;
        esac
        case "$(verdict_retenus "$rt" "${NOYAU_PAQUETS:-}")" in
            OK)      ok   "Aucun paquet retenu (kept back) sur $n" ;;
            RETENUS) k=$(retenus_utiles "$rt" "${NOYAU_PAQUETS:-}")
                     warn "Paquet(s) retenu(s) (kept back) sur $n : ${k//,/, } — ni 'apt upgrade' ni unattended-upgrades ne les installent (nouvelles dépendances, fichier de configuration modifié) : 'apt-get -s upgrade' dit pourquoi (#1591)" ;;
            *)       if [ "$enc" = oui ]; then ok "Paquets retenus sur $n : un passage d'installation est EN COURS — INCONNU, revérifié au prochain passage (#1591)"
                     else warn "Paquets retenus (kept back) de $n INCONNUS (simulation apt impossible : '${rt:-vide}') — ni vert ni rouge"; fi ;;
        esac
    done
    [ "$PEER_OK" -eq 0 ] || return 0
    #  Un constat COMMUN (il nomme les deux nœuds) : l'actif le porte, une fois.
    act=$(cote_actif "${S_active:-}" "${P_active:-}" "$SELF" "$PEER")
    for k in $PAQUETS_PARITE; do
        eval "a=\${S_$(cle_version "$k"):-} b=\${P_$(cle_version "$k"):-}"
        case "$act" in
            S) v=$(verdict_versions_parite_roles "$a" "$b") ;;
            P) v=$(verdict_versions_parite_roles "$b" "$a") ;;
            *) v=$(verdict_versions_parite "$a" "$b") ;;
        esac
        case "$v" in
            OK)                ;;
            STANDBY_EN_AVANCE) avances="$avances${avances:+ ; }$k : $SELF $a, $PEER $b" ;;
            DIVERGENCE)        ecarts="$ecarts${ecarts:+ ; }$k : $SELF $a, $PEER $b" ;;
            *)                 inconnus="$inconnus${inconnus:+, }$k" ;;
        esac
    done
    [ -z "$avances" ] || ok "Standby en avance sur l'actif ($S_active) — $avances : posé(s) après la bascule (#2198), l'actif les prend à la suivante"
    [ -z "$ecarts" ] || warn "Versions DIVERGENTES entre $SELF et $PEER — $ecarts : les deux nœuds se relaient chaque nuit et le moteur de conteneurs (comme le tunnel) ne devrait pas différer d'un jour à l'autre ; aligner le STANDBY d'abord (#1591)"
    [ -z "$inconnus" ] || warn "Parité des versions INCONNUE pour ${inconnus} entre $SELF et $PEER (dpkg-query illisible sur un nœud) — ni vert ni rouge"
    if [ -z "$ecarts" ] && [ -z "$inconnus" ] && [ -z "$avances" ]; then
        ok "Mêmes versions de ${PAQUETS_PARITE// /, } sur les 2 nœuds"
    fi
    #  #1677 : `Unattended-Upgrade::Mail "root"` sur rpi1 seul — sans /usr/bin/mail,
    #  une ERROR par passage et aucun courrier. La comparaison est celle des
    #  versions (`verdict_versions_parite`) : « ok: » vide des deux côtés est un
    #  fait mesuré, identique ; un relevé VIDE n'est jamais une égalité.
    a=${S_uu_mail:-} b=${P_uu_mail:-}
    case "$(verdict_versions_parite "$a" "$b")" in
        OK)         ok   "Unattended-Upgrade::Mail identique sur les 2 nœuds ($(valeur_uu_mail "$a"))" ;;
        DIVERGENCE) warn "Unattended-Upgrade::Mail DIFFÈRE entre $SELF et $PEER — $SELF $(valeur_uu_mail "$a"), $PEER $(valeur_uu_mail "$b") : sans /usr/bin/mail, le nœud qui le pose écrit une ERROR à chaque passage et rien ne part ; aligner les deux (/etc/apt/apt.conf.d/50unattended-upgrades, #1677)" ;;
        *)          warn "Unattended-Upgrade::Mail : comparaison INCONNUE entre $SELF et $PEER (apt-config illisible sur un nœud) — ni vert ni rouge" ;;
    esac
}

#  PURE. Le relevé « ok:<valeur> » → « « valeur » » ou « non posé ».
valeur_uu_mail() {
    case "${1:-}" in
        ok:) echo "non posé" ;;
        ok:*) echo "« ${1#ok:} »" ;;
        *) echo "illisible" ;;
    esac
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → ${r:-(rien)}" || { echo "FAIL  $1  attendu=${2:-(rien)} obtenu=${r:-(rien)}"; st=1; }; }

    echo "== (1) paquets hors sécurité =="
    t "au seuil exact → OK"                     OK       verdict_hors_secu 20
    t "un de plus → TROP"                       TROP     verdict_hors_secu 21
    t "rpi1 le 02/10 : 222 en attente"          TROP     verdict_hors_secu 222
    t "aucun → OK"                              OK       verdict_hors_secu 0
    t "vide (apt illisible) → INCONNU"          INCONNU  verdict_hors_secu ""
    t "non numérique → INCONNU, jamais OK"      INCONNU  verdict_hors_secu "n/a"

    echo "== (2) paquets retenus =="
    NOY="linux-image-rpi-2712 linux-image-rpi-v8 raspi-firmware"
    t "rien de retenu (mesuré) → OK"                OK       verdict_retenus "ok:" "$NOY"
    t "initramfs-tools-core retenu (rpi1, 02/10)"  RETENUS  verdict_retenus "ok:initramfs-tools-core" "$NOY"
    t "seuls des paquets du noyau → OK (leur geste existe)" OK verdict_retenus "ok:linux-image-rpi-2712,raspi-firmware" "$NOY"
    t "un du noyau et un autre → RETENUS"           RETENUS  verdict_retenus "ok:linux-image-rpi-v8,bluez" "$NOY"
    t "liste utile : le noyau est retiré, l'ordre gardé" "bluez,libfoo" retenus_utiles "ok:bluez,linux-image-rpi-v8,libfoo" "$NOY"
    t "simulation impossible (vide) → INCONNU"      INCONNU  verdict_retenus "" "$NOY"
    t "sans marqueur « ok: » → INCONNU, jamais OK"  INCONNU  verdict_retenus "bluez" "$NOY"
    t "un nom qui CONTIENT un exclu n'est pas exclu" RETENUS verdict_retenus "ok:raspi-firmware-extra" "$NOY"

    echo "== (3) parité des versions =="
    t "identiques"                               OK          verdict_versions_parite 5:29.2.1-1 5:29.2.1-1
    t "docker 29.2.1 / 29.4.0 (02/10)"           DIVERGENCE  verdict_versions_parite 5:29.2.1-1 5:29.4.0-1
    t "absent des deux → identique, mesuré"      OK          verdict_versions_parite absent absent
    t "présent d'un seul côté → DIVERGENCE"      DIVERGENCE  verdict_versions_parite 2026.9.3 absent
    t "vide d'un côté → INCONNU, jamais OK"      INCONNU     verdict_versions_parite 5:29.2.1-1 ""
    t "vide des deux côtés → INCONNU (pas « égaux »)" INCONNU verdict_versions_parite "" ""
    echo "== (3 bis) parité selon le rôle : le standby pose, l'actif suit (#2198) =="
    t "côté actif : ce nœud"                   S  cote_actif rpi1 rpi1 rpi1 rpi2
    t "côté actif : le pair"                   P  cote_actif rpi2 rpi2 rpi1 rpi2
    t ".active incohérent → aucun côté"        "" cote_actif rpi1 rpi2 rpi1 rpi2
    t ".active vide des deux côtés → aucun"    "" cote_actif "" "" rpi1 rpi2
    t "identiques → OK"                                     OK                verdict_versions_parite_roles 2026.10.5 2026.10.5
    t "cloudflared actif 10.4 / standby 10.5 (28/10)"       STANDBY_EN_AVANCE verdict_versions_parite_roles 2026.10.4 2026.10.5
    t "actif en avance → DIVERGENCE (le standby n'a pas posé)" DIVERGENCE     verdict_versions_parite_roles 2026.10.5 2026.10.4
    t "ordre numérique, pas lexical (9 < 10)"               STANDBY_EN_AVANCE verdict_versions_parite_roles 2026.9.3 2026.10.4
    t "époque docker comprise"                              STANDBY_EN_AVANCE verdict_versions_parite_roles 5:29.2.1-1 5:29.4.0-1
    t "absent sur l'actif → DIVERGENCE, jamais une avance"  DIVERGENCE        verdict_versions_parite_roles absent 2026.10.5
    t "absent sur le standby → DIVERGENCE"                  DIVERGENCE        verdict_versions_parite_roles 2026.10.5 absent
    t "vide d'un côté → INCONNU"                            INCONNU           verdict_versions_parite_roles "" 2026.10.5
    t "clé d'un paquet à point" ver_containerd_io cle_version containerd.io
    t "clé d'un paquet à tiret" ver_docker_ce     cle_version docker-ce

    echo "== la collecte, exécutée sur des apt et dpkg simulés aux formes RÉELLES =="
    apt() { cat <<'X'
Listing...
libheif1/stable-security 1.23.4-1~deb13u1 arm64 [upgradable from: 1.19.8-1+deb13u1]
bluez/stable 5.82-1.1+rpt2 arm64 [upgradable from: 5.82-1.1+rpt1]
docker-ce/trixie 5:29.8.2-1~debian.13~trixie arm64 [upgradable from: 5:29.2.1-1~debian.13~trixie]
cloudflared/any 2026.9.3 arm64 [upgradable from: 2026.3.0]
X
    }
    apt-get() { cat <<'X'
NOTE: This is only a simulation!
      apt-get needs root privileges for real execution.
Reading package lists...
Calculating upgrade...
The following packages have been kept back:
  initramfs-tools-core linux-image-rpi-2712
  raspi-firmware
The following packages will be upgraded:
  bluez libheif1
2 upgraded, 0 newly installed, 0 to remove and 3 not upgraded.
X
    }
    dpkg-query() { case "$4" in
        docker-ce)   echo "install ok installed|5:29.2.1-1~debian.13~trixie" ;;
        containerd.io) echo "install ok installed|2.2.1-1" ;;
        cloudflared) return 1 ;;
    esac; }
    champ() { eval "$COLLECT_PAQUETS" | sed -n "s/^$1=//p"; }
    t "collecte : 4 en attente dont 1 de sécurité → 3 hors sécurité" 3 champ apt_hors_secu
    t "collecte : retenus, sur plusieurs lignes, triés" "ok:initramfs-tools-core,linux-image-rpi-2712,raspi-firmware" champ apt_retenus
    t "collecte : version installée (époque comprise)" "5:29.2.1-1~debian.13~trixie" champ ver_docker_ce
    t "collecte : paquet à point dans son champ"        2.2.1-1  champ ver_containerd_io
    cloudflared() { return 1; }
    t "collecte : paquet non installé, aucun binaire → absent"  absent   champ ver_cloudflared
    #  04/10/2026 : rpi2 portait un cloudflared 2026.3.0 posé hors apt ; dpkg disait « absent ».
    cloudflared() { echo "cloudflared version 2026.3.0 (built 2026-03-09-14:08 UTC)"; }
    t "collecte : hors apt mais binaire présent → sa version, pas « absent »" 2026.3.0 champ ver_cloudflared
    t "collecte : le binaire ne masque pas un paquet que dpkg connaît"        "5:29.2.1-1~debian.13~trixie" champ ver_docker_ce
    unset -f cloudflared
    t "hors apt 2026.3.0 / apt 2026.9.3 → DIVERGENCE (rpi2 / rpi1, 04/10)" DIVERGENCE verdict_versions_parite 2026.3.0 2026.9.3
    apt-get() { cat <<'X'
Reading package lists...
Calculating upgrade...
0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.
X
    }
    t "collecte : aucun retenu → « ok: » vide (mesuré)" "ok:" champ apt_retenus
    #  #1677 : la valeur EFFECTIVE de Unattended-Upgrade::Mail, lue sans sudo.
    apt-config() { printf '%s\n' 'APT::Install-Recommends "0";' 'Unattended-Upgrade::Mail "root";' 'Unattended-Upgrade::MailReport "on-change";'; }
    t "collecte : Unattended-Upgrade::Mail posé (rpi1, 04/10)" "ok:root" champ uu_mail
    apt-config() { printf '%s\n' 'APT::Install-Recommends "0";' 'Unattended-Upgrade::MailReport "on-change";'; }
    t "collecte : Mail non posé (rpi2) → « ok: » vide, mesuré" "ok:" champ uu_mail
    apt-config() { return 1; }
    t "collecte : apt-config en échec → VIDE (INCONNU)" "" champ uu_mail
    unset -f apt-config
    apt() { return 1; }; apt-get() { return 100; }
    t "collecte : apt en échec → hors sécurité VIDE (INCONNU)" "" champ apt_hors_secu
    t "collecte : simulation en échec (verrou) → retenus VIDE"  "" champ apt_retenus
    unset -f apt apt-get dpkg-query champ
    t "collecte : sans apt ni dpkg → champs vides, jamais 0/absent" "apt_hors_secu=|apt_retenus=|ver_docker_ce=|ver_containerd_io=|ver_cloudflared=|uu_mail=" \
      eval 'PATH=/nonexistent "$BASH" -c "$COLLECT_PAQUETS" | paste -sd"|" -'
    t "collecte : un champ par paquet de la liste" 3 eval 'grep -c "^ver_" <<< "$(PATH=/nonexistent "$BASH" -c "$COLLECT_PAQUETS")"'
    if bash -n <(printf '%s' "$COLLECT_PAQUETS") 2>/dev/null; then echo "PASS  COLLECT_PAQUETS est du shell valide"
    else echo "FAIL  COLLECT_PAQUETS est du shell INVALIDE (apostrophe dans la chaîne ?)"; st=1; fi
    t "collecte : aucune apostrophe dans la chaîne (elle ferme les quotes)" 0 eval 'printf "%s" "$COLLECT_PAQUETS" | grep -c "$(printf "\047")"'

    echo "== les constats, sur les DEUX nœuds =="
    ok()   { echo "OK $*"; }
    warn() { echo "WARN $*"; }
    SELF=rpi1 PEER=rpi2 PEER_OK=0 NOYAU_PAQUETS="$NOY"
    plein() { # rpi1 et rpi2 sains
        S_apt_hors_secu=12 P_apt_hors_secu=9 S_apt_retenus="ok:" P_apt_retenus="ok:linux-image-rpi-2712"
        S_ver_docker_ce=5:29.4.0-1 P_ver_docker_ce=5:29.4.0-1 S_ver_containerd_io=2.2.3 P_ver_containerd_io=2.2.3
        S_ver_cloudflared=2026.9.3 P_ver_cloudflared=2026.9.3 S_apt_en_cours=non P_apt_en_cours=non
        S_uu_mail="ok:" P_uu_mail="ok:" S_active=rpi1 P_active=rpi1
    }
    plein; sortie=$(paquets_verdicts)
    t "deux nœuds sains → aucun WARN"       0 eval 'grep -c "^WARN" <<< "$sortie"'
    t "…et la parité dit OK"                1 eval 'grep -c "^OK Mêmes versions de docker-ce, containerd.io, cloudflared" <<< "$sortie"'
    #  Les faits du 02/10/2026, un à un.
    plein; S_apt_hors_secu=222 P_apt_hors_secu=191; sortie=$(paquets_verdicts)
    t "222 / 191 en attente → un WARN par nœud, chacun nommé" "1|1" \
      eval 'echo "$(grep -c "^WARN 222 paquets hors sécurité en attente sur rpi1" <<< "$sortie")|$(grep -c "^WARN 191 paquets hors sécurité en attente sur rpi2" <<< "$sortie")"'
    plein; S_apt_retenus="ok:initramfs-tools-core"; sortie=$(paquets_verdicts)
    t "initramfs-tools-core retenu sur rpi1 seul → WARN qui nomme rpi1" 1 \
      eval 'grep -c "^WARN Paquet(s) retenu(s) (kept back) sur rpi1 : initramfs-tools-core" <<< "$sortie"'
    t "…et rien sur rpi2" 0 eval 'grep -c "Paquet(s) retenu(s) (kept back) sur rpi2" <<< "$sortie"'
    #  02/10/2026 : l'ACTIF en retard ne s'admet plus (#2198) — ici rpi2 actif, en avance.
    plein; S_active=rpi2 P_active=rpi2 S_ver_docker_ce=5:29.2.1-1 P_ver_docker_ce=5:29.4.0-1 S_ver_containerd_io=2.2.1 P_ver_containerd_io=2.2.3; sortie=$(paquets_verdicts)
    t "docker ET containerd divergents → UN WARN commun qui nomme les deux paquets et les deux nœuds" 1 \
      eval 'grep -c "^WARN Versions DIVERGENTES entre rpi1 et rpi2 — docker-ce : rpi1 5:29.2.1-1, rpi2 5:29.4.0-1 ; containerd.io : rpi1 2.2.1, rpi2 2.2.3" <<< "$sortie"'
    #  28/10/2026 : rpi1 actif en 2026.10.4, rpi2 standby en 2026.10.5 — le geste de #2198.
    plein; S_ver_cloudflared=2026.10.4 P_ver_cloudflared=2026.10.5; sortie=$(paquets_verdicts)
    t "standby en avance → aucun WARN, un OK qui nomme l'avance" "0|1"       eval 'echo "$(grep -c "^WARN" <<< "$sortie")|$(grep -c "^OK Standby en avance sur l.actif (rpi1) — cloudflared : rpi1 2026.10.4, rpi2 2026.10.5" <<< "$sortie")"'
    t "…et pas de « mêmes versions » : ce n'est pas vrai" 0 eval 'grep -c "^OK Mêmes versions" <<< "$sortie"'
    plein; S_active=rpi2 P_active=rpi2 S_ver_cloudflared=2026.10.4 P_ver_cloudflared=2026.10.5; sortie=$(paquets_verdicts)
    t "l'ACTIF (rpi2, vu de rpi1) en avance → WARN DIVERGENTES" 1 eval 'grep -c "^WARN Versions DIVERGENTES entre rpi1 et rpi2 — cloudflared" <<< "$sortie"'
    plein; S_active=rpi1 P_active=rpi2 S_ver_cloudflared=2026.10.4 P_ver_cloudflared=2026.10.5; sortie=$(paquets_verdicts)
    t ".active incohérent → aucune avance admise, WARN" 1 eval 'grep -c "^WARN Versions DIVERGENTES" <<< "$sortie"'
    plein; S_ver_cloudflared=2026.10.4 P_ver_cloudflared=2026.10.5 S_ver_docker_ce=5:29.4.0-1 P_ver_docker_ce=5:29.2.1-1; sortie=$(paquets_verdicts)
    t "une avance ET un écart → l'écart reste WARN, l'avance OK" "1|1"       eval 'echo "$(grep -c "^WARN Versions DIVERGENTES entre rpi1 et rpi2 — docker-ce" <<< "$sortie")|$(grep -c "^OK Standby en avance" <<< "$sortie")"'
    plein; P_ver_cloudflared=""; sortie=$(paquets_verdicts)
    t "cloudflared illisible sur rpi2 → WARN INCONNU, pas de « mêmes versions »" "1|0" \
      eval 'echo "$(grep -c "^WARN Parité des versions INCONNUE pour cloudflared" <<< "$sortie")|$(grep -c "^OK Mêmes versions" <<< "$sortie")"'
    plein; S_apt_hors_secu=""; S_apt_retenus=""; sortie=$(paquets_verdicts)
    t "rien mesuré sur rpi1 → deux WARN INCONNU, jamais OK" "2|0" \
      eval 'echo "$(grep -c "^WARN .*INCONNUS" <<< "$sortie")|$(grep -c "^OK .* sur rpi1 : [0-9]" <<< "$sortie")"'
    plein; S_apt_hors_secu=""; S_apt_retenus=""; S_apt_en_cours=oui; sortie=$(paquets_verdicts)
    t "mesure impossible PENDANT un passage d'installation → aucun WARN" 0 eval 'grep -c "^WARN" <<< "$sortie"'
    #  #1677 : rpi1 portait `Unattended-Upgrade::Mail "root"`, rpi2 non — une
    #  ERROR par passage sur rpi1 (aucun /usr/bin/mail), que rien ne comparait.
    plein; S_uu_mail="ok:root"; sortie=$(paquets_verdicts)
    t "Mail posé sur rpi1 seul → UN WARN qui nomme la valeur des deux nœuds" 1 \
      eval 'grep -c "^WARN Unattended-Upgrade::Mail DIFFÈRE entre rpi1 et rpi2 — rpi1 « root », rpi2 non posé" <<< "$sortie"'
    plein; S_uu_mail="ok:root" P_uu_mail="ok:root"; sortie=$(paquets_verdicts)
    t "même valeur sur les deux → aucun WARN" 0 eval 'grep -c "^WARN" <<< "$sortie"'
    plein; P_uu_mail=""; sortie=$(paquets_verdicts)
    t "Mail illisible sur rpi2 → WARN INCONNU, jamais OK" 1 \
      eval 'grep -c "^WARN Unattended-Upgrade::Mail : comparaison INCONNUE" <<< "$sortie"'
    plein; PEER_OK=255; sortie=$(paquets_verdicts)
    t "pair injoignable : rien sur rpi2, pas de parité" "0" eval 'grep -c "rpi2" <<< "$sortie"'
    unset -f plein ok warn

    [ "$st" -eq 0 ] && echo "lib-paquets : tous les cas passent."
    exit "$st"
fi
