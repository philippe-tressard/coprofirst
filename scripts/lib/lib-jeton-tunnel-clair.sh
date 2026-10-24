#!/bin/bash
# =============================================================================
#  lib-jeton-tunnel-clair.sh — C39 : le jeton du tunnel est-il EN CLAIR ?
#
#  Né de #2115 (22/10/2026). Le relevé du 03/10 notait, dans une mémoire et nulle
#  part ailleurs, que `ExecStart` de `cloudflared.service` portait `--token <jeton>` :
#  lisible par tout compte local (`ps`, `systemctl cat`, `systemctl show`) et
#  recopié dans les journaux. Aucun ticket, aucun contrôle — le 22/10, les DEUX
#  nœuds le portaient encore. La cause : `cloudflared service install <jeton>`
#  (install-cloudflared.sh) et le `sed --token` de la rotation
#  (changer-jeton-tunnel.sh) l'écrivaient là. Les deux scripts rangent désormais
#  le jeton dans `JETON_FICHIER` (root 600, `lib-jeton-tunnel.sh`) ; ce contrôle
#  est ce qui empêche l'ancienne forme de revenir sans que personne le décide
#  (une réinstallation du nœud avec l'ancienne recette, un `service install` à la main).
#
#  LA MESURE, SUR CHAQUE NŒUD, SANS ROOT : `systemctl cat cloudflared` (lisible
#  par tout compte). 🔴 Le jeton ne QUITTE JAMAIS le nœud : la collecte ne rend
#  qu'un verdict (« clair » ou « absent »), jamais un extrait de l'unité — elle
#  alimente des courriels, un écran et des journaux. Le motif (`JETON_CLAIR_MOTIF`)
#  couvre toutes les formes : `--token <v>`, `--token=<v>`, `TUNNEL_TOKEN=<v>` et
#  toute chaîne `eyJ…` ; `--token-file <chemin>` n'en est pas une.
#
#  FAIL et non WARN : un secret lisible par tout compte local est une porte
#  ouverte, pas une hygiène (même raisonnement que C38). INCONNU → WARN, jamais OK
#  (`standards/04` §1) : une unité illisible ne prouve pas l'absence du jeton.
#
#  Le MODE du fichier (600) ne se lit qu'en root (`/etc/cloudflared` est en 700) :
#  chaque nœud juge le sien, et des droits illisibles chez soi rendent WARN
#  « INCONNUS », jamais OK. Ceux du pair ne se jugent pas ici (#2199) : sa collecte
#  passe par un compte sans root, et ce « non mesurable » se comptait vert à chaque passage.
#
#  SOURCÉ (mode 100644) par `lib-collecte.sh` (`collecte_jeton_tunnel`, repris dans
#  COLLECT) ; `jeton_tunnel_clair_verdicts` est appelé par `lib-conformite.sh`.
#  ⚠️ Il emploie `ok`, `warn`, `fail`, `$SELF`, `$PEER`, `$PEER_OK` et les champs
#  S_*/P_* de son appelant.
#  Autotest : bash scripts/lib/lib-jeton-tunnel-clair.sh --selftest
# =============================================================================

#: Ce qui fait un jeton EN CLAIR dans `systemctl cat cloudflared` (ERE). Écrit une
#: fois : la collecte l'interpole, l'autotest le rejoue. Ni apostrophe (le fragment de
#: collecte est entre guillemets simples), ni `--token-file` (`--token` suivi de `-`).
JETON_CLAIR_MOTIF='--token[= ]+[^ ]|TUNNEL_TOKEN=[^ ]|eyJ[A-Za-z0-9_-]{20,}'

