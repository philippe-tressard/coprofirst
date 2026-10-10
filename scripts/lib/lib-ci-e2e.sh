#!/bin/bash
# =============================================================================
#  lib-ci-e2e.sh — Ce que le rejeu décide pour les tests de NAVIGATEUR
#
#  Module SOURCÉ par `lib-ci-replay.sh`, jamais exécuté (pas de bit x). Ses cas
#  d'autotest (`ci_e2e_cas`) tournent dans `rejouer-ci.sh --selftest`, avec le
#  `t` de `ci_replay_selftest`.
#
#  Extrait de `lib-ci-replay.sh` le 10/10/2026 (#1809), quand la règle de
#  relance l'aurait fait passer au-dessus de 500 lignes : ces fonctions-là ne
#  lisent pas `ci.yml`, elles disent comment le POSTE peut servir les e2e.
#  Fonctions pures : texte en entrée, texte en sortie.
# =============================================================================

# ── Combien de workers e2e sur un poste occupé ? (#1665, 04/10/2026) ─────────
#  Trois rejeux complets de suite sont tombés sur les MÊMES quatre specs
#  d'administration, la machine prise à ~55 % par d'autres sessions : hydratation
#  médiane 2,9 s contre 0,8 s, pour des attentes de 5 s. La suite entière passait
#  à 335/335 avec `--workers=1`, et la CI GitHub — au repos — était verte. Ce
#  n'était pas le code mais la contention entre workers. La charge se mesure
#  AVANT le rejeu : c'est celle des autres, pas la nôtre. (PURE)
#    $1 = valeur imposée par qui lance (E2E_WORKERS), $2 = charge CPU en %
#    (vide si non mesurable), $3 = seuil en % → nombre de workers, ou vide
#    (le défaut de Playwright, celui de la CI).
ci_workers_e2e() {
  [ -n "${1:-}" ] && { echo "$1"; return; }
  #  Charge inconnue → le défaut : ne pas mesurer n'autorise pas à brider.
  case "${2:-}" in ''|*[!0-9]*) echo ""; return ;; esac
  [ "$2" -ge "$3" ] && echo 1 || echo ""
}

# ── Les e2e peuvent-ils se fier au node_modules du worktree ? (#1722) ────────
#  Un worktree dont `front/node_modules` est une JONCTION vers celui du clone
#  principal partage aussi le cache d'optimisation de Vite (`node_modules/.vite`).
#  Qu'une autre session lance Vite, et les e2e tombent au hasard — « Failed to
#  fetch dynamically imported module … app.js », hydratation à 10 s —, un spec
#  DIFFÉRENT à chaque passage, vert isolé. Écrit en mémoire le 03/10, revenu le
#  07/10 : trois rejeux rouges pour #1718. Le lot n'y est pour rien : INCONNU,
#  jamais FAIL. (PURE)
#    $1 = lien | repertoire | absent → "" (mesurable) | motif d'INCONNU
#    `absent` est laissé à l'étape elle-même, qui dit déjà « non installé ».
ci_node_modules_etat() {
  case "${1:-}" in
    repertoire|absent) echo "" ;;
    lien) echo "node_modules partagé par jonction : le cache de Vite l'est aussi (#1722)" ;;
    *)    echo "node_modules non examiné : son genre est illisible" ;;
  esac
}

#  Une étape SERT-elle l'application par Vite ? Ce sont les tests de navigateur :
#  `npm run e2e` dans ci.yml, `playwright test` s'il était appelé en direct. Le
#  mot « playwright » seul ne suffit pas — il désigne aussi l'INSTALLATION des
#  navigateurs, qui n'est jamais rejouée : un premier jet le prenait pour critère
#  et n'attrapait donc rien. (PURE) Corps sur stdin → oui | non
ci_sert_par_vite() {
  grep -v '^[[:space:]]*#' | grep -Eq '(^|[^[:alnum:]_:-])(npm run e2e([^[:alnum:]:_-]|$)|playwright test)'     && echo oui || echo non
}

