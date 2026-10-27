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

# ── La trace du rejeu de la CI (`rejeu-ci.ok`) : UN format, écrit et lu ici ────
#  `rejouer-ci.sh` l'écrit, le point 16 du pré-check la lit : deux copies du format
#  divergeaient au premier champ ajouté (SAUTS en #1734, RELANCES en #1809, TREE en
#  #2245). Elle porte le sha du commit rejoué ET l'arbre git (`HEAD^{tree}`) : le
#  rejeu mesure le code, pas l'historique — un reword ou un squash change le premier
#  et laisse le second (#2245).

# trace_rejeu_ecrire fichier sha epoch ok fail inconnu sauts relances arbre
trace_rejeu_ecrire() {
    printf '%s %s OK=%d FAIL=%d INCONNU=%d SAUTS=%d RELANCES=%d TREE=%s\n' \
        "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" > "$1"
}

# trace_rejeu_lire fichier — pose R_SHA R_OK R_FAIL R_INC R_SAUTS R_REL R_TREE.
#  Trace absente : tout vide, R_OK="?". Une trace d'avant un champ le laisse vide
#  (le verdict lit alors la trace pour son seul sha) ; `read` le fait seul, mais la
#  suite de noms doit rester COMPLÈTE : sans le dernier, R_REL avalerait le reste.
trace_rejeu_lire() {
    R_SHA=""; R_OK="?"; R_FAIL=""; R_INC=""; R_SAUTS=""; R_REL=""; R_TREE=""
    [ -f "$1" ] || return 0
    read -r R_SHA _ R_OK R_FAIL R_INC R_SAUTS R_REL R_TREE _ < "$1"
    R_FAIL=${R_FAIL#FAIL=}; R_INC=${R_INC#INCONNU=}; R_OK=${R_OK#OK=}
    R_SAUTS=${R_SAUTS#SAUTS=}; R_REL=${R_REL#RELANCES=}; R_TREE=${R_TREE#TREE=}
}
