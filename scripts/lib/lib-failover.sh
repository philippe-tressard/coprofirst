#!/bin/bash
# =============================================================================
#  lib-failover.sh — Les DÉCISIONS du failover automatique (`health-watch.sh`)
#  (module à sourcer ; extrait de health-watch le 15/10/2026, #1997 #2000)
#
#  Le failover fait passer le rôle actif d'un nœud qui ne sert plus au standby.
#  Il en décide en quatre temps, chacun ici en fonction PURE ou à gestes
#  injectés, pour que l'autotest éprouve l'ORDRE et pas seulement les cas :
#
#    1. faut-il basculer ?            `decide_failover` (sondes, déploiement,
#                                     tunnel de l'actif mesuré chez lui)
#    2. le tunnel démarre-t-il ici ?  `decide_suite_tunnel`
#    3. la base peut-elle être prise, et l'ancien actif isolé ?
#                                     `prendre_la_main` — DÉCIDER, puis ISOLER,
#                                     puis PROMOUVOIR, jamais dans un autre ordre
#    4. que conseiller ensuite ?      `conseil_apres_failover`
#
#  🔴 L'INCIDENT DU 15/10/2026 (#1997). Le failover a isolé rpi2 à 20:03:02, la
#  seconde même où son auto-deploy commençait un déploiement, lancé sur la foi
#  d'un `.active` lu au début du passage. À 20:06, ce déploiement a relancé
#  l'application ET le primaire PostgreSQL sur le nœud rétrogradé : deux
#  primaires, deux tunnels, le public réparti entre deux bases qui divergent.
#  D'où, ici :
#    • l'ISOLEMENT écrit `.active` chez l'ancien actif dans le même appel que
#      l'arrêt, sous SON verrou de déploiement : un déploiement en cours finit
#      d'abord (borné), un déploiement suivant lit le nouveau rôle ;
#    • le failover s'ABSTIENT tant que le pair déploie (`decide_failover`) — un
#      redémarrage de l'API pendant une MEP n'est pas une panne.
#    La relecture du rôle juste avant chaque `up` est dans `servir_images`
#    (`lib-parite.sh`), côté auto-deploy.
#
#  🔴 #2000. L'ancien actif était arrêté AVANT de savoir si la base locale
#  pouvait être prise : une réplique illisible abandonnait le failover en
#  laissant éteint un nœud qui servait en LAN. Et un ancien actif vivant mais
#  injoignable par SSH ne s'isolait pas — on promouvait quand même : deux
#  primaires. `prendre_la_main` décide d'abord, et s'abstient dans ce cas.
#
#  Test : bash lib-failover.sh --selftest   (aucun effet de bord)
# =============================================================================

_LIB_FAILOVER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib-verrou.sh
source "$_LIB_FAILOVER/lib-verrou.sh"         # etat_deploiement, VERROU_STALE_S
# shellcheck source=lib-applicatifs.sh
source "$_LIB_FAILOVER/lib-applicatifs.sh"    # SERVICES_APPLICATIFS, SERVICES_DU_NOEUD
# shellcheck source=lib-promotion.sh
source "$_LIB_FAILOVER/lib-promotion.sh"      # decider_prise_de_main

#  Combien de temps l'isolement attend qu'un déploiement en cours chez l'ancien
#  actif se termine (s). Un déploiement complet dure ~3 min 30 (15/10/2026 :
#  20:03:02 → 20:06:23) ; au-delà, on isole quand même — le site est en panne,
#  et la relecture du rôle par auto-deploy refusera de relancer quoi que ce soit.
ISOLEMENT_ATTENTE_S=${ISOLEMENT_ATTENTE_S:-300}

