#!/bin/bash
# =============================================================================
#  lib-paquets-proscrits.sh — C35 : la pile de bureau est-elle REVENUE sur un nœud ?
#
#  Né de #1648 (03/10/2026). Les deux nœuds sont des Raspberry Pi OS **Desktop** :
#  navigateurs, lecteur vidéo, VNC, impression, `rpcbind`/NFS… (~850 paquets) que
#  rien dans le projet n'emploie, et qui ouvrent une surface d'attaque (`rpcbind`
#  sur le LAN de rpi1, #1593). Le 03/10/2026 la pile a été retirée du standby par
#  `scripts/exploitation/alleger-noeud.sh`. Rien ne surveillait que cela TIENNE, et
#  trois évènements extérieurs la ramènent sans que personne le décide :
#    - une mise à jour : le `full-upgrade` du 03/10 a installé ~22 paquets neufs
#      de bureau, les méta-paquets `rpd-*` changeant de dépendances à chaque version ;
#    - `APT::Install-Recommends "1"` (défaut Debian) : un simple `apt install`
#      d'un outil ramène ses paquets recommandés, dont du bureau ;
#    - une réinstallation depuis l'image (`docs/restauration-complete.md`) : le
#      nœud redevient un Pi OS Desktop complet.
#
#  Trois mesures, par nœud, sans root et en lecture seule :
#    1. des paquets de la LISTE PROSCRITE sont-ils installés ? (et qui les a tirés)
#    2. la cible systemd par défaut est-elle redevenue `graphical.target` ?
#    3. `APT::Install-Recommends` est-il autre chose que `0` ?
#
#  🔴 LA LISTE S'ÉCRIT UNE FOIS, ICI (`PAQUETS_PROSCRITS`, `PAQUETS_GARDES`), et deux
#  lecteurs la relisent : ce contrôle et `alleger-noeud.sh`, qui la SOURCE. Ce
#  script vivait dans `/home/ptressard/` des deux nœuds, hors du dépôt : une liste
#  recopiée dans chacun aurait divergé au premier ajout, et le contrôle aurait
#  jugé « revenu » ce que le script ne retire pas (ou l'inverse).
#
#  WARN au pire, par nœud, qui le nomme (digest quotidien et Admin › Maintenance,
#  comme C33/C34). Aucune correction ici : ce module MESURE. `sudo` demande un mot
#  de passe sur les deux nœuds, la correction est un geste manuel.
#
#  SOURCÉ (mode 100644) par `lib-collecte.sh` (`collecte_paquets_proscrits`, repris
#  dans COLLECT), par `alleger-noeud.sh` (la liste seule) ; `paquets_proscrits_verdicts`
#  est appelé par `lib-conformite.sh`. ⚠️ Il emploie `ok`, `warn`, `$SELF`, `$PEER`,
#  `$PEER_OK` et les champs S_*/P_* de son appelant.
#  Autotest : bash scripts/lib/lib-paquets-proscrits.sh --selftest
# =============================================================================

#: Les paquets PROSCRITS — la pile de bureau, et elle seule (motifs de `dpkg-query`).
#: Règle d'ajout : au moindre doute, le composant est CONSERVÉ. Ni les noyaux, ni
#: plymouth/initramfs (le démarrage reste inchangé), ni nodejs, build-essential,
#: mkvtoolnix, bluez : installés à la main ou sans effet nuisible.
#: La pile CAMÉRA aussi (#2692, 11/11/2026) : venue de l'image, sans caméra ni
#: dépendant hors d'elle-même, et retenue (kept back) à chaque version de libcamera
#: — le paquet de la bibliothèque change de nom, et ni `apt upgrade` ni
#: `noyau-standby.sh` ne posent une mise à jour qui en retire un.
PAQUETS_PROSCRITS="${PAQUETS_PROSCRITS:-chromium* firefox* vlc* libvlc* realvnc* wayvnc rpi-connect* rpi-imager rpi-userguide
pocketsphinx* labwc thonny mypy python3-mypy cups* hplip printer-driver-* nfs-common rpcbind
rpd-* lightdm* pi-greeter lxpanel* wf-panel-pi pcmanfm* libreoffice* geany* claws-mail*
sense-hat* python3-sense-hat scratch* wolfram* minecraft* sonic-pi* squeekboard* gvfs*
udisks2 accounts-daemon xserver-xorg* xwayland ffmpeg
rpicam-apps* librpicam-app* libcamera* libpisp* libtensorflow-lite*}"
#: Ce qui est gardé coûte que coûte, même si un motif ci-dessus le désigne : le
#: démarrage (plymouth). Hors du constat comme hors de l'allègement.
PAQUETS_GARDES="${PAQUETS_GARDES:-plymouth plymouth-themes rpd-plym-splash}"
#: Combien de paquets le constat nomme (avec leur « tireur ») : un nœud resté en Pi OS
#: Desktop en porte une centaine, et le message va au courriel et à l'écran. La
#: collecte ne cherche les tireurs que pour ceux-là (`apt-cache rdepends` : ~0,2 s
#: chacun), le reste est compté, pas décrit.
PROSCRITS_AFFICHES="${PROSCRITS_AFFICHES:-8}"

