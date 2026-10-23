#!/bin/bash
# =============================================================================
#  lib-apt.sh — ce que apt dit des correctifs d'un nœud (C30)
#
#  Trois questions, dans l'ordre où elles se masquent l'une l'autre : la
#  configuration apt est-elle lisible (#1377) ? les listes sont-elles fraîches ?
#  un correctif de sécurité attend-il plus que le régime d'un passage
#  d'`unattended-upgrades` (#1441) ?
#
#  Extrait de `lib-mises-a-jour.sh` le 28/09/2026 : #1441 l'aurait porté au-delà
#  du plafond de 500 lignes. Les MESSAGES de C30 restent là-bas, dans la boucle
#  par nœud que `test_constats_nomment_leur_noeud.py` lit ; ici, la collecte et
#  la décision seulement.
#
#  SOURCÉ (mode 100644) par `lib-mises-a-jour.sh`, qui reprend `COLLECT_APT`
#  dans `COLLECT_MAJ` et appelle `verdict_apt`.
#  Autotest : bash scripts/lib/lib-apt.sh --selftest
# =============================================================================

#: Au-delà, les listes apt sont périmées : `unattended-upgrades` ne voit plus
#: rien, et « aucune mise à jour en attente » ne veut plus rien dire. Le dépôt
#: `*-updates` de Debian est republié presque chaque jour ; sept jours sans
#: listes neuves, c'est une semaine où le nœud n'a rien pu apprendre.
APT_LISTES_MAX_J=${APT_LISTES_MAX_J:-7}

#: Un passage « en cours » depuis plus longtemps que cela n'en est plus un : il
#: est bloqué, et le laisser masquer un correctif non posé reviendrait à
#: éteindre C30. Un passage d'`unattended-upgrades` dure de 20 s à quelques
#: minutes ; deux heures laissent la place à une montée de paquets lourde.
APT_EN_COURS_MAX_S=${APT_EN_COURS_MAX_S:-7200}

# ── La collecte, exécutée sur CHAQUE nœud (reprise par COLLECT_MAJ) ──────────
#  Même contrainte que `lib-collecte.sh` : chaîne entre guillemets SIMPLES, donc
#  AUCUNE apostrophe en dessous, même en commentaire. Tout ce qui s'explique
#  s'explique ici :
#   - apt_erreurs : lignes `E:` de `apt-config dump` — la configuration est-elle
#     seulement lisible ? (#1377). Vide si apt-config manque : INCONNU.
#   - apt_listes_j : âge en jours de la liste la PLUS RÉCENTE. On mesure la
#     chose (les listes), pas son enregistrement (un tampon de tentative, que
#     `apt-daily` pose même quand il échoue) — `standards/04` §14.
#  Nommée à part (`COLLECT_APT_LISTES`) : le contrôle des correctifs d'une
#  installation standard (`deploiement/standard/correctifs-systeme.sh`) l'assemble
#  avec SA liste de paquets en attente.
COLLECT_APT_LISTES='
_t0=$(date +%s)
echo "apt_erreurs=$(command -v apt-config >/dev/null 2>&1 && apt-config dump 2>&1 >/dev/null | grep -c "^E:")"
_t=$(find /var/lib/apt/lists -maxdepth 1 -name "*InRelease" -printf "%T@\n" 2>/dev/null | sort -n | tail -1)
echo "apt_listes_j=$([ -n "$_t" ] && echo $(( ( $(date +%s) - ${_t%.*} ) / 86400 )))"
'

#: Depuis quand chaque correctif de sécurité en attente l'est : « <epoch>
#: <paquet>=<version> » par ligne. Écrit par la collecte LOCALE (root) de chaque
#: nœud, lu aussi par celle du pair (ptressard). Par PAQUET, jamais par
#: ensemble : un nouveau correctif remettrait sinon à zéro l'horloge d'un
#: paquet bloqué, et le masquerait tant qu'il en arrive (#1441).
APT_SECU_VU="${APT_SECU_VU:-/var/lib/hostachy/apt-secu-vu}"
#: Régime : `apt-daily-upgrade.timer` passe chaque jour à 06:00 plus jusqu'à
#: 60 min (RandomizedDelaySec) ; deux passages sont séparés de 25 h au plus. Un
#: correctif publié juste après un passage attend donc jusqu'à 25 h sans aucun
#: défaut. 30 h = ce régime, plus un passage de C30 et un démarrage lent
#: (`standards/04` §18 ; le cas « 24 h 59 » de l'autotest le tient).
APT_SECU_DELAI_S=${APT_SECU_DELAI_S:-108000}