# ── 1. Faut-il basculer ? (PURE) ─────────────────────────────────────────────
#  $1 l'API de l'ACTIF répond-elle en LAN (http://<actif>/api/health) ? ok|autre
#  $2 CE nœud atteint-il l'edge Cloudflare (DNS + TLS) ?                ok|autre
#  $3 le déploiement chez l'actif (`etat_deploiement`) : libre|en-cours|bloque|inconnu
#  → failover | abstain:<raison>
#
#  POURQUOI l'edge (incident du 30/07/2026, 00:52→01:46) : une panne DNS/WAN a
#  coupé le tunnel des DEUX nœuds. Chacun ne sondait que l'URL publique et
#  concluait « l'autre est HS » : 12 failovers croisés en 55 min, sans jamais
#  rien rétablir. On ne bascule pas quand l'actif PROUVE qu'il sert (LAN) et que
#  nous-mêmes n'atteignons pas l'edge — nous ne ferions pas mieux.
#
#  POURQUOI le déploiement (#1997) : auto-deploy recrée l'API, qui ne répond plus
#  pendant une à deux minutes — LAN et public KO ensemble, l'image exacte d'un
#  nœud mort. Un déploiement en cours se lit chez le pair, donc le pair VIT : on
#  attend le passage suivant. Borné : un verrou tenu au-delà de VERROU_STALE_S
#  (`bloque`) n'interdit plus rien. Pair injoignable (`inconnu`) : rien ne prouve
#  qu'il vit — le chemin critique « actif mort » reste inchangé.
#
#  $4 le tunnel de l'actif (`etat_tunnel`) : sain|casse|inconnu
#  $5 le code de la sonde publique qui a confirmé la panne (`000` : aucune réponse)
#
#  POURQUOI le tunnel (17/10/2026, #2073) : deux `000` à 30 s d'écart, l'API de
#  l'actif vivante en LAN, l'edge joignable — la matrice concluait « tunnel
#  cassé » et a promu la base de rpi2. Le tunnel de rpi1 avait ses quatre
#  connexions, et les `000` ont continué toute la soirée avec rpi2 actif : la
#  requête n'atteignait même pas le Caddy de l'actif. Un tunnel réellement
#  coupé ne donne pas `000` : l'edge RÉPOND, par une erreur (503 le 25/09/2026,
#  530 selon Cloudflare). Une absence de réponse avec un tunnel sain est une
#  panne de chemin intermittente, que basculer ne réparerait pas — on la
#  mesure chez l'actif lui-même plutôt que de la déduire. Un tunnel illisible
#  avec un actif vivant ne s'isolerait pas davantage (même SSH) : on ne
#  promeut pas sur une supposition. Le cas du 25/09 (edge qui répond 503) et
#  le tunnel mesuré cassé basculent comme avant.
decide_failover() {
    local lan="$1" edge="$2" dep="${3:-inconnu}" tunnel="${4:-inconnu}" public="${5:-000}"
    if [ "$dep" = en-cours ]; then
        echo "abstain:deploiement-en-cours"; return
    fi
    if [ "$lan" = "ok" ] && [ "$edge" != "ok" ]; then
        echo "abstain:chemin-public-coupe"; return
    fi
    if [ "$lan" = "ok" ] && [ "$public" = 000 ] && [ "$tunnel" != casse ]; then
        if [ "$tunnel" = sain ]; then echo "abstain:tunnel-actif-sain"
        else echo "abstain:tunnel-actif-illisible"; fi
        return
    fi
    echo "failover"
}

#  La sonde du tunnel, exécutée CHEZ l'actif en un appel SSH (le compte des
#  nœuds, sans sudo) : l'état de l'unité, puis le nombre de connexions que
#  cloudflared tient avec l'edge, lu sur son serveur de métriques local
#  (`/ready`, premier port libre de 20241 à 20245 — 20241 sur les deux nœuds).
#  Écrit « tunnel <état systemd> <connexions|?> ».
etat_tunnel_sh() {
    printf '%s\n' \
        'e=$(systemctl is-active cloudflared 2>/dev/null); r=""' \
        'for p in 20241 20242 20243 20244 20245; do r=$(curl -s --max-time 3 "http://127.0.0.1:$p/ready" 2>/dev/null) && [ -n "$r" ] && break; done' \
        'n=$(printf "%s" "$r" | sed -n "s/.*\"readyConnections\":\([0-9][0-9]*\).*/\1/p")' \
        'echo "tunnel ${e:-inconnu} ${n:-?}"'
}

