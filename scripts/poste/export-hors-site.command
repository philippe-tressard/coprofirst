#!/bin/bash
# =============================================================================
#  export-hors-site.command — Lanceur macOS de la copie hors site des sauvegardes
#
#  Double-cliquer ce fichier (ou le lien posé sur le Bureau). Comme
#  export-hors-site.cmd pour Windows, il ne fait que confier le travail à
#  export-hors-site.sh, qui porte toute la logique — destination comprise :
#  aucune règle métier ici, sinon il y en aurait deux à maintenir.
#
#  La pause finale garde le résumé à l'écran : une fenêtre qui se referme ne
#  rend aucun compte, et c'est tout l'intérêt d'un lancement manuel.
# =============================================================================
#  Le lien du Bureau donne son propre chemin : le suivre jusqu'au dépôt.
ICI="$(cd "$(dirname "$(readlink "${BASH_SOURCE[0]}" || echo "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ICI/../.." || exit 1
bash ./scripts/poste/export-hors-site.sh
echo
read -r -p "Entrée pour fermer…" _
