#!/bin/bash
# =============================================================================
#  apt-ci.sh — La seule porte d'apt dans la CI, qui résiste à une panne de
#  RÉSOLUTION des miroirs (#2694).
#
#  ## Pourquoi (11/11/2026)
#
#  Depuis 15:20, sur les runners GitHub (ubuntu-26.04), apt ne résolvait plus
#  `azure.archive.ubuntu.com`, `archive.ubuntu.com` ni `security.ubuntu.com`
#  (« Temporary failure resolving ») ; GitHub n'annonçait rien, et depuis le
#  poste les noms se résolvaient. Les jobs pytest (`bibliotheques-pdf.sh`) et
#  WebKit (dépendances du navigateur) tombaient à l'installation, avant le
#  moindre test, et quatre PR prêtes restaient bloquées des heures sur un check
#  requis rouge sans rapport avec leur code.
#
#  ## Ce que fait la porte
#
#  1. Elle SONDE les hôtes des sources apt (`sources.list*`, `apt-mirrors.txt`)
#     par le résolveur du runner.
#  2. Si l'un ne se résout pas — ou si la commande échoue en le disant —, elle
#     pose un REPLI déclaré et journalisé : l'adresse demandée à un résolveur
#     public en DNS-sur-HTTPS (Cloudflare, puis Google, joints par leur IP : il
#     ne faut pas de DNS pour les joindre), écrite dans `/etc/hosts` le temps de
#     la commande, retirée ensuite. Puis elle rejoue la commande, une fois.
#  3. Si le repli ne suffit pas, l'étape échoue en disant « panne de miroir » —
#     jamais un vert. Un échec qui n'est PAS une panne de résolution (un paquet
#     qui n'existe pas) reste rouge tel quel, sans repli.
#
#  🔒 Le repli n'affaiblit rien : apt vérifie la signature d'`InRelease` et
#  l'empreinte de chaque paquet, quelle que soit l'adresse qui les a servis.
#
#  ⚠️ Pas de cache des `.deb` ici : il ne dispense pas d'`apt-get update`, qui
#  doit joindre les miroirs pour connaître les versions — c'est l'étape qui
#  tombe. WebKit garde le cache qu'il avait (#1865).
#
#  Usage :
#    bash scripts/ci/apt-ci.sh installer <paquet>…     update puis install
#    bash scripts/ci/apt-ci.sh executer -- <commande>  une commande qui appelle apt
#    bash scripts/ci/apt-ci.sh --selftest
#  Hors Debian (le poste, qui rejoue la CI), la porte exécute la commande telle
#  quelle et `installer` le dit sans rien faire.
# =============================================================================
set -euo pipefail

#  La marque des lignes posées dans `/etc/hosts` : c'est par elle qu'on les retire.
APT_CI_ETIQUETTE="repli-apt-ci-2694"
APT_CI_MARQUE="# $APT_CI_ETIQUETTE"
#  DNS-sur-HTTPS, format JSON, joint par IP (le certificat porte l'IP).
APT_CI_RESOLVEURS="https://1.1.1.1/dns-query https://8.8.8.8/resolve"

# ── Fonctions PURES ─────────────────────────────────────────────────────────

#  Les hôtes nommés par des sources apt (texte lu sur l'entrée), un par ligne.
apt_ci_hotes_des_sources() {
    local _t
    _t=$(cat)
    { grep -oE 'https?://[A-Za-z0-9.-]+' <<<"$_t" || true; } | sed -E 's#^https?://##' | sort -u
}

#  Les adresses IPv4 d'une réponse DNS-sur-HTTPS (JSON) : les `data` qui en sont
#  une. Un CNAME (`…cloudapp.azure.com.`) n'en est pas une et ne sort pas.
apt_ci_ipv4_de_reponse() {
    { grep -oE '"data": ?"([0-9]{1,3}\.){3}[0-9]{1,3}"' <<<"$1" || true; } \
        | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' || true
}

#  La sortie d'apt dit-elle une panne de RÉSOLUTION ? (oui|non)
apt_ci_panne_de_resolution() {
    if grep -qE "Temporary failure resolving|Could not resolve" <<<"$1"; then echo oui; else echo non; fi
}