#  PURE : la sortie de la sonde → sain | casse | inconnu
#  « sain » exige la PREUVE (unité active ET au moins une connexion) ; une unité
#  arrêtée, en échec ou qui boucle, ou active sans connexion, est cassée ; rien
#  lu (SSH en échec) ou un compte illisible ne prouvent rien.
etat_tunnel() {
    local _t e n
    read -r _t e n <<< "$(printf '%s\n' "${1:-}" | grep '^tunnel ' | tail -n 1)"
    [ "$_t" = tunnel ] || { echo inconnu; return; }
    case "$e" in
        active) ;;
        inactive|failed|activating|deactivating) echo casse; return ;;
        *) echo inconnu; return ;;
    esac
    case "$n" in
        ''|*[!0-9]*) echo inconnu ;;
        0)           echo casse ;;
        *)           echo sain ;;
    esac
}

# ── 2. Le tunnel démarre-t-il ici ? (PURE) ───────────────────────────────────
#  $1 l'état de l'unité après `systemctl start cloudflared` (`is-active`)
#  → poursuivre | abandon:<état>
#
#  POURQUOI (25/09/2026, #1318) : le jeton du tunnel était invalide sur les DEUX
#  nœuds ; le standby a basculé quand même, ignorant l'échec du tunnel. Sa cause
#  est souvent COMMUNE (jeton, configuration, compte) : sans tunnel, prendre le
#  rôle ne fait que démoter le seul nœud qui tourne. Seul « active » prouve le
#  démarrage — `activating` est la boucle de redémarrage, le vide une mesure ratée.
decide_suite_tunnel() {
    if [ "${1:-}" = "active" ]; then echo "poursuivre"; else echo "abandon:${1:-inconnu}"; fi
}

# ── 3. L'isolement de l'ancien actif ─────────────────────────────────────────
#  La commande exécutée CHEZ l'ancien actif, en UN appel SSH (le compte des nœuds) :
#    • prendre son verrou de DÉPLOIEMENT (attente bornée) : aucun auto-deploy ne
#      tourne pendant l'isolement, et le suivant lira le nouveau `.active` ;
#    • écrire `.active` AVANT d'arrêter quoi que ce soit — le 15/10, l'arrêt a
#      réussi à 20:03:02 et l'appel suivant, qui devait écrire `.active`, a
#      trouvé rpi2 « injoignable » : il s'est cru actif et a tout relancé ;
#    • arrêter l'application puis la base, chacune NOMMÉE (#1999) ;
#    • arrêter et désactiver le tunnel : `sudo -n` et deux gestes, exactement
#      ceux que la règle sudoers accorde (`lib-sudoers.sh`) — l'ancien
#      `disable --now` n'y figurait pas et échouait en silence.
#  La dernière ligne dit ce qui a été fait : `isole` ou `isole-sans-verrou`.
#  $1 le nœud qui prend la main (écrit dans `.active` de l'ancien) · $2 l'attente (s)
isoler_ancien_actif_sh() {
    printf '%s\n' \
        "cd /opt/5hostachy || exit 9" \
        "VERROU=isole; exec 8>>.auto-deploy.lock" \
        "command -v flock >/dev/null 2>&1 && ! flock -w ${2:-$ISOLEMENT_ATTENTE_S} 8 && VERROU=isole-sans-verrou" \
        "printf '%s\\n' '$1' > .active || exit 8" \
        "docker compose stop $SERVICES_APPLICATIFS >/dev/null 2>&1" \
        "docker compose stop $SERVICE_BASE >/dev/null 2>&1" \
        "sudo -n systemctl stop cloudflared >/dev/null 2>&1" \
        "sudo -n systemctl disable cloudflared >/dev/null 2>&1" \
        'echo "$VERROU"'
}

