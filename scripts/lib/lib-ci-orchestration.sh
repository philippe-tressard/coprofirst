#!/bin/bash
# =============================================================================
#  lib-ci-orchestration.sh — DANS QUEL ORDRE, et côte à côte, le rejeu joue la CI
#
#  Module SOURCÉ par `lib-ci-replay.sh`, jamais exécuté (pas de bit x). Ses cas
#  d'autotest (`ci_orchestration_cas`) tournent dans `rejouer-ci.sh --selftest`.
#
#  POURQUOI (#2224, 24/10/2026). Le rejeu jouait les 182 étapes une par une,
#  dans l'ordre du fichier, quand la CI GitHub fait tourner ses jobs côte à côte.
#  Mesuré sur un rejeu vert de 44 min : 166 étapes durent ≤ 10 s, et quatre
#  seules prennent 35 min (pytest 25). Un rouge de Modularité (31 s) sortait
#  après 9 à 31 min, rangé derrière pytest ; un rouge d'ESLint après 22 min.
#
#  TROIS RÈGLES, et aucune liste recopiée de `ci.yml` :
#   - PHASES : une étape est LENTE si sa durée MESURÉE au rejeu précédent
#     atteint le seuil — jamais parce qu'un nom figure dans une liste. Dans un
#     job dont les étapes s'enchaînent, tout ce qui suit une lente l'est aussi :
#     une étape peut lire ce qu'une précédente a produit (`lint:csp` lit le
#     `build`), et la phase rapide ne doit pas la faire passer devant ;
#   - COULOIRS : les étapes d'un job s'enchaînent comme sur GitHub, dans un même
#     couloir ; deux couloirs tournent en même temps. Les seules exceptions sont
#     DÉCLARÉES ci-dessous, avec leur raison ;
#   - PRIORITÉ : parmi les étapes prêtes, celle dont le couloir a le plus de
#     travail devant lui part d'abord — c'est le chemin le plus long qui fixe
#     la durée d'une phase.
#  Fonctions pures : texte en entrée, texte en sortie.
# =============================================================================

#: Seuil (s) au-delà duquel une étape mesurée est LENTE. 60 s : les quatre
#: étapes de 3 à 25 min, et aucune des 178 autres (la plus longue : 31 s).
CI_SEUIL_LENTE=60

#: Durée prêtée à une étape jamais mesurée — un lint ordinaire.
CI_DUREE_INCONNUE=5

#: Jobs dont les étapes ne s'attendent pas : chacune LIT le dépôt et n'écrit
#: rien que la suivante lirait (scans, `bash -n`, self-tests sur `mktemp`).
#: Chaque étape y a donc son propre couloir.
CI_JOBS_ETAPES_INDEPENDANTES="test-scripts"

#: Jobs qui partagent le couloir d'un autre, `job:hôte`. Les tests de navigateur
#: servent le front par Vite, qui RÉÉCRIT `front/.svelte-kit` et
#: `node_modules/.vite` — ce que `npm run check` et `npm run build` écrivent
#: aussi : côte à côte, l'un lirait les fichiers de l'autre à moitié écrits.
CI_COULOIRS_PARTAGES="e2e-frontend:build-frontend"

#  Le couloir d'une étape. (PURE) $1 = job, $2 = idx → nom du couloir
ci_couloir() {
  case " $CI_JOBS_ETAPES_INDEPENDANTES " in *" $1 "*) echo "$1#$2"; return ;; esac
  local paire
  for paire in $CI_COULOIRS_PARTAGES; do
    [ "${paire%%:*}" = "$1" ] && { echo "${paire#*:}"; return; }
  done
  echo "$1"
}