#  La collecte des correctifs de sécurité (paramétrée pour l'autotest).
#  Même contrainte que COLLECT_APT : aucune apostrophe dans la chaîne.
#   - apt_secu : paquets en attente venant d'un dépôt `*-security` ; vide si
#     apt manque (INCONNU) ;
#   - apt_secu_vu_s : depuis combien de secondes le PLUS ANCIEN est en attente ;
#   - apt_passage_s : depuis combien de secondes le dernier passage
#     d'installation (`apt-daily-upgrade`) a DÉMARRÉ — un correctif vu avant ce
#     démarrage a été vu par lui ;
#   - apt_prochain : l'heure du prochain passage, pour le dire.
#  L'ancienneté se relit dans le FICHIER, après son écriture : un relevé qui ne
#  s'écrit pas (disque plein, pair sans droit) rend un âge vide, donc INCONNU —
#  jamais « vu à l'instant » à chaque passage, qui serait un ATTENTE perpétuel.
#
#  $2 (facultatif) : la commande qui liste les paquets en attente, un
#  « <paquet>=<version> » par ligne — par défaut les correctifs `*-security`
#  (C30). Une installation standard y passe ce qu'`unattended-upgrades` posera
#  (`deploiement/standard/correctifs-systeme.sh`). Même contrainte : aucune
#  apostrophe.
APT_LISTE_SECU='apt list --upgradable 2>/dev/null | grep -- "-security" | awk -F"[/ ]" "{ print \$1 \"=\" \$3 }"'
collecte_secu() {
    printf '%s' '
_f='"$1"'
_n=$(date +%s)
if command -v apt >/dev/null 2>&1; then
_l=$('"${2:-$APT_LISTE_SECU}"' | sort)
echo "apt_secu=$(printf "%s" "$_l" | grep -c .)"
_vu() { awk -v p="$1" "\$2 == p && \$1 ~ /^[0-9]+\$/ { print \$1; exit }" "$_f" 2>/dev/null; }
if [ "$(id -u)" = 0 ] && mkdir -p "$(dirname "$_f")"; then
for _p in $_l; do _e=$(_vu "$_p"); echo "${_e:-$_n} $_p"; done > "$_f.tmp" && mv "$_f.tmp" "$_f"
fi
_v=""
for _p in $_l; do
_e=$(_vu "$_p")
[ -n "$_e" ] && { [ -z "$_v" ] || [ "$_e" -lt "$_v" ]; } && _v=$_e
done
echo "apt_secu_vu_s=${_v:+$(( _n - _v ))}"
else
echo "apt_secu="
fi
_d=$(systemctl show --timestamp=unix -p ExecMainStartTimestamp --value apt-daily-upgrade.service 2>/dev/null)
_a=""; case "$_d" in @[0-9]*) _a=$(( _n - ${_d#@} )) ;; esac
echo "apt_passage_s=$_a"
echo "apt_prochain=$(systemctl show -p NextElapseUSecRealtime --value apt-daily-upgrade.timer 2>/dev/null | awk "{ print substr(\$3, 1, 5) }")"
'
}
#  #1610 — un passage d'installation est-il EN COURS ? À la FIN de la collecte :
#  c'est le dernier relevé qui compte, et un passage démarré pendant les
#  précédents (le 01/10/2026 à 06:21, `unattended-upgrades` a démarré UNE seconde
#  après le début de C30) rend les correctifs lus plus haut caducs.
#   - apt_en_cours : « oui » si `apt-daily` ou `apt-daily-upgrade` est en cours
#     d'exécution (un service oneshot est `activating` tant qu'il tourne), OU si
#     le dernier passage a démarré APRÈS le début de cette collecte (`_t0`, posé
#     en tête de COLLECT_APT) ; « non » sinon ; VIDE si systemctl manque — la
#     mesure est alors impossible, et le verdict s'en tient à ce qu'il savait.
#  On ne cherche PAS le processus (`pgrep`) : `unattended-upgrade-shutdown`
#  tourne en permanence sous le même nom court, et le shell qui exécute cette
#  collecte porte le motif dans sa propre ligne de commande — faux positif sûr.
#  Même contrainte que COLLECT_APT : aucune apostrophe dans la chaîne.
collecte_apt_en_cours() {
    printf '%s' '
if command -v systemctl >/dev/null 2>&1; then
_ae=non
for _u in apt-daily.service apt-daily-upgrade.service; do
case "$(systemctl show -p ActiveState --value $_u 2>/dev/null)" in activating|reloading) _ae=oui ;; esac
done
_d=$(systemctl show --timestamp=unix -p ExecMainStartTimestamp --value apt-daily-upgrade.service 2>/dev/null)
case "$_d" in @[0-9]*) [ "${_d#@}" -ge "${_t0:-9999999999}" ] 2>/dev/null && _ae=oui ;; esac
echo "apt_en_cours=$_ae"
else
echo "apt_en_cours="
fi
'
}
COLLECT_APT="$COLLECT_APT_LISTES$(collecte_secu "$APT_SECU_VU")$(collecte_apt_en_cours)"

