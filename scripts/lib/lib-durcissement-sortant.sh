#!/bin/bash
# =============================================================================
#  lib-durcissement-sortant.sh — La sortie réseau d'un nœud en liste blanche :
#  ce qui se pose, et le jugement de ce qui est SERVI (#2367)
#
#  Module SOURCÉ par `lib-durcissement.sh`, qui déclare la liste
#  (DURCISSEMENT_UFW_SORTANT), jamais exécuté : pas de bit x. Son self-test vit
#  dans `lib-durcissement-sortant.selftest.sh`, sourcé par `durcissement_selftest`
#  (`durcir-noeud.sh --selftest`, job CI `test-scripts`).
#
#  ── POURQUOI ─────────────────────────────────────────────────────────────────
#
#  ufw refusait l'entrant et laissait tout sortir. Un reverse shell, une
#  exfiltration, le téléchargement d'un outil ont tous besoin de SORTIR : fermer
#  la sortie rend un nœud presque inutile à qui y entre, même root. Couper la
#  sortie peut aussi casser la bascule, auto-deploy, les alertes et le tunnel —
#  d'où les trois modes, et le constat d'abord.
#
#  ── TROIS MODES, lus sur la configuration SERVIE ─────────────────────────────
#
#    ouvert   `allow (outgoing)`, rien n'est journalisé — l'état d'avant #2367 ;
#    constat  idem, mais ce qui sortirait HORS liste est journalisé, sans être
#             refusé : la règle `allow out log to any` en DERNIER (hôte), et un
#             LOG suivi d'un RETURN au bout de DOCKER-USER (conteneurs) ;
#    refus    `reject (outgoing)`, et un LOG suivi d'un REJECT au bout de
#             DOCKER-USER. REJECT plutôt que DROP : un programme refusé échoue
#             tout de suite, au lieu d'attendre son délai en silence.
#
#  Le journal du noyau garde donc la trace dans les deux derniers modes —
#  `[UFW ALLOW]` (constat) ou `[UFW BLOCK]` (refus) à IN VIDE pour l'hôte,
#  `[SORTANT CONTENEUR]` pour les conteneurs — et S5 en fait chaque nuit
#  l'inventaire (`durcissement_sortant_resume_journal`). Une « nuit verte » est
#  une nuit de constat sans rien hors liste ; le refus en exige
#  DURCISSEMENT_SORTANT_NUITS_VERTES de suite, sur le nœud lui-même, et ne se
#  pose que sur le standby (`durcissement_sortant_peut_refuser`).
#
#  ── LES CONTENEURS ───────────────────────────────────────────────────────────
#
#  Ils ne sortent pas par OUTPUT : leur trafic traverse FORWARD, où Docker
#  l'accepte AVANT les chaînes d'ufw — une règle `ufw` ne les touche pas. La seule
#  chaîne que Docker passe avant les siennes est DOCKER-USER (`-A FORWARD -j
#  DOCKER-USER` en tête, relevé sur rpi2 le 01/11/2026), et il ne la réécrit
#  jamais. Elle se pose par un bloc d'`/etc/ufw/after.rules` : ufw la reconstruit
#  à chaque démarrage (avant Docker) et à chaque rechargement. Ce qui va VERS un
#  pont Docker (`-o br-+`, `-o docker0` : l'entrant publié, un conteneur vers un
#  autre) n'est pas une sortie et passe. IPv6 : les réseaux Docker des nœuds n'en
#  ont pas, les conteneurs ne sortent qu'en IPv4 — l'hôte, lui, est filtré dans
#  les deux (ufw, IPV6=yes).
#
#  Fonctions PURES (un texte reçu, un verdict rendu) sauf les `durcissement_lire_*`
#  (lecture seule, root). Une lecture vide rend INCONNU, jamais CONFORME.
# =============================================================================

# shellcheck source=lib-role.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib-role.sh"

