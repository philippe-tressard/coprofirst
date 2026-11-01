#!/usr/bin/env bash
# =============================================================================
#  SSH entre les nœuds — la confiance s'épingle, et s'écrit à UN endroit.
#
#  🔴 #1598 (audit du 02/10/2026) : cinq scripts d'exploitation recopiaient
#  `ssh -i /root/.ssh/id_ed25519_bascule … -o StrictHostKeyChecking=no`. La clé
#  dédiée authentifie le client, jamais le serveur : un hôte qui prenait l'IP du
#  pair recevait la connexion — et, pour la bascule, la base répliquée. Les cinq
#  passent désormais par `scripts/lib/lib-ssh-noeuds.sh` (`ssh_noeud_cmd`).
#
#  Ce contrôle refuse :
#    1. `StrictHostKeyChecking` à `no`, sous toutes ses graphies (`=no`, ` no`,
#       `"no"`), dans un script, un hook ou une procédure documentée — une
#       procédure copiée dans un terminal est un script ;
#    2. la clé dédiée nommée hors du module : une sixième copie de la commande
#       reviendrait avec ses propres options, et c'est ainsi que `no` s'était
#       recopié cinq fois ;
#    3. et le CAS ZÉRO (`standards/04` §2) : le module doit toujours porter
#       `StrictHostKeyChecking=yes`, sans quoi les deux règles ci-dessus seraient
#       vertes le jour où plus personne n'épingle rien.
#
#  Une ligne de COMMENTAIRE d'un script n'est pas jugée : l'historique se raconte
#  (ce fichier-ci le fait). Une ligne de Markdown l'est toujours — `#` y fait un
#  titre, et un bloc de code n'y a pas de commentaire.
#
#  Usage : bash scripts-ci-ssh-noeuds.sh               (l'arbre de travail)
#          bash scripts-ci-ssh-noeuds.sh <révision>    (ex. origin/main)
#          bash scripts-ci-ssh-noeuds.sh --selftest
# =============================================================================
set -uo pipefail
# shellcheck source=../lib/lib-poste-gnu.sh
. "$(dirname "$0")/../lib/lib-poste-gnu.sh"
poste_gnu_poser   # macOS : les outils GNU en tête du PATH, comme Git Bash et la CI (#2419)
MODULE=scripts/lib/lib-ssh-noeuds.sh
#  Ce fichier-ci porte, dans son auto-test, les lignes qu'il refuse : seule
#  exception, et elle est déclarée.
CE_FICHIER=scripts/poste/scripts-ci-ssh-noeuds.sh