# ── Relancer les tests tombés sur l'import dynamique de Vite ? (#1809) ───────
#  « Failed to fetch dynamically imported module …/generated/client/app.js » :
#  le module d'entrée de SvelteKit n'a pas pu être chargé. Trois causes l'ont
#  déjà produit et sont fermées — jonction de node_modules (#1722), Vite sur
#  `::1` seul (#1732), contention des workers (#1665) — et il revient : quatre
#  rejeux le 10/10/2026, un seul test chaque fois, un autre à chaque passage,
#  vert sur l'autre profil, jamais vu par la CI GitHub. Un rejeu complet coûte
#  20 à 25 min sous un verrou que d'autres sessions attendent.
#  D'où une relance UNIQUE des seuls tests tombés, à quatre conditions : l'étape
#  sert par Vite, sa sortie porte cette signature et non celle d'un rechargement
#  (#1421), et au plus `$3` tests sont tombés — au-delà ce n'est plus un hasard. Elle est NOMMÉE sur la ligne de
#  l'étape et JOURNALISÉE (date, charge, tests) : c'est la mesure qui manquait
#  pour trouver la cause. Un vrai défaut retombe à la relance. La CI GitHub,
#  elle, garde `retries: 0`. (PURE)
#    $1 = code de l'étape · $2 = sert par Vite oui|non · $3 = plafond de tests
#    sortie Playwright sur stdin → oui | non
CI_SIGNATURE_IMPORT_VITE='Failed to fetch dynamically imported module'
ci_relance_e2e() {
  local sortie n
  sortie=$(cat)
  [ "${1:-0}" != 0 ] && [ "${2:-}" = oui ] || { echo non; return; }
  printf '%s\n' "$sortie" | grep -qF "$CI_SIGNATURE_IMPORT_VITE" || { echo non; return; }
  #  Un rechargement de Vite pendant les tests a SA règle (#1421) : l'étape
  #  échoue en nommant la dépendance. La relance ne la contourne jamais.
  printf '%s\n' "$sortie" | grep -q "optimized dependencies changed" && { echo non; return; }
  n=$(printf '%s\n' "$sortie" | ci_tests_tombes | grep -c .)
  #  Le cas zéro : un bilan illisible (aucun test nommé) n'autorise rien.
  [ "$n" -ge 1 ] && [ "$n" -le "${3:-0}" ] && echo oui || echo non
}
#  Les tests tombés, tels que le bilan de Playwright les nomme — « [projet] ›
#  fichier:ligne › titre », sous la ligne « N failed ». (PURE) stdin → une ligne par test
ci_tests_tombes() {
  awk '/^[[:space:]]*[0-9]+ failed[[:space:]]*$/ { f = 1; next }
       f && /^[[:space:]]+\[/ { sub(/^[[:space:]]+/, ""); print; next }
       { f = 0 }'
}

# ── Cas d'autotest — appelés par `ci_replay_selftest`, avec son `t` ─────────
ci_e2e_cas() {
  t "workers — poste au repos : défaut"      "$(ci_workers_e2e "" 12 30)" ""
  t "workers — poste occupé : un seul"       "$(ci_workers_e2e "" 55 30)" "1"
  t "workers — au seuil : un seul"           "$(ci_workers_e2e "" 30 30)" "1"
  t "workers — imposé : il prime"            "$(ci_workers_e2e 3 90 30)" "3"
  #  🔴 Le cas zéro : une charge non mesurée ne bride pas en silence.
  t "workers — charge inconnue : défaut"     "$(ci_workers_e2e "" "" 30)" ""
  t "workers — charge illisible : défaut"    "$(ci_workers_e2e "" "n/a" 30)" ""

  t "node_modules — propre au worktree : mesurable" "$(ci_node_modules_etat repertoire)" ""
  t "node_modules — absent : laissé au contrôle de l'étape" "$(ci_node_modules_etat absent)" ""
  t "node_modules — jonction partagée : INCONNU nommé"     "$(ci_node_modules_etat lien)"     "node_modules partagé par jonction : le cache de Vite l'est aussi (#1722)"
  t "Vite — les tests de navigateur"       "$(printf 'npm run e2e 2>&1 | tee x.log
' | ci_sert_par_vite)" "oui"
  t "Vite — playwright appelé en direct"   "$(printf 'npx playwright test
' | ci_sert_par_vite)" "oui"
  t "Vite — l'installation n'en est pas"   "$(printf 'npx playwright install --with-deps chromium
' | ci_sert_par_vite)" "non"
  t "Vite — un lint voisin n'en est pas"   "$(printf 'npm run lint:e2e-serveur
' | ci_sert_par_vite)" "non"
  t "Vite — un commentaire n'en est pas"   "$(printf '# npm run e2e
npm run build
' | ci_sert_par_vite)" "non"
  #  🔴 Le cas zéro : un genre que personne n'a su lire n'autorise pas les e2e.
  t "node_modules — genre inconnu : INCONNU"     "$(ci_node_modules_etat '')" "node_modules non examiné : son genre est illisible"

  #  #1809 — la relance : nommée, bornée, et jamais sur un défaut ordinaire.
  local b='Running 4 tests using 1 worker
  ✓  1 [bureau] › e2e/a.spec.ts:3:1 › a (1.2s)
  ✘  2 [bureau] › e2e/pied.spec.ts:12:1 › la version est courte (3.1s)
    Error: page error: TypeError: Failed to fetch dynamically imported module: http://127.0.0.1:5392/@fs/C:/Dev/x/front/.svelte-kit/generated/client/app.js
  1 failed
    [bureau] › e2e/pied.spec.ts:12:1 › la version est courte
  3 passed (10.2s)
'
  t "relance — signature, un test : oui"       "$(ci_relance_e2e 1 oui 3 <<< "$b")" "oui"
  t "relance — les tests tombés, nommés"       "$(ci_tests_tombes <<< "$b")" "[bureau] › e2e/pied.spec.ts:12:1 › la version est courte"
  t "relance — étape verte : non"              "$(ci_relance_e2e 0 oui 3 <<< "$b")" "non"
  t "relance — étape hors Vite : non"          "$(ci_relance_e2e 1 non 3 <<< "$b")" "non"
  t "relance — plus de tests que le plafond"   "$(ci_relance_e2e 1 oui 0 <<< "$b")" "non"
  t "relance — un échec ordinaire : non" \
    "$(ci_relance_e2e 1 oui 3 <<< "${b//Failed to fetch dynamically imported module/expect(received).toBe}")" "non"
  t "relance — Vite a rechargé (#1421) : non" \
    "$(ci_relance_e2e 1 oui 3 <<< "$b"$'\n[WebServer] optimized dependencies changed. reloading')" "non"
  #  🔴 Le cas zéro : la signature sans bilan lisible n'autorise rien.
  t "relance — aucun test nommé : non"         "$(ci_relance_e2e 1 oui 3 <<< "$CI_SIGNATURE_IMPORT_VITE")" "non"
}