#  PURE : la sortie de l'appel → isole | isole-sans-verrou | injoignable
#  Seule la dernière ligne compte, et seulement avec un code 0 : un appel coupé
#  en route n'a rien prouvé.
bilan_isolement() {  # $1 sortie · $2 code de sortie de ssh
    local der
    der=$(printf '%s\n' "${1:-}" | tail -n 1)
    if [ "${2:-1}" = 0 ] && { [ "$der" = isole ] || [ "$der" = isole-sans-verrou ]; }; then
        echo "$der"
    else
        echo injoignable
    fi
}

#  PURE : l'isolement a-t-il échoué de telle façon qu'il faille renoncer ?
#  $1 sonde LAN de l'actif (ok|autre) · $2 bilan de l'isolement
#  → poursuivre | abandon:<raison>
#  Un actif MORT (LAN KO) injoignable, c'est le cas nominal du failover : il ne
#  sert rien, boot-role-guard le retirera à son retour. Un actif VIVANT (LAN OK)
#  qu'on n'a pas pu isoler sert encore sa base : promouvoir la nôtre ferait deux
#  primaires.
decider_apres_isolement() {
    case "${2:-}" in
        isole|isole-sans-verrou|sans-objet) echo poursuivre; return ;;
    esac
    if [ "${1:-}" = ok ]; then
        echo "abandon:l'ancien actif sert en LAN mais n'a pas pu être isolé — promouvoir ici ferait deux primaires"
    else
        echo poursuivre
    fi
}

#  Prendre la main : DÉCIDER, puis ISOLER, puis PROMOUVOIR (#2000).
#  $1 sonde LAN de l'actif
#  Gestes fournis par l'appelant : `role_base_locale`, `isoler_ancien_actif`
#  (écrit son bilan), `promouvoir_local`. Pose :
#    PRISE       décision sur la base (PROMOUVOIR|GARDER|ABSTENIR:…)
#    ISOLEMENT   non-tente | sans-objet | isole | isole-sans-verrou | injoignable
#    A_DEMARRER  la liste des services à démarrer (jamais vide si l'on poursuit)
#    RENONCEMENT la raison, si l'on renonce
#  Rend 0 si l'on démarre, 1 si l'on renonce. Une base qu'on ne peut pas prendre
#  ne démarre JAMAIS — elle s'initialiserait en primaire VIDE —, et l'application
#  n'a pas d'autre base : on ne démarre RIEN.
prendre_la_main() {
    local lan="${1:-}" suite
    ISOLEMENT=non-tente; A_DEMARRER=""; RENONCEMENT=""
    PRISE=$(decider_prise_de_main "$(role_base_locale)")
    #  🔴 Décidé AVANT tout geste : on ne prend pas, on ne touche à rien.
    case "$PRISE" in ABSTENIR:*) RENONCEMENT=${PRISE#ABSTENIR:}; return 1 ;; esac
    ISOLEMENT=$(isoler_ancien_actif)
    suite=$(decider_apres_isolement "$lan" "$ISOLEMENT")
    if [ "$suite" != poursuivre ]; then
        RENONCEMENT=${suite#abandon:}; return 1
    fi
    if [ "$PRISE" = PROMOUVOIR ] && ! promouvoir_local; then
        RENONCEMENT="la promotion de la réplique locale a échoué"
        PRISE="ABSTENIR:$RENONCEMENT"; return 1
    fi
    A_DEMARRER=$SERVICES_DU_NOEUD
    return 0
}

# ── 4. Que conseiller après un failover ? (PURE) ─────────────────────────────
#  $1 l'ancien actif · $2 bilan de l'isolement
#  L'ancien actif ne se resynchronise pas par une bascule : `phases_base_postgresql`
#  exige une réplique saine chez le pair, que le failover vient d'arrêter. Le
#  geste est la reconstruction (#2000).
conseil_apres_failover() {
    local ancien="${1:-ancien actif}"
    printf '%s
'         "La base est la réplique promue de ce nœud : $ancien n'a plus de réplique"         "à jour, et ses écritures depuis la promotion sont perdues."         ""         "Action recommandée dès que $ancien est de retour, SUR $ancien :"         "  sudo bash /opt/5hostachy/scripts/exploitation/reconstruire-replique.sh        (simulation)"         "  sudo bash /opt/5hostachy/scripts/exploitation/reconstruire-replique.sh --oui"         "Jamais de « docker compose up » sur $ancien : sa base redémarrerait en second primaire."
    case "${2:-}" in
        injoignable) printf '%s\n' "" \
            "⚠ $ancien n'a PAS pu être isolé (injoignable) : son .active le désigne encore actif." \
            "boot-role-guard le retirera à son redémarrage ; sinon, sur $ancien :" \
            "  docker compose stop $SERVICES_APPLICATIFS $SERVICE_BASE ; sudo systemctl disable --now cloudflared" ;;
        isole-sans-verrou) printf '%s\n' "" \
            "⚠ $ancien déployait encore après ${ISOLEMENT_ATTENTE_S} s : isolé sans attendre la fin." \
            "Son auto-deploy relit le rôle avant chaque démarrage et doit s'abstenir — à vérifier :" \
            "  tail -20 /var/log/hostachy-deploy.log ; docker ps" ;;
    esac
}

