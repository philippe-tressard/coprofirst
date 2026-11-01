#!/usr/bin/env bash
# =============================================================================
#  Retire une copie de travail git (worktree) sans rien perdre (#1890).
#
#  POURQUOI (13/10/2026). Chaque lot travaille dans sa copie à soi
#  (`git worktree add ../5hostachy-<lot>`, `standards/13` §10) — et aucun ne la
#  retirait : 134 copies accumulées en deux semaines. Le ménage à la main a
#  rencontré les deux pièges que ce script tient :
#   - une vingtaine avaient `front/node_modules` en JONCTION vers le clone
#     principal. Un retrait qui suit le lien vide les dépendances de toutes les
#     sessions (vécu le 01/10/2026) : le lien se retire d'abord, SEUL (`rmdir`
#     retire une jonction, jamais sa cible), et la cible est relue ensuite ;
#   - un retrait lancé pendant qu'un programme tient le répertoire ouvert (un
#     terminal, un serveur Vite) échoue À MOITIÉ sous Windows : `.git` disparaît,
#     des fichiers restent, et le reste n'est plus une copie git
#     (`5hostachy-1445` le 29/09, `5hostachy-ouverture` le 13/10). Le répertoire
#     courant de ce script est donc refusé, et l'échec dit quoi fermer.
#
#  CE QUI NE SE PERD JAMAIS. Une copie se retire seulement si elle n'a AUCUNE
#  modification (suivie ou non) et si son HEAD est atteint par une branche ou
#  une étiquette : la branche du lot reste, ses commits aussi. Jamais `--force`
#  — git refuse de lui-même ce qui serait perdu, et ce refus est voulu. Les
#  fichiers IGNORÉS (`node_modules`, captures de tests, caches) partent avec la
#  copie : ils se reconstruisent.
#
#  VERDICTS (code de sortie) :
#    0  tout ce qui était à retirer l'a été (ou rien n'était à retirer)
#    1  un retrait a échoué, une jonction a vidé sa cible, ou la copie NOMMÉE a
#       été gardée (le motif est écrit) — en mode --inactifs, garder est normal
#    2  usage
#
#  Usage :
#    bash scripts/poste/retirer-worktree.sh <chemin>         # la copie d'un lot livré
#    bash scripts/poste/retirer-worktree.sh --inactifs [H]   # celles inactives depuis H heures (24)
#    bash scripts/poste/retirer-worktree.sh --inactifs [H] --voir   # sans rien retirer
#    bash scripts/poste/retirer-worktree.sh --selftest
# =============================================================================
set -uo pipefail
# shellcheck source=../lib/lib-poste-gnu.sh
. "$(dirname "$0")/../lib/lib-poste-gnu.sh"
poste_gnu_poser "$@"   # macOS : les outils GNU en tête du PATH, comme Git Bash et la CI (#2419)

#  Le script ne s'exécute JAMAIS depuis la copie qu'il retire : bash tient son
#  fichier ouvert, et sous Windows le retrait échouerait à moitié. Il se relaie
#  donc par une copie temporaire, lancée depuis le clone principal — en gardant
#  le répertoire de l'APPELANT, qui compte aussi : son shell tient le répertoire.
if [ "${1:-}" != "--selftest" ] && [ -z "${RETIRER_WT_RELAYE:-}" ]; then
  principal_brut=$(git -C "$(dirname "$0")" worktree list --porcelain | sed -n '1s/^worktree //p')
  racine=$(cd "$principal_brut" && pwd -P) || { echo "Clone principal introuvable" >&2; exit 2; }
  args=()
  for a in "$@"; do
    if [ -d "$a" ]; then args+=("$(cd "$a" && pwd -P)"); else args+=("$a"); fi
  done
  copie=$(mktemp) && cp "$0" "$copie" || exit 2
  cd "$racine" || exit 2
  RETIRER_WT_RELAYE="$copie" APPELANT_PWD="$(cd "$OLDPWD" && pwd -P)" \
    exec bash "$copie" "${args[@]}"
