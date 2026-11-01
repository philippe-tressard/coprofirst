#!/usr/bin/env bash
# =============================================================================
#  rejouer-ci.sh — Rejoue en local, sur le poste, les commandes de la CI.
#
#  POURQUOI (#319). Le 12/08/2026, la CI est passée rouge sur `Lint Python
#  (Ruff)` après un lot où pytest, svelte-check, le build, les six lints du front
#  et les self-tests des scripts avaient tous été rejoués à la main. **Le seul
#  job non lancé est le seul qui a échoué.** La skill `avant-commit` §7 demande
#  pourtant d'exécuter chaque commande de chaque job, et donne même le `grep`
#  pour les extraire. Rien ne forçait à le faire, rien ne constatait qu'on
#  l'avait fait.
#
#  Le point 0c du pré-check regarde la CI DISTANTE et PASSÉE. Entre les deux, il
#  y a tout le lot qu'on s'apprête à pousser. Ce script comble cet intervalle ;
#  le point 16 du pré-check lit sa trace.
#
#  CE QUI FAIT SA VALEUR : il n'a pas de liste. Les commandes sont extraites de
#  `.github/workflows/ci.yml` par `lib-ci-replay.sh`. Une liste recopiée
#  divergerait au premier job ajouté — et c'est le job ajouté qu'on oublie.
#
#  RÈGLES (socle 04) :
#   - une étape non rejouable ici rend INCONNU, jamais OK ;
#   - une étape d'INSTALLATION n'est pas un contrôle : elle est affichée comme
#     telle, et non exécutée — elle écraserait l'environnement du poste ;
#   - le compte de ce qui a été vérifié est affiché : « 0 étape rejouée » n'est
#     pas un succès, c'est un parseur qui n'a rien compris ;
#   - la parité entre les `run:` écrits et les étapes extraites est vérifiée
#     AVANT tout : sans elle, le script rendrait un vert sur ce qu'il n'a pas lu.
#
#  DÉROULEMENT (#2224) : un PRÉ-VOL d'abord (dépendances, base des tests,
#  node_modules, Playwright, versions, venv — un écart refuse le rejeu en
#  quelques secondes), puis les étapes RAPIDES de tous les jobs, puis les
#  LENTES (pytest, e2e…), chaque job dans son couloir, plusieurs couloirs côte
#  à côte. Un rouge arrête le rejeu à la fin de sa phase. Les règles :
#  `lib-ci-orchestration.sh` (pures) ; les gestes : `lib-ci-execution.sh`.
#
#  Usage : bash scripts/poste/rejouer-ci.sh                 # tous les jobs, écrit la trace
#          bash scripts/poste/rejouer-ci.sh lint-backend …  # un ou plusieurs jobs, sans trace
#          bash scripts/poste/rejouer-ci.sh --attendre …    # prend son tour dans la file (#2225)
#          bash scripts/poste/rejouer-ci.sh --reprendre     # les rouges d'avant en tête
#          bash scripts/poste/rejouer-ci.sh --tout          # ne s'arrête pas au premier rouge
#          bash scripts/poste/rejouer-ci.sh --venv          # dans un venv aligné sur le lot
#          REJEU_PARALLELE=1 bash scripts/poste/rejouer-ci.sh   # une étape à la fois
#          bash scripts/poste/rejouer-ci.sh --selftest      # éprouve l'extraction
# =============================================================================
set -uo pipefail
# shellcheck source=../lib/lib-poste-gnu.sh
. "$(dirname "$0")/../lib/lib-poste-gnu.sh"
poste_gnu_poser   # macOS : les outils GNU en tête du PATH, comme Git Bash et la CI (#2419)

CI="${CI_FICHIER:-.github/workflows/ci.yml}"

# shellcheck source=../lib/lib-ci-replay.sh
#  Modules à la racine du dépôt — cf. le commentaire de precheck-mep.sh (#337).
RACINE_DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RACINE_DEPOT" || exit 1   # le rejeu extrait .github/workflows/ci.yml en relatif
. "$RACINE_DEPOT/scripts/lib/lib-ci-replay.sh"
# shellcheck source=../lib/lib-depot.sh
. "$RACINE_DEPOT/scripts/lib/lib-depot.sh"
#  La trace vit dans le répertoire git DU clone — un fichier dans un worktree (#1226).
MARQUEUR="${MARQUEUR_CI:-$(dossier_git)/rejeu-ci.ok}"

