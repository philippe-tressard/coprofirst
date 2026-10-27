#!/bin/bash
# =============================================================================
#  lib-depot.selftest.sh — éprouve `dossier_git` sur un VRAI worktree (#1226)
#
#  Un test qui ne créerait qu'un clone ne dirait rien : `.git` y est un
#  répertoire, et l'écriture en dur y marchait déjà. Le cas qui a échoué est le
#  worktree, où `.git` est un fichier — il est donc construit ici, dans un
#  dossier temporaire, puis effacé.
#
#  Lancer : bash scripts/lib/lib-depot.selftest.sh   (job CI `test-scripts`)
# =============================================================================
set -u
. "$(dirname "$0")/lib-depot.sh"

fail=0
check() { # description condition(0/1)
    if [ "$2" = 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; fail=1; fi
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git init -q "$TMP/clone"
git -C "$TMP/clone" -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
git -C "$TMP/clone" worktree add -q "$TMP/wt" -b essai 2>/dev/null

echo "== self-test lib-depot.dossier_git =="
D_CLONE=$(dossier_git "$TMP/clone")
D_WT=$(dossier_git "$TMP/wt")
[ -d "$D_CLONE" ]; check "clone : un répertoire" $?
[ -f "$TMP/wt/.git" ]; check "worktree : .git y est bien un FICHIER (le cas qui échouait)" $?
[ -d "$D_WT" ]; check "worktree : dossier_git rend un répertoire" $?
[ "$D_WT" != "$D_CLONE" ]; check "worktree : son propre répertoire, pas celui du clone" $?
( : > "$D_WT/rejeu-ci.ok" ) 2>/dev/null; check "worktree : une trace s'y écrit" $?
D_HORS=$(dossier_git "$TMP"); r=$?
[ -z "$D_HORS" ] && [ "$r" != 0 ]; check "hors dépôt : chemin vide et code d'échec, jamais « .git »" $?

#  ── La trace du rejeu, liée à l'arbre (#2245) — sur un VRAI historique réécrit ──
echo "== self-test trace du rejeu : le sha change, l'arbre non =="
. "$(dirname "$0")/lib-verdicts-mep.sh"
G="git -C $TMP/clone -c user.name=t -c user.email=t@t"
echo un > "$TMP/clone/f.txt"; $G add f.txt; $G commit -q -m "wip: brouillon"
SHA_AVANT=$($G rev-parse HEAD); ARBRE_AVANT=$($G rev-parse 'HEAD^{tree}')
trace_rejeu_ecrire "$TMP/trace" "$SHA_AVANT" 1700000000 185 0 0 2 1 "$ARBRE_AVANT"
trace_rejeu_lire "$TMP/trace"
[ "$R_SHA" = "$SHA_AVANT" ] && [ "$R_OK" = 185 ] && [ "$R_FAIL" = 0 ] && [ "$R_INC" = 0 ] \
    && [ "$R_SAUTS" = 2 ] && [ "$R_REL" = 1 ] && [ "$R_TREE" = "$ARBRE_AVANT" ]
check "trace : ce qui est écrit se relit, champ par champ" $?
v() {  # verdict du point 16 pour la trace lue, devant le HEAD courant
    verdict_rejeu_ci "$R_SHA" "$($G rev-parse HEAD)" "$R_FAIL" "$R_INC" "$R_TREE" "$($G rev-parse 'HEAD^{tree}')"
}
[ "$(v)" = OK ]; check "même commit → OK" $?
#  Le cas du 25/10/2026 : un commit « wip: » réécrit en « feat: », contenu inchangé.
$G commit -q --amend -m "feat: livré"
[ "$($G rev-parse HEAD)" != "$SHA_AVANT" ]; check "reword : le sha a bien changé" $?
[ "$(v)" = OK ]; check "reword à arbre identique → OK, pas de rejeu perdu" $?
SHA_REWORD=$($G rev-parse HEAD)
#  Tout changement de contenu invalide la trace, comme avant.
echo deux >> "$TMP/clone/f.txt"; $G commit -q -a -m "fix: autre contenu"
[ "$(v)" = INCONNU ]; check "contenu modifié → INCONNU" $?
#  Une trace d'avant #2245 (sans TREE) ne vaut que pour son sha.
printf '%s 1700000000 OK=185 FAIL=0 INCONNU=0 SAUTS=2 RELANCES=1\n' "$SHA_AVANT" > "$TMP/ancienne"
trace_rejeu_lire "$TMP/ancienne"
[ -z "$R_TREE" ] && [ "$R_REL" = 1 ]; check "ancienne trace : arbre vide, le reste se relit" $?
#  On revient au commit reword : même arbre que la trace, autre sha — mais la trace n'a pas d'arbre à comparer.
$G checkout -q --detach "$SHA_REWORD"
[ "$(v)" = INCONNU ]; check "ancienne trace, autre sha → INCONNU (jamais OK sans arbre)" $?
trace_rejeu_lire "$TMP/absente"
[ -z "$R_SHA" ] && [ "$R_OK" = "?" ]; check "trace absente : vide, jamais un sha inventé" $?

[ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
exit $fail