# ── La collecte, exécutée sur CHAQUE nœud (reprise par COLLECT) ──────────────
#  Même contrainte que `lib-collecte.sh` : fragment entre guillemets SIMPLES, donc
#  AUCUNE apostrophe, même en commentaire. Trois champs :
#   - proscrits : « ok: » puis « nom~tireur1+tireur2 » (trois tireurs au plus,
#     jamais un autre paquet proscrit : c'est la racine qui compte), séparés par des
#     virgules ; VIDE si dpkg ne répond pas. Le marqueur « ok: » distingue « aucun
#     paquet proscrit » de « dpkg illisible » — cas zéro : sans lui, les deux
#     seraient la même chaîne vide, donc un faux vert. `dpkg-query -W dpkg` est la
#     sonde : le paquet dpkg est toujours installé, sa réponse prouve que la base
#     se lit. `${db:Status-Abbrev}` rend « ii » suivi d une espace : le format en
#     ajoute une autre, d où `tr -s` avant `cut` (sans lui le nom est le champ
#     VIDE, et la mesure rend « ok: » sur un nœud qui porte toute la pile — vu sur
#     rpi2 le 03/10/2026, que les paquets simulés d un autotest ne montraient pas).
#     La liste est mise sur UNE ligne (`liste`) : un saut de ligne dans
#     `for … in` terminerait la boucle. `set -f` : les motifs (`chromium*`) ne doivent pas se développer
#     contre les fichiers du répertoire courant ;
#   - cible_systemd : `systemctl get-default`, VIDE s il échoue ;
#   - install_recommends : la valeur de APT::Install-Recommends, VIDE si apt-config
#     est absent. `tr -d` retire le point-virgule et les guillemets de « "1"; ».
collecte_paquets_proscrits() {
    local g='' n liste=${PAQUETS_PROSCRITS//$'\n'/ }
    for n in $PAQUETS_GARDES; do g="$g -e $n"; done
    printf '%s' '
if command -v dpkg-query >/dev/null 2>&1 && dpkg-query -W dpkg >/dev/null 2>&1; then
set -f
_pp=$(for _p in '"$liste"'; do dpkg-query -W -f "\${db:Status-Abbrev} \${Package}\n" "$_p" 2>/dev/null; done | grep "^ii " | tr -s " " | cut -d" " -f2 | sort -u | grep -vxF'"$g"')
set +f
_e=""
for _y in $_pp; do _e="$_e -e $_y"; done
_o=""; _i=0
for _x in $_pp; do
_i=$((_i+1)); _t=""
if [ "$_i" -le '"$PROSCRITS_AFFICHES"' ]; then _t=$(timeout 10 apt-cache rdepends --installed --no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances "$_x" 2>/dev/null | sed "1,2d" | tr -d " |" | sed "s/:[a-z0-9]*$//" | grep -vxF -e "$_x" $_e | sort -u | head -3 | paste -sd+ -); fi
_o="$_o${_o:+,}$_x${_t:+~$_t}"
done
echo "proscrits=ok:$_o"
else
echo "proscrits="
fi
echo "cible_systemd=$(systemctl get-default 2>/dev/null)"
echo "install_recommends=$(apt-config dump 2>/dev/null | grep "^APT::Install-Recommends " | cut -d" " -f2 | tr -d ";\"")"
'
}

# ── Décisions PURES (aucun effet de bord) ────────────────────────────────────

#  $1 le relevé « ok:a~x+y,b » → « a~x+y,b » (vide si aucun) ; échoue sans le
#  marqueur « ok: » (mesure impossible).
proscrits_liste() {
    case "${1:-}" in ok:*) printf '%s' "${1#ok:}" ;; *) return 1 ;; esac
}