# ── La collecte, exécutée sur CHAQUE nœud (reprise par COLLECT) ──────────────
#  Même contrainte que `lib-collecte.sh` : fragment entre guillemets SIMPLES, donc
#  AUCUNE apostrophe, même en commentaire. Deux champs :
#   - tunnel_jeton : « clair » | « absent » ; VIDE si l'unité est illisible (pas de
#     ligne ExecStart) — cas zéro : sans lui, « illisible » se lirait « absent ».
#   - tunnel_jeton_mode : droits du fichier de `--token-file` (ex. 600), « ? » si
#     le fichier ne se lit pas (hors root), VIDE sans `--token-file`.
collecte_jeton_tunnel() {
    printf '%s' '
_tu=$(systemctl cat cloudflared 2>/dev/null)
if printf "%s\n" "$_tu" | grep -q "^ExecStart="; then
if printf "%s\n" "$_tu" | grep -Eq -- "'"$JETON_CLAIR_MOTIF"'"; then echo "tunnel_jeton=clair"; else echo "tunnel_jeton=absent"; fi
_tf=$(printf "%s\n" "$_tu" | sed -n "s/^ExecStart=.*--token-file[= ]\([^ ]*\).*/\1/p" | head -n 1)
if [ -n "$_tf" ]; then echo "tunnel_jeton_mode=$(stat -c %a "$_tf" 2>/dev/null || echo "?")"; else echo "tunnel_jeton_mode="; fi
else
echo "tunnel_jeton="
echo "tunnel_jeton_mode="
fi
'
}

# ── Décision PURE (aucun effet de bord) ──────────────────────────────────────
#  $1 tunnel_jeton · $2 tunnel_jeton_mode · $3 ici|pair
#    → CLAIR | MODE:<droits> | OK | MODE_INCONNU | HORS_UNITE | INCONNU
#  Les DROITS ne se jugent que chez soi (#2199) : la collecte du pair passe par le
#  compte sans root, qui ne lit pas `/etc/cloudflared` — elle rendait « ? » à chaque
#  passage, et « non mesurable » se lisait OK. Chaque nœud juge les siens en root ;
#  chez le pair, seul le jeton en clair (lisible sans root) se juge.
#  🔒 `api/tests/test_controles_mesures_par_soi.py` refuse `P_tunnel_jeton_mode`.
verdict_tunnel_jeton() {
    case "${1:-}" in
        clair)  echo "CLAIR" ;;
        absent)
            if [ "${3:-ici}" = pair ]; then echo "HORS_UNITE"; return; fi
            case "${2:-}" in
                ""|"?") echo "MODE_INCONNU" ;;
                600|400) echo "OK" ;;
                *)      echo "MODE:$2" ;;
            esac ;;
        *)      echo "INCONNU" ;;
    esac
}

