#!/bin/bash
# =============================================================================
#  lib-ci-verrou-poste.sh — Le rejeu prend son rang au verrou commun du poste (#2765)
#
#  Module SOURCÉ par `lib-ci-verrou.sh` (donc par `rejouer-ci.sh` et `etat-rejeu.sh`) ;
#  exécuté seulement pour son `--selftest` (job `test-scripts`). Pas de bit x.
#
#  POURQUOI. Sur le Mac, le rejeu de la CI, une suite `xcodebuild` (CoproFirst-iOS) et
#  Gradle (CoproFirst-Android) partent de sessions différentes : ensemble, charge 67 sur
#  12 cœurs le 15/11/2026. Le verrou du rejeu (`lib-ci-verrou.sh`) ne départage que les
#  rejeux entre eux. Le verrou commun des TÂCHES LOURDES vit hors du dépôt,
#  `~/.claude/bin/verrou_poste.py` (claude-config#552) : une à la fois, dans l'ordre
#  d'arrivée, relâché par le noyau à la mort du tenant ; `verrou_poste.py etat` dit qui
#  le tient. Une consigne ne suffisait pas : le geste vit dans le script qui lance.
#
#  L'ORDRE DES DEUX VERROUS — celui du REJEU d'abord, celui du POSTE ensuite :
#   - aucun interblocage : le verrou du poste est toujours le DERNIER pris, et rien de
#     ce qui le tient n'attend celui du rejeu — xcodebuild et Gradle l'ignorent, un
#     rejeu ne prend le poste qu'après le sien. Deux verrous pris dans un ordre unique
#     ne forment pas de cycle ;
#   - la file du rejeu reste juge entre les rejeux : un lancement direct est refusé
#     quand un rejeu tourne, `--attendre` et `file-rejeu.sh devant` gardent leur sens.
#     Pris d'abord, le verrou du poste ferait de SA file l'ordre des rejeux, que le
#     coordinateur ne réordonne pas, et un rejeu « direct » attendrait au lieu d'être refusé ;
#   - attendre le poste en tenant le verrou du rejeu ne retarde personne : l'autre
#     rejeu devrait attendre le poste lui aussi. L'attente se lit dans `etat-rejeu.sh`.
#  ⚠️ Corollaire : rien de ce que le rejeu lance ne prend le verrou du poste — il le
#  tient déjà, par un autre descripteur, et l'enfant attendrait son propre parent.
#  (L'autotest de ce module lance des rejeux sous un DOUBLE du verrou : jamais le vrai.)
#
#  LE GESTE. `verrou_poste.py prendre … -- <commande>` DEVIENT la commande (exec, même
#  pid) et le verrou meurt avec elle. Le rejeu, son propre verrou pris, se relance donc
#  sous le verrou du poste (`ci_verrou_poste_prendre`), marqué REJEU_SOUS_VERROU_POSTE=<pid> ;
#  la seconde entrée, même pid, retrouve son verrou du rejeu et ne le reprend pas
#  (`ci_verrou_poste_entree`). Le veilleur, lancé à la première entrée, continue.
#
#  ABSENT (CI GitHub, poste sans `~/.claude`, python3 manquant) : le rejeu reste
#  possible et le DIT — « verrou du poste INCONNU », jamais un silence ni un « OK »
#  (`standards/04` §1). Refuser bloquerait tout rejeu hors du Mac, alors que ce verrou
#  ne juge pas le lot : il protège les autres tâches du poste.
#
#  VERROU_POSTE_PY impose le chemin (l'autotest y met son double). Défaut :
#  $HOME/.claude/bin/verrou_poste.py — jamais un chemin de poste écrit en dur.
# =============================================================================

ci_verrou_poste_chemin() {     # → le verrou_poste.py à appeler
  printf '%s\n' "${VERROU_POSTE_PY:-${HOME:-}/.claude/bin/verrou_poste.py}"
}
ci_verrou_poste_disponible() { # $1 = chemin → « disponible » | « absent : <raison> »
  [ -f "$1" ] || { echo "absent : $1 introuvable"; return 0; }
  command -v python3 >/dev/null 2>&1 || { echo "absent : python3 introuvable"; return 0; }
  echo disponible
}
#  $1 = REJEU_SOUS_VERROU_POSTE · $2 = pid du rejeu · $3 = pid lu dans le verrou du rejeu
#  → premiere (prendre le verrou du rejeu, puis le poste) | reentree (sous le poste, le
#  verrou du rejeu est à soi) | perdu (sous le poste, il a changé de main) (PURE)
ci_verrou_poste_entree() {
  { [ -n "${1:-}" ] && [ "$1" = "$2" ]; } || { echo premiere; return; }
  [ "${3:-}" = "$2" ] && echo reentree || echo perdu
}
#  Le verrou du rejeu PRIS, se relance sous le verrou du poste : ne revient pas, sauf
#  si le verrou du poste est absent — et alors il le dit.
ci_verrou_poste_prendre() {    # $1 = verrou du rejeu · $2 = script à relancer · $3… = ses arguments
  local verrou=$1 script=$2 py etat; shift 2
  py=$(ci_verrou_poste_chemin); etat=$(ci_verrou_poste_disponible "$py")
  if [ "$etat" != disponible ]; then
    echo "? Verrou du poste INCONNU — ${etat#absent : } : ce rejeu ne prend pas son rang parmi"
    echo "  les tâches lourdes du poste (claude-config#552) et peut tourner à côté d'un xcodebuild ou d'un Gradle."
    return 0
  fi
  ci_battement "$verrou" "attente du verrou du poste (python3 $py etat)" "?"
  echo "· Verrou du rejeu pris ; rang au verrou du poste (tâches lourdes) — état : python3 $py etat"
  export REJEU_SOUS_VERROU_POSTE=$$
  exec python3 "$py" prendre --libelle "rejeu de la CI${REJEU_PROPRIETAIRE:+ — $REJEU_PROPRIETAIRE}" \
    --depot "$(pwd)" -- "$BASH" "$script" "$@"
}
ci_verrou_poste_dire() {       # → l'état du verrou du poste, ou INCONNU et pourquoi (lecture seule)
  local py etat s
  py=$(ci_verrou_poste_chemin); etat=$(ci_verrou_poste_disponible "$py")
  [ "$etat" = disponible ] || { echo "INCONNU — ${etat#absent : }"; return 0; }
  s=$(python3 "$py" etat 2>/dev/null) && [ -n "$s" ] && { printf '%s\n' "$s"; return 0; }
  echo "INCONNU — « python3 $py etat » n'a rien rendu"
}

# ── Self-test ────────────────────────────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  # shellcheck source=lib-ci-verrou-poste.selftest.sh
  . "$(dirname "${BASH_SOURCE[0]}")/lib-ci-verrou-poste.selftest.sh"
  ci_verrou_poste_selftest
  exit $?
fi