#  Le PLAN d'un rejeu. (PURE)
#    $1 = seuil (s), $2 = fichier des étapes à REPRENDRE (`job<TAB>étape`, une
#    par ligne ; vide ou absent : aucune reprise)
#    stdin : les étapes à exécuter, dans l'ordre de ci.yml —
#            `idx<TAB>job<TAB>étape<TAB>durée mesurée (vide si jamais)`
#    stdout : `phase<TAB>idx<TAB>couloir<TAB>précédent<TAB>reste`, dans l'ordre
#             où l'ordonnanceur doit les considérer : phase (reprise, rapide,
#             lente), puis le reste du couloir décroissant, puis l'idx.
#    `précédent` : l'étape du même couloir qui doit être finie avant celle-ci
#    (`-` sinon) — dans un couloir, l'ordre de ci.yml est aussi celui des
#    phases : la reprise en est un début, et rien ne suit une lente que de lent.
#    `reste` : la durée estimée de ce qui reste à faire dans le couloir ET la
#    phase, celle-ci comprise.
#
#  REPRISE : une étape rouge du rejeu précédent repart en tête — et, dans un
#  couloir qui s'enchaîne, avec TOUT ce qui la précède dans son couloir : rejouer
#  `lint:csp` seul le jugerait sur le `build` du rejeu précédent.
ci_plan() {
  local seuil="$1" reprendre="${2:-}" idx job etape duree
  while IFS=$'\t' read -r idx job etape duree; do
    [ -z "$idx" ] && continue
    printf '%s\t%s\t%s\t%s\t%s\n' "$idx" "$job" "$etape" "$duree" "$(ci_couloir "$job" "$idx")"
  done | awk -F'\t' -v OFS='\t' -v seuil="$seuil" -v defaut="$CI_DUREE_INCONNUE" '
    #  `lu` passe à 1 entre les deux fichiers (affectation sur la ligne de
    #  commande) : `FNR == NR` confondrait un fichier de rouges VIDE avec le flux.
    !lu { if ($0 != "") rouge[$1 "\t" $2] = 1; next }
    {
      n++; idx[n] = $1; job[n] = $2; cle[n] = $2 "\t" $3; c[n] = $5
      d[n] = ($4 == "" ? defaut : $4 + 0); mesure[n] = ($4 != "")
      enchaine[n] = (index($5, "#") == 0)
    }
    END {
      #  1. La reprise : les rouges, et ce qui les précède dans un couloir enchaîné.
      for (i = n; i >= 1; i--) {
        if (cle[i] in rouge) { ph[i] = "reprise"; if (enchaine[i]) tire[c[i]] = 1 }
        else if (tire[c[i]]) ph[i] = "reprise"
      }
      #  2. Lente : mesurée au-dessus du seuil, ou après une lente du même couloir.
      for (i = 1; i <= n; i++) {
        if (ph[i] == "reprise") continue
        if ((mesure[i] && d[i] >= seuil) || lente_vue[c[i]]) { ph[i] = "lente"; lente_vue[c[i]] = 1 }
        else ph[i] = "rapide"
      }
      #  3. Le précédent dans le COULOIR, quelle que soit sa phase — une lente
      #  anticipée attend la fin de la rapide qui la précède (pytest attend
      #  « Licences tierces ») ; le reste, dans le couloir ET la phase.
      for (i = 1; i <= n; i++) {
        prec[i] = (c[i] in dernier) ? dernier[c[i]] : "-"
        dernier[c[i]] = idx[i]
      }
      for (i = n; i >= 1; i--) { k = ph[i] SUBSEP c[i]; somme[k] += d[i]; reste[i] = somme[k] }
      rang["reprise"] = 1; rang["rapide"] = 2; rang["lente"] = 3
      for (i = 1; i <= n; i++) print rang[ph[i]], ph[i], idx[i], c[i], prec[i], reste[i]
    }
  ' "${reprendre:-/dev/null}" lu=1 - \
    | sort -t$'\t' -k1,1n -k6,6nr -k3,3n | cut -f2-
}

#  Combien d'étapes côte à côte ? (PURE) Le poste porte souvent d'autres
#  sessions : le budget part des cœurs LIBRES, mesurés avant le rejeu, à raison
#  de quatre par étape — un lint lance node, un scan des dizaines de processus.
#  Borné à 8 : au-delà, Windows passe son temps à créer des processus.
#    $1 = imposé (REJEU_PARALLELE), $2 = cœurs logiques, $3 = charge en % (vide :
#    non mesurée) → un entier ≥ 1
ci_budget_parallele() {
  case "${1:-}" in ''|*[!0-9]*) ;; 0) echo 1; return ;; *) echo "$1"; return ;; esac
  case "${2:-}" in ''|*[!0-9]*) echo 2; return ;; esac
  local charge="${3:-}"
  case "$charge" in ''|*[!0-9]*) charge=50 ;; esac   # non mesurée : prudence, pas l'optimisme
  local libres=$(( $2 * (100 - charge) / 100 / 4 ))
  [ "$libres" -lt 1 ] && libres=1
  [ "$libres" -gt 8 ] && libres=8
  echo "$libres"
}

#  Après une phase, continue-t-on ? (PURE) Un rouge arrête le rejeu AVANT la
#  phase suivante — tous les rouges de la phase finie sont déjà là, et une
#  phase lente de 25 min ne changerait rien au verdict. `--tout` joue tout.
#    $1 = nombre d'échecs de la phase, $2 = tout oui|non → continuer | arreter
ci_suite_apres_phase() {
  [ "${1:-0}" -gt 0 ] && [ "${2:-non}" != oui ] && echo arreter || echo continuer
}