# ── C39, par nœud ────────────────────────────────────────────────────────────
jeton_tunnel_clair_verdicts() {
    local n p rj rm cote v
    for n in "$SELF" "$PEER"; do
        if [ "$n" = "$SELF" ]; then p=S cote=ici rm=${S_tunnel_jeton_mode:-}
        else [ "$PEER_OK" -eq 0 ] || continue; p=P cote=pair rm=""; fi
        eval "rj=\${${p}_tunnel_jeton:-}"
        v=$(verdict_tunnel_jeton "$rj" "$rm" "$cote")
        case "$v" in
            OK)           ok   "Jeton du tunnel de $n hors de l'unité : lu dans un fichier de droits $rm" ;;
            HORS_UNITE)   ok   "Jeton du tunnel de $n hors de l'unité (ses droits, $n les mesure lui-même)" ;;
            MODE_INCONNU) warn "Jeton du tunnel de $n hors de l'unité, mais droits du fichier INCONNUS (stat muet sur --token-file) — ni vert ni rouge : check-reliability doit tourner en root" ;;
            MODE:*)       fail "Jeton du tunnel de $n dans un fichier de droits ${v#MODE:} (600 attendu) — lisible par d'autres comptes : sudo chmod 600 sur le fichier de --token-file, puis le faire tourner (#2115)" ;;
            CLAIR)        fail "Jeton du tunnel EN CLAIR dans l'unité cloudflared de $n (--token <valeur> dans ExecStart) — lisible par tout compte local (ps, systemctl cat) : sudo bash /opt/5hostachy/scripts/exploitation/changer-jeton-tunnel.sh --migrer sur $n (le standby d'abord), puis faire tourner le jeton dans Cloudflare (#2115)" ;;
            *)            warn "Jeton du tunnel de $n : unité cloudflared illisible (systemctl cat muet) — ni vert ni rouge" ;;
        esac
    done
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → ${r:-(rien)}" || { echo "FAIL  $1  attendu=${2:-(rien)} obtenu=${r:-(rien)}"; st=1; }; }
    eg() { [ "$3" = "$2" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; }; }
    ICI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    #  Un FAUX jeton, de la forme d'un vrai (base64 d'un JSON a/t/s) : il ne vaut rien,
    #  mais il porte le préfixe eyJ que le motif cherche.
    FAUX=$(printf '{"a":"compte","t":"11111111-2222-3333-4444-555555555555","s":"c2VjcmV0"}' | base64 | tr -d '\n=')

    echo "== la décision =="
    t "jeton en clair → CLAIR"                                   CLAIR        verdict_tunnel_jeton clair "" ici
    t "fichier, droits 600 → OK"                                 OK           verdict_tunnel_jeton absent 600 ici
    t "fichier, droits 400 → OK"                                 OK           verdict_tunnel_jeton absent 400 ici
    t "fichier lisible par tous (644) → MODE"                    MODE:644     verdict_tunnel_jeton absent 644 ici
    #  #2199 : « non mesurable » se lisait OK — la moitié du contrôle n'était pas jugée.
    t "droits illisibles chez soi → MODE_INCONNU, jamais OK"     MODE_INCONNU verdict_tunnel_jeton absent "?" ici
    t "ni fichier ni jeton chez soi (autre forme) → MODE_INCONNU" MODE_INCONNU verdict_tunnel_jeton absent "" ici
    t "unité illisible (champ vide) → INCONNU, jamais OK"        INCONNU      verdict_tunnel_jeton "" "" ici
    #  Chez le pair, seul le jeton se juge : ses droits, il les mesure lui-même.
    t "pair : jeton hors de l'unité → HORS_UNITE"                HORS_UNITE   verdict_tunnel_jeton absent "" pair
    t "pair : des droits fournis ne se jugent pas ici"           HORS_UNITE   verdict_tunnel_jeton absent 644 pair
    t "pair : jeton en clair → CLAIR"                            CLAIR        verdict_tunnel_jeton clair "" pair
    t "pair : unité illisible → INCONNU"                         INCONNU      verdict_tunnel_jeton "" "" pair

    echo "== la collecte : le VRAI fragment, sur des unités simulées =="
    #  systemctl simulé : rend l'unité de $UNITE_FAUSSE (ou échoue si UNITE_KO=oui) ; stat simulé.
    fx() { bash -c "systemctl() { [ \"\${UNITE_KO:-non}\" = oui ] && return 1; printf '%s\n' \"\$UNITE_FAUSSE\"; }; stat() { [ \"\${MODE_FAUX:-}\" ] && echo \"\$MODE_FAUX\" || return 1; }; export UNITE_FAUSSE UNITE_KO MODE_FAUX; $(collecte_jeton_tunnel)" | sed -n "s/^$1=//p"; }
    export UNITE_FAUSSE UNITE_KO MODE_FAUX
    UNITE_KO=non
    HEAD="[Service]
Type=notify"
    UNITE_FAUSSE="$HEAD
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run --token $FAUX"
    t "collecte : l'unité du 22/10/2026 (--token <valeur>) → clair"            clair  fx tunnel_jeton
    UNITE_FAUSSE="$HEAD
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run --token=$FAUX"
    t "collecte : --token=<valeur> → clair"                                    clair  fx tunnel_jeton
    UNITE_FAUSSE="$HEAD
Environment=TUNNEL_TOKEN=$FAUX
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run"
    t "collecte : jeton en variable d'environnement de l'unité → clair"        clair  fx tunnel_jeton
    UNITE_FAUSSE="$HEAD
