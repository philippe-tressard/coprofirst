#!/bin/sh
# =============================================================================
#  lib-depot.sh — où vivent les traces du poste : le répertoire git DU clone
#
#  Le pré-check, le rejeu de la CI et le hook `pre-push` déposent leurs traces
#  (`precheck-mep.ok`, `rejeu-ci.ok`, `pr-brief.md`, `erreur-corrigee`,
#  `reecriture-dev`) dans le répertoire git, hors de l'arbre versionné.
#
#  🔴 Ils l'écrivaient `.git/…`, en dur (#1226, 24/09/2026). Dans un worktree
#  (`git worktree add`), `.git` est un FICHIER qui pointe ailleurs : le rejeu
#  complet finissait sur « .git/rejeu-ci.ok: Not a directory », la trace n'était
#  jamais écrite, et le point 16 restait INCONNU. Deux sessions travaillant en
#  parallèle sur le même clone, c'est pourtant le worktree qui les sépare
#  (`standards/13-outillage-claude-code.md` §10).
#
#  `--absolute-git-dir` rend le répertoire PROPRE au worktree : une trace y
#  porte le commit de ce worktree-là, et ne peut pas être prise pour celle du
#  clone principal.
#
#  POSIX : sourcé aussi par `.githooks/pre-push`, qui tourne sous `sh`.
#  Self-test : bash scripts/lib/lib-depot.selftest.sh
# =============================================================================

# dossier_git [répertoire] — chemin absolu du répertoire git, vide et code ≠ 0
# hors d'un dépôt (l'appelant décide : un chemin vide n'est pas « .git »).
dossier_git() {
    git -C "${1:-.}" rev-parse --absolute-git-dir 2>/dev/null
}

# dossier_git_commun [répertoire] — le répertoire git PARTAGÉ par le clone et tous ses
# worktrees, absolu ; vide et code ≠ 0 hors d'un dépôt. Ce qui vaut pour le poste
# entier s'y range — la déclaration d'une exception du pré-check, l'état du
# conducteur de MEP (#2631) —, ce qui vaut pour un lot va dans `dossier_git`.
dossier_git_commun() {
    git -C "${1:-.}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null
}

# Les trois comptes des checks d'une PR, en filtre jq sur `statusCheckRollup` :
# tous, en cours (non terminés), rouges (terminés autrement que SUCCESS, SKIPPED ou
# NEUTRAL). Lus par le point 16 du pré-check ET par le conducteur de MEP : écrits
# une fois, ils ne peuvent pas compter deux choses différentes.
COMPTES_CHECKS_JQ='(.statusCheckRollup | length), ([.statusCheckRollup[] | select(.status != "COMPLETED")] | length), ([.statusCheckRollup[] | select(.status == "COMPLETED" and .conclusion != "SUCCESS" and .conclusion != "SKIPPED" and .conclusion != "NEUTRAL")] | length)'

# ── La trace du rejeu de la CI (`rejeu-ci.ok`) : UN format, écrit et lu ici ────
#  `rejouer-ci.sh` l'écrit, le point 16 du pré-check la lit : deux copies du format
#  divergeaient au premier champ ajouté (SAUTS en #1734, RELANCES en #1809, TREE en
#  #2245). Elle porte le sha du commit rejoué ET l'arbre git (`HEAD^{tree}`) : le
#  rejeu mesure le code, pas l'historique — un reword ou un squash change le premier
#  et laisse le second (#2245). Depuis #2571, elle porte aussi son MODE : le rejeu
#  ordinaire s'arrête à la phase rapide et CONFIE les étapes lentes (pytest, e2e) à la
#  CI de la PR — `rapide`, avec leur nombre ; `--complet` les joue ici — `complet`.

# trace_rejeu_ecrire fichier sha epoch ok fail inconnu sauts relances arbre [mode confiées]
trace_rejeu_ecrire() {
    printf '%s %s OK=%d FAIL=%d INCONNU=%d SAUTS=%d RELANCES=%d TREE=%s MODE=%s CONFIEES=%d\n' \
        "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" "${10:-complet}" "${11:-0}" > "$1"
}

# trace_rejeu_lire fichier — pose R_SHA R_OK R_FAIL R_INC R_SAUTS R_REL R_TREE R_MODE R_CONF.
#  Une trace d'avant #2571 n'a pas de mode : elle était complète par construction.
#  Trace absente : tout vide, R_OK="?". Une trace d'avant un champ le laisse vide
#  (le verdict lit alors la trace pour son seul sha) ; `read` le fait seul, mais la
#  suite de noms doit rester COMPLÈTE : sans le dernier, R_REL avalerait le reste.
trace_rejeu_lire() {
    R_SHA=""; R_OK="?"; R_FAIL=""; R_INC=""; R_SAUTS=""; R_REL=""; R_TREE=""; R_MODE=""; R_CONF=""
    [ -f "$1" ] || return 0
    read -r R_SHA _ R_OK R_FAIL R_INC R_SAUTS R_REL R_TREE R_MODE R_CONF _ < "$1"
    R_FAIL=${R_FAIL#FAIL=}; R_INC=${R_INC#INCONNU=}; R_OK=${R_OK#OK=}
    R_SAUTS=${R_SAUTS#SAUTS=}; R_REL=${R_REL#RELANCES=}; R_TREE=${R_TREE#TREE=}
    R_MODE=${R_MODE#MODE=}; R_CONF=${R_CONF#CONFIEES=}
    R_MODE=${R_MODE:-complet}; R_CONF=${R_CONF:-0}
}

# ── Ce qu'une trace RAPIDE vaut : rien sans la CI de la PR (#2571) — PURES ─────
#  La phase rapide ne joue ni pytest ni les tests de navigateur : la suite complète
#  est jugée par la CI de la PR, sur le MÊME arbre. Une trace rapide sans CI verte
#  rend INCONNU, jamais OK — et une CI illisible ne se lit pas comme verte.

# etat_checks_pr checks en_cours rouges → VERT | ROUGE | EN_COURS | ABSENT
etat_checks_pr() {
    [ -n "${1:-}" ] && [ -n "${2:-}" ] && [ -n "${3:-}" ] || { echo ABSENT; return; }
    case "$1$2$3" in *[!0-9]*) echo ABSENT; return ;; esac
    [ "$1" -eq 0 ] && { echo ABSENT; return; }
    [ "$3" -gt 0 ] && { echo ROUGE; return; }
    [ "$2" -gt 0 ] && { echo EN_COURS; return; }
    echo VERT
}

# verdict_suite_complete verdict_de_la_trace mode etat_de_la_ci → OK | FAIL | INCONNU
verdict_suite_complete() {
    case "${1:-}" in OK) ;; FAIL) echo FAIL; return ;; *) echo INCONNU; return ;; esac
    case "${2:-}" in
        complet) echo OK ;;
        rapide)  case "${3:-}" in VERT) echo OK ;; ROUGE) echo FAIL ;; *) echo INCONNU ;; esac ;;
        *)       echo INCONNU ;;
    esac
}