# ── Autotest (job CI `test-scripts`) ──────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    fail=0
    ok_ko() { if [ "$2" = "$3" ]; then echo "PASS  $1  → $3"; else echo "FAIL  $1  attendu=$2 obtenu=$3"; fail=1; fi; }
    #  `flock` manque sous Git Bash (le poste) : le cas se NOMME sauté, et la CI
    #  (Linux), qui l'a toujours, échoue si elle ne l'avait plus — jamais un vert.
    flock_ou_saut() {
        command -v flock >/dev/null 2>&1 && return 0
        if [ -n "${CI:-}" ]; then echo "FAIL  flock absent en CI : $1 ne peut pas être éprouvé"; fail=1
        else echo "SAUTÉ  $1 — flock absent sur ce poste, la CI (Linux) l'éprouve"; fi
        return 1
    }

    echo "== decide_failover =="
    ok_ko "actif mort, edge OK (cas nominal)"            failover                      "$(decide_failover ko ok libre)"
    ok_ko "actif mort + WAN KO (on prend le rôle)"       failover                      "$(decide_failover ko ko inconnu)"
    ok_ko "actif vivant en LAN, edge KO (30/07/2026)"    abstain:chemin-public-coupe   "$(decide_failover ok ko libre)"
    ok_ko "actif vivant, edge OK, tunnel MESURÉ cassé"   failover                      "$(decide_failover ok ok libre casse 000)"
    #  🔴 Le 17/10/2026 (#2073) : 000, 000, LAN ok, edge ok, tunnel de l'actif sain.
    ok_ko "17/10 : 000 deux fois, tunnel de l'actif SAIN" abstain:tunnel-actif-sain   "$(decide_failover ok ok libre sain 000)"
    ok_ko "000, tunnel de l'actif ILLISIBLE : on ne promeut pas" abstain:tunnel-actif-illisible "$(decide_failover ok ok libre inconnu 000)"
    #  Le 25/09/2026 : l'edge RÉPOND (503) — l'origine lui manque ; on bascule comme avant.
    ok_ko "25/09 : l'edge répond 503, tunnel cassé"      failover                      "$(decide_failover ok ok libre casse 503)"
    ok_ko "l'edge répond 530, tunnel illisible"          failover                      "$(decide_failover ok ok libre inconnu 530)"
    #  Le chemin critique : l'API de l'actif ne répond plus, le tunnel n'y change rien.
    ok_ko "actif MORT, tunnel encore « sain » : failover" failover                     "$(decide_failover ko ok libre sain 000)"
    ok_ko "actif mort, rien de plus lu"                  failover                      "$(decide_failover ko ok inconnu)"
    #  Une sonde qui n'a PAS pu s'exécuter ne vaut pas « actif vivant ».
    ok_ko "sonde LAN indisponible → pas de blocage"      failover                      "$(decide_failover "" ko inconnu)"
    #  🔴 #1997 : l'API redémarre pendant une MEP — LAN et public KO, le pair déploie.
    ok_ko "le pair DÉPLOIE (API qui redémarre)"          abstain:deploiement-en-cours  "$(decide_failover ko ok en-cours)"
    ok_ko "le pair déploie, tunnel HS"                   abstain:deploiement-en-cours  "$(decide_failover ok ok en-cours)"
    ok_ko "déploiement BLOQUÉ au-delà du seuil"          failover                      "$(decide_failover ko ok bloque)"
    ok_ko "pair injoignable : rien ne prouve qu'il vit"  failover                      "$(decide_failover ko ok inconnu)"

    echo "== etat_tunnel (la sonde du tunnel de l'actif, jugée) =="
    ok_ko "unité active, 4 connexions (17/10)"   sain    "$(etat_tunnel "tunnel active 4")"
    ok_ko "unité active, aucune connexion"       casse   "$(etat_tunnel "tunnel active 0")"
    ok_ko "unité arrêtée (témoin)"               casse   "$(etat_tunnel "tunnel inactive ?")"
    ok_ko "unité en échec"                       casse   "$(etat_tunnel "tunnel failed ?")"
    ok_ko "jeton refusé, systemd relance"        casse   "$(etat_tunnel "tunnel activating ?")"
    ok_ko "active, métriques illisibles"         inconnu "$(etat_tunnel "tunnel active ?")"
    ok_ko "SSH en échec (rien lu)"               inconnu "$(etat_tunnel "")"
    ok_ko "réponse inattendue"                   inconnu "$(etat_tunnel "Permission denied")"

    echo "== la sonde du tunnel, EXÉCUTÉE avec systemctl et curl simulés =="
    st() {  # $1 libellé · $2 attendu · $3 état systemd · $4 réponse de /ready (vide : rien n'écoute)
        local r
        r=$(E="$3" R="$4" bash -c "systemctl() { echo \"\$E\"; }; curl() { [ -n \"\$R\" ] && case \"\$*\" in *:20241/*) printf '%s' \"\$R\" ;; *) return 7 ;; esac; }; $(etat_tunnel_sh)")
        ok_ko "$1" "$2" "$(etat_tunnel "$r")"
    }
    st "17/10 : rpi1, quatre connexions → sain" sain    active '{"status":200,"readyConnections":4,"connectorId":"x"}'
    st "TÉMOIN : tunnel réellement arrêté → cassé" casse inactive ''
    st "active mais /ready muet → illisible"   inconnu active ''
    st "active, /ready sans connexion → cassé" casse   active '{"status":503,"readyConnections":0}'

    echo "== la décision ENTIÈRE, des sondes à l'issue =="
    ok_ko "17/10 rejoué : 000, 000, LAN ok, edge ok, tunnel sain → abstention" abstain:tunnel-actif-sain         "$(decide_failover ok ok "$(etat_deploiement libre 1000000)" "$(etat_tunnel "tunnel active 4")" 000)"
    ok_ko "témoin : le tunnel de l'actif est arrêté → failover"                failover         "$(decide_failover ok ok "$(etat_deploiement libre 1000000)" "$(etat_tunnel "tunnel inactive ?")" 000)"

    echo "== etat_deploiement (la sonde du pair, jugée) =="
    ok_ko "verrou libre"                       libre    "$(etat_deploiement libre 1000000)"
    ok_ko "tenu depuis 3 min"                  en-cours "$(etat_deploiement "tenu 999820" 1000000)"
    ok_ko "tenu depuis 20 min : bloqué"        bloque   "$(etat_deploiement "tenu 998800" 1000000)"
    ok_ko "tenu, début illisible : on attend"  en-cours "$(etat_deploiement "tenu " 1000000)"
    ok_ko "pair injoignable (rien lu)"         inconnu  "$(etat_deploiement "" 1000000)"
    ok_ko "réponse inattendue"                 inconnu  "$(etat_deploiement "Permission denied" 1000000)"

    echo "== la sonde du déploiement, EXÉCUTÉE sur un verrou réel =="
    if flock_ou_saut "la sonde du déploiement"; then
        d=$(mktemp -d)
        ok_ko "aucun fichier de verrou → libre"   libre "$(bash -c "$(etat_deploiement_sh "$d")")"
        : > "$d/.auto-deploy.lock"; touch -d @999820 "$d/$DEBUT_DEPLOIEMENT"
        ok_ko "verrou présent, personne ne le tient → libre" libre "$(bash -c "$(etat_deploiement_sh "$d")")"
        ( flock -x 9; sleep 3 ) 9>>"$d/.auto-deploy.lock" &
        sleep 0.5
        ok_ko "un déploiement TIENT le verrou → tenu <début>" "tenu 999820" "$(bash -c "$(etat_deploiement_sh "$d")")"
        wait; rm -rf "$d"
    fi

    echo "== decide_suite_tunnel =="
    ok_ko "tunnel démarré"                        poursuivre          "$(decide_suite_tunnel active)"
    ok_ko "jeton refusé, systemd relance (25/09)" abandon:activating  "$(decide_suite_tunnel activating)"
    ok_ko "échec définitif"                       abandon:failed      "$(decide_suite_tunnel failed)"
    ok_ko "état illisible"                        abandon:inconnu     "$(decide_suite_tunnel "")"

    echo "== bilan_isolement =="
    ok_ko "isolé sous le verrou"          isole             "$(bilan_isolement "isole" 0)"
    ok_ko "isolé après l'attente"         isole-sans-verrou "$(bilan_isolement "x