if [ "${1:-}" = "--selftest" ]; then
  ci_replay_selftest
  exit $?
fi

RACINE=$(git rev-parse --show-toplevel 2>/dev/null) || RACINE=$(pwd)
cd "$RACINE" || exit 2
[ -f "$CI" ] || { echo "✗ $CI introuvable — lancer depuis la racine du dépôt."; exit 2; }

#  ── Un seul rejeu à la fois (#1417), nommé, en file, sans orphelin (#2225) ──
#  Les règles vivent dans `lib-ci-verrou.sh` : `ci_rejeu_acquerir` (verrou
#  libre, ou file d'attente avec `--attendre`), la fiche du propriétaire, et le
#  veilleur qui bat le pouls et arrête ce rejeu si son lanceur disparaît.
#  État lisible par tous : `bash scripts/poste/etat-rejeu.sh`.
MODE_REJEU=direct; ARGS_REJEU=()
for a in "$@"; do [ "$a" = --attendre ] && MODE_REJEU=attendre || ARGS_REJEU+=("$a"); done
set -- ${ARGS_REJEU[@]+"${ARGS_REJEU[@]}"}
VERROU_REJEU="$(ci_dossier_commun)/rejeu-ci.verrou"
ANCRE_REJEU=$(ci_ancre "$(ci_chaine_ancetres $$)")
FICHE_REJEU=$(ci_fiche $$ "$ANCRE_REJEU" "$(ci_noms_de_jobs "$@")")   # les jobs, pas les options (#2229)
ci_rejeu_acquerir "$VERROU_REJEU" "$MODE_REJEU" "$ANCRE_REJEU" "$FICHE_REJEU" || exit 2
trap 'ci_verrou_liberer "$VERROU_REJEU" $$' EXIT
#  Le lanceur parti, la sortie peut l'être aussi : écrire ne doit pas tuer le trap.
trap 'trap "" PIPE; ci_rejeu_arrete "$VERROU_REJEU"; exit 2' TERM HUP
ci_verrou_signer "$VERROU_REJEU" "$FICHE_REJEU"
ci_veilleur "$VERROU_REJEU" $$ "$ANCRE_REJEU" >/dev/null 2>&1 &
[ -n "$ANCRE_REJEU" ] || echo "· lanceur non surveillé (aucun shell parent) : un rejeu abandonné ne s'arrêtera pas seul."

#  ── Workers e2e sur un poste occupé (#1665) — la règle : `ci_workers_e2e` ────
#  La charge est mesurée MAINTENANT, avant nos propres étapes : c'est celle des
#  autres sessions. Sous Git Bash, `/proc/loadavg` est une émulation figée ; on
#  demande donc à Windows. Trois relevés, l'instantané seul est trop bruité.
charge_cpu() {             # → pourcentage entier, vide si non mesurable
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      command -v powershell.exe >/dev/null 2>&1 || return
      powershell.exe -NoProfile -Command '$s=0; 1..3 | ForEach-Object { $s += (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average; Start-Sleep -Milliseconds 500 }; [int]($s/3)' 2>/dev/null | tr -d '\r' ;;
    Darwin)
      #  macOS n'a pas `/proc/loadavg` : la charge sur une minute se lit par sysctl
      #  (« { 1.23 1.10 1.05 } ») ; `nproc` vient de coreutils, par la porte GNU (#2419).
      command -v nproc >/dev/null 2>&1 || return
      sysctl -n vm.loadavg 2>/dev/null | awk -v n="$(nproc)" '{ printf "%d\n", $2 * 100 / n }' ;;
    *)
      [ -r /proc/loadavg ] && command -v nproc >/dev/null 2>&1 || return
      awk -v n="$(nproc)" '{ printf "%d\n", $1 * 100 / n }' /proc/loadavg ;;
  esac
}
SEUIL_CHARGE_E2E=30
CHARGE=$(charge_cpu)
E2E_WORKERS=$(ci_workers_e2e "${E2E_WORKERS:-}" "$CHARGE" "$SEUIL_CHARGE_E2E")
if [ -n "$E2E_WORKERS" ]; then
  export E2E_WORKERS
  echo "· e2e sur ${E2E_WORKERS} worker(s) — charge du poste ${CHARGE:-?} % avant le rejeu (seuil ${SEUIL_CHARGE_E2E} %, imposable par E2E_WORKERS)"
