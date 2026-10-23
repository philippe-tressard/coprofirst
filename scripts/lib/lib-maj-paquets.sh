#!/bin/bash
# =============================================================================
#  lib-maj-paquets.sh — le standby pose TOUTES ses mises à jour (#2198)
#
#  Le 23/10/2026, après les failles d'octobre (Node.js du 21/10, PHP, Next.js),
#  les conteneurs étaient à jour et les HÔTES ne l'étaient pas : nodejs 22.23.3
#  (faille Brotli), cloudflared 2026.9.3 (le tunnel public), Docker 29.8.2,
#  containerd 2.3.6 — sur les deux nœuds, depuis la mise à jour manuelle du
#  03/10. `unattended-upgrades` ne pose que les origines Debian ; docker.com,
#  NodeSource, Cloudflare et Raspberry Pi n'avaient AUCUN geste. C30 les
#  comptait (`lib-paquets.sh`, #1591) sous un seuil de cent, et se taisait.
#
#  Le geste vit dans `noyau-standby.sh` : il tourne déjà en root, sur le nœud
#  qui vient de devenir standby, après une bascule réussie et seulement si
#  l'actif sert. Chaque nœud est donc à jour en 48 h au plus, toujours hors
#  production. Ce module ne porte que la DÉCISION : que poser, qu'écarter.
#
#  🔴 Deux refus, parce que l'allègement du 03/10/2026 (#1648) a retiré la pile
#  de bureau pour réduire la surface d'attaque, et qu'une mise à jour la ramène
#  (le `full-upgrade` du 03/10 avait réinstallé ~22 paquets de bureau) :
#    1. un paquet NOUVEAU que la mise à jour tirerait et que C35 proscrit
#       (`PAQUETS_PROSCRITS`, lu dans `lib-paquets-proscrits.sh`, jamais recopié) ;
#    2. un paquet que la mise à jour RETIRERAIT : un retrait ne se décide pas
#       la nuit, sans personne.
#  Le paquet en attente qui en est la cause est ÉCARTÉ, les autres sont posés,
#  et l'écart est dit (journal, courriel). Le noyau n'en fait pas partie : il a
#  son propre geste, révision seule (`NOYAU_PAQUETS`, #1395).
#
#  « Seulement les LTS » est tenu par les dépôts eux-mêmes, et pas ici :
#  NodeSource est configuré sur la branche 22.x, Docker et Cloudflare sur leur
#  canal stable, Debian sur trixie. Ce module pose la dernière version que
#  chaque dépôt CONFIGURÉ propose, jamais une autre branche.
#
#  Décisions PURES, sauf `simuler_maj` (une simulation `apt-get -s` : ni verrou,
#  ni écriture), que l'autotest remplace. SOURCÉ (mode 100644) par
#  `noyau-standby.sh`. Autotest : bash scripts/lib/lib-maj-paquets.sh --selftest
# =============================================================================

#  La liste proscrite (C35) : une seule source, que `alleger-noeud.sh` lit aussi.
. "$(dirname "${BASH_SOURCE[0]}")/lib-paquets-proscrits.sh"

#  $1 un nom de paquet → vrai s'il est proscrit et n'est pas gardé (plymouth).
#  `set -f` : les motifs (`chromium*`) se comparent au NOM, jamais aux fichiers
#  du répertoire courant.
est_proscrit() {
    local p=$1 m
    case " $PAQUETS_GARDES " in *" $p "*) return 1 ;; esac
    set -f
    for m in ${PAQUETS_PROSCRITS//$'\n'/ }; do
        # shellcheck disable=SC2254  # le motif EST une glob, voulue
        case "$p" in $m) set +f; return 0 ;; esac
    done
    set +f
    return 1
}

#  $1 la sortie de `apt list --upgradable` · $2 les paquets exclus (séparés par
#  des espaces) → les paquets en attente, un par ligne.
paquets_en_attente() {
    local p
    printf '%s\n' "${1:-}" | awk -F/ '/\[upgradable/ { print $1 }' | while read -r p; do
        case " ${2:-} " in *" $p "*) ;; *) echo "$p" ;; esac
    done
}

#  $1 la simulation (`LC_ALL=C apt-get -s …`) → les paquets NOUVEAUX : une ligne
#  « Inst x (…) » sans « [version installée] ».
simulation_nouveaux() {
    printf '%s\n' "${1:-}" | awk '$1 == "Inst" && $3 !~ /^\[/ { sub(/:.*/, "", $2); print $2 }'
}

#  $1 la simulation → les paquets RETIRÉS (« Remv x … »).
simulation_retraits() {
    printf '%s\n' "${1:-}" | awk '$1 == "Remv" { sub(/:.*/, "", $2); print $2 }'
}