# ── Décision PURE (aucun effet de bord) ──────────────────────────────────────

#  $1 erreurs de configuration · $2 âge des listes (j) · $3 paquets de sécurité
#  $4 depuis combien de secondes le plus ancien attend · $5 depuis combien de
#  secondes le dernier passage d'installation a démarré · $6 « oui » si un
#  passage est en cours (vide : non mesuré)
#  → OK | ILLISIBLE | PERIMEES | ATTENTE | SECURITE | SANS_PASSAGE | EN_COURS | INCONNU
#  L'ordre compte : une configuration illisible rend les listes périmées, et des
#  listes périmées rendent le compte de sécurité faux (il vaut 0 sur rpi2).
#  Annoncer le symptôme le plus profond, c'est dire quoi réparer.
#  Un correctif en attente n'est pas un défaut : il le devient quand un passage
#  l'a vu sans le poser (SECURITE), ou quand il attend au-delà du régime d'un
#  passage (SANS_PASSAGE). Avant, ATTENTE (#1441 : le 28/09/2026, C30 disait
#  « ne les a pas posés » d'un correctif publié quatre heures après le passage).
#  EN_COURS (#1610) : un passage d'installation tourne — le relevé va changer
#  dans la minute, et SECURITE/SANS_PASSAGE jugeraient un fait déjà périmé. C'est
#  la famille INCONNU (ni vert ni rouge, revérifié au passage suivant), jamais un
#  OK : il ne remplace que les deux verdicts qui alertent. Borné par
#  APT_EN_COURS_MAX_S, pour qu'un passage bloqué ne masque rien.
verdict_apt() {
    local err=$1 age=$2 secu=$3 vu=${4:-} passage=${5:-} encours=${6:-}
    case "$err" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    [ "$err" -gt 0 ] && { echo ILLISIBLE; return; }
    case "$age" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    [ "$age" -gt "$APT_LISTES_MAX_J" ] && { echo PERIMEES; return; }
    case "$secu" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    [ "$secu" -gt 0 ] || { echo OK; return; }
    #  Un début négatif (le passage a démarré après la collecte) ou illisible n'est
    #  pas une durée : il ne borne rien, et ne sert qu'à SECURITE/SANS_PASSAGE.
    case "$passage" in *[!0-9]*) passage='' ;; esac
    if [ "$encours" = oui ] && { [ -z "$passage" ] || [ "$passage" -le "$APT_EN_COURS_MAX_S" ]; }; then
        echo EN_COURS; return
    fi
    case "$vu" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    if [ -n "$passage" ] && [ "$vu" -gt "$passage" ]; then echo SECURITE
    elif [ "$vu" -gt "$APT_SECU_DELAI_S" ]; then echo SANS_PASSAGE
    elif [ -n "$passage" ]; then echo ATTENTE
    else echo INCONNU; fi
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }

    t "nœud sain"                                      OK         verdict_apt 0 1 0
    t "rpi2 le 27/09 : configuration illisible"        ILLISIBLE  verdict_apt 1 162 0
    t "illisible l'emporte sur périmé"                 ILLISIBLE  verdict_apt 2 0 5
    t "listes vieilles de 8 j"                         PERIMEES   verdict_apt 0 8 0
    t "listes à 7 j : encore bon"                      OK         verdict_apt 0 7 0
    t "périmé l'emporte sur « 0 correctif »"           PERIMEES   verdict_apt 0 162 0
    t "apt-config absent → INCONNU, jamais OK"         INCONNU    verdict_apt "" 1 0
    t "âge illisible → INCONNU"                        INCONNU    verdict_apt 0 "" 0
    t "compte de sécurité illisible → INCONNU"         INCONNU    verdict_apt 0 1 ""
    #  #1441 — rpi2 le 28/09 à 17:51 : libheif vu à 12:21, passage à 06:50.
    t "rpi2 le 28/09 : publié après le passage"        ATTENTE    verdict_apt 0 0 3 19800 39660
    t "vu par le passage de ce matin, pas posé"        SECURITE   verdict_apt 0 0 3 36000 7200
    t "vu il y a 31 h, aucun passage depuis"           SANS_PASSAGE verdict_apt 0 0 3 111600 118800
    t "régime : 24 h 59 d'attente reste ATTENTE"       ATTENTE    verdict_apt 0 0 1 89940 90000
    t "passage illisible, attente > délai"             SANS_PASSAGE verdict_apt 0 0 1 111600 ""
    t "passage illisible, attente courte → INCONNU"    INCONNU    verdict_apt 0 0 1 7200 ""
    t "ancienneté illisible → INCONNU, jamais ATTENTE" INCONNU    verdict_apt 0 0 3 "" 7200

    #  #1610 — rpi1 le 01/10 à 06:21 : un digest est parti pour « 3 correctifs vus
    #  par le passage d'hier, pas posés », vingt secondes avant que le passage de
    #  CE matin ne les pose. Un passage EN COURS rend la mesure caduque : EN_COURS
    #  (la famille INCONNU — ni vert ni rouge), revérifié au passage suivant.
    t "#1610 : passage en cours depuis 6 s → EN_COURS, pas SECURITE"  EN_COURS verdict_apt 0 0 3 86400 6 oui
    t "#1610 : sans l'indication, le même relevé reste SECURITE"       SECURITE verdict_apt 0 0 3 86400 6 non
    t "#1610 : en cours, attente > délai → EN_COURS, pas SANS_PASSAGE" EN_COURS verdict_apt 0 0 3 111600 6 oui
    t "#1610 : démarré APRÈS la collecte (passage négatif) → EN_COURS" EN_COURS verdict_apt 0 0 3 86400 -2 oui
    t "#1610 : en cours, début illisible → EN_COURS (INCONNU)"         EN_COURS verdict_apt 0 0 3 86400 "" oui
    t "#1610 : aucun correctif en attente → OK malgré le passage"      OK       verdict_apt 0 0 0 "" 6 oui
    t "#1610 : configuration illisible l'emporte sur le passage"       ILLISIBLE verdict_apt 1 0 3 86400 6 oui
    t "#1610 : listes périmées l'emportent sur le passage"             PERIMEES verdict_apt 0 9 3 86400 6 oui
    #  Un « passage » qui dure plus que sa borne n'est plus un passage : il ne
    #  doit pas masquer indéfiniment un correctif non posé.
    t "#1610 : « en cours » depuis 3 h (bloqué) → verdict habituel"    SECURITE verdict_apt 0 0 3 86400 10800 oui
    t "#1610 : « en cours » à la borne (2 h) → encore EN_COURS"        EN_COURS verdict_apt 0 0 3 86400 7200 oui
    t "#1610 : mesure absente (systemctl manquant) → verdict habituel" SECURITE verdict_apt 0 0 3 86400 6 ""


    #  #1441 — la collecte des correctifs, sur un apt et un systemd simulés aux
    #  formes RÉELLES (sortie de rpi2 le 28/09/2026).
    tmps=$(mktemp -d); vuf="$tmps/sous/apt-secu-vu"; now=$(date +%s)
    heif='libheif1/stable-security 1.23.4-1~deb13u1 arm64 [upgradable from: 1.19.8-1+deb13u1]'
    apt() { printf 'Listing...\n%s\nbluez/stable 5.82-1.1+rpt2 arm64 [upgradable from: 5.82-1.1+rpt1]\n' "$heif"; }
    systemctl() { case "$*" in
        *ExecMainStartTimestamp*) echo "@$(( now - 36000 ))" ;;
        *NextElapseUSecRealtime*) echo "Tue 2026-09-29 06:39:48 CEST" ;; esac; }
    id() { echo 0; }
    champ() { eval "$(collecte_secu "$vuf")" | sed -n "s/^$1=//p"; }
    t "collecte : seuls les paquets -security comptent" 1 champ apt_secu
    t "collecte : premier relevé → vu à l'instant" oui eval '[ "$(champ apt_secu_vu_s)" -le 5 ] && echo oui'
    t "collecte : relevé écrit, répertoire créé" "libheif1=1.23.4-1~deb13u1" eval 'cut -d" " -f2 "$vuf"'
    t "collecte : début du dernier passage" oui eval 'a=$(champ apt_passage_s); [ "$a" -ge 36000 ] && [ "$a" -le 36005 ] && echo oui'
    t "collecte : heure du prochain passage" 06:39 champ apt_prochain
    #  Un paquet bloqué garde SON ancienneté quand un autre correctif arrive.
    echo "$(( now - 50000 )) libheif1=1.23.4-1~deb13u1" > "$vuf"
    apt() { printf '%s\nlibfoo/stable-security 2.0-1 arm64 [upgradable from: 1.0-1]\n' "$heif"; }
    t "collecte : un nouveau correctif ne remet pas l'horloge à zéro" oui \
      eval '[ "$(champ apt_secu_vu_s)" -ge 50000 ] && echo oui'
    t "collecte : les deux paquets sont relevés" 2 eval 'grep -c . "$vuf"'
    #  Une nouvelle VERSION du même paquet est un nouveau correctif.
    echo "$(( now - 50000 )) libheif1=1.19.9-1" > "$vuf"
    apt() { printf '%s\n' "$heif"; }
    t "collecte : nouvelle version → nouvelle horloge" oui eval '[ "$(champ apt_secu_vu_s)" -le 5 ] && echo oui'
    #  Le pair lit sans écrire : un paquet absent du relevé ne compte pas.
    rm -f "$vuf"; id() { echo 1000; }
    t "collecte : hors root, rien d'écrit ni d'inventé" "" champ apt_secu_vu_s
    t "collecte : hors root, aucun fichier créé" non eval '[ -e "$vuf" ] && echo oui || echo non'
    #  Une autre liste (celle d'une installation standard) : même relevé, même horloge.
    rm -f "$vuf"; id() { echo 0; }
    autre="$tmps/attente"; printf 'docker-ce=5:29.9.2-1
