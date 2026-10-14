#!/bin/bash
# =============================================================================
#  lib-ssh-mot-de-passe.sh — C38 : chaque nœud REFUSE-t-il le mot de passe SSH ?
#
#  Né de #1941 (14/10/2026). D'avril à octobre 2026, les deux nœuds ont accepté
#  l'authentification SSH par mot de passe (#1918) : `hardening.conf` disait
#  `no`, mais `50-cloud-init.conf` — posé par l'image Raspberry Pi OS — disait
#  `yes` et passait avant lui. Rien ne mesurait la configuration SERVIE.
#  `durcir-noeud.sh --appliquer` l'a corrigé le 14/10 ; trois évènements
#  extérieurs peuvent la défaire sans que personne le décide : une
#  réinstallation depuis l'image, une mise à jour de cloud-init ou
#  d'openssh-server qui repose son fichier, un `sshd_config.d/` retouché.
#
#  LA MESURE, PAR LE COMPORTEMENT : la sonde demande la méthode `none`
#  (`ssh_noeud_sonde_auth_cmd`, `lib-ssh-noeuds.sh`) ; sshd la refuse en nommant
#  ce qu'il accepte, et `durcissement_ssh_sonde_verdict` (`lib-durcissement.sh`,
#  la règle du durcissement, écrite UNE fois) juge la liste. Aucune clé n'est
#  présentée, aucun mot de passe tenté.
#
#  QUI SONDE QUI : chaque nœud sonde son PAIR (clé d'hôte épinglée de
#  `known_hosts_bascule`) et LUI-MÊME (sa clé d'hôte lue localement), toujours
#  par l'adresse du LAN — la vue de qui attaquerait depuis le réseau local.
#  Le pair est sondé MÊME s'il ne répond pas à la collecte : un nœud réinstallé
#  depuis l'image n'a plus la clé de bascule (collecte KO), ne lance pas encore
#  ce contrôle, et offre le mot de passe — c'est le cas que C38 doit voir.
#  `repartir_constats` (#1402) garde ce constat-là parce que le pair est muet ;
#  quand le pair répond, c'est sa propre sonde qui s'affiche sous son nom.
#
#  fail2ban : sshd journalise la sonde « Connection closed by authenticating
#  user … [preauth] », que le filtre sshd en mode `normal` (celui des deux
#  nœuds) IGNORE — mesuré par `fail2ban-regex` le 14/10/2026 ; en mode
#  `aggressive` elle compterait. Chaque source n'en envoie qu'une par quart
#  d'heure, la prison bannit à 5 en 10 minutes : la marge tient même alors.
#  Un bannissement de l'IP du pair couperait la bascule : ne JAMAIS raccourcir
#  la cadence, ni lancer `check-reliability.sh` en boucle à la main.
#
#  FAIL et non WARN : un mot de passe accepté est une porte ouverte, pas une
#  hygiène. INCONNU → WARN, jamais OK (`standards/04` §1).
#
#  SOURCÉ (mode 100644) par `check-reliability.sh` (boucle des modules) ;
#  `ssh_mot_de_passe_verdicts` est appelé par `lib-conformite.sh`. ⚠️ Il emploie
#  `ok`, `warn`, `fail`, `$SELF`, `$PEER`, `$SELF_IP`, `$PEER_IP` de son appelant.
#  Autotest : bash scripts/lib/lib-ssh-mot-de-passe.sh --selftest
# =============================================================================

# shellcheck source=lib-durcissement.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib-durcissement.sh"
# shellcheck source=lib-ssh-noeuds.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib-ssh-noeuds.sh"

#: Le compte sondé : celui de l'exploitation (`SSH_NOEUDS_COMPTE`) — le seul qui
#: ait une raison d'entrer, donc celui qu'un `Match User` viserait.
#: La fonction qui sonde — remplacée par une sonde simulée dans l'autotest.
SSH_MDP_SONDE=ssh_mot_de_passe_sonder

# ── La sonde (effet de bord : UNE connexion SSH, rien d'autre) ───────────────
#  $1 le nœud · $2 son IP → écrit ce qu'a dit ssh, rend son code de retour.
#  `timeout` borne l'échange au-delà du délai de connexion : 124 → INCONNU.
ssh_mot_de_passe_sonder() {
  local n=$1 ip=$2 kh="" rc sortie
  if [ "$n" = "$SELF" ]; then
    kh=$(mktemp) || return 255
    ssh_noeud_epingle_local "$ip" > "$kh"
    if [ ! -s "$kh" ]; then
      rm -f "$kh"
      echo "clé d'hôte locale illisible (/etc/ssh/ssh_host_ed25519_key.pub, root requis)"
      return 255
    fi
  fi
  sortie=$(timeout 20 $(ssh_noeud_sonde_auth_cmd 8 "$kh") "$SSH_NOEUDS_COMPTE@$ip" true 2>&1 </dev/null)
  rc=$?
  [ -z "$kh" ] || rm -f "$kh"
  printf '%s\n' "$sortie"
  return "$rc"
}