else
  unset E2E_WORKERS
  echo "· e2e au défaut de Playwright — charge du poste ${CHARGE:-non mesurée}${CHARGE:+ %} avant le rejeu"
fi

#  ─────────────────────────────────────────────────────────────────────────────
#  Le fichier de CI se CHARGE-t-il ? (17/09/2026)
#
#  🔴 Ce script extrait les commandes de `ci.yml` ligne par ligne : un YAML
#  cassé lui reste parfaitement lisible. Ce jour-là, un retour chariot isolé
#  inséré au milieu d'un commentaire a rendu le fichier illisible pour GitHub,
#  et le rejeu a conclu « 97 étapes OK » sur un workflow qui ne démarrait plus.
#
#  Conséquence côté GitHub : AUCUN check ne tourne. Les checks requis ne sont
#  donc ni verts ni rouges, ils sont ABSENTS — la protection de `main` refuse la
#  fusion, et rien n'explique pourquoi. Un rejeu vert sur un workflow mort est
#  le pire des faux verts : il porte précisément sur l'outil qui devait juger.
#
#  ⚠️ Sans analyseur YAML disponible, on rend INCONNU et non OK : un contrôle
#  qui ne peut pas s'exécuter ne conclut pas (`standards/04` §1).
#  ─────────────────────────────────────────────────────────────────────────────
verdict_yaml=$(python -c "
import sys, pathlib
try:
    import yaml
except ImportError:
    print('INCONNU: analyseur YAML absent (pip install pyyaml)'); sys.exit(0)
try:
    yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
except Exception as erreur:
    print('CASSE: ' + str(erreur).replace(chr(10), ' ')[:200]); sys.exit(0)
print('OK')
" "$CI" 2>/dev/null) || verdict_yaml="INCONNU: python indisponible"

case "$verdict_yaml" in
  OK) ;;
  CASSE*)
    echo "✗ $CI ne se charge PAS — GitHub ne lancera aucun check, et les checks"
    echo "  requis seront ABSENTS plutôt que rouges (fusion refusée sans motif)."
    echo "  ${verdict_yaml#CASSE: }"
    echo "  Rien n'est rejoué : conclure ici porterait sur un workflow mort."
    exit 2
    ;;
  *)
    echo "? Validité de $CI : ${verdict_yaml#INCONNU: } — le rejeu continue, mais"
    echo "  il ne prouve rien sur le chargement du workflow par GitHub."
    ;;
esac

#  En intégration continue, `pip install` dépose ses exécutables dans un
#  répertoire déjà présent dans le PATH. Sur un poste Windows, non : `ruff` et
#  `pytest` sont installés et introuvables depuis Git Bash. Sans cette ligne, le
#  job qui a motivé #319 resterait INCONNU pour toujours — c'est-à-dire jamais
#  rejoué, ce que ce script existe précisément pour empêcher.
#  Le chemin est DEMANDÉ à Python, jamais écrit en dur : il dépend de la version
#  installée et changerait au prochain interpréteur.
#
#  🔴 SES FICHIERS en tête, jamais le RÉPERTOIRE entier (24/09/2026). Ce
#  répertoire n'est pas réservé à pip : en session cloud c'est `/usr/local/bin`,
#  qui porte aussi `node`, `npm` et `npx` — des LIENS vers un Node 20. Placé
#  devant tel quel, il masquait le Node 22 de la CI, et sept contrôles du front
#  échouaient au rejeu (`fs.globSync` absent, `--experimental-strip-types`
#  refusé) alors qu'ils passaient sur GitHub. Placé DERRIÈRE, c'est le `pytest`
#  isolé de `uv` (`~/.local/bin`, sans les dépendances de l'API) qui gagnait.
#  Aucun ordre de répertoires ne convient aux deux : on expose donc, en tête,
#  des liens vers les seuls FICHIERS ordinaires du répertoire — ce que pip y
#  écrit (`pytest`, `ruff`, `pip-audit`…) —, jamais les liens symboliques qu'un
#  autre installateur y a posés. Sous Windows, où tout y est fichier, rien ne
#  change — sauf l'interpréteur d'un venv, jamais exposé : `ci_script_a_exposer` (#2112).
SCRIPTS_PY=$(python -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null)
if [ -n "$SCRIPTS_PY" ] && [ -d "$SCRIPTS_PY" ]; then
  SCRIPTS_PY_EXPOSES=$(mktemp -d) || exit 2
  for f in "$SCRIPTS_PY"/*; do
    [ "$(ci_script_a_exposer "${f##*/}" "$([ -f "$f" ] && [ ! -L "$f" ] && echo fichier || echo lien)" \
      "$([ -x "$f" ] && echo oui || echo non)")" = oui ] && ln -s "$f" "$SCRIPTS_PY_EXPOSES/"
  done
  PATH="$SCRIPTS_PY_EXPOSES:$PATH" && export PATH
