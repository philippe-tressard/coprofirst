#!/bin/bash
# =============================================================================
#  lib-role.sh — Identité des nœuds : hostname ⇄ rôle ⇄ IP (module à sourcer)
#
#  POURQUOI ce module existe :
#    La table « PhT-RB5 = rpi1 = 192.168.1.222 » était recopiée dans SEPT
#    scripts : bascule.sh, health-watch.sh, boot-role-guard.sh, auto-deploy.sh,
#    check-reliability.sh, maintenance.sh et MaJ-Hostachy.sh. Renommer un hôte
#    ou changer une IP exigeait sept modifications cohérentes, et un oubli ne se
#    manifeste qu'à l'exécution du script concerné — c'est-à-dire au pire moment
#    possible : pendant une bascule ou un failover.
#
#  Ce module ne contient QUE des fonctions pures : ni SSH, ni docker, ni
#  écriture, ni lecture de `.active`. L'identité (« qui suis-je ») est figée par
#  le matériel ; le RÔLE COURANT (« qui sert la prod ») est un état volatil, il
#  reste lu dans $REPO/.active par chaque appelant. Ne pas mélanger les deux.
#
#  Usage :
#    source /opt/5hostachy/scripts/lib/lib-role.sh
#    SELF=$(role_of "$(hostname)")       # "" si hostname inconnu
#    PEER=$(role_peer "$SELF")
#    PEER_IP=$(role_ip "$PEER")
#
#  ⚠ Les fonctions rendent TOUJOURS 0, même sur entrée inconnue (elles rendent
#    alors une chaîne vide). Un `return 1` ferait avorter les appelants sous
#    `set -e` dans `SELF=$(role_of …)`, AVANT leur propre message d'erreur —
#    chacun gère l'inconnu à sa façon (exit 0 pour auto-deploy, 2 pour
#    check-reliability…). C'est à l'appelant de tester la chaîne vide.
#
#  Test : bash lib-role.sh --selftest   (aucun effet de bord)
# =============================================================================

# Table unique. Ajouter un nœud = une ligne ICI, et nulle part ailleurs.
ROLE_TABLE="PhT-RB5:rpi1:192.168.1.222
PhT-RB5i2:rpi2:192.168.1.223"

#: Le compte d'exploitation qui se connecte aux nœuds depuis le poste (`standards/03`
#: §8 : jamais un autre). Un script du poste écrit `$(noeud_ssh rpi1)`, jamais l'adresse
#: recopiée — c'est le conducteur de MEP qui l'a demandé (#2631).
COMPTE_EXPLOITATION="${COMPTE_EXPLOITATION:-ptressard}"

# ── rôle → adresse SSH « compte@ip » ─────────────────────────────────────────
noeud_ssh() {
  local ip; ip=$(role_ip "${1:-}")
  [ -n "$ip" ] && echo "$COMPTE_EXPLOITATION@$ip" || echo ""
}

# ── hostname → rôle ──────────────────────────────────────────────────────────
role_of() {
  local want="$1" host role ip
  while IFS=: read -r host role ip; do
    [ -n "$host" ] || continue
    [ "$host" = "$want" ] && { echo "$role"; return 0; }
  done <<< "$ROLE_TABLE"
  echo ""
}

# ── rôle → IP ────────────────────────────────────────────────────────────────
role_ip() {
  local want="$1" host role ip
  while IFS=: read -r host role ip; do
    [ -n "$host" ] || continue
    [ "$role" = "$want" ] && { echo "$ip"; return 0; }
  done <<< "$ROLE_TABLE"
  echo ""
}

# ── rôle → rôle de l'autre nœud ──────────────────────────────────────────────
# Cluster à deux nœuds : le peer est le seul autre rôle de la table.
role_peer() {
  local want="$1" host role ip
  [ -n "$want" ] || { echo ""; return 0; }
  while IFS=: read -r host role ip; do
    [ -n "$host" ] || continue
    [ "$role" != "$want" ] && { echo "$role"; return 0; }
  done <<< "$ROLE_TABLE"
  echo ""
}

# ── Self-test ────────────────────────────────────────────────────────────────
# `[ "${BASH_SOURCE[0]}" = "$0" ]` : sans ce garde, sourcer ce module depuis un
# script lui-même appelé avec `--selftest` déclencherait CE bloc (les fonctions
# sourcées héritent des paramètres de l'appelant) et sortirait à sa place.
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  st_fail=0
  check() { # description attendu obtenu
    if [ "$3" = "$2" ]; then echo "PASS  $1  → '$3'"
    else echo "FAIL  $1  attendu='$2' obtenu='$3'"; st_fail=1; fi
  }
  echo "== self-test lib-role =="
  check "hostname rpi1 → rôle"      "rpi1"          "$(role_of PhT-RB5)"
  check "hostname rpi2 → rôle"      "rpi2"          "$(role_of PhT-RB5i2)"
  check "hostname inconnu → vide"   ""              "$(role_of PhT-RB9)"
  check "hostname vide → vide"      ""              "$(role_of '')"
  check "rôle rpi1 → IP"            "192.168.1.222" "$(role_ip rpi1)"
  check "rôle rpi2 → adresse SSH"   "ptressard@192.168.1.223" "$(noeud_ssh rpi2)"
  check "rôle inconnu → adresse vide" "" "$(noeud_ssh rpi9)"
  check "rôle rpi2 → IP"            "192.168.1.223" "$(role_ip rpi2)"
  check "rôle inconnu → IP vide"    ""              "$(role_ip rpi9)"
  check "peer de rpi1"              "rpi2"          "$(role_peer rpi1)"
  check "peer de rpi2"              "rpi1"          "$(role_peer rpi2)"
  check "peer d'un rôle vide"       ""              "$(role_peer '')"
  # Le cas qui casserait les appelants sous `set -e` : entrée inconnue.
  role_of PhT-RB9 >/dev/null; check "code retour sur inconnu" "0" "$?"
  [ $st_fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $st_fail
fi
