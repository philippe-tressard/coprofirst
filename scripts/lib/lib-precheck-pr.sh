#!/bin/bash
# =============================================================================
#  lib-precheck-pr.sh — point 23 du pré-check : aucune PR ouverte vers `main`
#  hors de `dev` (#1870)
#
#  Chaque MEP supprime `dev` (squash + `delete_branch_on_merge`) ; GitHub
#  réoriente alors vers `main` les PR qui la visaient — Dependabot compris, sept
#  le 12/10/2026. Une PR verte vers `main` se fusionne d'un clic et se déploie
#  sans pré-check. Le point tourne AUSSI en `--post-mep` : c'est la fusion qui
#  les réoriente, le post-check est donc le premier à pouvoir les voir.
#
#  La décision vit dans `scripts/poste/reprendre-dependabot.py --verifier`
#  (pure, self-testée) — le même script qui les reprend. Une PR réorientée rend
#  ÉCART : elle ne fausse pas la MEP en cours, elle en menace la suivante.
#
#  Sourcé par `scripts/poste/precheck-mep.sh`, qui fournit `rapporter`.
# =============================================================================

precheck_point_pr() {
  local sortie verdict detail
  if ! command -v python >/dev/null 2>&1; then
    rapporter 23 INCONNU "Aucune PR vers main hors de dev" "python absent du poste"
    return
  fi
  sortie=$(python "$RACINE_DEPOT/scripts/poste/reprendre-dependabot.py" --verifier 2>/dev/null | tail -1)
  verdict="${sortie%% *}"
  detail="${sortie#* }"
  case "$verdict" in OK|ECART|INCONNU) ;; *) verdict=INCONNU; detail="vérificateur muet" ;; esac
  rapporter 23 "$verdict" "Aucune PR vers main hors de dev" "$detail"
}