#: La règle d'ufw qui JOURNALISE ce que rien d'autre n'a laissé sortir — le
#: constat. Forme canonique de `ufw show added` (banc ufw 0.36.2 du 01/11/2026).
DURCISSEMENT_UFW_SORTANT_CONSTAT="allow out log to any"
#: Le commentaire porté par les règles posées : sans apostrophe, ufw l'écrit
#: entre guillemets simples.
DURCISSEMENT_UFW_SORTANT_COMMENTAIRE="sortie 2367"
#: Le préfixe des conteneurs dans le journal du noyau.
DURCISSEMENT_SORTANT_PREFIXE="[SORTANT CONTENEUR] "
#: Le fichier d'ufw qui porte DOCKER-USER, et les bornes du bloc qu'on y pose.
#: 🔴 Tout le bloc en ASCII : ufw réécrit ses fichiers en ASCII et PLANTE sur le
#: premier caractère qui ne l'est pas (`UnicodeEncodeError`, banc du 01/11/2026 :
#: un tiret cadratin dans la borne cassait `ufw default`). Le self-test l'exige.
DURCISSEMENT_UFW_APRES=/etc/ufw/after.rules
DURCISSEMENT_SORTANT_DEBUT="# BEGIN hostachy-sortant - pose par durcir-noeud.sh (#2367), ne pas editer a la main"
DURCISSEMENT_SORTANT_FIN="# END hostachy-sortant"
#: Les nuits de constat vertes, de suite, avant le refus (sur le nœud lui-même :
#: les rôles alternent chaque nuit, trois nuits voient les deux rôles).
DURCISSEMENT_SORTANT_NUITS_VERTES=3
#: La phrase de S5 qui fait une nuit verte — écrite ici, lue par le compte.
DURCISSEMENT_SORTANT_PHRASE_VERTE="aucune sortie hors liste en 24 h"
#: Le journal de l'audit nocturne, où se comptent les nuits vertes.
DURCISSEMENT_SORTANT_JOURNAL_AUDIT=/var/log/hostachy-audit-securite.log

# ── La liste ─────────────────────────────────────────────────────────────────
#  Les règles canoniques, une par ligne. $1 = `hote` (toutes : l'hôte porte aussi
#  ce qu'emploient ses conteneurs, la construction de secours en est un) ou
#  `conteneurs` (la portée `tous` seule).
durcissement_sortant_regles() {
  local portee=${1:-hote} host role ip
  printf '%s\n' "$DURCISSEMENT_UFW_SORTANT" \
    | awk -F'|' -v p="$portee" '$2 != "" && (p == "hote" || $1 == "tous") { print $2 }'
  while IFS=: read -r host role ip; do
    [ -n "$ip" ] && printf 'allow out to %s\n' "$ip"
  done <<< "$ROLE_TABLE"
}

