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
#  Usage : bash scripts/poste/rejouer-ci.sh                 # tous les jobs, écrit la trace
#          bash scripts/poste/rejouer-ci.sh lint-backend …  # un ou plusieurs jobs, sans trace
#          bash scripts/poste/rejouer-ci.sh --selftest      # éprouve l'extraction
# =============================================================================
set -uo pipefail

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

#  ── Un seul rejeu à la fois (#1417) — la règle : `ci_verrou_etat` ──────────
VERROU_REJEU="$(cd "$(git rev-parse --git-common-dir 2>/dev/null || echo .git)" && pwd)/rejeu-ci.verrou"
pid_verrou=$(cat "$VERROU_REJEU/pid" 2>/dev/null || true)
vivant=non
[ -n "$pid_verrou" ] && kill -0 "$pid_verrou" 2>/dev/null && vivant=oui
case "$(ci_verrou_etat "$pid_verrou" "$vivant")" in
  occupe)
    echo "✗ Un autre rejeu tourne déjà (pid $pid_verrou) : deux rejeux simultanés se sabotent."
    echo "  Attendre sa fin — rien n'a été rejoué, ce n'est pas un succès."
    exit 2 ;;
  orphelin) ci_verrou_reprendre "$VERROU_REJEU" "$pid_verrou" ;;   # refus → le mkdir le dira
esac
#  Le pid relu après écriture : un verrou déplacé pendant ce temps n'est pas à nous (#1808).
if ! mkdir "$VERROU_REJEU" 2>/dev/null || ! echo $$ > "$VERROU_REJEU/pid" 2>/dev/null \
   || [ "$(cat "$VERROU_REJEU/pid" 2>/dev/null)" != "$$" ]; then
  echo "✗ Le verrou du rejeu vient d'être pris par un autre rejeu : attendre sa fin."
  exit 2
fi
trap 'ci_verrou_liberer "$VERROU_REJEU" $$' EXIT