cloudflared=2026.10.3
' > "$autre"
    t "collecte : liste fournie → ses paquets comptent" 2 eval 'eval "$(collecte_secu "$vuf" "cat $autre")" | sed -n "s/^apt_secu=//p"'
    t "collecte : liste fournie → relevée par paquet" "cloudflared=2026.10.3" eval 'cut -d" " -f2 "$vuf" | head -1'
    : > "$autre"
    t "collecte : liste fournie vide → 0" 0 eval 'eval "$(collecte_secu "$vuf" "cat $autre")" | sed -n "s/^apt_secu=//p"'
    unset -f apt systemctl id champ; rm -rf "$tmps"

    #  #1610 — la collecte du passage en cours, exécutée sur un systemd simulé aux
    #  formes RÉELLES (`ActiveState` d'un service oneshot, horodatage `@epoch`).
    now=$(date +%s); etat="inactive"; debut="@$(( now - 36000 ))"
    systemctl() { case "$*" in
        *ActiveState*) echo "$etat" ;;
        *ExecMainStartTimestamp*) echo "$debut" ;; esac; }
    enc() { _t0=$now eval "$(collecte_apt_en_cours)" | sed -n 's/^apt_en_cours=//p'; }
    t "en cours : service inactif, dernier passage d'il y a 10 h" non enc
    etat=activating
    t "en cours : le service tourne (activating)" oui enc
    etat=inactive; debut="@$(( now + 2 ))"
    t "en cours : passage démarré APRÈS le début de la collecte" oui enc
    debut="@$now"
    t "en cours : démarré dans la même seconde → prudence (oui)" oui enc
    debut=""
    t "en cours : service jamais lancé (horodatage vide) → non" non enc
    debut="@$(( now - 5 ))"
    t "en cours : fini il y a 5 s, rien ne tourne → non (fait déjà posé)" non enc
    unset -f systemctl
    #  Sans systemctl, rien n'est mesurable : valeur VIDE, jamais « non ». PATH vidé
    #  pour que la fonction ci-dessus et le binaire de l'hôte n'existent pas.
    t "en cours : systemctl absent → vide, jamais « non »" "apt_en_cours="       eval 'PATH=/nonexistent "$BASH" -c "$(collecte_apt_en_cours)"'
    t "en cours : la collecte assemblée porte les deux issues (mesurée, vide)" 2 eval 'echo "$COLLECT_APT" | grep -c "^echo \"apt_en_cours="'
    t "en cours : _t0 posé AVANT tout relevé" _t0 eval 'echo "$COLLECT_APT" | grep -m1 -o "^_t0"'
    unset -f enc

    #  La chaîne assemblée est du shell valide : c'est elle que les nœuds exécutent.
    t "COLLECT_APT assemblé est du shell valide" oui eval 'bash -n <<<"$COLLECT_APT" && echo oui'

    [ "$st" -eq 0 ] && echo "lib-apt : tous les cas passent."
    exit "$st"
fi