#  La décision après une exécution : <code> <panne de résolution oui|non> <repli posé oui|non>
#    fini         la commande a réussi
#    echec        elle a échoué pour une autre raison : rouge tel quel
#    repli        panne de résolution, pas encore de repli : le poser et rejouer
#    panne-miroir panne de résolution malgré le repli : rouge, en le disant
apt_ci_decider() {
    local code=$1 panne=$2 repli=$3
    if [ "$code" -eq 0 ]; then echo fini
    elif [ "$panne" != oui ]; then echo echec
    elif [ "$repli" != oui ]; then echo repli
    else echo panne-miroir
    fi
}

# ── Gestes (remplacés par l'autotest) ───────────────────────────────────────

APT_CI_SUDO=""
[ "$(id -u)" -eq 0 ] || APT_CI_SUDO="sudo"

apt_ci_sources() {
    cat /etc/apt/sources.list /etc/apt/sources.list.d/* /etc/apt/apt-mirrors.txt 2>/dev/null || true
}
#  L'hôte se résout-il par le résolveur du runner ?
apt_ci_resolu() { timeout 15 getent hosts "$1" >/dev/null 2>&1; }
#  La réponse JSON d'un résolveur public pour l'hôte.
apt_ci_doh() {
    curl -fsS --max-time 10 -H 'accept: application/dns-json' "$1?name=$2&type=A" 2>/dev/null || true
}
apt_ci_poser_hote() { echo "$1 $2 $APT_CI_MARQUE" | $APT_CI_SUDO tee -a /etc/hosts >/dev/null; }
apt_ci_retirer_repli() {
    if grep -qF "$APT_CI_MARQUE" /etc/hosts 2>/dev/null; then
        $APT_CI_SUDO sed -i "/$APT_CI_ETIQUETTE/d" /etc/hosts
        echo "· repli DNS retiré de /etc/hosts."
    fi
}

# ── Orchestration ────────────────────────────────────────────────────────────

APT_CI_REPLI=non

#  Pose le repli pour chaque hôte des sources que le runner ne résout pas.
#  Rend 0 si au moins une adresse a été posée, 1 sinon.
apt_ci_poser_repli() {
    local hotes h r ip poses=0
    hotes=$(apt_ci_sources | apt_ci_hotes_des_sources)
    for h in $hotes; do
        if apt_ci_resolu "$h"; then continue; fi
        ip=""
        for r in $APT_CI_RESOLVEURS; do
            ip=$(apt_ci_ipv4_de_reponse "$(apt_ci_doh "$r" "$h")" | head -1)
            [ -n "$ip" ] && break
        done
        if [ -n "$ip" ]; then
            apt_ci_poser_hote "$ip" "$h"
            echo "↻ repli DNS (#2694) : $h → $ip, obtenu de $r — posé dans /etc/hosts le temps de la commande."
            poses=$((poses + 1))
        else
            echo "✗ repli DNS : $h ne se résout ni par le runner ni par les résolveurs publics."
        fi
    done
    APT_CI_REPLI=oui
    [ "$poses" -gt 0 ]
}

#  La sonde AVANT la première exécution : un hôte non résolu pose le repli tout
#  de suite — apt passerait sinon plusieurs minutes à échouer.
apt_ci_sonder() {
    local h non_resolus=""
    for h in $(apt_ci_sources | apt_ci_hotes_des_sources); do
        apt_ci_resolu "$h" || non_resolus="$non_resolus $h"
    done
    if [ -n "$non_resolus" ]; then
        echo "⚠ Le résolveur du runner ne connaît pas :$non_resolus — panne de résolution, repli."
        apt_ci_poser_repli || true
    fi
}

#  Exécute la commande ; sur une panne de résolution, pose le repli et rejoue une fois.
apt_ci_executer() {
    local journal code decision
    journal=$(mktemp)
    apt_ci_sonder
    for _essai in 1 2; do
        set +e
        "$@" 2>&1 | tee "$journal"
        code=${PIPESTATUS[0]}
        set -e
        decision=$(apt_ci_decider "$code" "$(apt_ci_panne_de_resolution "$(cat "$journal")")" "$APT_CI_REPLI")
        case "$decision" in
            fini) break ;;
            repli)
                echo "⚠ apt n'a pas résolu un miroir (#2694) : repli DNS, puis nouvelle tentative."
                apt_ci_poser_repli || true
                ;;
            panne-miroir)
                echo "✗ PANNE DE MIROIR : les miroirs Ubuntu ne se joignent pas, même par le repli DNS."
                echo "  Ce n'est pas le lot : relancer le job quand les runners les retrouvent (#2694)."
                break ;;
            echec) break ;;
        esac
    done
    rm -f "$journal"
    return "$code"
}

apt_ci_principal() {
    case "${1:-}" in
        installer)
            shift
            if ! command -v apt-get >/dev/null 2>&1; then
                echo "· apt-get absent : installation sans objet hors Debian ($*)."
                return 0
            fi
            trap apt_ci_retirer_repli EXIT
            apt_ci_executer $APT_CI_SUDO sh -c \
                "apt-get update -qq && apt-get install -y --no-install-recommends $*"
            ;;
        executer)
            shift
            [ "${1:-}" = "--" ] && shift
            if ! command -v apt-get >/dev/null 2>&1; then
                "$@"
                return
            fi
            trap apt_ci_retirer_repli EXIT
            apt_ci_executer "$@"
            ;;
        *)
            echo "Usage : $0 installer <paquet>… | executer -- <commande> | --selftest" >&2
            return 2
            ;;
    esac
}

# ── Autotest ─────────────────────────────────────────────────────────────────

apt_ci_autotest() {
    local ko=0
    _v() { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1 → « $2 », attendu « $3 »"; ko=1; fi; }

    #  Les sources de l'image ubuntu-26.04 : deb822 + liste de miroirs.
    local sources=$'Types: deb\nURIs: mirror+file:/etc/apt/apt-mirrors.txt\nSuites: resolute\n'
    sources+=$'http://azure.archive.ubuntu.com/ubuntu/\tpriority:1\n'
    sources+=$'https://archive.ubuntu.com/ubuntu/\tpriority:2\nhttp://security.ubuntu.com/ubuntu/\tpriority:3'
    _v "hôtes des sources" "$(apt_ci_hotes_des_sources <<<"$sources" | tr '\n' ' ')" \
        "archive.ubuntu.com azure.archive.ubuntu.com security.ubuntu.com "
    _v "sources vides : aucun hôte" "$(apt_ci_hotes_des_sources <<<"")" ""

    local cname='{"Status":0,"Answer":[{"name":"azure.archive.ubuntu.com.","type":5,"TTL":60,"data":"cloud-mirror-lb.swedencentral.cloudapp.azure.com."},{"name":"cloud-mirror-lb.swedencentral.cloudapp.azure.com.","type":1,"TTL":10,"data":"20.91.1.1"}]}'
    _v "IPv4 après un CNAME" "$(apt_ci_ipv4_de_reponse "$cname")" "20.91.1.1"
    _v "réponse vide : aucune IPv4" "$(apt_ci_ipv4_de_reponse '{"Status":2}')" ""

    _v "la ligne de la panne du 11/11" "$(apt_ci_panne_de_resolution \
        "E: Failed to fetch https://security.ubuntu.com/ubuntu/pool/main/h/harfbuzz/x.deb  Temporary failure resolving 'security.ubuntu.com'")" oui
    _v "un paquet inconnu n'est pas une panne" "$(apt_ci_panne_de_resolution "E: Unable to locate package libinconnu")" non

    _v "réussite" "$(apt_ci_decider 0 non non)" fini
    _v "réussite après repli" "$(apt_ci_decider 0 non oui)" fini
    _v "panne de résolution → repli" "$(apt_ci_decider 100 oui non)" repli
    _v "panne malgré le repli → panne-miroir" "$(apt_ci_decider 100 oui oui)" panne-miroir
    _v "autre échec : rouge tel quel" "$(apt_ci_decider 100 non non)" echec

    #  🔴 La panne SIMULÉE de bout en bout : le runner ne résout rien, le résolveur
    #  public répond, apt échoue tant que le repli n'est pas posé.
    local dossier
    dossier=$(mktemp -d)
    (
        apt_ci_sources() { echo "http://security.ubuntu.com/ubuntu/"; }
        apt_ci_resolu() { grep -q " $1 " "$dossier/hosts" 2>/dev/null; }
        apt_ci_doh() { echo '{"Answer":[{"type":1,"data":"91.189.91.82"}]}'; }
        apt_ci_poser_hote() { echo "$1 $2 $APT_CI_MARQUE" >>"$dossier/hosts"; }
        apt_faux() {
            if grep -q "security.ubuntu.com" "$dossier/hosts" 2>/dev/null; then echo "Setting up libharfbuzz-subset0"; return 0; fi
            echo "E: Failed to fetch x  Temporary failure resolving 'security.ubuntu.com'"; return 100
        }
        apt_ci_executer apt_faux >"$dossier/sortie" 2>&1
        echo "code=$?" >>"$dossier/sortie"
    ) || true
    _v "panne simulée : le repli est posé" "$(grep -c '91.189.91.82 security.ubuntu.com' "$dossier/hosts" 2>/dev/null || echo 0)" 1
    _v "panne simulée : la commande passe" "$(tail -1 "$dossier/sortie")" "code=0"
    _v "panne simulée : le repli est journalisé" \
        "$(grep -c 'repli DNS (#2694) : security.ubuntu.com → 91.189.91.82' "$dossier/sortie")" 1

    #  Le repli ne suffit pas : rouge, en disant « panne de miroir ».
    rm -f "$dossier/hosts"
    (
        apt_ci_sources() { echo "http://security.ubuntu.com/ubuntu/"; }
        apt_ci_resolu() { return 1; }
        apt_ci_doh() { echo '{"Status":2}'; }
        apt_ci_poser_hote() { echo "$1 $2" >>"$dossier/hosts"; }
        apt_faux() { echo "E: x  Temporary failure resolving 'security.ubuntu.com'"; return 100; }
        apt_ci_executer apt_faux >"$dossier/sortie" 2>&1
        echo "code=$?" >>"$dossier/sortie"
    ) || true
    _v "panne persistante : rouge" "$(tail -1 "$dossier/sortie")" "code=100"
    _v "panne persistante : dite" "$(grep -c 'PANNE DE MIROIR' "$dossier/sortie")" 1

    #  Un vrai échec (paquet inconnu) : rouge, sans repli ni seconde tentative.
    (
        apt_ci_sources() { echo "http://security.ubuntu.com/ubuntu/"; }
        apt_ci_resolu() { return 0; }
        apt_ci_poser_hote() { echo "posé" >>"$dossier/pose"; }
        apt_faux() { echo "passage" >>"$dossier/passages"; echo "E: Unable to locate package x"; return 100; }
        apt_ci_executer apt_faux >"$dossier/sortie" 2>&1
        echo "code=$?" >>"$dossier/sortie"
    ) || true
    _v "paquet inconnu : rouge" "$(tail -1 "$dossier/sortie")" "code=100"
    _v "paquet inconnu : une seule tentative" "$(wc -l <"$dossier/passages" | tr -d ' ')" 1
    _v "paquet inconnu : aucun repli" "$([ -e "$dossier/pose" ] && echo posé || echo aucun)" aucun
    rm -rf "$dossier"

    #  🔒 La porte est UNIQUE : aucun `apt-get` ni `--with-deps` dans les workflows
    #  ni dans `scripts/ci/`, hors commentaires et hors cette porte.
    local racine contournements
    racine=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
    contournements=$(grep -nE 'apt-get|--with-deps' "$racine"/.github/workflows/*.yml "$racine"/scripts/ci/*.sh 2>/dev/null \
        | grep -vE '^[^:]+:[0-9]+:\s*#' | grep -v '/scripts/ci/apt-ci.sh:' || true)
    _v "aucun apt hors de la porte" "${contournements:-aucun}" aucun
    local nb_workflows
    nb_workflows=$(find "$racine/.github/workflows" -name '*.yml' 2>/dev/null | wc -l | tr -d ' ')
    _v "la porte lit des workflows (cas zéro)" "$([ "${nb_workflows:-0}" -gt 0 ] && echo oui || echo non)" oui
    return "$ko"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    if [ "${1:-}" = "--selftest" ]; then
        apt_ci_autotest
    else
        apt_ci_principal "$@"
    fi
fi