#  $1 le relevé des paquets · $2 la cible systemd · $3 la valeur d'Install-Recommends
#  → OK | ECART | INCONNU. Un écart prime sur une mesure manquante : une pile de
#  bureau revenue se dit même si l'une des trois mesures a manqué.
verdict_proscrits() {
    local l ecart=0 inconnu=0
    if l=$(proscrits_liste "${1:-}"); then [ -n "$l" ] && ecart=1; else inconnu=1; fi
    case "${2:-}" in multi-user.target) ;; '') inconnu=1 ;; *) ecart=1 ;; esac
    case "${3:-}" in 0|false|no) ;; '') inconnu=1 ;; *) ecart=1 ;; esac
    if [ "$ecart" = 1 ]; then echo ECART; elif [ "$inconnu" = 1 ]; then echo INCONNU; else echo OK; fi
}

#  $1 « a~x+y,b » → le nombre de paquets
proscrits_compter() { local IFS=,; set -- ${1:-}; echo $#; }

#  $1 « a~x+y,b » → « a (tiré par x, y), b » ; au-delà de PROSCRITS_AFFICHES, les
#  suivants sont comptés (« … et 82 autres »), pas décrits.
proscrits_decrire_paquets() {
    local e out='' nom tir i=0 total
    local IFS=,
    set -- ${1:-}
    total=$#
    for e in "$@"; do
        [ "$i" -lt "$PROSCRITS_AFFICHES" ] || break
        i=$((i + 1))
        nom=${e%%~*}
        if [ "$nom" != "$e" ]; then tir=${e#*~}; out="$out${out:+, }$nom (tiré par ${tir//+/, })"
        else out="$out${out:+, }$nom"; fi
    done
    [ "$total" -gt "$i" ] && out="$out … et $((total - i)) autre(s)"
    printf '%s' "$out"
}

#  $1 relevé paquets · $2 cible → 0 si la pile est RÉELLEMENT revenue (un paquet
#  proscrit installé, ou une cible autre que multi-user), 1 si seul le réglage
#  d'apt la MENACE (Install-Recommends) : le message ne dit « revenue » que du premier.
proscrits_est_revenue() {
    local l
    if l=$(proscrits_liste "${1:-}") && [ -n "$l" ]; then return 0; fi
    case "${2:-}" in ''|multi-user.target) return 1 ;; *) return 0 ;; esac
}

#  Le message d'écart, une cause après l'autre, chacune avec SA correction.
#  $1 relevé paquets · $2 cible · $3 recommends
proscrits_decrire_ecarts() {
    local l out=''
    if l=$(proscrits_liste "${1:-}") && [ -n "$l" ]; then
        out="$(proscrits_compter "$l") paquet(s) proscrit(s) installé(s) : $(proscrits_decrire_paquets "$l") — à retirer par scripts/exploitation/alleger-noeud.sh, sur le STANDBY (il refuse un nœud qui sert)"
    fi
    case "${2:-}" in ''|multi-user.target) ;; *)
        out="$out${out:+ ; }cible systemd par défaut = ${2} au lieu de multi-user.target (sudo systemctl set-default multi-user.target)" ;;
    esac
    case "${3:-}" in ''|0|false|no) ;; *)
        out="$out${out:+ ; }APT::Install-Recommends vaut ${3} : un apt install ramène des paquets recommandés, dont du bureau (écrire APT::Install-Recommends \"0\"; dans /etc/apt/apt.conf.d/99-hostachy-sans-recommends)" ;;
    esac
    printf '%s' "$out"
}