#  $1 la simulation → OK | PROSCRITS:a,b | RETRAITS:a,b | INCONNU
#  INCONNU sans la ligne de bilan d'apt (« N upgraded, M newly installed… ») ou
#  avec une erreur « E: » : verrou pris, dépôt illisible, paquet retenu — jamais
#  un « rien à craindre ». Un proscrit l'emporte sur un retrait : c'est lui que
#  l'allègement interdit.
verdict_simulation() {
    local s=${1:-} p pr='' rv
    printf '%s\n' "$s" | grep -q '^E:' && { echo INCONNU; return; }
    printf '%s\n' "$s" | grep -qE '^[0-9]+ upgraded, [0-9]+ newly installed' || { echo INCONNU; return; }
    for p in $(simulation_nouveaux "$s"); do
        est_proscrit "$p" && pr="$pr${pr:+,}$p"
    done
    rv=$(simulation_retraits "$s" | paste -sd, -)
    if   [ -n "$pr" ]; then echo "PROSCRITS:$pr"
    elif [ -n "$rv" ]; then echo "RETRAITS:$rv"
    else echo OK; fi
}

#  La simulation d'une pose. Hors autotest, la vraie : sans verrou ni écriture,
#  donc sans root. Les recommandés sont refusés ici AUSSI, même si
#  `APT::Install-Recommends "0"` est posé sur les deux nœuds : C35 surveille
#  qu'il le reste, ce geste-ci n'en dépend pas.
simuler_maj() {
    LC_ALL=C apt-get -s -o APT::Install-Recommends=0 install --only-upgrade "$@" 2>&1
}

#  $@ les paquets en attente → le plan :
#    « POSER a b c » (première ligne ; vide après POSER s'il n'y a rien à poser),
#    puis « ECARTE <paquet> <verdict> » pour chaque paquet écarté ;
#    ou « INCONNU <cause> », et rien n'est posé.
#  L'ensemble d'abord ; s'il tire un proscrit ou retire un paquet, chacun est
#  simulé seul pour trouver le fautif, puis l'ensemble sans lui est revérifié —
#  deux paquets sains peuvent ensemble tirer ce qu'aucun ne tire seul.
planifier_maj_paquets() {
    local v p
    local -a gardes=() ecartes=()
    [ $# -gt 0 ] || { echo "POSER"; return; }
    v=$(verdict_simulation "$(simuler_maj "$@")")
    case "$v" in
        OK)      echo "POSER $*"; return ;;
        INCONNU) echo "INCONNU la simulation de l'ensemble n'a pas abouti"; return ;;
    esac
    for p in "$@"; do
        v=$(verdict_simulation "$(simuler_maj "$p")")
        if [ "$v" = OK ]; then gardes+=("$p"); else ecartes+=("$p $v"); fi
    done
    if [ ${#gardes[@]} -gt 0 ]; then
        v=$(verdict_simulation "$(simuler_maj "${gardes[@]}")")
        [ "$v" = OK ] || { echo "INCONNU sans les paquets écartés, l'ensemble reste $v"; return; }
    fi
    echo "POSER ${gardes[*]}"
    for p in "${ecartes[@]}"; do echo "ECARTE $p"; done
}

#: Les paquets dont la pose redémarre le moteur de conteneurs : la réplique de
#: la base et les conteneurs d'un autre projet (List-dons sur rpi2) s'arrêtent
#: puis repartent (`restart: unless-stopped`).
PAQUETS_MOTEUR="docker-ce containerd.io"

#  $@ les paquets posés → vrai si l'un redémarre le moteur de conteneurs.
touche_le_moteur() {
    local p
    for p in "$@"; do
        case " $PAQUETS_MOTEUR " in *" $p "*) return 0 ;; esac
    done
    return 1
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }
    vrai() { if "$@"; then echo oui; else echo non; fi; }

    t "chromium-browser : proscrit"       oui vrai est_proscrit chromium-browser
    t "rpd-wallpaper : proscrit (rpd-*)"  oui vrai est_proscrit rpd-wallpaper
    t "rpd-plym-splash : GARDÉ"           non vrai est_proscrit rpd-plym-splash
    t "rpcbind : proscrit"                oui vrai est_proscrit rpcbind
    t "docker-ce : permis"                non vrai est_proscrit docker-ce
    t "nodejs : permis (gardé le 03/10)"  non vrai est_proscrit nodejs
    tmpd=$(mktemp -d); touch "$tmpd/chromium-x"
    t "une glob ne se développe pas contre le répertoire" oui \
      eval '(cd "$tmpd" && vrai est_proscrit chromium-browser)'
    rm -rf "$tmpd"

    #  La forme RÉELLE d'`apt list --upgradable` (rpi1, 23/10/2026).
    liste='Listing...
