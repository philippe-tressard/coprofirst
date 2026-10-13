#!/bin/bash
# =============================================================================
#  lib-ports-ecoute.sh — C32 : quels ports écoutent sur TOUTES les interfaces ?
#
#  Né de #1593 (audit du 02/10/2026) : `rpcbind` écoutait sur `0.0.0.0:111` et
#  `[::]:111` de rpi1 SEULEMENT — un service inutile (aucun NFS dans le projet),
#  ouvert sur le LAN d'un seul nœud, que C18/C20/C22/C24 (crons, sudo, points
#  d'entrée) ne pouvaient pas voir : aucun contrôle ne comparait les ports.
#  C'est la troisième divergence rpi1/rpi2 silencieuse de la famille décrite
#  par `infra-rpi` (C27).
#
#  Ce que C32 mesure : les ports TCP à l'écoute sur une adresse JOKER
#  (`0.0.0.0`, `*`, `[::]`, `::`) — ceux qu'un autre poste du LAN atteint. Les
#  écoutes locales (`127.0.0.1:8090` du bridge, `127.0.0.1:20241` de
#  cloudflared) n'en sont pas : elles ne sortent pas du nœud.
#
#  Deux questions, une seule ligne par nœud :
#    1. chaque port est-il dans la LISTE BLANCHE déclarée ci-dessous ?
#    2. un port hors liste est-il le MÊME sur les deux nœuds, ou propre à un seul ?
#       (le constat le dit : « absent de rpi2 » — c'est la divergence du 02/10)
#  Les ports de la liste blanche ne se comparent PAS entre nœuds : Caddy (80)
#  n'écoute que sur l'actif, List-dons (8080) que sur rpi2.
#
#  Lecture seule, sans sudo : `ss -tln` (sans `-p`, qui demanderait root pour
#  nommer le processus). Tout en WARN (digest quotidien), jamais FAIL.
#
#  SOURCÉ (mode 100644) par `lib-collecte.sh` (`COLLECT_PORTS`, repris dans
#  COLLECT) ; `ports_ecoute_verdicts` est appelé par `lib-conformite.sh`.
#  ⚠️ `ports_ecoute_verdicts` emploie `ok`, `warn`, `$SELF`, `$PEER`, `$PEER_OK`
#  et les champs S_*/P_* de son appelant.
#  Autotest : bash scripts/lib/lib-ports-ecoute.sh --selftest
# =============================================================================

#: La liste blanche, DÉCLARÉE — chaque entrée dit pourquoi elle est là :
#:   22    SSH (UFW : ouvert au seul LAN, `docs/restauration-complete.md` étape 4, `durcir-noeud.sh`) ;
#:   80    Caddy, publié par `docker-compose.yml` (`"80:80"`) — actif seulement ;
#:   443   ouvert par UFW (étape 8) ; rien n'y écoute aujourd'hui, le tunnel
#:         Cloudflare sort au lieu d'entrer — le déclarer évite de crier si Caddy
#:         ou un autre service y écoutait un jour ;
#:   8080  List-dons, autre projet qui cohabite sur rpi2 (mémoire
#:         `project_listdons_cohabite_sur_rpi2`).
#: Tout ce que `docker-compose.yml` publie sur toutes les interfaces doit y
#: figurer : l'autotest le vérifie sur le fichier du dépôt (`ports_publies_compose`).
PORTS_ECOUTE_BLANCHE="${PORTS_ECOUTE_BLANCHE:-22 80 443 8080}"