# ── C38, par nœud ────────────────────────────────────────────────────────────
ssh_mot_de_passe_verdicts() {
  local n ip sortie rc v
  for n in "$SELF" "$PEER"; do
    if [ "$n" = "$SELF" ]; then ip=$SELF_IP; else ip=$PEER_IP; fi
    sortie=$("$SSH_MDP_SONDE" "$n" "$ip"); rc=$?
    v=$(durcissement_ssh_sonde_verdict "$rc" "$sortie")
    case "$v" in
      CONFORME)  ok   "SSH de $n : mot de passe refusé — méthode(s) offerte(s) : $(durcissement_ssh_methodes_offertes "$sortie")" ;;
      ECART:*)   fail "SSH de $n : le MOT DE PASSE est accepté (${v#ECART:}) — relancer sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --appliquer sur $n ; une réinstallation depuis l'image ou une mise à jour de cloud-init repose 50-cloud-init.conf (#1918, #1941)" ;;
      *)         warn "SSH de $n : refus du mot de passe NON MESURÉ (${v#INCONNU:}) — ni vert ni rouge" ;;
    esac
  done
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  st=0
  t() { [ "$3" = "$2" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; }; }
  ok()   { echo "OK $*"; }
  warn() { echo "WARN $*"; }
  fail() { echo "FAIL $*"; }
  SELF=rpi1 PEER=rpi2 SELF_IP=10.0.0.1 PEER_IP=10.0.0.2
  P="compte@10.0.0.x: Permission denied"
  #  La sonde simulée : la réponse de chaque nœud se règle par REP_<nœud>, son
  #  code par RC_<nœud> (255 : refusé, comme ssh le rend).
  SSH_MDP_SONDE=sonde_simulee
  sonde_simulee() { eval "printf '%s\n' \"\${REP_$1:-}\"; return \${RC_$1:-255}"; }
  compte() { grep -c "$1" <<< "$sortie"; }
  echo "== self-test lib-ssh-mot-de-passe (C38) =="

  REP_rpi1="$P (publickey)." REP_rpi2="$P (publickey)."
  sortie=$(ssh_mot_de_passe_verdicts)
  t "les deux nœuds en publickey seul → deux OK, ni FAIL ni WARN" "2|0" \
    "$(compte '^OK SSH de rpi[12] : mot de passe refusé — méthode(s) offerte(s) : publickey$')|$(compte '^\(FAIL\|WARN\)')"

  #  LA FAUTE INJECTÉE : rpi2 tel qu'il était d'avril à octobre 2026 (#1918).
  REP_rpi2="$P (publickey,password)."
  sortie=$(ssh_mot_de_passe_verdicts)
  t "rpi2 offre password → un FAIL qui nomme rpi2 et la correction" 1 \
    "$(compte '^FAIL SSH de rpi2 : le MOT DE PASSE est accepté (password offert.*durcir-noeud.sh --appliquer sur rpi2')"
  t "… et rpi1 reste vert" 1 "$(compte '^OK SSH de rpi1 ')"

  REP_rpi1="$P (publickey,keyboard-interactive)."
  sortie=$(ssh_mot_de_passe_verdicts)
  t "keyboard-interactive (mot de passe par PAM) → FAIL" 1 "$(compte '^FAIL SSH de rpi1 .*keyboard-interactive')"

  #  LE CAS ZÉRO : aucune réponse ne fait jamais un vert.
  REP_rpi1="" RC_rpi1=124 REP_rpi2="Host key verification failed." RC_rpi2=255
  sortie=$(ssh_mot_de_passe_verdicts)
  t "aucune réponse, clé d'hôte non vérifiée → deux WARN, aucun OK" "2|0" \
    "$(compte '^WARN SSH de rpi[12] : refus du mot de passe NON MESURÉ')|$(compte '^OK')"

  REP_rpi1="" RC_rpi1=0
  sortie=$(ssh_mot_de_passe_verdicts)
  t "entrée sans authentification → FAIL" 1 "$(compte '^FAIL SSH de rpi1 .*sans aucune authentification')"
  unset RC_rpi1 RC_rpi2

  #  La sonde RÉELLE, sans réseau : son SSH est remplacé par un témoin qui
  #  rend ses arguments. Elle passe par lib-ssh-noeuds, et épingle le nœud
  #  lui-même par sa clé locale — jamais sans clé d'hôte.
  SSH_MDP_SONDE=ssh_mot_de_passe_sonder
  timeout() { shift; echo "$*"; return 255; }
  t "pair : la sonde de lib-ssh-noeuds, sur son IP du LAN" \
    "$(ssh_noeud_sonde_auth_cmd 8) $SSH_NOEUDS_COMPTE@10.0.0.2 true" "$(ssh_mot_de_passe_sonder rpi2 10.0.0.2)"
  ssh_noeud_epingle_local() { :; }
  t "lui-même, clé d'hôte locale illisible → la sonde n'est pas lancée" \
    "clé d'hôte locale illisible (/etc/ssh/ssh_host_ed25519_key.pub, root requis)" \
    "$(ssh_mot_de_passe_sonder rpi1 10.0.0.1)"
  ssh_noeud_epingle_local() { echo "$1 ssh-ed25519 AAAA"; }
  t "lui-même : known_hosts temporaire, StrictHostKeyChecking=yes" 1 \
    "$(ssh_mot_de_passe_sonder rpi1 10.0.0.1 | grep -c 'StrictHostKeyChecking=yes -o UserKnownHostsFile=/[^ ]*tmp[^ ]* .*PreferredAuthentications=none.* '"$SSH_NOEUDS_COMPTE"'@10.0.0.1 true$')"
  t "la sonde rend le code de ssh" 255 "$(ssh_mot_de_passe_sonder rpi2 10.0.0.2 >/dev/null; echo $?)"
  unset -f timeout ssh_noeud_epingle_local ok warn fail

  [ "$st" -eq 0 ] && echo "lib-ssh-mot-de-passe : tous les cas passent."
  exit "$st"
fi