#  Les rouges du rejeu précédent valent-ils pour CE lot ? (PURE) Même lot :
#  le SHA d'alors est un ancêtre de HEAD (on a corrigé par-dessus), ou la
#  branche est la même (on a rebasé, les SHA ont changé).
#    $1 = branche d'alors, $2 = branche courante, $3 = ancêtre oui|non → oui | non
ci_reprise_valable() {
  [ "${3:-non}" = oui ] && { echo oui; return; }
  [ -n "${1:-}" ] && [ "$1" != HEAD ] && [ "$1" = "${2:-}" ] && echo oui || echo non
}

#  Les durées connues, mises à jour par celles d'un rejeu. (PURE)
#    $1 = durées connues, $2 = durées mesurées — `job<TAB>étape<TAB>s` → fusion
ci_durees_fusionner() {
  awk -F'\t' -v OFS='\t' 'NF == 3 { d[$1 "\t" $2] = $3 } END { for (k in d) print k, d[k] }' \
    "${1:-/dev/null}" "${2:-/dev/null}" | sort
}

#  Les rouges que la prochaine `--reprendre` rejouera en tête. (PURE) Un rejeu
#  partiel ne doit pas effacer les rouges des jobs qu'il n'a pas joués.
#    $1 = rouges d'avant (même lot ; sinon vide), $2 = étapes jouées ce coup-ci,
#    $3 = rouges de ce coup-ci — `job<TAB>étape` → les rouges d'avant que ce
#    rejeu n'a pas rejoués, et les siens, sans doublon
ci_rouges_fusionner() {
  #  L'en-tête (`#…`) est écarté dans awk, jamais par un `grep -v` : sur une
  #  sortie vide, celui-ci rend 1, et sous `pipefail` l'écriture qui suit
  #  sautait — les rouges reverdis restaient en tête de la reprise suivante.
  awk '/^#/ { next } f == 1 { joue[$0] = 1; next } f == 2 && !($0 in joue) { print; next } f == 3 { print }' \
    f=1 "${2:-/dev/null}" f=2 "${1:-/dev/null}" f=3 "${3:-/dev/null}" | sort -u
}