# ── C35, par nœud ────────────────────────────────────────────────────────────
paquets_proscrits_verdicts() {
    local n p rp rc rr
    for n in "$SELF" "$PEER"; do
        if [ "$n" = "$SELF" ]; then p=S; else [ "$PEER_OK" -eq 0 ] || continue; p=P; fi
        eval "rp=\${${p}_proscrits:-} rc=\${${p}_cible_systemd:-} rr=\${${p}_install_recommends:-}"
        case "$(verdict_proscrits "$rp" "$rc" "$rr")" in
            OK)     ok   "Pas de pile de bureau sur $n : aucun paquet proscrit installé, cible multi-user, Install-Recommends à 0" ;;
            ECART)
                if proscrits_est_revenue "$rp" "$rc"; then
                    warn "Pile de bureau REVENUE sur $n : $(proscrits_decrire_ecarts "$rp" "$rc" "$rr") — rien ne l'a décidé : mise à jour (les méta-paquets rpd-* changent de dépendances), paquets recommandés, ou réinstallation depuis l'image ; chaque retour rouvre navigateurs, VNC ou rpcbind sur le LAN (#1648)"
                else
                    warn "Pile de bureau MENACÉE sur $n : $(proscrits_decrire_ecarts "$rp" "$rc" "$rr") — aucun paquet de bureau n'est revenu, mais le prochain apt install peut le ramener (#1648)"
                fi ;;
            *)      warn "Pile de bureau de $n INCONNUE (dpkg, systemctl ou apt-config muet : paquets='${rp:-vide}' cible='${rc:-vide}' recommends='${rr:-vide}') — ni vert ni rouge" ;;
        esac
    done
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → ${r:-(rien)}" || { echo "FAIL  $1  attendu=${2:-(rien)} obtenu=${r:-(rien)}"; st=1; }; }
    ICI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

    echo "== la décision =="
    MU=multi-user.target; GR=graphical.target
    t "nœud allégé (rpi1 après le 03/10) → OK"                  OK      verdict_proscrits "ok:" "$MU" 0
    t "des paquets proscrits installés → ECART"                 ECART   verdict_proscrits "ok:chromium-browser~rpd-wayland-extras" "$MU" 0
    t "cible redevenue graphical.target → ECART"                ECART   verdict_proscrits "ok:" "$GR" 0
    t "Install-Recommends à 1 → ECART"                          ECART   verdict_proscrits "ok:" "$MU" 1
    t "Install-Recommends « false » est un zéro"                OK      verdict_proscrits "ok:" "$MU" false
    t "une cible inattendue n'est pas multi-user → ECART"       ECART   verdict_proscrits "ok:" "rescue.target" 0
    t "dpkg muet (relevé vide) → INCONNU, jamais OK"            INCONNU verdict_proscrits "" "$MU" 0
    t "sans marqueur « ok: » → INCONNU, jamais OK"              INCONNU verdict_proscrits "chromium" "$MU" 0
    t "systemctl muet → INCONNU"                                INCONNU verdict_proscrits "ok:" "" 0
    t "apt-config muet → INCONNU"                               INCONNU verdict_proscrits "ok:" "$MU" ""
    t "un écart prime sur une mesure manquante"                 ECART   verdict_proscrits "" "$GR" 0
    t "description : « a (tiré par x, y), b »" "a (tiré par x, y), b" proscrits_decrire_paquets "a~x+y,b"
    t "description bornée : au-delà de huit paquets, les suivants sont comptés"       "a1, a2, a3, a4, a5, a6, a7, a8 … et 4 autre(s)" proscrits_decrire_paquets "a1,a2,a3,a4,a5,a6,a7,a8,a9,a10,a11,a12"
    t "le compte des paquets du constat" 3 proscrits_compter "a~x+y,b,c"
    t "« revenue » : un paquet proscrit installé" oui eval 'proscrits_est_revenue "ok:cups" multi-user.target && echo oui || echo non'
    t "« revenue » : la cible redevenue graphique" oui eval 'proscrits_est_revenue "ok:" graphical.target && echo oui || echo non'
    t "« menacée » : ni paquet ni cible, seul le réglage d'apt" non eval 'proscrits_est_revenue "ok:" multi-user.target && echo oui || echo non'
    t "« menacée » : une mesure muette ne fait pas dire « revenue »" non eval 'proscrits_est_revenue "" "" && echo oui || echo non'
    t "le message d'écart nomme chaque cause et sa correction" 3 \
      eval 'proscrits_decrire_ecarts "ok:cups~hplip" graphical.target 1 | grep -o "alleger-noeud.sh\|set-default multi-user.target\|99-hostachy-sans-recommends" | wc -l | tr -d " "'

    echo "== la collecte, exécutée sur dpkg, apt-cache, systemctl et apt-config simulés =="
    dpkg-query() {
        [ "${DPKG_KO:-non}" = oui ] && return 1
        local pat=${!#} p
        #  Le format réel : « ii » + une espace (Status-Abbrev) + celle du format → DEUX.
        [ "$pat" = dpkg ] && { echo "ii  dpkg"; return 0; }
        for p in $FAUX_INSTALLES; do case "$p" in $pat) printf 'ii  %s\n' "$p" ;; esac; done
        for p in $FAUX_RESIDUS; do case "$p" in $pat) printf 'rc  %s\n' "$p" ;; esac; done
        return 0
    }
    #  `--installed` : seuls les paquets installés figurent parmi les dépendants.
    apt-cache() { local x=${!#} d; [ -z "${APT_TRACE:-}" ] || echo "$*" >> "$APT_TRACE"; printf '%s\nReverse Depends:\n' "$x"
        case "$x" in
            chromium-browser) set -- rpd-wayland-extras lxpanel-pi mon-outil ;;
            rpcbind)          set -- nfs-common autre-un autre-deux autre-trois autre-quatre ;;
            cups-daemon)      set -- autre-un:armhf autre-un autre-un:arm64 ;;
            *)                set -- ;;
        esac
        for d in "$@"; do case " $FAUX_INSTALLES " in *" ${d%%:*} "*) printf '  %s\n' "$d" ;; esac; done; }
    timeout() { shift; "$@"; }
    systemctl() { echo "${CIBLE:-multi-user.target}"; }
    apt-config() { printf 'APT::Install-Compat "1";\nAPT::Install-Recommends "%s";\nAPT::Install-Suggests "0";\n' "${REC:-1}"; }
    fx() { bash -c "$(declare -f dpkg-query apt-cache timeout systemctl apt-config); export FAUX_INSTALLES='${FAUX_INSTALLES:-}' FAUX_RESIDUS='${FAUX_RESIDUS:-}' DPKG_KO=${DPKG_KO:-non} CIBLE=${CIBLE:-multi-user.target} REC=${REC:-1} APT_TRACE=${APT_TRACE:-}; export APT_TRACE; $(collecte_paquets_proscrits)" | sed -n "s/^$1=//p"; }

    FAUX_INSTALLES="bash coreutils" FAUX_RESIDUS="firefox-esr"
    t "collecte : rien de proscrit → « ok: » vide (mesuré) ; un résidu « rc » n'est pas installé" "ok:" fx proscrits
    #  rpd-wayland-extras et nfs-common sont proscrits ET dépendants : relevés eux-mêmes,
    #  jamais cités comme « tireur » (la racine seule compte) ; lxpanel-pi n'est pas
    #  installé, `--installed` ne le liste donc pas.
    FAUX_INSTALLES="bash chromium-browser chromium-common rpcbind rpd-plym-splash plymouth-themes cups-daemon coreutils rpd-wayland-extras nfs-common mon-outil autre-un autre-deux autre-trois autre-quatre"
    t "collecte : motifs développés, tireurs hors proscrits (trois au plus, par ordre alphabétique), gardés écartés" \
      "ok:chromium-browser~mon-outil,chromium-common,cups-daemon~autre-un,nfs-common,rpcbind~autre-deux+autre-quatre+autre-trois,rpd-wayland-extras" fx proscrits
    t "collecte : un tireur n'est cité qu'une fois, sans suffixe d'architecture (:armhf, :arm64)" 1       eval 'fx proscrits | tr "," "