# ── La collecte, exécutée sur CHAQUE nœud (reprise par COLLECT) ──────────────
#  Même contrainte que `lib-collecte.sh` : chaîne entre guillemets SIMPLES, donc
#  AUCUNE apostrophe dans le fragment, même en commentaire. Tout s'explique ici :
#   - ports_ecoute : « ok: » puis les ports à l'écoute sur une adresse joker,
#     triés numériquement, séparés par des virgules. Le marqueur « ok: » distingue
#     « aucun » de « ss absent ou muet », qui rend VIDE — cas zéro : sans lui, deux
#     mesures impossibles seraient deux chaînes égales, donc un faux « identiques » ;
#   - `tr -s` + `cut -f4` : la 4e colonne de `ss -tln` est l adresse locale ;
#     l en-tête (« Local ») ne correspond à aucun motif ;
#   - une adresse « 0.0.0.0%eth0 » (liée à UNE interface) n est pas un joker.
COLLECT_PORTS='
if command -v ss >/dev/null 2>&1 && _s=$(ss -tln 2>/dev/null) && [ -n "$_s" ]; then
echo "ports_ecoute=ok:$(printf "%s\n" "$_s" | tr -s " " | sed "s/^ //" | cut -d" " -f4 | grep -E "^(0\.0\.0\.0|\*|\[::\]|::):[0-9]+\$" | sed "s/.*://" | sort -un | paste -sd, -)"
else
echo "ports_ecoute="
fi
'

# ── Décisions PURES (aucun effet de bord) ────────────────────────────────────

#  $1 le relevé « ok:22,80,111 » → les ports « 22,80,111 » (vide si aucun) ;
#  échoue si le relevé n'a pas le marqueur « ok: » (mesure impossible).
ports_valeur() {
    case "${1:-}" in ok:*) printf '%s' "${1#ok:}" ;; *) return 1 ;; esac
}

#  $1 les ports « a,b,c » · $2 la liste blanche (espaces) → ceux qui n'y sont pas
ports_hors_liste() {
    local p out=''
    local IFS=,
    for p in ${1:-}; do
        case " ${2:-} " in *" $p "*) continue ;; esac
        out="$out${out:+,}$p"
    done
    printf '%s' "$out"
}

#  $1 le relevé · $2 la liste blanche → OK | HORS_LISTE | INCONNU
verdict_ports_ecoute() {
    local v h
    v=$(ports_valeur "${1:-}") || { echo INCONNU; return; }
    h=$(ports_hors_liste "$v" "${2:-}")
    [ -n "$h" ] && echo HORS_LISTE || echo OK
}

#  $1 mon relevé · $2 le relevé de l'autre nœud · $3 la liste blanche · $4 le nom
#  de l'autre nœud → « 111 (absent de rpi2), 631 (aussi sur rpi2) » : chaque port
#  hors liste, et ce que l'autre nœud en fait. Un relevé de l'autre illisible ne
#  prétend rien : le port reste seul, sans parenthèse.
ports_decrire_hors_liste() {
    local mes autre p out='' note
    mes=$(ports_hors_liste "$(ports_valeur "${1:-}")" "${3:-}")
    if autre=$(ports_valeur "${2:-}"); then autre=$(ports_hors_liste "$autre" "${3:-}"); else autre=NA; fi
    local IFS=,
    for p in $mes; do
        if [ "$autre" = NA ]; then note=''
        else case ",$autre," in *",$p,"*) note=" (aussi sur ${4:-autre nœud})" ;; *) note=" (absent de ${4:-autre nœud})" ;; esac
        fi
        out="$out${out:+, }$p$note"
    done
    printf '%s' "$out"
}