fi

#  ── La base PostgreSQL des tests — la règle : `ci_base_tests_etat` ─────────
#  Posée ici si personne ne l'a posée ; l'`env:` d'un job de ci.yml la remplace
#  le temps de son étape, comme sur GitHub. Sondée à la première étape pytest.
export TESTS_BASE_URL="${TESTS_BASE_URL:-$CI_BASE_TESTS_DEFAUT}"

#  ── Les options (#2224) — tout le reste est le filtre de jobs ──────────────
#    --tout       joue la phase suivante même après un rouge ;
#    --reprendre  rejoue d'abord les rouges du rejeu précédent de ce lot ;
#    --venv       rejoue dans un venv aligné sur le lot (construit au besoin).
TOUT=non; REPRENDRE=non; VENV=non; FILTRE=""
for arg in "$@"; do
  case "$arg" in
    --tout)      TOUT=oui ;;
    --reprendre) REPRENDRE=oui ;;
    --venv)      VENV=oui ;;
    --*) echo "✗ Option inconnue : $arg (connues : --tout, --reprendre, --venv, --selftest) — rien n'a été rejoué."; exit 2 ;;
    *)   FILTRE="${FILTRE:+$FILTRE }$arg" ;;
  esac
done
#  Le répertoire git COMMUN : durées mesurées, venvs, journal des relances —
#  ce que les worktrees partagent.
COMMUN=$(cd "$(git rev-parse --git-common-dir 2>/dev/null || echo .git)" && pwd)
T_DEBUT=$EPOCHSECONDS   # l'horloge du rejeu : pré-vol compris
SHA=$(git rev-parse HEAD 2>/dev/null)
SHA_COURT=$(git rev-parse --short HEAD 2>/dev/null)
#  L'arbre de HEAD (#2245) : ce que le rejeu teste, indépendamment du message et de
#  l'historique. La trace le porte pour qu'un reword ou un squash ne coûte pas un rejeu.
ARBRE=$(git rev-parse 'HEAD^{tree}' 2>/dev/null)

# ── Parité : refuser de conclure sur ce qu'on n'a pas lu ─────────────────────
read -r ECRIT EXTRAIT <<< "$(ci_parite "$CI")"
if [ "${ECRIT:-0}" -eq 0 ] || [ "$ECRIT" != "$EXTRAIT" ]; then
  echo "✗ Extraction INCOMPLÈTE — $ECRIT commande(s) \`run:\` écrite(s), $EXTRAIT extraite(s)."
  echo "  Le fichier a changé de forme : corriger \`ci_extraire\` dans lib-ci-replay.sh."
  echo "  Ne pas lire ceci comme un succès — rien n'a été rejoué."
  exit 2
fi

