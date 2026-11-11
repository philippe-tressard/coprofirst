#!/bin/bash
# =============================================================================
#  lib-precheck-pr.sh — l'état du dépôt GITHUB vu par le pré-check :
#    23 — aucune PR ouverte vers `main` hors de `dev` (#1870)
#    24 — aucune alerte Dependabot haute ou critique ouverte (#2148)
#    25 — chaque règle d'affichage que le front calcule encore est portée par
#         un ticket OUVERT (#2633)
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
#  Point 24 : deux alertes hautes ont dormi deux jours le 22/10/2026, sans PR ni
#  ticket. FAIL, sauf si le lot modifie le manifeste qu'elles nomment, ou si le
#  graphe de dépendances de `main` ne porte plus que des versions corrigées —
#  l'alerte attend alors la ré-analyse de Dependabot (ÉCART, #2180) —
#  décision `verdict_alertes`, même script, même autotest.
#
#  Point 25 : neuf dérogations de `check-regles-partagees.regles.mjs` sont restées
#  portées par deux tickets fermés (#2511, #2507) — la dette n'avait plus de
#  porteur, et `lint`, hors ligne, ne juge que la forme `#NNNN`. FAIL qui nomme le
#  porteur fermé et ses règles ; GitHub muet, INCONNU. Décision et autotest :
#  `front/scripts/check-regles-partagees.mjs --tickets` (`verdictPorteurs`).
#
#  Sourcé par `scripts/poste/precheck-mep.sh`, qui fournit `rapporter`.
# =============================================================================

#  _point_github <n°> <libellé> <option> <verdicts admis> — une ligne du script.
_point_github() {
  local sortie verdict detail
  if ! command -v python >/dev/null 2>&1; then
    rapporter "$1" INCONNU "$2" "python absent du poste"
    return
  fi
  sortie=$(python "$RACINE_DEPOT/scripts/poste/reprendre-dependabot.py" "$3" 2>/dev/null | tail -1)
  verdict="${sortie%% *}"
  detail="${sortie#* }"
  case " $4 " in *" $verdict "*) ;; *) verdict=INCONNU; detail="vérificateur muet" ;; esac
  rapporter "$1" "$verdict" "$2" "$detail"
}

precheck_point_pr() {
  _point_github 23 "Aucune PR vers main hors de dev" --verifier "OK ECART INCONNU"
}

precheck_point_alertes() {
  _point_github 24 "Aucune alerte de sécurité haute ouverte" --alertes "OK ECART FAIL INCONNU"
}

precheck_point_porteurs() {
  local libelle="Dérogations des règles partagées portées par un ticket ouvert" sortie verdict
  if ! command -v node >/dev/null 2>&1; then
    rapporter 25 INCONNU "$libelle" "node absent du poste"
    return
  fi
  sortie=$(node "$RACINE_DEPOT/front/scripts/check-regles-partagees.mjs" --tickets 2>/dev/null | tail -1)
  verdict="${sortie%% *}"
  case "$verdict" in OK|FAIL|INCONNU) ;; *) verdict=INCONNU; sortie="x vérificateur muet" ;; esac
  rapporter 25 "$verdict" "$libelle" "${sortie#* }"
}