ExecStart=/usr/bin/cloudflared tunnel run
# copie : $FAUX"
    t "collecte : un eyJ… traînant dans l'unité (commentaire) → clair"         clair  fx tunnel_jeton
    #  LE TÉMOIN : la forme saine ne déclenche pas (le motif ne mord pas --token-file).
    UNITE_FAUSSE="$HEAD
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run --token-file /etc/cloudflared/jeton"
    MODE_FAUX=600
    t "collecte : --token-file → absent (témoin)"                              absent fx tunnel_jeton
    t "collecte : --token-file → droits du fichier relevés"                    600    fx tunnel_jeton_mode
    MODE_FAUX=""
    t "collecte : fichier illisible (hors root) → « ? », pas un chiffre inventé" "?"  fx tunnel_jeton_mode
    #  LE CAS ZÉRO : l'unité illisible ne se lit jamais « absent ».
    UNITE_KO=oui
    t "collecte : systemctl muet → champ VIDE (cas zéro)"                      ""     fx tunnel_jeton
    UNITE_KO=non UNITE_FAUSSE="[Unit]
Description=x"
    t "collecte : unité sans ExecStart → champ VIDE"                           ""     fx tunnel_jeton
    t "le fragment ne contient aucune apostrophe (il vit entre guillemets simples)" 0 \
        bash -c "source '$ICI/lib-jeton-tunnel-clair.sh'; collecte_jeton_tunnel | grep -c \"'\" || true"

    echo "== les constats =="
    ok()   { echo "OK $*"; }
    warn() { echo "WARN $*"; }
    fail() { echo "FAIL $*"; }
    SELF=rpi1 PEER=rpi2 PEER_OK=0
    compte() { grep -c "$1" <<< "$sortie"; }
    S_tunnel_jeton=absent S_tunnel_jeton_mode=600 P_tunnel_jeton=absent
    sortie=$(jeton_tunnel_clair_verdicts)
    eg "les deux nœuds migrés → deux OK, ni FAIL ni WARN" "2|0" \
        "$(compte '^OK Jeton du tunnel de rpi[12] ')|$(compte '^\(FAIL\|WARN\)')"
    eg "… et le OK du pair ne prétend rien de ses droits" 0 "$(compte '^OK Jeton du tunnel de rpi2 .*\(fichier de droits\|non mesurables\)')"
    #  #2199 : ce nœud ne lit pas les droits de son propre fichier → WARN, jamais OK.
    S_tunnel_jeton_mode="?"
    sortie=$(jeton_tunnel_clair_verdicts)
    eg "droits illisibles chez soi → WARN INCONNUS, aucun OK pour rpi1" "1|0" \
        "$(compte '^WARN Jeton du tunnel de rpi1 .*droits du fichier INCONNUS')|$(compte '^OK Jeton du tunnel de rpi1')"
    S_tunnel_jeton_mode=600
    #  LA FAUTE INJECTÉE : rpi2 comme le 22/10/2026.
    P_tunnel_jeton=clair
    sortie=$(jeton_tunnel_clair_verdicts)
    eg "rpi2 en clair → un FAIL qui nomme rpi2, la correction et #2115" 1 \
        "$(compte '^FAIL Jeton du tunnel EN CLAIR dans l.unité cloudflared de rpi2 .*changer-jeton-tunnel.sh --migrer sur rpi2.*#2115')"
    eg "… et rpi1 reste vert" 1 "$(compte '^OK Jeton du tunnel de rpi1 ')"
    eg "… et le constat ne cite JAMAIS une valeur de jeton" 0 "$(grep -c 'eyJ' <<< "$sortie")"
    S_tunnel_jeton=absent S_tunnel_jeton_mode=644 P_tunnel_jeton=""
    sortie=$(jeton_tunnel_clair_verdicts)
    eg "fichier en 644 → FAIL" 1 "$(compte '^FAIL Jeton du tunnel de rpi1 dans un fichier de droits 644')"
    eg "unité du pair illisible → WARN, aucun OK pour rpi2" "1|0" \
        "$(compte '^WARN Jeton du tunnel de rpi2 ')|$(compte '^OK Jeton du tunnel de rpi2')"
    PEER_OK=1
    sortie=$(jeton_tunnel_clair_verdicts)
    eg "pair injoignable → rien dit sur lui (c'est « Peer injoignable »)" 0 "$(compte 'rpi2')"
    unset -f ok warn fail

    [ "$st" -eq 0 ] && echo "lib-jeton-tunnel-clair : tous les cas passent."
    exit "$st"
fi