#  Lit des lignes « chemin:numéro:contenu » (la sortie de `git grep -n`) et rend
#  celles qui enfreignent les règles 1 et 2. Fonction PURE : l'auto-test
#  l'exerce sans dépôt.
ecarts_ssh() {
  local chemin num contenu
  while IFS=: read -r chemin num contenu; do
    case "$chemin" in
      "$CE_FICHIER") continue ;;
      *.md) ;;
      *) [[ "$contenu" =~ ^[[:space:]]*# ]] && continue ;;
    esac
    if [[ "$contenu" =~ StrictHostKeyChecking[[:space:]=]+\"?[Nn][Oo]([^A-Za-z0-9_-]|$) ]]; then
      echo "  $chemin:$num : StrictHostKeyChecking=no — un hôte usurpé serait accepté à chaque connexion (épingler : $MODULE)"
    fi
    if [[ "$contenu" == *id_ed25519_bascule* && "$chemin" != "$MODULE" && "$chemin" != *.md ]]; then
      echo "  $chemin:$num : clé inter-nœuds nommée hors de $MODULE — employer \`ssh_noeud_cmd\`"
    fi
  done
  return 0
}

if [ "${1:-}" = "--selftest" ]; then
  st=0
  t() { r=$(printf '%s\n' "$2" | ecarts_ssh); [ "$r" = "$3" ] && echo "PASS  $1" \
        || { echo "FAIL  $1  attendu=[$3] obtenu=[$r]"; st=1; }; }
  E1=" : StrictHostKeyChecking=no — un hôte usurpé serait accepté à chaque connexion (épingler : $MODULE)"
  E2=" : clé inter-nœuds nommée hors de $MODULE — employer \`ssh_noeud_cmd\`"
  #  La ligne exacte d'avant #1598 : DEUX écarts, la confiance et la copie.
  t "la ligne d'origine de bascule.sh" \
    'scripts/exploitation/bascule.sh:88:SSH_CMD="ssh -i /root/.ssh/id_ed25519_bascule -o BatchMode=yes -o StrictHostKeyChecking=no"' \
    "  scripts/exploitation/bascule.sh:88$E1
  scripts/exploitation/bascule.sh:88$E2"
  t "graphie de ssh_config (espace)"   'docs/a.md:84:    StrictHostKeyChecking no'      "  docs/a.md:84$E1"
  t "graphie entre guillemets"         'x.sh:1:ssh -o StrictHostKeyChecking="no" h'   "  x.sh:1$E1"
  t "casse indifférente"               'x.sh:1:ssh -o StrictHostKeyChecking=No h'     "  x.sh:1$E1"
  t "yes accepté"                      'x.sh:1:ssh -o StrictHostKeyChecking=yes h'    ""
  t "accept-new n'est pas no"          'x.sh:1:ssh -o StrictHostKeyChecking=accept-new h' ""
  t "commentaire de script non jugé"   'x.sh:1:  # StrictHostKeyChecking=no était recopié' ""
  t "titre Markdown jugé quand même"   'd.md:1:# StrictHostKeyChecking=no'           "  d.md:1$E1"
  t "le module nomme la clé"           "$MODULE:40:SSH_NOEUDS_CLE=/root/.ssh/id_ed25519_bascule" ""
  t "une procédure nomme la clé"       'docs/r.md:9:sudo ssh-keygen -f /root/.ssh/id_ed25519_bascule' ""
  t "une sixième copie de la commande" 'scripts/x.sh:3:ssh -i /root/.ssh/id_ed25519_bascule h' "  scripts/x.sh:3$E2"
  t "aucune ligne → aucun écart"       ''                                             ""
  #  Vécu à la première exécution sur l'arbre committé : le contrôle se
  #  refusait lui-même, sur les lignes de son propre auto-test.
  t "le contrôle et son auto-test"     "$CE_FICHIER:9:ssh -i /root/.ssh/id_ed25519_bascule -o StrictHostKeyChecking=no" ""
  exit $st
fi

REV=${1:-}
#  `git grep <rév>` préfixe chaque ligne par « <rév>: » : on le retire pour que
#  les chemins se lisent de la même façon dans les deux modes.
lignes=$(git grep -nIE 'StrictHostKeyChecking|id_ed25519_bascule' ${REV:+"$REV"} \
           -- '*.sh' '*.md' '.githooks/*' 'infra/*' | sed "s|^${REV:+$REV:}||")
ecarts=$(printf '%s\n' "$lignes" | ecarts_ssh)
module=$(if [ -n "$REV" ]; then git show "$REV:$MODULE" 2>/dev/null; else cat "$MODULE" 2>/dev/null; fi)
case "$module" in
  *StrictHostKeyChecking=yes*) ;;
  *) ecarts="$ecarts
  $MODULE : absent ou sans StrictHostKeyChecking=yes — les règles ci-dessus ne mesurent plus rien" ;;
esac
ecarts=$(printf '%s\n' "$ecarts" | sed '/^$/d')
if [ -n "$ecarts" ]; then
  echo "❌ SSH entre les nœuds : confiance non épinglée ou commande recopiée (#1598)"
  printf '%s\n' "$ecarts"
  exit 1
fi
echo "✅ SSH entre les nœuds : confiance épinglée, commande écrite dans $MODULE seulement."