fi
[ -n "${RETIRER_WT_RELAYE:-}" ] && trap 'rm -f "$RETIRER_WT_RELAYE"' EXIT
RACINE_DEPOT="$(pwd -P)"

# ── Fonction de décision PURE ────────────────────────────────────────────────
#  decider_retrait <principal 0|1> <modifs> <atteint 0|1> <courant 0|1> <age_h> <seuil_h>
#  → « RETIRER », ou « GARDER|<raison> ». `seuil_h` vaut 0 quand la copie est
#  nommée : l'âge ne compte que pour le ménage du stock.
decider_retrait() {
  local principal="$1" modifs="$2" atteint="$3" courant="$4" age="$5" seuil="$6"
  if [ "$principal" = 1 ]; then echo "GARDER|clone principal"; return; fi
  if [ "$courant" = 1 ]; then echo "GARDER|répertoire courant — en sortir d'abord"; return; fi
  if [ "$modifs" != 0 ]; then echo "GARDER|$modifs modification(s) non committée(s)"; return; fi
  if [ "$atteint" != 1 ]; then echo "GARDER|commits sur aucune branche"; return; fi
  if [ "$age" -lt "$seuil" ]; then echo "GARDER|active il y a ${age} h"; return; fi
  echo "RETIRER"
}

retirer_selftest() {
  local ko=0
  t() {
    local nom="$1" attendu="$2" obtenu
    shift 2
    obtenu=$(decider_retrait "$@")
    if [ "$obtenu" = "$attendu" ]; then echo "  OK  $nom"
    else echo "  KO  $nom — attendu « $attendu », obtenu « $obtenu »"; ko=1; fi
  }
  t "copie propre et livrée"            "RETIRER"                                   0 0 1 0 0 0
  t "clone principal, même propre"      "GARDER|clone principal"                    1 0 1 0 900 24
  t "travail non committé"              "GARDER|2 modification(s) non committée(s)" 0 2 1 0 900 24
  t "HEAD détaché sur aucune branche"   "GARDER|commits sur aucune branche"         0 0 0 0 900 24
  t "répertoire courant du script"      "GARDER|répertoire courant — en sortir d'abord" 0 0 1 1 900 24
  t "stock : active récemment"          "GARDER|active il y a 3 h"                  0 0 1 0 3 24
  t "stock : inactive depuis le seuil"  "RETIRER"                                   0 0 1 0 24 24
  t "nommée : l'âge ne compte pas"      "RETIRER"                                   0 0 1 0 0 0
  #  Le refus le plus grave l'emporte : non committé ET détaché → le non committé.
  t "plusieurs refus, le premier dit"   "GARDER|1 modification(s) non committée(s)" 0 1 0 0 900 24
  [ "$ko" = 0 ] && echo "retirer-worktree : TOUS OK" || echo "retirer-worktree : ÉCHEC"
  return "$ko"
}

# ── Mesures (lisent le dépôt, n'écrivent rien) ───────────────────────────────

#  Âge en heures du dernier geste git dans la copie : l'index bouge à chaque
#  `status`, `add`, `checkout` — c'est le battement d'une session qui y travaille.
age_heures() {
  local index
  index="$(git -C "$1" rev-parse --absolute-git-dir 2>/dev/null)/index"
  [ -f "$index" ] || { echo 0; return; }
  echo $(( ( $(date +%s) - $(stat -c %Y "$index") ) / 3600 ))
}

est_atteint() {
  local head
  head=$(git -C "$1" rev-parse HEAD 2>/dev/null) || { echo 0; return; }
  [ -n "$(git -C "$RACINE_DEPOT" for-each-ref --contains "$head" --count=1 \
      refs/heads refs/remotes refs/tags 2>/dev/null)" ] && echo 1 || echo 0
}

