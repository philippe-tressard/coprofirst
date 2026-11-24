#!/bin/bash
# env-report.sh — Rapport d'environnement injecté au démarrage de session.
# Objectif : rendre IMPOSSIBLE de travailler sur le mauvais projet sans le voir.
# L'étiquette de session et la banque de mémoire découlent du répertoire de
# lancement, pas du contenu de la demande : une session ouverte ailleurs et
# pilotée en chemins absolus écrit ses mémoires au mauvais endroit et n'exécute
# pas ce pré-flight (constaté le 31/07/2026).
#
# Les répertoires du projet sont la liste ATTENDUS (poste Windows et poste Mac).
# Chaque chemin porte sa banque de mémoire : `case` ci-dessous. Un répertoire
# hors liste n'est pas une erreur en soi : il déclenche l'alerte.
# Garde-fou : `bash .claude/env-report.sh --selftest` (#2746).
set -uo pipefail

ATTENDUS=(
  "/c/Dev/5hostachy"               # Git Bash, poste Windows
  "/volumes/data/dev/5hostachy"    # Mac (minuscules : comparaison insensible à la casse)
)

# En minuscules, sans `${x,,}` : le bash d'Apple est un 3.2, qui ne le connaît pas
# — l'autotest y sortait en 0 sans avoir jugé un seul cas (#2935).
minuscules() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# Banque de mémoire du poste pour un répertoire donné (les deux noms sont constatés).
memoire_pour() {
  case "$(minuscules "$1")" in
    /c/dev/5hostachy)            echo "C--Dev-5hostachy" ;;
    /volumes/data/dev/5hostachy) echo "-Volumes-Data-Dev-5hostachy" ;;
    *)                           echo "" ;;
  esac
}

# Vrai si le répertoire donné est l'un des répertoires attendus du projet.
dans_le_projet() {
  local a
  for a in "${ATTENDUS[@]}"; do
    [ "$(minuscules "$1")" = "$(minuscules "$a")" ] && return 0
  done
  return 1
}

if [ "${1:-}" = "--selftest" ]; then
  echo_ok=0; echo_ko=0
  verifier() { # verifier <attendu-vrai|faux> <répertoire>
    local attendu="$1" r="$2" obtenu=faux
    dans_le_projet "$r" && obtenu=vrai
    if [ "$attendu" = "$obtenu" ]; then echo_ok=$((echo_ok+1)); else
      echo_ko=$((echo_ko+1)); echo "KO : « $r » attendu $attendu, obtenu $obtenu" >&2; fi
  }
  verifier vrai  "/c/Dev/5hostachy"
  verifier vrai  "/Volumes/Data/Dev/5hostachy"
  verifier vrai  "/VOLUMES/data/dev/5HOSTACHY"
  verifier faux  "/Volumes/Data/Dev/List-dons"
  verifier faux  "/home/user/coprofirst"
  verifier faux  "/c/Dev/5hostachy-test"
  [ "$(memoire_pour /Volumes/Data/Dev/5hostachy)" = "-Volumes-Data-Dev-5hostachy" ] \
    || { echo_ko=$((echo_ko+1)); echo "KO : banque Mac" >&2; }
  [ "$(memoire_pour /c/Dev/5hostachy)" = "C--Dev-5hostachy" ] \
    || { echo_ko=$((echo_ko+1)); echo "KO : banque Windows" >&2; }
  echo "env-report --selftest : $echo_ok OK, $echo_ko KO"
  #  Aucun cas jugé n'est pas un succès (`standards/04` §2) : c'est l'autotest qui
  #  n'a pas tourné.
  [ "$echo_ok" -gt 0 ] || { echo "KO : aucun cas jugé — l'autotest n'a pas tourné" >&2; exit 1; }
  [ "$echo_ko" -eq 0 ]
  exit $?
fi

COURANT=$(pwd)
echo "═══════════════ ENVIRONNEMENT DE TRAVAIL ═══════════════"
echo "  Projet        : 5Hostachy (copropriété — prod HA sur 2 RPi)"
echo "  Étiquette     : 5Hostachy — <sujet>"
echo "  Répertoire    : $COURANT"
echo "  Dépôt/branche : $(git config --get remote.origin.url 2>/dev/null) [$(git branch --show-current 2>/dev/null)]"
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  MEMOIRE=$(memoire_pour "$COURANT")
  if [ -n "$MEMOIRE" ]; then
    echo "  Mémoire       : ~/.claude/projects/$MEMOIRE/memory/"
  else
    echo "  Mémoire       : 🔴 répertoire hors projet — la banque ne se devine pas"
  fi
fi
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
  # Session CLOUD (claude.ai/code) — le répertoire attendu n'y a pas de sens.
  # Ce bloc est le contrôle de `.claude/cloud/setup.sh` : il relit à CHAQUE
  # session ce que le setup a posé, et déclare ABSENT ce qui manque au lieu de
  # laisser croire que tout est là (socle 04 : INCONNU, jamais OK).
  echo "  Session       : ☁️  CLOUD — pas de SSH : pré-check INCONNU, post-check au poste."
  echo "                  La MEP s'enchaîne SANS validation jusqu'à main (CLAUDE.md, « Session cloud »)."
  echo "  Mémoire       : banque du poste ABSENTE — rien de ce qui s'écrit ici n'est gardé."
  [ -d front/node_modules ] \
    && echo "  Dépendances   : présentes" \
    || echo "  Dépendances   : 🔴 ABSENTES — lancer : bash .claude/cloud/setup.sh"
  [ -f "$HOME/.claude/standards/INDEX.md" ] \
    && echo "  Socle         : présent (~/.claude/standards/)" \
    || echo "  Socle         : 🔴 ABSENT — claude-config non attaché à la session"
  GARDE="$HOME/claude-config/bin/garde-git-destructif.py"
  if [ -f "$GARDE" ] && timeout 5 python3 "$GARDE" --selftest >/dev/null 2>&1; then
    echo "  Garde-fou git : actif (autotest passé)"
  else
    echo "  Garde-fou git : 🔴 ABSENT — RIEN ne refuse \`git reset --hard\`, \`clean -f\`,"
    echo "                  \`push --force\` : ces gestes restent INTERDITS sans l'accord de Philippe."
  fi
elif ! dans_le_projet "$COURANT"; then
  echo "  ⚠️  RÉPERTOIRE INATTENDU (attendus : ${ATTENDUS[*]}) — signale-le à l'utilisateur"
  echo "      AVANT d'agir : mémoires et étiquette partiront au mauvais endroit."
fi
if ! dans_le_projet "$COURANT"; then
  echo "  → Si la demande porte sur un autre projet, dis-le et propose de relancer la session depuis son"
  echo "    répertoire, tel que ~/.claude/projets.json le déclare pour ce poste."
fi
echo "  → Reprends cette ligne en tête de ta 1ʳᵉ réponse."
echo "════════════════════════════════════════════════════════"