" | grep -c "^cups-daemon~autre-un$"'
    #  Le coût borné : au-delà de PROSCRITS_AFFICHES paquets, plus d'apt-cache ; et
    #  seules les dépendances FORTES comptent (ni Conflicts, ni Breaks, ni Suggests…).
    FAUX_INSTALLES="bash $(for i in 1 2 3 4 5 6 7 8 9 10 11 12; do printf 'cups-x%s ' "$i"; done)"
    APT_TRACE=$(mktemp)
    t "collecte : douze paquets proscrits relevés, mais apt-cache n'est interrogé que huit fois" "12|8"       eval 'echo "$(fx proscrits | tr "," "
" | wc -l | tr -d " ")|$(wc -l < "$APT_TRACE" | tr -d " ")"'
    t "collecte : apt-cache écarte Conflicts, Breaks, Replaces, Enhances et Suggests" 8       eval 'grep -c -- "--no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances" "$APT_TRACE"'
    rm -f "$APT_TRACE"; unset APT_TRACE
    FAUX_INSTALLES="bash chromium-browser chromium-common rpcbind rpd-plym-splash plymouth-themes cups-daemon coreutils rpd-wayland-extras nfs-common mon-outil autre-un autre-deux autre-trois autre-quatre"
    t "collecte : rpd-plym-splash et plymouth-themes (gardés) ne sont jamais relevés" 0 \
      eval 'fx proscrits | grep -c "plym"'
    DPKG_KO=oui
    t "collecte : dpkg illisible → VIDE (INCONNU), jamais « ok: »" "" fx proscrits
    unset DPKG_KO
    CIBLE=graphical.target
    t "collecte : la cible systemd est relevée telle quelle" graphical.target fx cible_systemd
    unset CIBLE
    REC=0; t "collecte : Install-Recommends « \"0\"; » → 0"  0 fx install_recommends
    REC=1; t "collecte : Install-Recommends « \"1\"; » → 1"  1 fx install_recommends
    unset REC
    t "collecte : sans dpkg-query ni systemctl ni apt-config → trois champs VIDES" "proscrits=|cible_systemd=|install_recommends=" \
      eval 'PATH=/nonexistent "$BASH" -c "$(collecte_paquets_proscrits)" 2>/dev/null | paste -sd"|" -'
    t "collecte : le fragment est du shell valide" oui eval 'bash -n <<<"$(collecte_paquets_proscrits)" && echo oui'
    t "collecte : aucune apostrophe dans le fragment" 0 eval 'collecte_paquets_proscrits | grep -c "$(printf "\047")"'
    t "collecte : set -f est rétabli (aucun motif développé hors de la boucle)" 1 \
      eval 'collecte_paquets_proscrits | grep -c "^set +f$"'
    unset -f dpkg-query apt-cache timeout systemctl apt-config

    echo "== la liste, UNE seule écriture =="
    t "alleger-noeud.sh SOURCE la liste" 1 eval 'grep -c "^\. .*lib-paquets-proscrits.sh" "$ICI/../exploitation/alleger-noeud.sh"'
    t "alleger-noeud.sh n'en recopie aucun motif" 0 eval 'grep -cE "chromium|firefox|libreoffice|xserver-xorg|accounts-daemon" "$ICI/../exploitation/alleger-noeud.sh"'
    t "la liste ne porte ni doublon ni entrée vide" 0 eval 'for p in $PAQUETS_PROSCRITS; do echo "$p"; done | sort | uniq -d | wc -l | tr -d " "'
    t "chaque paquet gardé est désigné par un motif de la liste (sinon la garde ne sert à rien)" 1 \
      eval 'for g in $PAQUETS_GARDES; do for m in $PAQUETS_PROSCRITS; do case "$g" in $m) echo "$g"; break ;; esac; done; done | grep -cx rpd-plym-splash'

    echo "== les constats, sur les DEUX nœuds =="
    ok()   { echo "OK $*"; }
    warn() { echo "WARN $*"; }
    SELF=rpi1 PEER=rpi2 PEER_OK=0
    S_proscrits="ok:" S_cible_systemd=multi-user.target S_install_recommends=0
    P_proscrits="ok:" P_cible_systemd=multi-user.target P_install_recommends=0
    sortie=$(paquets_proscrits_verdicts)
    t "deux nœuds allégés → deux OK, aucun WARN" "2|0" eval 'echo "$(grep -c "^OK" <<< "$sortie")|$(grep -c "^WARN" <<< "$sortie")"'
    #  Les faits du 03/10/2026 : rpi1 allégé (mais Install-Recommends encore à 1),
    #  rpi2 encore en Pi OS Desktop complet.
    S_install_recommends=1
    P_proscrits="ok:chromium-browser~rpd-wayland-extras,rpcbind" P_cible_systemd=graphical.target
    sortie=$(paquets_proscrits_verdicts)
    t "rpi1 : un WARN « MENACÉE » (rien n'est revenu) qui ne nomme que le Install-Recommends" 1 \
      eval 'grep -c "^WARN Pile de bureau MENACÉE sur rpi1 : APT::Install-Recommends vaut 1" <<< "$sortie"'
    t "rpi2 : un WARN distinct qui nomme paquets, tireur et cible" 1 \
      eval 'grep -c "^WARN Pile de bureau REVENUE sur rpi2 : 2 paquet(s) proscrit(s) installé(s) : chromium-browser (tiré par rpd-wayland-extras), rpcbind .* graphical.target" <<< "$sortie"'
    S_proscrits="" S_cible_systemd="" S_install_recommends=""
    sortie=$(paquets_proscrits_verdicts)
    t "rien mesuré sur rpi1 → un WARN INCONNU, jamais OK" "1|0" \
      eval 'echo "$(grep "^WARN" <<< "$sortie" | grep -c "rpi1 INCONNUE")|$(grep -c "^OK .*rpi1" <<< "$sortie")"'
    PEER_OK=255
    t "pair injoignable : rien sur rpi2" 0 eval 'paquets_proscrits_verdicts | grep -c "rpi2"'
    unset -f ok warn

    [ "$st" -eq 0 ] && echo "lib-paquets-proscrits : tous les cas passent."
    exit "$st"
fi
