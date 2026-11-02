#!/bin/bash
# =============================================================================
#  lib-depot-distant.sh — D'où les nœuds tirent le code : HTTPS, plus SSH (#2367)
#
#  Module SOURCÉ par `auto-deploy.sh`, `MaJ-Hostachy.sh` et `bascule.sh` (qui en
#  tire la commande jouée chez le pair) : jamais exécuté par un cron. Pas de bit x
#  (`lib-*.sh` sont en 100644).
#
#  ## Pourquoi
#
#  `git fetch` passait par SSH (`git@github.com`, port 22). La sortie des nœuds se
#  ferme par liste blanche (#2367), et ufw ne nomme pas un hôte : il aurait fallu
#  déclarer les plages « git » de GitHub — or `github.com` se résout parfois vers
#  l'une des ~55 adresses isolées qu'`api.github.com/meta` publie (rpi2, le
#  01/11/2026 : `20.250.119.67`, 62 sorties en 24 h hors de la liste), et elles
#  changent. Le dépôt est PUBLIC : l'HTTPS se passe de clé, et le 443 est déjà
#  ouvert vers GitHub, ghcr.io et l'API. Plus aucune plage à tenir.
#
#  ## Comment un nœud y passe
#
#  Sans geste : le remote d'un nœud est réécrit par le premier passage d'un script
#  qui source ce module (`depot_distant_preparer`), idempotent. Chez le pair, la
#  bascule joue `depot_distant_commande` AVANT son fetch : le code du pair est
#  encore l'ancien, il ne connaît pas ce module.
#
#  Test : bash scripts/lib/lib-depot-distant.sh --selftest
# =============================================================================

#: L'adresse du dépôt, une fois. `SOURCE_IMAGES` (`lib-images-ci.sh`) en est la
#: même sans `.git` — `test_depot_distant_https.py` les confronte.
DEPOT_DISTANT_URL="https://github.com/philippe-tressard/coprofirst.git"

#  Aligne le remote `origin` du dépôt $1 (défaut : le courant) sur l'HTTPS, et
#  interdit à git de demander un mot de passe : sous cron, la demande attendrait
#  une saisie qui ne viendra jamais.
depot_distant_preparer() {
  local d=${1:-.} courant
  export GIT_TERMINAL_PROMPT=0
  courant=$(git -C "$d" remote get-url origin 2>/dev/null || true)
  [ "$courant" = "$DEPOT_DISTANT_URL" ] && return 0
  if [ -n "$courant" ]; then git -C "$d" remote set-url origin "$DEPOT_DISTANT_URL"
  else git -C "$d" remote add origin "$DEPOT_DISTANT_URL"; fi
}

#  La même chose, en une commande à jouer chez un pair dont le code est ancien.
depot_distant_commande() {
  printf "export GIT_TERMINAL_PROMPT=0 && git remote set-url origin '%s'" "$DEPOT_DISTANT_URL"
}

depot_distant_selftest() {
  local st=0 t d
  v() {  # $1 libellé · $2 attendu · $3 obtenu
    if [ "$3" = "$2" ]; then echo "PASS  $1"; else echo "FAIL  $1  attendu=$2 obtenu=$3"; st=1; fi
  }
  echo "== self-test lib-depot-distant =="
  t=$(mktemp -d); d="$t/depot"
  git init -q "$d"

  v "l'adresse est de l'HTTPS, sans identifiant" OUI \
    "$([[ $DEPOT_DISTANT_URL == https://github.com/*/*.git && $DEPOT_DISTANT_URL != *@* ]] && echo OUI || echo NON)"

  git -C "$d" remote add origin "git@github.com:philippe-tressard/coprofirst.git"
  depot_distant_preparer "$d"
  v "un remote SSH est réécrit en HTTPS" "$DEPOT_DISTANT_URL" "$(git -C "$d" remote get-url origin)"
  v "git ne demande jamais de mot de passe" 0 "$GIT_TERMINAL_PROMPT"

  depot_distant_preparer "$d"
  v "idempotent : un second passage ne change rien" "$DEPOT_DISTANT_URL" "$(git -C "$d" remote get-url origin)"
  v "un seul remote, jamais un second" 1 "$(git -C "$d" remote | grep -c .)"

  git -C "$d" remote remove origin
  depot_distant_preparer "$d"
  v "sans origin, il est ajouté" "$DEPOT_DISTANT_URL" "$(git -C "$d" remote get-url origin)"

  #  La commande du pair, jouée pour de vrai sur un dépôt qui porte l'ancien remote.
  git -C "$d" remote set-url origin "git@github.com:philippe-tressard/coprofirst.git"
  (cd "$d" && eval "$(depot_distant_commande)")
  v "la commande du pair réécrit le remote" "$DEPOT_DISTANT_URL" "$(git -C "$d" remote get-url origin)"
  v "la commande du pair ne dépend d'aucune fonction" 0 "$(depot_distant_commande | grep -c 'depot_distant_')"

  rm -rf "$t"
  [ "$st" -eq 0 ] && echo "lib-depot-distant : tous les cas passent."
  return "$st"
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  depot_distant_selftest
  exit $?
fi