#  Une règle canonique → ses lignes `iptables -S` dans DOCKER-USER (RETURN : rendue
#  à Docker). Grammaire : `allow out PORT[/PROTO]` · `allow out to ADRESSE[/N]` ·
#  `allow out to ADRESSE[/N] port PORT proto PROTO`. Une autre forme rend une
#  ligne `?` : le self-test exige que chaque règle déclarée se traduise.
durcissement_sortant_iptables_de() {
  local -a m
  read -r -a m <<< "${1:-}"
  local c="-A DOCKER-USER" a p
  if [ "${#m[@]}" -eq 3 ] && [ "${m[0]} ${m[1]}" = "allow out" ] && [[ ${m[2]} =~ ^([0-9]+)(/(tcp|udp))?$ ]]; then
    for p in ${BASH_REMATCH[3]:-tcp udp}; do
      echo "$c -p $p -m $p --dport ${BASH_REMATCH[1]} -j RETURN"
    done
  elif [ "${m[0]:-} ${m[1]:-} ${m[2]:-}" = "allow out to" ] && [ -n "${m[3]:-}" ]; then
    a=${m[3]}; [[ $a == */* ]] || a="$a/32"
    if [ "${#m[@]}" -eq 4 ]; then
      echo "$c -d $a -j RETURN"
    elif [ "${#m[@]}" -eq 8 ] && [ "${m[4]} ${m[6]}" = "port proto" ]; then
      echo "$c -d $a -p ${m[7]} -m ${m[7]} --dport ${m[5]} -j RETURN"
    else
      echo "? $1"
    fi
  else
    echo "? $1"
  fi
}

#  Ce que `iptables -S DOCKER-USER` doit servir, `-N` exclu. $1 = constat | refus
durcissement_sortant_docker_user() {
  local r
  printf '%s\n' "-A DOCKER-USER -o br-+ -j RETURN" "-A DOCKER-USER -o docker0 -j RETURN" \
    "-A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN"
  while IFS= read -r r; do
    [ -n "$r" ] && durcissement_sortant_iptables_de "$r"
  done < <(durcissement_sortant_regles conteneurs)
  printf '%s\n' "-A DOCKER-USER -m conntrack --ctstate NEW -m limit --limit 3/min --limit-burst 10 -j LOG --log-prefix \"$DURCISSEMENT_SORTANT_PREFIXE\""
  if [ "${1:-}" = refus ]; then
    echo "-A DOCKER-USER -j REJECT --reject-with icmp-port-unreachable"
  else
    echo "-A DOCKER-USER -j RETURN"
  fi
}

#  Le bloc d'after.rules qui pose DOCKER-USER. $1 = constat | refus
durcissement_sortant_bloc() {
  printf '%s\n' "$DURCISSEMENT_SORTANT_DEBUT" "*filter" ":DOCKER-USER - [0:0]"
  durcissement_sortant_docker_user "${1:-}"
  printf '%s\n' "COMMIT" "$DURCISSEMENT_SORTANT_FIN"
}

#  after.rules réécrit : l'ancien bloc retiré, le nouveau ($2, vide : aucun) en fin.
#  $1 = le contenu actuel du fichier
durcissement_sortant_apres_regles() {
  #  Les lignes vides laissées en fin par l'ancien bloc ne s'accumulent pas.
  printf '%s\n' "${1:-}" | awk -v d="$DURCISSEMENT_SORTANT_DEBUT" -v f="$DURCISSEMENT_SORTANT_FIN" '
    $0 == d { dedans = 1; next }
    dedans { if ($0 == f) dedans = 0; next }
    $0 == "" { vides++; next }
    { while (vides > 0) { print ""; vides-- } print }'
  [ -z "${2:-}" ] || printf '\n%s\n' "$2"
}

# ── Le mode et le jugement de l'hôte ─────────────────────────────────────────
#  $1 = `ufw status verbose` · $2 = `ufw show added` → refus | constat | ouvert
durcissement_sortant_mode() {
  if grep -qE '^Default: .*(deny|reject) \(outgoing\)' <<< "${1:-}"; then echo refus
  elif grep -qxF -- "$DURCISSEMENT_UFW_SORTANT_CONSTAT" <<< "$(durcissement_ufw_normaliser "${2:-}")"; then echo constat
  else echo ouvert; fi
}

#  $1 = `ufw show added` → les règles déclarées absentes, une par ligne
durcissement_sortant_manquantes() {
  local posees r
  posees=$(durcissement_ufw_normaliser "${1:-}")
  while IFS= read -r r; do
    [ -n "$r" ] && ! grep -qxF -- "$r" <<< "$posees" && printf '%s\n' "$r"
  done < <(durcissement_sortant_regles hote)
  return 0
}

#  Une règle qui laisse SORTIR sans être déclarée — `allow out to any`, un port
#  ajouté à la main. Les `deny out` restreignent : ils ne se jugent pas ici.
#  $1 = `ufw show added` → les règles fautives, une par ligne
durcissement_sortant_hors_liste() {
  local declarees r
  declarees=$(durcissement_sortant_regles hote; echo "$DURCISSEMENT_UFW_SORTANT_CONSTAT")
  while IFS= read -r r; do
    [ -n "$r" ] && ! grep -qxF -- "$r" <<< "$declarees" && printf '%s\n' "$r"
  done < <(durcissement_ufw_normaliser "${1:-}" | grep -E '^(allow|limit) out( |$)')
  return 0
}

# ── Le jugement des conteneurs ───────────────────────────────────────────────
#  $1 = `iptables -S DOCKER-USER` · $2 = `iptables -S FORWARD` · $3 = constat | refus
#  → OUI · NON:<raison> · INCONNU:<raison>
durcissement_sortant_conteneurs() {
  local du=${1:-} fw=${2:-} attendu servies n premiere reste
  [ -n "$du" ] && [ -n "$fw" ] || { echo "INCONNU:iptables illisible (root requis)"; return 0; }
  premiere=$(awk '/^-A FORWARD /{ print; exit }' <<< "$fw")
  [ "$premiere" = "-A FORWARD -j DOCKER-USER" ] \
    || { echo "NON:FORWARD ne passe pas d'abord par DOCKER-USER (${premiere:-aucune règle})"; return 0; }
  attendu=$(durcissement_sortant_docker_user "${3:-}")
  servies=$(grep -E '^-A DOCKER-USER ' <<< "$du" || true)
  n=$(grep -c . <<< "$attendu")
  #  La tête doit être la nôtre, à l'identique ; Docker peut avoir laissé un
  #  `-j RETURN` derrière — il ne laisse rien passer de plus.
  [ "$(head -n "$n" <<< "$servies")" = "$attendu" ] \
    || { echo "NON:DOCKER-USER ne sert pas la liste (bloc d'after.rules absent ou modifié)"; return 0; }
  reste=$(tail -n +"$((n + 1))" <<< "$servies" | grep -vxF -- "-A DOCKER-USER -j RETURN" || true)
  [ -z "$reste" ] || { echo "NON:règle(s) en trop dans DOCKER-USER : $(paste -sd ';' - <<< "$reste")"; return 0; }
  echo OUI
}

# ── Le verdict de la sortie ──────────────────────────────────────────────────
#  $1 = `ufw status verbose` · $2 = `ufw show added` · $3 = `iptables -S
#  DOCKER-USER` · $4 = `iptables -S FORWARD`
#  → CONFORME (refus servi) · CONSTAT:<notes, vide si complet> · OUVERT:<pourquoi>
#    · ECART:<…> · INCONNU:<…>
durcissement_sortant_verdict() {
  local etat=${1:-} ajoutees=${2:-} du=${3:-} fw=${4:-} mode h m c notes=""
  [ -n "$etat" ] || { echo "INCONNU:ufw illisible (absent, ou root requis)"; return 0; }
  grep -q '^Status: active' <<< "$etat" || { echo "OUVERT:ufw inactif, rien n'est filtré"; return 0; }
  h=$(durcissement_sortant_hors_liste "$ajoutees" | paste -sd ',' -)
  [ -z "$h" ] || { echo "ECART:règle(s) de sortie non déclarée(s)=[$h]"; return 0; }
  mode=$(durcissement_sortant_mode "$etat" "$ajoutees")
  m=$(durcissement_sortant_manquantes "$ajoutees" | paste -sd ',' -)
  case "$mode" in
    ouvert)
      #  Un retour arrière qui n'a rouvert que l'hôte laisse les conteneurs refusés.
      if grep -qE -- '-j (REJECT|DROP)' <<< "$du"; then
        echo "ECART:l'hôte laisse sortir mais DOCKER-USER refuse encore (retour arrière inachevé)"
      else
        echo "OUVERT:sortie non filtrée (#2367 : poser le constat, le standby d'abord)"
      fi ;;
    constat)
      c=$(durcissement_sortant_conteneurs "$du" "$fw" constat)
      [ -z "$m" ] || notes="$notes manquantes=[$m];"
      [ "$c" = OUI ] || notes="$notes conteneurs-non-journalisés=${c#*:};"
      echo "CONSTAT:${notes# }" ;;
    refus)
      if grep -qxF -- "$DURCISSEMENT_UFW_SORTANT_CONSTAT" <<< "$(durcissement_ufw_normaliser "$ajoutees")"; then
        echo "ECART:refus servi, mais '$DURCISSEMENT_UFW_SORTANT_CONSTAT' laisse tout sortir"; return 0
      fi
      c=$(durcissement_sortant_conteneurs "$du" "$fw" refus)
      case "$c" in INCONNU:*) echo "$c"; return 0 ;; esac
      [ -z "$m" ] || notes="$notes manquantes=[$m] (ce qui en dépend est refusé);"
      [ "$c" = OUI ] || notes="$notes conteneurs-non-filtrés=${c#*:};"
      if [ -n "$notes" ]; then echo "ECART:${notes# }"; else echo CONFORME; fi ;;
  esac
}

# ── Le journal : ce qui est sorti hors liste ─────────────────────────────────
#  $1 = le journal du noyau (`journalctl -k -o cat`) · $2 = « IP nom » des conteneurs
#  → une ligne par destination, la plus fréquente d'abord : `N DST PORT/PROTO QUI`.
#  Retenues : `[UFW ALLOW]`/`[UFW BLOCK]` à IN VIDE (émis par le nœud ; l'entrant
#  refusé porte IN=eth0) et `[SORTANT CONTENEUR]`. Le journal est borné par ufw
#  (3/min, rafale de 10) : un compte est un plancher, la liste des destinations
#  est ce qui compte.
durcissement_sortant_resume_journal() {
  awk 'FNR == NR { if ($1 != "") nom[$1] = $2; next }
       /\[UFW (ALLOW|BLOCK)\] IN= OUT=/ || /\[SORTANT CONTENEUR\] / {
         dst = ""; src = ""; dpt = ""; proto = ""; type = ""
         for (i = 1; i <= NF; i++) {
           if ($i ~ /^DST=/) dst = substr($i, 5); else if ($i ~ /^SRC=/) src = substr($i, 5)
           else if ($i ~ /^DPT=/) dpt = substr($i, 5); else if ($i ~ /^PROTO=/) proto = tolower(substr($i, 7))
           else if ($i ~ /^TYPE=/) type = substr($i, 6)
         }
         if ($0 ~ /\[SORTANT CONTENEUR\]/) qui = (src in nom) ? nom[src] : "conteneur:" src; else qui = "hôte"
         port = (dpt != "") ? dpt "/" proto : proto (type != "" ? "-type" type : "")
         n[dst " " port " " qui]++
       }
       END { for (k in n) print n[k], k }' \
    <(printf '%s\n' "${2:-}") <(printf '%s\n' "${1:-}") | sort -k1,1nr -k2
}

#  Les nuits vertes de suite, en remontant depuis la dernière, dans le journal de
#  l'audit (un passage commence par sa ligne « ═══ audit-securite (… »). Un passage
#  sans ligne « S5 Sortie » ne compte ni pour ni contre : c'est celui qui s'écrit
#  à l'instant (l'audit écrit dans ce journal), ou un passage interrompu.
#  $1 = le journal → un nombre
durcissement_sortant_nuits_vertes() {
  awk -v phrase="$DURCISSEMENT_SORTANT_PHRASE_VERTE" '
    index($0, "═") == 1 && index($0, " audit-securite (") { k++; vu[k] = 0; vert[k] = 0; next }
    k && /S5 Sortie / { vu[k] = 1; if (index($0, phrase) && /^\[ OK \]/) vert[k] = 1 }
    END { c = 0; for (i = k; i >= 1; i--) { if (!vu[i]) continue; if (!vert[i]) break; c++ } print c }' <<< "${1:-}"
}

#  Passer en refus. $1 = verdict servi · $2 = résumé du journal (24 h) · $3 = nuits
#  vertes · $4 = le nœud actif (.active) · $5 = ce nœud → OUI ou REFUS:<pourquoi>
durcissement_sortant_peut_refuser() {
  local verdict=${1:-} resume=${2:-} nuits=${3:-0} actif=${4:-} soi=${5:-}
  [ "$verdict" = CONFORME ] && { echo OUI; return 0; }   # déjà en refus : réparer
  case "$verdict" in
    CONSTAT:) ;;
    CONSTAT:*) echo "REFUS:constat incomplet (${verdict#CONSTAT:})"; return 0 ;;
    *)         echo "REFUS:le constat n'est pas servi (${verdict%%:*}) — poser d'abord --sortant constat"; return 0 ;;
  esac
  [ -z "$resume" ] || { echo "REFUS:$(grep -c . <<< "$resume") destination(s) hors liste en 24 h — les déclarer ou les comprendre d'abord"; return 0; }
  [[ $nuits =~ ^[0-9]+$ ]] && [ "$nuits" -ge "$DURCISSEMENT_SORTANT_NUITS_VERTES" ] \
    || { echo "REFUS:${nuits:-?} nuit(s) de constat verte(s) de suite, $DURCISSEMENT_SORTANT_NUITS_VERTES exigées"; return 0; }
  [ -n "$actif" ] && [ -n "$soi" ] \
    || { echo "REFUS:rôle illisible (.active ou nom d'hôte) — on ne ferme pas à l'aveugle"; return 0; }
  [ "$actif" != "$soi" ] || { echo "REFUS:ce nœud est l'actif — le refus se pose sur le standby d'abord"; return 0; }
  echo OUI
}

# ── Les lectures de l'état EFFECTIF (lecture seule, root) ────────────────────
durcissement_lire_docker_user() { command -v iptables >/dev/null && iptables -S DOCKER-USER 2>/dev/null; }
durcissement_lire_forward()     { command -v iptables >/dev/null && iptables -S FORWARD 2>/dev/null; }
durcissement_lire_sortant_journal() { journalctl -k --since -24h -o cat -q --no-pager 2>/dev/null; }
#  « IP nom » de chaque conteneur en marche, pour nommer qui sort.
durcissement_lire_ip_conteneurs() {
  command -v docker >/dev/null || return 0
  docker ps -q 2>/dev/null | xargs -r docker inspect \
    -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{$.Name}}{{"\n"}}{{end}}' 2>/dev/null \
    | sed 's#/##' | grep -v '^ '
}

durcissement_etat_sortant() {
  durcissement_sortant_verdict "$(durcissement_lire_ufw_etat)" "$(durcissement_lire_ufw_ajoutees)" \
    "$(durcissement_lire_docker_user)" "$(durcissement_lire_forward)"
}
durcissement_sortant_resume() {
  durcissement_sortant_resume_journal "$(durcissement_lire_sortant_journal)" "$(durcissement_lire_ip_conteneurs)"
}