cloudflared/unknown 2026.10.3 arm64 [upgradable from: 2026.9.3]
docker-ce/trixie 5:29.9.2-1~debian.13~trixie arm64 [upgradable from: 5:29.8.2-1~debian.13~trixie]
linux-image-rpi-2712/stable 1:6.18.52-1+rpt1 arm64 [upgradable from: 1:6.18.50-1+rpt1]
nodejs/nodistro 22.23.4-1nodesource1 arm64 [upgradable from: 22.23.3-1nodesource1]'
    t "en attente, sans le noyau" "cloudflared docker-ce nodejs" \
      eval 'paquets_en_attente "$liste" "linux-image-rpi-2712 raspi-firmware" | paste -sd" " -'
    t "rien en attente → rien" "" paquets_en_attente "Listing..." ""

    bilan='2 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.'
    sim_ok="$bilan
Inst docker-ce [5:29.8.2-1~debian.13~trixie] (5:29.9.2-1~debian.13~trixie Docker CE:trixie [arm64])
Inst nodejs [22.23.3-1nodesource1] (22.23.4-1nodesource1 . nodistro:nodistro [arm64])
Conf docker-ce (5:29.9.2-1~debian.13~trixie Docker CE:trixie [arm64])"
    sim_dep="1 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.
Inst libfoo1 (1.2-1 Debian:13/stable [arm64])
Inst docker-ce [5:29.8.2-1] (5:29.9.2-1 Docker CE:trixie [arm64])"
    sim_bureau="1 upgraded, 2 newly installed, 0 to remove and 0 not upgraded.
Inst rpd-wallpaper (0.3 Raspberry Pi Foundation:stable [all])
Inst chromium:arm64 (130.0 Raspberry Pi Foundation:stable [arm64])
Inst raspi-config [20261026] (20261026+2 Raspberry Pi Foundation:stable [all])"
    sim_retrait="1 upgraded, 0 newly installed, 1 to remove and 0 not upgraded.
Remv libcamera0.6 [0.6.0]
Inst libcamera-ipa [0.7.2+rpt20260817-1] (0.7.2+rpt20261009-1 Raspberry Pi Foundation:stable [arm64])"
    t "mise à jour simple → OK"                OK verdict_simulation "$sim_ok"
    t "dépendance neuve permise → OK"          OK verdict_simulation "$sim_dep"
    t "pile de bureau tirée → PROSCRITS"       PROSCRITS:rpd-wallpaper,chromium verdict_simulation "$sim_bureau"
    t "un retrait → RETRAITS"                  RETRAITS:libcamera0.6 verdict_simulation "$sim_retrait"
    t "verrou pris (E:) → INCONNU"             INCONNU verdict_simulation "E: Could not get lock /var/lib/dpkg/lock-frontend
$bilan"
    t "sortie vide → INCONNU, jamais OK"       INCONNU verdict_simulation ""
    t "sans bilan → INCONNU"                   INCONNU verdict_simulation "Reading package lists..."

    #  Le plan, sur un apt simulé : raspi-config tire la pile de bureau, libcamera
    #  retire un paquet ; les autres passent.
    simuler_maj() {
        local a=" $* "
        case "$a" in
            *" raspi-config "*) printf '%s\n' "$sim_bureau" ;;
            *" libcamera-ipa "*) printf '%s\n' "$sim_retrait" ;;
            *" verrou "*) echo "E: Could not get lock" ;;
            *) printf '%s\n' "$sim_ok" ;;
        esac
    }
    t "tout est sain → tout est posé" "POSER docker-ce nodejs" planifier_maj_paquets docker-ce nodejs
    t "rien en attente → POSER vide"  "POSER" planifier_maj_paquets
    t "le fautif est écarté, le reste posé" \
      "POSER docker-ce nodejs|ECARTE raspi-config PROSCRITS:rpd-wallpaper,chromium|ECARTE libcamera-ipa RETRAITS:libcamera0.6" \
      eval 'planifier_maj_paquets docker-ce raspi-config nodejs libcamera-ipa | paste -sd"|" -'
    t "simulation illisible → INCONNU, rien posé" INCONNU \
      eval 'planifier_maj_paquets verrou docker-ce | cut -d" " -f1'
    t "tout est écarté → POSER vide, puis l'écart" "POSER |ECARTE raspi-config PROSCRITS:rpd-wallpaper,chromium" \
      eval 'planifier_maj_paquets raspi-config | paste -sd"|" -'
    #  Deux paquets sains seuls, fautifs ensemble : on ne pose rien.
    simuler_maj() { if [ $# -gt 1 ]; then printf '%s\n' "$sim_bureau"; else printf '%s\n' "$sim_ok"; fi; }
    t "sains seuls, fautifs ensemble → INCONNU" INCONNU \
      eval 'planifier_maj_paquets docker-ce nodejs | cut -d" " -f1'

    t "docker-ce redémarre le moteur"    oui vrai touche_le_moteur nodejs docker-ce
    t "containerd.io aussi"              oui vrai touche_le_moteur containerd.io
    t "nodejs, cloudflared : non"        non vrai touche_le_moteur nodejs cloudflared
    t "rien posé : non"                  non vrai touche_le_moteur

    [ "$st" -eq 0 ] && echo "lib-maj-paquets : tous les cas passent."
    exit "$st"
fi
