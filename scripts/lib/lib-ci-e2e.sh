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
  local _corps; _corps=$(grep -v '^[[:space:]]*#' || true)
  grep -Eq '(^|[^[:alnum:]_:-])(npm run e2e([^[:alnum:]:_-]|$)|playwright test)' <<<"$_corps" && echo oui || echo non
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
#
#  🔴 Une SECONDE cause, de la même famille (#1989, 15/10/2026) : la pile réseau
#  de Windows à court de tampons, au `goto` — `net::ERR_NO_BUFFER_SPACE`
#  (WSAENOBUFS), 1 échec sur 560, vert seul trois fois de suite, jamais vu par la
#  CI GitHub (Linux). Mêmes conditions, même journal, même plafond : chaque cause
#  se NOMME (`ci_cause_relance`), sur la ligne de l'étape et dans le journal —
#  c'est cette mesure qui dira s'il faut tarir la source (le proxy de Vite).
#    $1 = code de l'étape · $2 = sert par Vite oui|non · $3 = plafond de tests
#    sortie Playwright sur stdin → oui | non
CI_SIGNATURE_IMPORT_VITE='Failed to fetch dynamically imported module'
CI_SIGNATURE_TAMPONS='net::ERR_NO_BUFFER_SPACE'
#  La cause propre au poste que porte une sortie d'e2e, nommée — ou vide. (PURE)
ci_cause_relance() {
  local sortie
  sortie=$(cat)
  if grep -qF "$CI_SIGNATURE_IMPORT_VITE" <<< "$sortie"; then echo "import dynamique de Vite (#1809)"
  elif grep -qF "$CI_SIGNATURE_TAMPONS" <<< "$sortie"; then echo "tampons réseau de Windows (#1989)"
  fi
}
ci_relance_e2e() {
  local sortie n
  sortie=$(cat)
  [ "${1:-0}" != 0 ] && [ "${2:-}" = oui ] || { echo non; return; }
  #  🔴 `<<<`, jamais `printf … | grep -q` (#1923) : sur une sortie de plus de
  #  64 Ko, `grep -q` ferme le tube dès la signature, `printf` meurt en SIGPIPE,
  #  et le `pipefail` du rejeu fait de ce succès un échec (standards/10, SIGPIPE).
  [ -n "$(ci_cause_relance <<< "$sortie")" ] || { echo non; return; }
  #  Un rechargement de Vite pendant les tests a SA règle (#1421) : l'étape
  #  échoue en nommant la dépendance. La relance ne la contourne jamais.
  grep -q "optimized dependencies changed" <<< "$sortie" && { echo non; return; }
  n=$(ci_tests_tombes <<< "$sortie" | grep -c .)
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
  #  #1989 — la pile réseau de Windows à court de tampons, au `goto` : propre au
  #  poste comme l'import de Vite, même relance, même journal, même plafond.
  local w="${b//TypeError: Failed to fetch dynamically imported module: /page.goto: net::ERR_NO_BUFFER_SPACE at }"
  t "relance — tampons de Windows, un test : oui" "$(ci_relance_e2e 1 oui 3 <<< "$w")" "oui"
  t "cause — import de Vite"                    "$(ci_cause_relance <<< "$b")" "import dynamique de Vite (#1809)"
  t "cause — tampons réseau de Windows"         "$(ci_cause_relance <<< "$w")" "tampons réseau de Windows (#1989)"
  t "cause — échec ordinaire : aucune"          "$(ci_cause_relance <<< "expect(received).toBe")" ""
  #  🔴 Le cas zéro : la signature sans bilan lisible n'autorise rien.
  t "relance — aucun test nommé : non"         "$(ci_relance_e2e 1 oui 3 <<< "$CI_SIGNATURE_IMPORT_VITE")" "non"
  #  🔴 #1923 (13/10/2026) : une VRAIE sortie d'e2e pèse plus de 64 Ko. Lue par
  #  `printf … | grep -q`, `grep` s'arrête à la signature, `printf` prend
  #  SIGPIPE, et sous le `pipefail` du rejeu le tube rend un échec : la relance
  #  répondait « non » alors que tout la justifiait — un rejeu complet de plus.
  #  Les cas ci-dessus, de dix lignes, ne pouvaient pas le voir.
  local gros
  #  La signature EN TÊTE, puis ~280 Ko (plus de quatre fois le tampon d'un tube) :
  #  `grep -q` sort à la première ligne, `printf` reste bloqué — SIGPIPE certain.
  gros="$(printf '    Error: %s: http://127.0.0.1:5392/app.js
' "$CI_SIGNATURE_IMPORT_VITE"
    for _ in $(seq 1 3000); do
      printf '  ✓  1 [bureau] › e2e/a.spec.ts:3:1 › un test parmi cinq cents (1.2s)
'; done
    printf '%s
' "$b")"
  t "relance — sortie de plus de 64 Ko, sous pipefail : oui"     "$(set -o pipefail; ci_relance_e2e 1 oui 3 <<< "$gros")" "oui"
}