TMP=$(mktemp -d) || exit 2
#  À la sortie, quelle qu'elle soit, plus rien du rejeu ne survit (#2270) : l'arbre entier est
#  tué AVANT de rendre le verrou — un pytest qui lui survivrait tiendrait la base des tests.
trap 'ci_proc_tuer sous "$(ci_winpid $$)" "" 2>/dev/null; ci_verrou_liberer "$VERROU_REJEU" $$; rm -rf "$TMP" ${SCRIPTS_PY_EXPOSES:+"$SCRIPTS_PY_EXPOSES"}' EXIT
ci_extraire < "$CI" > "$TMP/flux"

#  ── Le venv aligné sur le lot (`--venv`, #2224) — `ci_venv_preparer` ───────
#  Construit (ou repris) SOUS le verrou, puis placé en tête du PATH par un
#  chemin `/c/…` : écrit `C:/…`, le deux-points coupe l'entrée (23/10/2026).
if [ "$VENV" = oui ]; then
  BIN_VENV=$(ci_venv_preparer "$RACINE" "$COMMUN" "$TMP/flux") \
    || { echo "✗ Le venv aligné sur le lot n'a pas pu être construit — rien n'a été rejoué."; exit 2; }
  BIN_VENV=$(cygpath -u "$BIN_VENV" 2>/dev/null || echo "$BIN_VENV")
  VIRTUAL_ENV=${BIN_VENV%/*}
  PATH="$BIN_VENV:$PATH"
  export PATH VIRTUAL_ENV
  echo "· venv aligné sur le lot : $VIRTUAL_ENV"
fi

#  Les gestes d'une étape (#2224) : `lib-ci-execution.sh`, et le pré-vol.
# shellcheck source=../lib/lib-ci-execution.sh
. "$RACINE_DEPOT/scripts/lib/lib-ci-execution.sh"
ECHECS="$(dirname "$MARQUEUR")/rejeu-ci-echecs"
rm -rf "$ECHECS"
PLAFOND_RELANCE_E2E=3
JOURNAL_RELANCES="$COMMUN/rejeu-e2e-relances.log"
DUREES="$COMMUN/rejeu-ci-durees.tsv"           # mesurées, partagées par les worktrees
ROUGES="$(dirname "$MARQUEUR")/rejeu-ci-rouges.tsv"   # celles DE ce worktree

#  Interrompre le rejeu arrête ses étapes, et l'arbre de leurs processus
#  (`ci_arreter_pids`) : sous Windows, un `kill` ne descend pas jusqu'au python
#  ou au node qu'une étape a lancé.
JOURNAL_DUREES="$COMMUN/rejeu-durees.log"   # une ligne par étape, chaque rejeu (`mesurer-rejeux.py`)
PORTEE="complet"; [ -n "$FILTRE" ] && PORTEE="partiel : $FILTRE"
trap 'echo; echo "✗ Rejeu interrompu — aucune trace écrite."; ci_arreter_pids $(jobs -p); ci_journaliser "$JOURNAL_DUREES" INTERROMPU "$PORTEE"; exit 130' INT
#  Le veilleur de #2225 (lanceur disparu) envoie TERM : les étapes partent avec.
trap 'trap "" PIPE; ci_arreter_pids $(jobs -p); ci_journaliser "$JOURNAL_DUREES" INTERROMPU "$PORTEE"; ci_rejeu_arrete "$VERROU_REJEU"; exit 2' TERM HUP

# ── Les étapes retenues, une par dossier ─────────────────────────────────────
#  Chaque étape `run:` (ou `uses:`, pour le pré-vol) reçoit son dossier : job,
#  nom, rép, `env:`, corps, genre. Rien de partagé entre deux étapes qui
#  tournent ensemble.
JOB=""; ETAPE=""; GENRE=""; REP=""; USES=""; WITH=""; DANS_RUN=0; D=""; IDX=0
mkdir -p "$TMP/e"
while IFS= read -r ligne <&3; do
  case "$ligne" in
    '@@ERREUR'*)
      echo "✗ Protocole rompu : ${ligne#*$'\t'}"
      echo "  Rien n'a été rejoué — ne pas lire ceci comme un succès."
      exit 2 ;;
    '@@STEP'*)
      IFS=$'\t' read -r _ JOB _ ETAPE GENRE REP USES WITH <<< "$ligne"
      #  `-` est le marqueur de champ vide posé par `nz()` côté extraction.
      for v in ETAPE REP USES WITH; do [ "${!v}" = "-" ] && printf -v "$v" ''; done
      D=""; DANS_RUN=0
      [ -n "$FILTRE" ] && case " $FILTRE " in *" $JOB "*) ;; *) continue ;; esac
      case "$GENRE:$USES" in run:*|uses:*) ;; *) continue ;; esac
      case "$USES" in *checkout*) continue ;; esac
      IDX=$((IDX + 1)); D="$TMP/e/$(printf '%04d' "$IDX")"
      mkdir -p "$D"
      printf '%s' "$JOB" > "$D/job"; printf '%s' "${ETAPE:-$USES}" > "$D/etape"
      printf '%s' "$REP" > "$D/rep"; printf '%s' "$USES" > "$D/uses"; printf '%s' "$WITH" > "$D/with"
      : > "$D/env"; : > "$D/brut"
      [ "$GENRE" = uses ] && echo USES > "$D/genre" ;;
    '@@ENV'*)   [ -n "$D" ] && printf '%s\n' "${ligne#*$'\t'}" >> "$D/env" ;;
    '@@RUN')    DANS_RUN=1 ;;
    '@@END')
      DANS_RUN=0
      [ -n "$D" ] || continue
      ci_substituer "$SHA_COURT" < "$D/brut" > "$D/corps"
      genre=$(ci_classer < "$D/corps")
      case "$genre" in
        PREPARATION) printf 'PRÉP\tinstallation — non exécutée sur le poste\n' > "$D/res" ;;
        INCONNU*)    printf 'INCONNU\t%s\n' "${genre#INCONNU }" > "$D/res"; genre=INCONNU ;;
      esac
      echo "$genre" > "$D/genre" ;;
    *)          [ "$DANS_RUN" -eq 1 ] && [ -n "$D" ] && printf '%s\n' "$ligne" >> "$D/brut" ;;
  esac
done 3< "$TMP/flux"

echo "Rejeu de $CI sur $SHA_COURT — $ECRIT commande(s) extraite(s)"
[ -n "$FILTRE" ] && echo "Jobs retenus : $FILTRE"

# ── Pré-vol : le poste peut-il mesurer le lot ? (#2224) — `ci_prevol` ────────
ci_prevol "$TMP/e" || { ci_journaliser "$JOURNAL_DUREES" REFUS "$PORTEE"; exit 2; }

# ── Le plan : phases, couloirs, priorité — `ci_plan` ─────────────────────────
for d in "$TMP"/e/*/; do
  d=${d%/}
  [ "$(<"$d/genre")" = CONTROLE ] && printf '%s\t%s\t%s\n' "${d##*/}" "$(<"$d/job")" "$(<"$d/etape")"
done > "$TMP/a-jouer"
awk -F'\t' -v OFS='\t' '!lu { d[$1 "\t" $2] = $3; next } { print $0, d[$2 "\t" $3] }' \
  "$([ -f "$DUREES" ] && echo "$DUREES" || echo /dev/null)" lu=1 "$TMP/a-jouer" > "$TMP/a-jouer-durees"
#  Le plafond d'une étape figée se tire de sa durée mesurée (#2270).
while IFS=$'\t' read -r idx _ _ duree; do printf '%s\n' "$duree" > "$TMP/e/$idx/mesuree"; done < "$TMP/a-jouer-durees"

#  Les rouges d'avant valent-ils pour ce lot ? (même lot : `ci_reprise_valable`)
ROUGES_VALABLES=non
if [ -s "$ROUGES" ]; then
  IFS=$'\t' read -r _ sha_avant branche_avant < "$ROUGES"
  ancetre=non
  git merge-base --is-ancestor "$sha_avant" HEAD 2>/dev/null && ancetre=oui
  ROUGES_VALABLES=$(ci_reprise_valable "$branche_avant" "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" "$ancetre")
fi
: > "$TMP/reprendre"
if [ "$REPRENDRE" = oui ]; then
  [ "$ROUGES_VALABLES" = oui ] && grep -v '^#' "$ROUGES" > "$TMP/reprendre"
  if [ -s "$TMP/reprendre" ]; then
    echo "· Reprise : $(wc -l < "$TMP/reprendre") étape(s) rouge(s) du rejeu précédent ($sha_avant) en tête, avec ce qui les précède dans leur couloir"
  else
    echo "· Reprise : aucun rouge d'un rejeu précédent de ce lot — rejeu ordinaire."
  fi
fi
SEUIL_LENTE="${REJEU_SEUIL_LENTE:-$CI_SEUIL_LENTE}"   # imposable, comme le budget
ci_plan "$SEUIL_LENTE" "$TMP/reprendre" < "$TMP/a-jouer-durees" > "$TMP/plan"
[ -s "$TMP/a-jouer-durees" ] && ! grep -q . <<<"$(cut -f4 "$TMP/a-jouer-durees")" \
  && echo "· Aucune durée mesurée encore : tout est « rapide » ce coup-ci ; les durées s'apprennent ($DUREES)."

BUDGET=$(ci_budget_parallele "${REJEU_PARALLELE:-}" "$(nproc 2>/dev/null)" "${CHARGE:-}")
compte_phase() { awk -F'\t' -v p="$1" '$1 == p' "$TMP/plan" | grep -c .; }
printf 'Plan : %d étape(s) à jouer — reprise %d · rapide %d · lente %d (mesurée ≥ %d s) · %d côte à côte (%s cœurs, charge %s %%, imposable par REJEU_PARALLELE)\n' \
  "$(grep -c . "$TMP/plan")" "$(compte_phase reprise)" "$(compte_phase rapide)" "$(compte_phase lente)" \
  "$SEUIL_LENTE" "$BUDGET" "$(nproc 2>/dev/null || echo ?)" "${CHARGE:-?}"
echo "───────────────────────────────────────────────────────────────────────────────"

#  Ce qui n'est pas joué ici (installations, expressions GitHub), dans l'ordre.
for d in "$TMP"/e/*/; do
  case "$(<"${d%/}/genre")" in PREPARATION|INCONNU) ci_afficher_etape "${d%/}" ;; esac
done

# ── Déroulement : reprise, rapide, lente — `ci_jouer` ────────────────────────
#  Un rouge arrête le rejeu à la fin de sa phase (`ci_suite_apres_phase`) :
#  tous les rouges de la phase sont là, et la suivante ne changerait pas le
#  verdict ; ce qu'elle avait commencé par anticipation est arrêté. `--tout`
#  joue tout. Les lignes d'une phase s'affichent à sa fin, dans l'ordre de
#  ci.yml ; chaque rouge s'annonce dès qu'il tombe.
ci_jouer "$TMP/plan" "$TOUT"

# ── Conclusion ───────────────────────────────────────────────────────────────
NB_OK=0; NB_FAIL=0; NB_INCONNU=0; NB_PREP=0; NB_SAUTS=0; NB_RELANCES=0; NB_NON_JOUEES=0
: > "$TMP/mesures"; : > "$TMP/jouees"; : > "$TMP/rouges"
for d in "$TMP"/e/*/; do
  d=${d%/}
  [ "$(<"$d/genre")" = USES ] && continue
  if [ ! -f "$d/res" ]; then NB_NON_JOUEES=$((NB_NON_JOUEES + 1)); continue; fi
  IFS=$'\t' read -r verdict _ < "$d/res"
  case "$verdict" in
    OK) NB_OK=$((NB_OK + 1)) ;; FAIL) NB_FAIL=$((NB_FAIL + 1)) ;;
    INCONNU) NB_INCONNU=$((NB_INCONNU + 1)) ;; PRÉP) NB_PREP=$((NB_PREP + 1)) ;;
  esac
  #  `$(<f)`, jamais `$(cat f)` : une fourche coûte ~50 ms sous Windows.
  [ -f "$d/nb_sauts" ] && NB_SAUTS=$((NB_SAUTS + $(<"$d/nb_sauts")))
  [ -f "$d/nb_relances" ] && NB_RELANCES=$((NB_RELANCES + $(<"$d/nb_relances")))
  if [ -f "$d/duree" ]; then
    printf '%s\t%s\n' "$(<"$d/job")" "$(<"$d/etape")" >> "$TMP/jouees"
    case "$verdict" in OK|FAIL) printf '%s\t%s\t%s\n' "$(<"$d/job")" "$(<"$d/etape")" "$(<"$d/duree")" >> "$TMP/mesures" ;; esac
    [ "$verdict" = FAIL ] && printf '%s\t%s\n' "$(<"$d/job")" "$(<"$d/etape")" >> "$TMP/rouges"
  fi