contient_courant() {
  local ici w
  ici="${APPELANT_PWD:-$(pwd -P)}"; w="$(cd "$1" 2>/dev/null && pwd -P)" || { echo 0; return; }
  case "$ici/" in "$w"/*) echo 1 ;; *) echo 0 ;; esac
}

# ── Gestes ───────────────────────────────────────────────────────────────────

#  Retire les jonctions (Windows) de la copie, le LIEN seul, et vérifie que leur
#  cible est intacte. Sous Linux, git traite un lien symbolique comme un fichier.
retirer_jonctions() {
  local w="$1" ligne cible nb avant
  command -v cygpath >/dev/null 2>&1 || return 0
  while IFS='|' read -r ligne cible; do
    [ -n "$ligne" ] || continue
    avant=$(ls -A "$(cygpath -u "$cible")" 2>/dev/null | wc -l)
    powershell -NoProfile -Command "cmd /c rmdir \"$ligne\"" >/dev/null
    nb=$(ls -A "$(cygpath -u "$cible")" 2>/dev/null | wc -l)
    echo "  jonction retirée : $ligne (cible $cible : $nb entrées)"
    if [ "$nb" -lt "$avant" ]; then
      echo "  🔴 la cible a perdu des entrées ($avant → $nb) : ARRÊT" >&2
      return 1
    fi
  done < <(powershell -NoProfile -Command "Get-ChildItem -LiteralPath '$(cygpath -w "$w")' -Recurse -Depth 3 -Force -Attributes ReparsePoint -ErrorAction SilentlyContinue | ForEach-Object { \$_.FullName + '|' + (\$_.Target -join '') }" | tr -d '\r')
}

#  retirer_un <chemin> <seuil_h> <voir 0|1> → 0 retirée (ou vue), 1 échec, 4 gardée
retirer_un() {
  local w="$1" seuil="$2" voir="$3" principal=0 decision err age
  [ "$(cd "$w" && pwd -P)" = "$RACINE_DEPOT" ] && principal=1
  #  L'âge AVANT le status, et un status sans verrou optionnel : un `git status`
  #  ordinaire réécrit l'index, et ce script rajeunissait la copie qu'il mesurait.
  age=$(age_heures "$w")
  decision=$(decider_retrait "$principal" \
    "$(git --no-optional-locks -C "$w" status --porcelain 2>/dev/null | wc -l)" \
    "$(est_atteint "$w")" "$(contient_courant "$w")" "$age" "$seuil")
  if [ "$decision" != "RETIRER" ]; then
    echo "GARDÉE   $w — ${decision#GARDER|}"; return 4
  fi
  if [ "$voir" = 1 ]; then echo "À RETIRER $w"; return 0; fi
  retirer_jonctions "$w" || return 1
  if err=$(git -C "$RACINE_DEPOT" worktree remove "$w" 2>&1); then
    echo "RETIRÉE  $w"
  else
    echo "ÉCHEC    $w — $err" >&2
    echo "         Un programme tient sans doute ce répertoire ouvert (terminal, Vite) : le fermer, puis relancer." >&2
    return 1
  fi
}

principal() {
  local seuil=24 voir=0 st=0 w
  case "${1:-}" in
    --selftest) retirer_selftest; return $? ;;
    --inactifs)
      shift
      case "${1:-}" in ''|--voir) ;; *[!0-9]*) echo "Seuil en heures : $1 ?" >&2; return 2 ;; *) seuil="$1"; shift ;; esac
      [ "${1:-}" = "--voir" ] && voir=1
      while read -r w; do
        retirer_un "$w" "$seuil" "$voir"; [ $? = 1 ] && st=1
      done < <(git -C "$RACINE_DEPOT" worktree list --porcelain | sed -n 's/^worktree //p' | tail -n +2)
      git -C "$RACINE_DEPOT" worktree prune
      return $st ;;
    ''|-*) echo "Usage : $0 <chemin> | --inactifs [heures] [--voir] | --selftest" >&2; return 2 ;;
    *)
      [ -d "$1" ] || { echo "Copie introuvable : $1" >&2; return 2; }
      retirer_un "$1" 0 0 || st=1
      git -C "$RACINE_DEPOT" worktree prune
      return $st ;;
  esac
}

principal "$@"