#  $1 un fichier docker-compose → les ports hôte qu'il publie sur TOUTES les
#  interfaces, un par ligne. `"80:80"` et `"0.0.0.0:80:80"` en sont ; `"127.0.0.1:8090:8090"`
#  non. Seules les lignes `- "N:N"` / `- "IP:N:N"` comptent : une variable
#  d'environnement ou un volume contient des lettres.
ports_publies_compose() {
    awk '
        { sub(/\r$/, "") }
        /^[[:space:]]*-[[:space:]]*"?[0-9.]+:[0-9.]+(:[0-9.]+)?"?[[:space:]]*(#.*)?$/ {
            l = $0; sub(/^[[:space:]]*-[[:space:]]*"?/, "", l); sub(/"?[[:space:]]*(#.*)?$/, "", l)
            n = split(l, a, ":")
            if (n == 2) print a[1]
            else if (n == 3 && a[1] == "0.0.0.0") print a[2]
        }
    ' "$1" 2>/dev/null | sort -un
}

# ── C32. Les ports à l'écoute sur toutes les interfaces, par nœud ────────────
ports_ecoute_verdicts() {
    local n p mon autre autre_nom liste
    for n in "$SELF" "$PEER"; do
        if [ "$n" = "$SELF" ]; then p=S; autre_nom=$PEER; else [ "$PEER_OK" -eq 0 ] || continue; p=P; autre_nom=$SELF; fi
        eval "mon=\${${p}_ports_ecoute:-}"
        #  Le relevé de l'AUTRE nœud, seulement s'il a pu être pris (pair joignable).
        if [ "$n" = "$SELF" ]; then
            if [ "$PEER_OK" -eq 0 ]; then autre=${P_ports_ecoute:-}; else autre=''; fi
        else autre=${S_ports_ecoute:-}; fi
        case "$(verdict_ports_ecoute "$mon" "$PORTS_ECOUTE_BLANCHE")" in
            OK)         liste=$(ports_valeur "$mon")
                        ok   "Ports à l'écoute sur toutes les interfaces de $n : ${liste//,/, } — tous dans la liste blanche (${PORTS_ECOUTE_BLANCHE// /, })" ;;
            HORS_LISTE) warn "Port(s) à l'écoute sur TOUTES les interfaces de $n, hors liste blanche (${PORTS_ECOUTE_BLANCHE// /, }) : $(ports_decrire_hors_liste "$mon" "$autre" "$PORTS_ECOUTE_BLANCHE" "$autre_nom") — un service ouvert sur le LAN que personne n'a déclaré ; 'ss -tlnp' (root) nomme le processus : le désactiver, ou l'ajouter à PORTS_ECOUTE_BLANCHE avec sa raison (#1593)" ;;
            *)          warn "Ports à l'écoute de $n INCONNUS (ss absent ou muet : '${mon:-vide}') — ni vert ni rouge" ;;
        esac
    done
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → ${r:-(rien)}" || { echo "FAIL  $1  attendu=${2:-(rien)} obtenu=${r:-(rien)}"; st=1; }; }
    BL="22 80 443 8080"
    ICI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

    echo "== la décision =="
    t "rpi1 le 02/10 : 22, 80 et rpcbind (111)"   HORS_LISTE verdict_ports_ecoute "ok:22,80,111" "$BL"
    t "rpi2 le 02/10 : 22 et List-dons (8080)"    OK         verdict_ports_ecoute "ok:22,8080" "$BL"
    t "le standby : 22 seul (Caddy arrêté)"       OK         verdict_ports_ecoute "ok:22" "$BL"
    t "aucun port mesuré (ok: vide) → OK, mesuré" OK         verdict_ports_ecoute "ok:" "$BL"
    t "relevé vide (ss absent) → INCONNU"         INCONNU    verdict_ports_ecoute "" "$BL"
    t "sans marqueur « ok: » → INCONNU, jamais OK" INCONNU   verdict_ports_ecoute "22,80" "$BL"
    t "liste blanche vide : tout est hors liste"  HORS_LISTE verdict_ports_ecoute "ok:22" ""
    t "2222 n'est pas 22 (comparaison EXACTE)"    HORS_LISTE verdict_ports_ecoute "ok:2222" "$BL"
    t "80 n'est pas 8080"                         HORS_LISTE verdict_ports_ecoute "ok:80" "8080"
    t "les ports hors liste, dans l'ordre"        "111,631"  ports_hors_liste "22,111,631,80" "$BL"
    t "…aucun si tout est déclaré"                ""         ports_hors_liste "22,80" "$BL"

    echo "== le constat décrit la divergence =="
    t "111 sur rpi1 seul"                  "111 (absent de rpi2)"  ports_decrire_hors_liste "ok:22,80,111" "ok:22,8080" "$BL" rpi2
    t "111 des DEUX côtés"                 "111 (aussi sur rpi1)"  ports_decrire_hors_liste "ok:22,111" "ok:22,111" "$BL" rpi1
    t "un des deux seulement partagé"      "111 (aussi sur rpi2), 631 (absent de rpi2)" ports_decrire_hors_liste "ok:111,631" "ok:111" "$BL" rpi2
    t "l'autre nœud muet : pas de comparaison inventée" "111" ports_decrire_hors_liste "ok:111" "" "$BL" rpi2
    t "l'autre nœud sans marqueur : idem"  "111"  ports_decrire_hors_liste "ok:111" "111" "$BL" rpi2

    echo "== la collecte, exécutée sur un ss simulé aux formes RÉELLES (rpi1, 02/10/2026) =="
    ss() { cat <<'X'
State  Recv-Q Send-Q Local Address:Port  Peer Address:PortProcess
LISTEN 0      4096         0.0.0.0:111        0.0.0.0:*
LISTEN 0      128          0.0.0.0:22         0.0.0.0:*
LISTEN 0      4096         0.0.0.0:80         0.0.0.0:*
LISTEN 0      4096       127.0.0.1:8090       0.0.0.0:*
LISTEN 0      4096       127.0.0.1:20241      0.0.0.0:*
LISTEN 0      4096    127.0.0.53%lo:53        0.0.0.0:*
LISTEN 0      4096            [::]:111           [::]:*
LISTEN 0      128             [::]:22            [::]:*
LISTEN 0      4096            [::]:80            [::]:*
LISTEN 0      32                 *:5353              *:*
LISTEN 0      4096     [fe80::1%eth0]:9100         [::]:*
LISTEN 0      4096         0.0.0.0%eth0:67   0.0.0.0:*
X
    }
    champ() { eval "$COLLECT_PORTS" | sed -n "s/^$1=//p"; }
    t "collecte : jokers IPv4, IPv6 et *, dédoublonnés et triés" "ok:22,80,111,5353" champ ports_ecoute
    t "collecte : 127.0.0.1 et 127.0.0.53%lo n'en sont pas"     0 eval 'champ ports_ecoute | grep -cE "8090|20241|[:,]53([,]|$)"'
    t "collecte : une adresse liée à UNE interface n'en est pas un" 0 eval 'champ ports_ecoute | grep -cE "67|9100"'
    ss() { printf 'State Recv-Q Send-Q Local Address:Port Peer Address:Port\nLISTEN 0 128 :::22 :::*\nLISTEN 0 128 *:80 *:*\n'; }
    t "collecte : formes anciennes de ss (:::22, *:80)" "ok:22,80" champ ports_ecoute
    ss() { printf 'State Recv-Q Send-Q Local Address:Port Peer Address:Port\nLISTEN 0 128 127.0.0.1:631 0.0.0.0:*\n'; }
    t "collecte : aucun joker → « ok: » vide, mesuré" "ok:" champ ports_ecoute
    ss() { return 1; }
    t "collecte : ss en échec → VIDE (INCONNU)" "" champ ports_ecoute
    ss() { :; }
    t "collecte : ss muet → VIDE, jamais « ok: »" "" champ ports_ecoute
    unset -f ss champ
    t "collecte : sans ss → VIDE" "ports_ecoute=" eval 'PATH=/nonexistent "$BASH" -c "$COLLECT_PORTS"'
    if bash -n <(printf '%s' "$COLLECT_PORTS") 2>/dev/null; then echo "PASS  COLLECT_PORTS est du shell valide"
    else echo "FAIL  COLLECT_PORTS est du shell INVALIDE (apostrophe dans la chaîne ?)"; st=1; fi
    t "collecte : aucune apostrophe dans la chaîne" 0 eval 'printf "%s" "$COLLECT_PORTS" | grep -c "$(printf "\047")"'

    echo "== la liste blanche tient ce que le dépôt fait écouter =="
    pub=$(ports_publies_compose "$ICI/../../docker-compose.yml" | paste -sd, -)
    t "docker-compose.yml : 80 est publié sur toutes les interfaces" 80 eval 'echo "$pub"'
    t "…tout ce qu'il publie est dans la liste blanche" "" ports_hors_liste "$pub" "$BL"
    t "…et le 8090 du bridge (127.0.0.1) n'est PAS compté" 0 eval 'echo "$pub" | grep -c 8090'
    tmpc=$(mktemp)
    printf '%s\r\n' 'services:' '  a:' '    ports:' '      - "80:80"' '      - "127.0.0.1:8090:8090"' '      - "0.0.0.0:9000:9000"  # public' \
      '      - 111:111' '    environment:' '      - WA_PORT=8090' '      - TZ=Europe/Paris' '    volumes:' '      - ./Caddyfile:/etc/caddy/Caddyfile:ro' > "$tmpc"
    t "forme réelle : joker, IP explicite, CRLF, commentaire, sans guillemets" "80,111,9000" eval 'ports_publies_compose "$tmpc" | paste -sd, -'
    printf '%s\n' '    ports:' '      - "6379:6379"' > "$tmpc"
    t "faute injectée : un port publié hors liste blanche est refusé" 6379 \
      eval 'ports_hors_liste "$(ports_publies_compose "$tmpc" | paste -sd, -)" "$BL"'
    t "fichier absent → rien (et l'autotest ci-dessus échouerait sur le 80)" "" ports_publies_compose "$tmpc.absent"
    rm -f "$tmpc"

    echo "== les constats, sur les DEUX nœuds =="
    ok()   { echo "OK $*"; }
    warn() { echo "WARN $*"; }
    SELF=rpi1 PEER=rpi2 PEER_OK=0 PORTS_ECOUTE_BLANCHE="$BL"
    S_ports_ecoute="ok:22,80" P_ports_ecoute="ok:22,8080"; sortie=$(ports_ecoute_verdicts)
    t "rpi1 : 22,80 / rpi2 : 22,8080 (le régime normal) → deux OK, aucun WARN" "2|0" \
      eval 'echo "$(grep -c "^OK Ports à l.écoute sur toutes les interfaces de rpi" <<< "$sortie")|$(grep -c "^WARN" <<< "$sortie")"'
    #  La faute du ticket : rpcbind sur rpi1 seulement.
    S_ports_ecoute="ok:22,80,111"; sortie=$(ports_ecoute_verdicts)
    t "faute injectée : 111 sur rpi1 seul → UN WARN qui nomme rpi1 et dit « absent de rpi2 »" 1 \
      eval 'grep -c "^WARN Port(s) à l.écoute sur TOUTES les interfaces de rpi1, hors liste blanche (22, 80, 443, 8080) : 111 (absent de rpi2)" <<< "$sortie"'
    t "…et rpi2, sain, reste OK (un constat par nœud)" "1|1" \
      eval 'echo "$(grep -c "^WARN" <<< "$sortie")|$(grep -c "^OK .* de rpi2 : 22, 8080" <<< "$sortie")"'
    P_ports_ecoute="ok:22,111"; sortie=$(ports_ecoute_verdicts)
    t "111 des deux côtés : un WARN PAR nœud, qui dit « aussi sur »" "2|1" \
      eval 'echo "$(grep -c "^WARN" <<< "$sortie")|$(grep -c "111 (aussi sur rpi1)" <<< "$sortie")"'
    S_ports_ecoute="" ; P_ports_ecoute="ok:22"; sortie=$(ports_ecoute_verdicts)
    t "rien mesuré sur rpi1 → WARN INCONNU, jamais OK" "1|1" \
      eval 'echo "$(grep -c "^WARN Ports à l.écoute de rpi1 INCONNUS" <<< "$sortie")|$(grep -c "^OK .* de rpi2" <<< "$sortie")"'
    S_ports_ecoute="ok:22,111"; PEER_OK=255; P_ports_ecoute=""; sortie=$(ports_ecoute_verdicts)
    t "pair injoignable : seul rpi1 est jugé, sans comparaison inventée" "1|0" \
      eval 'echo "$(grep -c "^WARN .* rpi1, hors liste blanche (22, 80, 443, 8080) : 111 — " <<< "$sortie")|$(grep -c "rpi2" <<< "$sortie")"'
    unset -f ok warn

    [ "$st" -eq 0 ] && echo "lib-ports-ecoute : tous les cas passent."
    exit "$st"
fi