done
#  Ce que le rejeu apprend : les durées (pour le plan suivant), les rouges
#  (pour `--reprendre`) — jamais la trace, qui suit ses propres règles.
ci_durees_fusionner "$([ -f "$DUREES" ] && echo "$DUREES")" "$TMP/mesures" > "$TMP/durees" \
  && mv -f "$TMP/durees" "$DUREES"
{ printf '#\t%s\t%s\n' "$SHA" "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  ci_rouges_fusionner "$([ "$ROUGES_VALABLES" = oui ] && echo "$ROUGES")" "$TMP/jouees" "$TMP/rouges"
} > "$TMP/rouges-fusion" && mv -f "$TMP/rouges-fusion" "$ROUGES"

REJOUEES=$((NB_OK + NB_FAIL + NB_INCONNU))
if [ "$NB_FAIL" -gt 0 ]; then VERDICT_REJEU=ROUGE
elif [ "$NB_INCONNU" -gt 0 ] || [ "$REJOUEES" -eq 0 ]; then VERDICT_REJEU=INCONNU
else VERDICT_REJEU=VERT; fi
[ -z "$FILTRE" ] && [ "$NB_NON_JOUEES" -gt 0 ] && PORTEE="arrêté après la phase $ARRET"
ci_journaliser "$JOURNAL_DUREES" "$VERDICT_REJEU" "$PORTEE"
echo "───────────────────────────────────────────────────────────────────────────────"
printf "%d étape(s) rejouée(s) sur %d extraite(s) — OK=%d ÉCHEC=%d INCONNU=%d (préparation=%d) — en %s\n" \
       "$REJOUEES" "$ECRIT" "$NB_OK" "$NB_FAIL" "$NB_INCONNU" "$NB_PREP" "$(ci_horloge)"