#  ── Workers e2e sur un poste occupé (#1665) — la règle : `ci_workers_e2e` ────
#  La charge est mesurée MAINTENANT, avant nos propres étapes : c'est celle des
#  autres sessions. Sous Git Bash, `/proc/loadavg` est une émulation figée ; on
#  demande donc à Windows. Trois relevés, l'instantané seul est trop bruité.
charge_cpu() {             # → pourcentage entier, vide si non mesurable
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      command -v powershell.exe >/dev/null 2>&1 || return
      powershell.exe -NoProfile -Command '$s=0; 1..3 | ForEach-Object { $s += (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average; Start-Sleep -Milliseconds 500 }; [int]($s/3)' 2>/dev/null | tr -d '\r' ;;
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
#  change.
SCRIPTS_PY=$(python -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null)
if [ -n "$SCRIPTS_PY" ] && [ -d "$SCRIPTS_PY" ]; then
  SCRIPTS_PY_EXPOSES=$(mktemp -d) || exit 2
  for f in "$SCRIPTS_PY"/*; do
    [ -f "$f" ] && [ ! -L "$f" ] && [ -x "$f" ] && ln -s "$f" "$SCRIPTS_PY_EXPOSES/"
  done
  PATH="$SCRIPTS_PY_EXPOSES:$PATH" && export PATH
fi

#  ── Le node_modules du front est-il celui du worktree ? (#1722) ────────────
#  La règle est `ci_node_modules_etat` ; ici, seulement le constat. `-L`
#  reconnaît aussi une jonction NTFS sous Git Bash (mesuré le 07/10/2026).
genre_node_modules() {
  local d="$RACINE/front/node_modules"
  if [ -L "$d" ]; then echo lien
  elif [ -d "$d" ]; then echo repertoire
  else echo absent; fi
}
MOTIF_NODE_MODULES=$(ci_node_modules_etat "$(genre_node_modules)")
[ -n "$MOTIF_NODE_MODULES" ] && {
  echo "? $MOTIF_NODE_MODULES — les tests de navigateur rendront INCONNU."
  echo "  Réparer : cmd //c \"rmdir front\node_modules\" && (cd front && npm ci --legacy-peer-deps)"
  echo "  (rmdir retire le LIEN, jamais le node_modules partagé.)"
}

FILTRE="$*"
SHA=$(git rev-parse HEAD 2>/dev/null)
SHA_COURT=$(git rev-parse --short HEAD 2>/dev/null)

# ── Parité : refuser de conclure sur ce qu'on n'a pas lu ─────────────────────
read -r ECRIT EXTRAIT <<< "$(ci_parite "$CI")"
if [ "${ECRIT:-0}" -eq 0 ] || [ "$ECRIT" != "$EXTRAIT" ]; then
  echo "✗ Extraction INCOMPLÈTE — $ECRIT commande(s) \`run:\` écrite(s), $EXTRAIT extraite(s)."
  echo "  Le fichier a changé de forme : corriger \`ci_extraire\` dans lib-ci-replay.sh."
  echo "  Ne pas lire ceci comme un succès — rien n'a été rejoué."
  exit 2
fi

TMP=$(mktemp -d) || exit 2
trap 'ci_verrou_liberer "$VERROU_REJEU" $$; rm -rf "$TMP" ${SCRIPTS_PY_EXPOSES:+"$SCRIPTS_PY_EXPOSES"}' EXIT
ci_extraire < "$CI" > "$TMP/flux"

NB_OK=0; NB_FAIL=0; NB_INCONNU=0; NB_PREP=0; NB_SAUTS=0; NB_RELANCES=0

#  Les tests SAUTÉS se nomment (#1734) : le crochet de `api/tests/conftest.py`
#  les consigne dans ce fichier, que chaque étape vide avant de tourner. Hors
#  rejeu la variable est absente, et pytest n'écrit rien.
export REJEU_SAUTS="$TMP/sauts"

#  🔴 La sortie COMPLÈTE d'une étape en échec est gardée (#1150, 25/09/2026).
#  Le rapport n'en montre que la queue, et pour Playwright la queue est faite
#  des `ECONNREFUSED` du proxy — l'assertion en cause n'y apparaissait jamais,
#  et trois échecs e2e sont restés sans diagnostic. Un dossier par rejeu, vidé
#  au suivant : ce qu'il contient parle TOUJOURS du dernier rejeu.
ECHECS="$(dirname "$MARQUEUR")/rejeu-ci-echecs"
rm -rf "$ECHECS"

#  Le verdict et le job sont en TÊTE, le nom de l'étape en queue : `printf`
#  compte des OCTETS, pas des caractères, si bien qu'une colonne de largeur fixe
#  contenant « Modularité » ou « Libellés » se décale d'autant d'accents. Une
#  colonne qui ne s'aligne pas se lit mal, et un rapport qu'on lit mal, on cesse
#  de le lire.
rapporter() {              # $1 = verdict, $2 = job, $3 = étape, $4 = détail
  local icone
  case "$1" in
    OK)      icone="✓"; NB_OK=$((NB_OK+1)) ;;
    FAIL)    icone="✗"; NB_FAIL=$((NB_FAIL+1)) ;;
    INCONNU) icone="?"; NB_INCONNU=$((NB_INCONNU+1)) ;;
    PRÉP)    icone="·"; NB_PREP=$((NB_PREP+1)) ;;
    *)       icone="·" ;;
  esac
  printf "%s %-7s %-15s %s%s\n" "$icone" "$1" "$2" "$3" "${4:+  — $4}"
}

version_locale() {         # $1 = uses — ce que la CI ÉPINGLE, ce que le poste a
  case "$1" in
    *setup-python*) python --version 2>&1 | awk '{print $2}' ;;
    *setup-node*)   node --version 2>&1 | tr -d 'v' ;;
    *) echo "" ;;
  esac
}

#  Les contrôles d'un job ne mesurent le lot que si le poste a installé ce que
#  ses étapes d'installation épinglent (#1417). Sinon ils rendent INCONNU, et
#  la ligne ENV dit l'écart et la commande qui aligne le poste.
verifier_dependances() {   # $1 = job, $2 = rép, $3 = corps de l'installation
  local verdict motif
  verdict=$(printf '%s\n' "$3" \
    | python "$RACINE/scripts/poste/verifier-dependances-poste.py" --rep "$RACINE${2:+/$2}" 2>/dev/null \
    | tail -1)
  motif=$(ci_dependances_etat "$verdict")
  [ -z "$motif" ] && return
  printf '%s\n' "$motif" > "$TMP/deps-$1"
  rapporter "ENV" "$1" "dépendances" \
    "$motif · aligner : (cd ${2:-.} && $(printf '%s' "$3" | grep -v '^[[:space:]]*#' | tr '\n' ' ' | sed 's/ *$//'))"
}

#  Une commande dans le répertoire d'une étape, avec l'`env:` de son job.
dans_etape() {             # $1 = rép, puis la commande
  (
    cd "$RACINE${1:+/$1}" || exit 127
    shift
    while IFS= read -r kv; do
      [ -z "$kv" ] && continue
      local_cle=${kv%%:*}
      local_val=${kv#*: }
      local_val=${local_val%\"}; local_val=${local_val#\"}
      local_val=${local_val%\'}; local_val=${local_val#\'}
      export "$local_cle=$local_val"
    done < "$TMP/env"
    "$@" < /dev/null
  )
}

#  ── Relance des e2e tombés sur l'import dynamique de Vite (#1809) ───────────
#  La règle est `ci_relance_e2e` (lib-ci-e2e.sh) : une seule relance, des seuls
#  tests tombés, nommée sur la ligne de l'étape et JOURNALISÉE — date, lot,
#  charge, workers, tests —, pour qu'on mesure enfin la cause. Sortie vide :
#  pas de relance, ou relance rouge (sa sortie s'ajoute alors à celle de l'étape).
PLAFOND_RELANCE_E2E=3
JOURNAL_RELANCES="$(dirname "$VERROU_REJEU")/rejeu-e2e-relances.log"
relancer_si_import_vite() { # $1 = rép, $2 = code, $3 = corps → détail à rapporter, ou vide
  local tombes
  [ "$(ci_relance_e2e "$2" "$(printf '%s\n' "$3" | ci_sert_par_vite)" "$PLAFOND_RELANCE_E2E" \
       < "$TMP/sortie")" = oui ] || return 0
  tombes=$(ci_tests_tombes < "$TMP/sortie")
  if dans_etape "$1" npx playwright test --last-failed > "$TMP/relance" 2>&1 \
     && ! grep -q "optimized dependencies changed" "$TMP/relance"; then
    printf '%s\t%s\tcharge=%s\tworkers=%s\t%s\n' "$(date '+%F %T')" "$SHA_COURT" \
      "${CHARGE:-?}" "${E2E_WORKERS:-défaut}" "$(printf '%s' "$tombes" | paste -sd '|' -)" \
      >> "$JOURNAL_RELANCES"
    echo "relancé, vert : $(printf '%s' "$tombes" | paste -sd ';' -) — import dynamique de Vite (#1809)"
  else
    { echo; echo "── Relance (#1809), rouge elle aussi ──"; cat "$TMP/relance"; } >> "$TMP/sortie"
  fi
}

executer() {               # $1 = job, $2 = étape, $3 = rép, corps dans $TMP/corps
  local corps genre sortie code duree t0 sauts n_sauts relance
  corps=$(ci_substituer "$SHA_COURT" < "$TMP/corps")
  genre=$(printf '%s\n' "$corps" | ci_classer)

  case "$genre" in
    PREPARATION)
      rapporter "PRÉP" "$1" "$2" "installation — non exécutée sur le poste"
      verifier_dependances "$1" "$3" "$corps"
      return ;;
    INCONNU*)
      rapporter INCONNU "$1" "$2" "${genre#INCONNU }"
      return ;;
  esac
  if [ -s "$TMP/deps-$1" ]; then
    rapporter INCONNU "$1" "$2" "ne mesure pas le lot : dépendances du poste (ligne ENV)"
    return
  fi
  #  Les tests de navigateur, et eux seuls, servent l'application par Vite.
  if [ -n "$MOTIF_NODE_MODULES" ] && [ "$(printf '%s
' "$corps" | ci_sert_par_vite)" = oui ]; then
    rapporter INCONNU "$1" "$2" "$MOTIF_NODE_MODULES"
    return
  fi

  printf '%s\n' "$corps" > "$TMP/etape.sh"
  : > "$TMP/sauts"
  t0=$(date +%s)
  dans_etape "$3" bash -e "$TMP/etape.sh" > "$TMP/sortie" 2>&1
  code=$?
  sortie=$(ci_requalifier "$code" < "$TMP/sortie")
  relance=$(relancer_si_import_vite "$3" "$code" "$corps")
  [ -n "$relance" ] && { sortie=OK; NB_RELANCES=$((NB_RELANCES + $(ci_tests_tombes < "$TMP/sortie" | grep -c .))); }
  duree=$(( $(date +%s) - t0 ))
  case "$sortie" in
    OK)       sauts=$(ci_resumer_sauts < "$TMP/sauts")
              n_sauts=${sauts%% *}
              NB_SAUTS=$((NB_SAUTS + ${n_sauts:-0}))
              rapporter OK "$1" "$2" "${duree}s${sauts:+ — $sauts}${relance:+ — $relance}" ;;
    INCONNU*) rapporter INCONNU "$1" "$2" "${sortie#INCONNU } (${duree}s)" ;;
    *)        rapporter FAIL "$1" "$2" "code $code (${duree}s)"
              sed 's/^/      │ /' "$TMP/sortie" | tail -15
              mkdir -p "$ECHECS"
              cp "$TMP/sortie" "$ECHECS/$1-$NB_FAIL.log"
              echo "      │ … sortie complète : $ECHECS/$1-$NB_FAIL.log" ;;
  esac
}

# ── Déroulement ──────────────────────────────────────────────────────────────
echo "Rejeu de $CI sur $SHA_COURT — $ECRIT commande(s) extraite(s)"
[ -n "$FILTRE" ] && echo "Jobs retenus : $FILTRE"
echo "───────────────────────────────────────────────────────────────────────────────"

JOB=""; ETAPE=""; GENRE=""; REP=""; USES=""; WITH=""; DANS_RUN=0; RETENU=1
: > "$TMP/env"; : > "$TMP/corps"

lancer_si_besoin() {
  [ "$RETENU" -eq 1 ] || return
  [ "$GENRE" = "run" ] || return
  executer "$JOB" "$ETAPE" "$REP"
}

while IFS= read -r ligne <&3; do
  case "$ligne" in
    '@@ERREUR'*)
      echo "✗ Protocole rompu : ${ligne#*$'\t'}"
      echo "  Rien n'a été rejoué — ne pas lire ceci comme un succès."
      exit 2 ;;
    '@@STEP'*)
      IFS=$'\t' read -r _ JOB _ ETAPE GENRE REP USES WITH <<< "$ligne"
      #  `-` est le marqueur de champ vide posé par `nz()` côté extraction.
      [ "$ETAPE" = "-" ] && ETAPE=""
      [ "$REP"   = "-" ] && REP=""
      [ "$USES"  = "-" ] && USES=""
      [ "$WITH"  = "-" ] && WITH=""
      : > "$TMP/env"; : > "$TMP/corps"; DANS_RUN=0
      RETENU=1
      if [ -n "$FILTRE" ]; then
        case " $FILTRE " in *" $JOB "*) RETENU=1 ;; *) RETENU=0 ;; esac
      fi
      if [ "$GENRE" = "uses" ] && [ "$RETENU" -eq 1 ]; then
        case "$USES" in
          *checkout*) ;;
          *) rapporter "ENV" "$JOB" "${ETAPE:-$USES}" \
               "épinglé « ${WITH:-—} » · poste $(version_locale "$USES")" ;;
        esac
      fi ;;
    '@@ENV'*)   printf '%s\n' "${ligne#*$'\t'}" >> "$TMP/env" ;;
    '@@RUN')    DANS_RUN=1; : > "$TMP/corps" ;;
    '@@END')    DANS_RUN=0; lancer_si_besoin ;;
    *)          [ "$DANS_RUN" -eq 1 ] && printf '%s\n' "$ligne" >> "$TMP/corps" ;;
  esac
done 3< "$TMP/flux"

# ── Conclusion ───────────────────────────────────────────────────────────────
REJOUEES=$((NB_OK + NB_FAIL + NB_INCONNU))
echo "───────────────────────────────────────────────────────────────────────────────"
printf "%d étape(s) rejouée(s) sur %d extraite(s) — OK=%d ÉCHEC=%d INCONNU=%d (préparation=%d)\n" \
       "$REJOUEES" "$ECRIT" "$NB_OK" "$NB_FAIL" "$NB_INCONNU" "$NB_PREP"
[ "$NB_SAUTS" -gt 0 ] && echo "· $NB_SAUTS test(s) sauté(s) ici, que seule la CI GitHub joue — le détail est sur la ligne de leur étape (#1734)."
[ "$NB_RELANCES" -gt 0 ] && echo "· $NB_RELANCES test(s) e2e relancé(s) après l'import dynamique de Vite (#1809) — journal : $JOURNAL_RELANCES"

if [ "$REJOUEES" -eq 0 ]; then
  echo "? Aucune étape rejouée — ce n'est pas un succès, c'est une absence de mesure."
  exit 2
fi

if [ -n "$FILTRE" ]; then
  echo "  (rejeu partiel : aucune trace écrite — le point 16 du pré-check exige le rejeu complet.)"
else
  mkdir -p "$(dirname "$MARQUEUR")"
  printf '%s %s OK=%d FAIL=%d INCONNU=%d SAUTS=%d RELANCES=%d\n' "$SHA" "$(date +%s)" \
    "$NB_OK" "$NB_FAIL" "$NB_INCONNU" "$NB_SAUTS" "$NB_RELANCES" > "$MARQUEUR"
fi

[ "$NB_FAIL" -gt 0 ] && { echo "✗ La CI échouerait — corriger avant de pousser."; exit 1; }
[ "$NB_INCONNU" -gt 0 ] && { echo "? Des étapes n'ont pas pu être rejouées ici : un INCONNU n'est pas un vert."; exit 2; }
echo "✓ Toutes les étapes rejouables sont passées."
exit 0