# ── Cas d'autotest — appelés par `ci_replay_selftest`, avec son `t` ─────────
ci_orchestration_cas() {
  local plan rouges
  t "couloir — un job s'enchaîne"           "$(ci_couloir lint-backend 3)" "lint-backend"
  t "couloir — étapes indépendantes"        "$(ci_couloir test-scripts 7)" "test-scripts#7"
  t "couloir — partagé (Vite réécrit .svelte-kit)" "$(ci_couloir e2e-frontend 9)" "build-frontend"

  plan=$(printf '1\tlint\tA\t2\n2\tlint\tB\t\n3\ttest\tPytest\t1500\n4\ttest\tApres\t1\n5\ttest-scripts\tScan\t200\n6\ttest-scripts\tBits\t1\n' \
    | ci_plan 60 "")
  t "plan — une lente mesurée"       "$(printf '%s\n' "$plan" | awk -F'\t' '$2==3{print $1}')" "lente"
  t "plan — ce qui suit une lente, dans un job qui s'enchaîne, l'est aussi" \
    "$(printf '%s\n' "$plan" | awk -F'\t' '$2==4{print $1}')" "lente"
  t "plan — l'indépendante qui suit une lente reste rapide" \
    "$(printf '%s\n' "$plan" | awk -F'\t' '$2==6{print $1}')" "rapide"
  t "plan — jamais mesurée : rapide" "$(printf '%s\n' "$plan" | awk -F'\t' '$2==2{print $1}')" "rapide"
  t "plan — le précédent dans le couloir" "$(printf '%s\n' "$plan" | awk -F'\t' '$2==2{print $4}')" "1"
  t "plan — premier de son couloir : sans précédent" "$(printf '%s\n' "$plan" | awk -F'\t' '$2==3{print $4}')" "-"
  t "plan — la lente qui suit une lente l'attend" "$(printf '%s\n' "$plan" | awk -F'\t' '$2==4{print $4}')" "3"
  t "plan — une lente attend la RAPIDE qui la précède (anticipation sûre)" \
    "$(printf '1\tj\tA\t2\n2\tj\tB\t900\n' | ci_plan 60 "" | awk -F'\t' '$2==2{print $1 "/" $4}')" "lente/1"
  t "plan — les rapides d'abord, le plus long couloir en tête" \
    "$(printf '%s\n' "$plan" | cut -f2 | paste -sd' ' -)" "1 2 6 3 5 4"
  #  Le cas zéro : rien à exécuter, rien de planifié — et pas d'erreur.
  t "plan — aucune étape" "$(printf '' | ci_plan 60 "")" ""

  rouges=$(mktemp)
  printf 'lint\tB\n' > "$rouges"
  plan=$(printf '1\tlint\tA\t2\n2\tlint\tB\t3\n3\tlint\tC\t1\n4\ttest-scripts\tX\t1\n' | ci_plan 60 "$rouges")
  t "reprise — le rouge et ce qui le précède dans son couloir, en tête" \
    "$(printf '%s\n' "$plan" | awk -F'\t' '$1=="reprise"{print $2}' | paste -sd' ' -)" "1 2"
  t "reprise — ce qui le suit attend la phase rapide" \
    "$(printf '%s\n' "$plan" | awk -F'\t' '$2==3{print $1}')" "rapide"
  printf 'test-scripts\tX\n' > "$rouges"
  t "reprise — une indépendante repart seule" \
    "$(printf '1\tlint\tA\t2\n4\ttest-scripts\tX\t1\n' | ci_plan 60 "$rouges" | awk -F'\t' '$1=="reprise"{print $2}')" "4"
  rm -f "$rouges"

  t "budget — imposé"                     "$(ci_budget_parallele 3 28 10)" "3"
  t "budget — imposé à 0 : en série"      "$(ci_budget_parallele 0 28 10)" "1"
  t "budget — poste libre, borné à 8"     "$(ci_budget_parallele "" 64 0)" "8"
  t "budget — 28 cœurs à 10 %"            "$(ci_budget_parallele "" 28 10)" "6"
  t "budget — poste chargé"               "$(ci_budget_parallele "" 28 90)" "1"
  #  🔴 Ne pas mesurer n'autorise pas à tout lancer.
  t "budget — charge non mesurée : prudence" "$(ci_budget_parallele "" 28 "")" "3"
  t "budget — cœurs inconnus"             "$(ci_budget_parallele "" "" 10)" "2"

  t "suite — phase verte"                 "$(ci_suite_apres_phase 0 non)" "continuer"
  t "suite — un rouge arrête"             "$(ci_suite_apres_phase 2 non)" "arreter"
  t "suite — --tout joue tout"            "$(ci_suite_apres_phase 2 oui)" "continuer"

  t "reprise valable — ancêtre"           "$(ci_reprise_valable autre ma-branche oui)" "oui"
  t "reprise valable — même branche, rebasée" "$(ci_reprise_valable ma-branche ma-branche non)" "oui"
  t "reprise valable — autre lot"         "$(ci_reprise_valable autre ma-branche non)" "non"
  t "reprise valable — tête détachée : jamais par le nom" "$(ci_reprise_valable HEAD HEAD non)" "non"

  local a b
  a=$(mktemp); b=$(mktemp)
  printf 'j\tA\t10\nj\tB\t20\n' > "$a"; printf 'j\tB\t25\nk\tC\t3\n' > "$b"
  t "durées — la mesure neuve remplace, l'ancienne reste" "$(ci_durees_fusionner "$a" "$b" | paste -sd'|' -)" \
    "j	A	10|j	B	25|k	C	3"
  t "durées — aucun fichier" "$(ci_durees_fusionner "" "")" ""
  local c
  c=$(mktemp)
  printf '#\tabc\tbranche\nj\tA\nk\tB\n' > "$a"; printf 'j\tA\nj\tC\n' > "$b"; printf 'j\tC\n' > "$c"
  t "rouges — reverdi effacé, non rejoué gardé, nouveau ajouté" \
    "$(ci_rouges_fusionner "$a" "$b" "$c" | paste -sd'|' -)" "j	C|k	B"
  t "rouges — autre lot : seuls les siens" "$(ci_rouges_fusionner "" "$b" "$c")" "j	C"
  printf '#\tabc\tbranche\nj\tA\n' > "$a"; printf 'j\tA\n' > "$b"; : > "$c"
  t "rouges — tout a reverdi : vide, et un code 0 (sous pipefail)" \
    "$(set -o pipefail; ci_rouges_fusionner "$a" "$b" "$c" && echo code0)" "code0"
  rm -f "$a" "$b" "$c"

  #  Les tables déclarées nomment des jobs qui EXISTENT : une entrée morte ne
  #  protégerait plus rien, en silence.
  if [ -f .github/workflows/ci.yml ]; then
    local jobs j morts=""
    jobs=$(ci_extraire < .github/workflows/ci.yml | awk -F'\t' '/^@@STEP/{print $2}' | sort -u)
    for j in $CI_JOBS_ETAPES_INDEPENDANTES ${CI_COULOIRS_PARTAGES//:/ }; do
      grep -qx "$j" <<<"$jobs" || morts="$morts $j"
    done
    t "tables des couloirs — chaque job nommé existe dans ci.yml" "${morts:-aucun mort}" "aucun mort"
  fi
}