[ "$NB_SAUTS" -gt 0 ] && echo "· $NB_SAUTS test(s) sauté(s) ici, que seule la CI GitHub joue — le détail est sur la ligne de leur étape (#1734)."
[ "$NB_RELANCES" -gt 0 ] && echo "· $NB_RELANCES test(s) e2e relancé(s) sur une cause propre au poste (#1809, #1989) — journal : $JOURNAL_RELANCES"
[ -n "$ARRET" ] && [ "$NB_NON_JOUEES" -gt 0 ] && \
  echo "· Arrêté après la phase $ARRET : $NB_NON_JOUEES étape(s) non jouée(s). Corriger, puis \`--reprendre\` ; \`--tout\` joue tout malgré un rouge."

if [ "$REJOUEES" -eq 0 ]; then
  echo "? Aucune étape rejouée — ce n'est pas un succès, c'est une absence de mesure."
  exit 2
fi

if [ -n "$FILTRE" ]; then
  echo "  (rejeu partiel : aucune trace écrite — le point 16 du pré-check exige le rejeu complet.)"
elif [ "$NB_NON_JOUEES" -gt 0 ]; then
  echo "  (rejeu incomplet : aucune trace écrite — le point 16 du pré-check exige le rejeu complet.)"
else
  mkdir -p "$(dirname "$MARQUEUR")"
  trace_rejeu_ecrire "$MARQUEUR" "$SHA" "$(date +%s)" \
    "$NB_OK" "$NB_FAIL" "$NB_INCONNU" "$NB_SAUTS" "$NB_RELANCES" "$ARBRE"
fi

[ "$NB_FAIL" -gt 0 ] && { echo "✗ La CI échouerait — corriger avant de pousser."; exit 1; }
[ "$NB_INCONNU" -gt 0 ] && { echo "? Des étapes n'ont pas pu être rejouées ici : un INCONNU n'est pas un vert."; exit 2; }
echo "✓ Toutes les étapes rejouables sont passées."
exit 0