isole-sans-verrou" 0)"
    ok_ko "ssh en échec"                  injoignable       "$(bilan_isolement "" 255)"
    ok_ko "coupé avant la fin"            injoignable       "$(bilan_isolement "isole" 255)"
    ok_ko ".active non écrit (exit 8)"    injoignable       "$(bilan_isolement "" 8)"

    echo "== la commande d'isolement, EXÉCUTÉE avec docker et sudo simulés =="
    d=$(mktemp -d); mkdir -p "$d/opt/5hostachy"; echo rpi2 > "$d/opt/5hostachy/.active"
    cmd=$(isoler_ancien_actif_sh rpi1 1 | sed "s#/opt/5hostachy#$d/opt/5hostachy#")
    trace=$(TR="$d/trace" bash -c "docker() { echo \"docker \$*\" >> \"\$TR\"; }; sudo() { echo \"sudo \$*\" >> \"\$TR\"; }; $cmd")
    ok_ko "bilan rendu"                                  isole "$trace"
    ok_ko ".active écrit chez l'ancien actif"            rpi1  "$(cat "$d/opt/5hostachy/.active")"
    ok_ko "application, base et tunnel, chacun NOMMÉ" \
        "docker compose stop $SERVICES_APPLICATIFS|docker compose stop $SERVICE_BASE|sudo -n systemctl stop cloudflared|sudo -n systemctl disable cloudflared" \
        "$(paste -sd'|' "$d/trace")"
    #  Un déploiement tient le verrou plus longtemps que l'attente : on isole quand même, et on le DIT.
    if flock_ou_saut "l'isolement sous un déploiement trop long"; then
        rm -f "$d/trace"; echo rpi2 > "$d/opt/5hostachy/.active"
        ( flock -x 9; sleep 3 ) 9>>"$d/opt/5hostachy/.auto-deploy.lock" &
        sleep 0.5
        trace=$(TR="$d/trace" bash -c "docker() { echo \"docker \$*\" >> \"\$TR\"; }; sudo() { :; }; $cmd")
        wait
        ok_ko "déploiement plus long que l'attente → isolé, dit" isole-sans-verrou "$trace"
        ok_ko "…et .active écrit quand même"                     rpi1              "$(cat "$d/opt/5hostachy/.active")"
    fi
    rm -rf "$d"

    echo "== prendre_la_main : décider, PUIS isoler, PUIS promouvoir (#2000) =="
    #  Gestes simulés : la trace dit lesquels ont eu lieu, et dans quel ordre.
    pm() {  # $1 libellé · $2 trace attendue · $3 rendu attendu · $4 rôle de la base · $5 bilan d'isolement · $6 promotion (0|1) · $7 LAN
        local T; T=$(mktemp)
        _ROLE=$4; _ISOL=$5; _PROMO=$6   # lus par les gestes simulés, à l'appel
        role_base_locale()    { echo "$_ROLE"; }
        isoler_ancien_actif() { echo isoler >> "$T"; echo "$_ISOL"; }
        promouvoir_local()    { echo promouvoir >> "$T"; return "$_PROMO"; }
        local rc=0; prendre_la_main "$7" || rc=$?
        ok_ko "$1" "$2" "$(paste -sd'>' "$T")"
        ok_ko "$1 — démarrage" "$3" "$([ $rc -eq 0 ] && echo "$A_DEMARRER" || echo RENONCE)"
        rm -f "$T"
    }
    tout="$SERVICES_APPLICATIFS $SERVICE_BASE"
    pm "réplique saine : isoler puis promouvoir"     "isoler>promouvoir" "$tout"  replique_ok isole       0 ok
    pm "réplique déconnectée : on promeut, et on le dit" "isoler>promouvoir" "$tout" replique_ko isole   0 ko
    #  🔴 LE CAS DU TICKET : base locale illisible ⇒ l'ancien actif n'est PAS touché.
    pm "réplique ILLISIBLE : l'ancien actif n'est pas touché" "" RENONCE illisible isole 0 ok
    pm "base ABSENTE : rien n'est touché"            ""                  RENONCE  absente     isole       0 ko
    #  🔴 L'actif vit en LAN mais ne s'isole pas : promouvoir ferait deux primaires.
    pm "actif VIVANT non isolé : pas de promotion"   "isoler"            RENONCE  replique_ok injoignable 0 ok
    pm "actif MORT non isolé : on prend la main"     "isoler>promouvoir" "$tout"  replique_ok injoignable 0 ko
    pm "déjà primaire : isoler, sans promouvoir"     "isoler"            "$tout"  primaire    isole       0 ko
    pm "promotion en échec : rien ne démarre"        "isoler>promouvoir" RENONCE  replique_ok isole       1 ko
    unset -f role_base_locale isoler_ancien_actif promouvoir_local

    echo "== conseil_apres_failover =="
    c=$(conseil_apres_failover rpi2 isole)
    case "$c" in *reconstruire-replique.sh*--oui*) echo "PASS  nomme reconstruire-replique.sh" ;; *) echo "FAIL  $c"; fail=1 ;; esac
    case "$c" in *"bascule manuelle"*) echo "FAIL  conseille une bascule"; fail=1 ;; *) echo "PASS  ne conseille pas la bascule (impossible sans réplique)" ;; esac
    case "$(conseil_apres_failover rpi2 injoignable)" in *"PAS pu être isolé"*) echo "PASS  ancien actif non isolé : dit" ;; *) echo "FAIL  injoignable non dit"; fail=1 ;; esac

    [ $fail -eq 0 ] && echo "== lib-failover : TOUS OK ==" || echo "== lib-failover : ÉCHECS =="
    exit $fail
fi
