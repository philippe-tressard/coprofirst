#!/bin/bash
# =============================================================================
#  lib-ci-prevol.sh — Le PRÉ-VOL du rejeu : le poste peut-il mesurer le lot ?
#
#  Module SOURCÉ par `lib-ci-replay.sh`, jamais exécuté (pas de bit x). Ses cas
#  d'autotest (`ci_prevol_cas`) tournent dans `rejouer-ci.sh --selftest`.
#
#  POURQUOI (#2224, 24/10/2026). Sur 72 rejeux, sept ont fini INCONNU parce que
#  le poste n'avait pas les dépendances du lot (nh3, pypdf, markupsafe) : 149 min
#  tournées pour rien, l'écart découvert au bout de 20 min, à l'étape pytest. Le
#  rejeu savait le dire dès la première seconde — il ne le disait qu'en route.
#  Le pré-vol pose TOUTES les questions d'environnement avant la première étape,
#  et un écart REFUSE le rejeu avec la commande qui répare. Un refus n'est pas
#  un échec du lot : rien n'a été mesuré, et rien n'est écrit.
#
#  Ce qui est sondé dépend des jobs RETENUS : un rejeu de `lint-backend` seul ne
#  demande ni Playwright ni la base des tests — c'est aussi l'issue de secours
#  quand un écart ne se répare pas tout de suite.
#  Les verdicts sont purs ; les sondes, à côté, ne font que lire.
# =============================================================================

# ── Verdicts (PURS) ─────────────────────────────────────────────────────────
#  Une version du poste contre celle que la CI épingle. Plus ANCIENNE : refus —
#  le 24/09/2026, un Node 20 masquait le 22 de la CI et sept contrôles du front
#  échouaient (`fs.globSync` absent). Plus RÉCENTE : noté, le rejeu continue —
#  c'est l'état ordinaire du poste (Python 3.14, Node 24), et le refuser
#  interdirait tout rejeu.
#    $1 = node | python, $2 = épinglée (« 22 », '3.12'), $3 = celle du poste
#    → "" | "NOTE <motif>" | "REFUS <motif>"
ci_version_etat() {
  local epinglee="${2//[\"\' ]/}" poste="${3:-}" n=1 a b
  [ "$1" = python ] && n=2
  [ -z "$poste" ] && { echo "REFUS $1 introuvable sur le poste (CI : $epinglee)"; return; }
  [ -z "$epinglee" ] && { echo ""; return; }
  a=$(printf '%s' "$epinglee" | cut -d. -f1-"$n")
  b=$(printf '%s' "$poste" | cut -d. -f1-"$n")
  if [ "$a" = "$b" ]; then echo ""
  elif [ "$(printf '%s\n%s\n' "$a" "$b" | sort -t. -k1,1n -k2,2n | head -1)" = "$b" ]; then
    echo "REFUS $1 $poste plus ancien que la CI ($epinglee) : installer $1 $a"
  else
    echo "NOTE $1 $poste, plus récent que la CI ($epinglee)"
  fi
}

#  Les navigateurs de Playwright du lot sont-ils installés ? Le lot épingle une
#  RÉVISION de Chromium (`playwright-core/browsers.json`) ; un dossier d'une
#  autre révision ne la remplace pas.
#    $1 = révision attendue (vide : illisible), $2 = présente oui|non
ci_playwright_etat() {
  [ -z "${1:-}" ] && { echo "REFUS révision de Chromium illisible (front/node_modules absent ?) · réparer : (cd front && npm ci --legacy-peer-deps)"; return; }
  [ "${2:-non}" = oui ] && echo "" \
    || echo "REFUS Chromium $1 de Playwright absent du poste · réparer : (cd front && npx playwright install chromium)"
}

#  Un venv ANNONCÉ (`VIRTUAL_ENV`) est-il celui qui répond ? Écrit `C:/…` dans
#  le PATH, le deux-points coupe l'entrée sous Git Bash et c'est le Python du
#  poste qui répond — trois rejeux perdus le 23/10/2026.
#    $1 = VIRTUAL_ENV, $2 = sys.prefix du `python` du PATH — tous deux sous la
#    même forme (`cygpath -m`, minuscules)
ci_venv_etat() {
  [ -z "${1:-}" ] && { echo ""; return; }
  [ "$1" = "${2:-}" ] && echo "" \
    || echo "REFUS le venv annoncé ($1) n'est pas celui qui répond (${2:-python muet}) · réparer : PATH=\"\$(cygpath -u \"\$VIRTUAL_ENV\")/Scripts:\$PATH\" — jamais un chemin C:/…"
}

#  Les installations Python que la CI écrit, à rejouer dans un venv. (PURE)
#    stdin : flux de `ci_extraire` → `rép<TAB>arguments de pip install` — rép `-`
#    pour la racine : `read` avec IFS=tabulation avalerait un champ vide en tête.
#  Toutes, d'où qu'elles viennent — `pip install ruff==…`, `python -m pip
#  install reuse==…`, `pip install -r requirements-dev.txt` — : la liste des
#  outils n'est écrite qu'une fois, dans ci.yml.
ci_installations_python() {
  awk -F'\t' -v OFS='\t' '
    /^@@STEP/ { rep = $6; next }
    /^@@/     { next }
    {
      l = $0; sub(/^[[:space:]]+/, "", l)
      if (l ~ /^(python[0-9.]*[[:space:]]+-m[[:space:]]+)?pip3?[[:space:]]+install[[:space:]]/) {
        sub(/^.*install[[:space:]]+/, "", l); sub(/[[:space:]]*(&&|;|#).*$/, "", l)
        print rep, l
      }
    }'
}

# ── Sondes (lisent, n'écrivent rien) ────────────────────────────────────────
#  La révision de Chromium que le lot attend, ou vide.
ci_revision_chromium() {
  python - "$1/front/node_modules/playwright-core/browsers.json" 2>/dev/null <<'PYTHON' | tr -d '\r'
import json, sys
try:
    for b in json.load(open(sys.argv[1], encoding="utf-8"))["browsers"]:
        if b.get("name") == "chromium":
            print(b["revision"])
except Exception:
    pass
PYTHON
}

#  Où Playwright range ses navigateurs sur CE poste.
ci_dossier_navigateurs() {
  if [ -n "${PLAYWRIGHT_BROWSERS_PATH:-}" ]; then echo "$PLAYWRIGHT_BROWSERS_PATH"
  elif [ -n "${LOCALAPPDATA:-}" ]; then echo "$(cygpath -u "$LOCALAPPDATA" 2>/dev/null || echo "$LOCALAPPDATA")/ms-playwright"
  elif [ "$(uname -s)" = Darwin ]; then echo "$HOME/Library/Caches/ms-playwright"
  else echo "$HOME/.cache/ms-playwright"; fi
}

#  Le `node_modules` du front : un répertoire, un LIEN (jonction vers le clone
#  principal, #1722), ou absent. `-L` reconnaît aussi une jonction NTFS sous
#  Git Bash (mesuré le 07/10/2026).
ci_genre_node_modules() {
  local d="$1/front/node_modules"
  if [ -L "$d" ]; then echo lien
  elif [ -d "$d" ]; then echo repertoire
  else echo absent; fi
}

#  Un chemin sous une forme comparable (Windows : `C:/…` en minuscules).
ci_chemin_comparable() {
  local c="$1"
  command -v cygpath >/dev/null 2>&1 && c=$(cygpath -m "$c" 2>/dev/null || printf '%s' "$c")
  printf '%s\n' "${c,,}" | sed 's#/*$##'
}

# ── Le pré-vol lui-même ─────────────────────────────────────────────────────
#  Lit les dossiers d'étapes RETENUES (`$1/<idx>/` : job, genre, rep, corps,
#  env, uses, with) et pose chaque question une fois. Les dépendances se
#  vérifient côte à côte : le pré-vol tient en quelques secondes.
#    → affiche son bilan ; code 0 (le rejeu peut mesurer) | 2 (refus)
ci_prevol() {
  local e="$1" d job genre uses version poste motif t0 vite="" pytest="" ligne
  local -a sondes=()
  local refus="$TMP/prevol-refus" notes="$TMP/prevol-notes" faits="$TMP/prevol-faits"
  : > "$refus"; : > "$notes"; : > "$faits"
  t0=$(date +%s)
  for d in "$e"/*/; do
    d=${d%/}; job=$(<"$d/job"); genre=$(<"$d/genre")
    case "$genre" in
      USES)
        uses=$(<"$d/uses")
        version=$(sed -nE 's/.*-version: *([^ ]+).*/\1/p' "$d/with")
        case "$uses" in
          *setup-node*)   poste=$(node --version 2>/dev/null | tr -d 'v\r'); motif=$(ci_version_etat node "$version" "$poste") ;;
          *setup-python*) poste=$(python --version 2>&1 | awk '/^Python/{print $2}' | tr -d '\r'); motif=$(ci_version_etat python "$version" "$poste") ;;
          *) continue ;;
        esac
        case "$motif" in
          REFUS*) printf '%s\t%s\n' "$job" "${motif#REFUS }" >> "$refus" ;;
          NOTE*)  printf '%s\n' "${motif#NOTE }" >> "$notes" ;;
        esac ;;
      PREPARATION)
        #  Ce que l'installation poserait, contre ce que le poste a (#1417).
        ( ligne=$(python "$RACINE/scripts/poste/verifier-dependances-poste.py" --rep "$RACINE$(sed 's#^.#/&#' "$d/rep")" \
                    < "$d/corps" 2>/dev/null | tr -d '\r' | tail -1)
          printf '%s\n' "$(ci_dependances_etat "$ligne")" > "$d/prevol" ) &
        sondes+=("$!") ;;
      CONTROLE)
        [ -z "$pytest" ] && [ "$(ci_lance_pytest < "$d/corps")" = oui ] && pytest=$d
        [ -z "$vite" ] && [ "$(ci_sert_par_vite < "$d/corps")" = oui ] && vite=$d ;;
    esac
  done
  #  Ses sondes, et elles seules : un `wait` nu attendrait aussi le veilleur du
  #  verrou (#2225), qui ne finit qu'avec le rejeu — le pré-vol ne rendait jamais.
  [ ${#sondes[@]} -gt 0 ] && wait "${sondes[@]}"
  local nb_ecarts=0 rep
  for d in "$e"/*/; do
    d=${d%/}
    [ -s "$d/prevol" ] || continue
    motif=$(<"$d/prevol")
    [ -z "$motif" ] && continue
    nb_ecarts=$((nb_ecarts + 1)); rep=$(<"$d/rep")
    printf '%s\t%s · aligner : (cd %s && %s)%s\n' "$(<"$d/job")" "$motif" "${rep:-.}" \
      "$(grep -v '^[[:space:]]*#' "$d/corps" | tr '\n' ' ' | sed 's/ *$//')" \
      "$(grep -q 'pip' "$d/corps" && echo " — ou un venv aligné sur le lot : rejouer-ci.sh --venv")" >> "$refus"
  done
  [ "$nb_ecarts" -eq 0 ] && echo "dépendances alignées sur le lot" >> "$faits"
  if [ -n "$pytest" ]; then
    motif=$(ci_base_tests_etat "$(ci_dans_etape "$(<"$pytest/rep")" "$pytest/env" ci_sonder_base_tests)")
    if [ -n "$motif" ]; then printf '%s\t%s\n' "$(<"$pytest/job")" "$motif" >> "$refus"
    else echo "base des tests jointe" >> "$faits"; fi
    #  Un arbre de rejeu mort tient la base des tests : pytest s'y figerait (#2270). Le rejeu
    #  tient le verrou, aucun autre rejeu ne peut donc en être l'auteur : ces restes sont
    #  tués (`REJEU_ORPHELINS=signaler` : seulement nommés), puis les schémas qu'ils tenaient
    #  — ceux de plus d'une heure — sont retirés. Un reste qui résiste refuse le rejeu.
    if ! ci_orphelins_traiter "${REJEU_ORPHELINS:-tuer}"; then
      printf '%s	%s
' "$(<"$pytest/job")" "un reste de rejeu mort résiste et tient la base des tests · arrêter : taskkill //F //T //PID <pid ci-dessus>" >> "$refus"
    fi
    ci_gel_schemas_purger "$RACINE"
  fi
  if [ -n "$vite" ]; then
    job=$(<"$vite/job")
    motif=$(ci_node_modules_etat "$(ci_genre_node_modules "$RACINE")")
    [ -n "$motif" ] && printf '%s\t%s · réparer : cmd //c "rmdir front\\node_modules" && (cd front && npm ci --legacy-peer-deps) — rmdir retire le LIEN, jamais le node_modules partagé\n' "$job" "$motif" >> "$refus"
    version=$(ci_revision_chromium "$RACINE")
    motif=$(ci_playwright_etat "$version" "$([ -n "$version" ] && [ -d "$(ci_dossier_navigateurs)/chromium-$version" ] && echo oui || echo non)")
    if [ -n "$motif" ]; then printf '%s\t%s\n' "$job" "${motif#REFUS }" >> "$refus"
    else echo "node_modules du worktree, Chromium $version" >> "$faits"; fi
  fi
  motif=$(ci_venv_etat "$([ -n "${VIRTUAL_ENV:-}" ] && ci_chemin_comparable "$VIRTUAL_ENV")" \
    "$(ci_chemin_comparable "$(python -c 'import sys; print(sys.prefix)' 2>/dev/null | tr -d '\r')")")
  [ -n "$motif" ] && printf '%s\t%s\n' "tous" "${motif#REFUS }" >> "$refus"
  [ -n "${VIRTUAL_ENV:-}" ] && [ -z "$motif" ] && echo "venv en tête du PATH" >> "$faits"

  if [ -s "$refus" ]; then
    echo "✗ Pré-vol ($(( $(date +%s) - t0 )) s) : $(wc -l < "$refus") écart(s) — rien n'a été rejoué, ce n'est pas un échec du lot."
    sort -u "$refus" | while IFS=$'\t' read -r job motif; do echo "  ✗ [$job] $motif"; done
    local concernes autres
    concernes=$(cut -f1 "$refus" | sort -u | paste -sd' ' -)
    autres=$(for d in "$e"/*/; do cat "${d%/}/job"; echo; done | sort -u | grep -vxF -f <(cut -f1 "$refus") | paste -sd' ' -)
    case " $concernes " in
      *" tous "*) ;;
      *) [ -n "$autres" ] && echo "  Issue de secours, sans trace : bash scripts/poste/rejouer-ci.sh $autres" ;;
    esac
    return 2
  fi
  #  `paste -d` ne prend qu'un OCTET : « · » y serait coupé en deux.
  echo "✓ Pré-vol ($(( $(date +%s) - t0 )) s) : $(awk 'NR > 1 { printf " · " } { printf "%s", $0 }' "$faits")"
  sort -u "$notes" | while IFS= read -r ligne; do echo "  · $ligne — un écart de comportement reste possible"; done
  return 0
}

# ── Le venv aligné sur le lot (`--venv`) ────────────────────────────────────
#  Créé une fois par jeu de dépendances — la clé est l'empreinte des
#  installations de ci.yml, des fichiers qu'elles lisent (`-r`, suivis) et de
#  l'interpréteur —, puis réutilisé par tous les worktrees : il vit dans le
#  répertoire git COMMUN. Un venv ne se déplace pas (les lanceurs de pip y
#  écrivent leur chemin absolu) : il se construit en place, et ne compte qu'une
#  fois marqué `.complet`. Appelé SOUS le verrou du rejeu : deux rejeux ne le
#  construisent jamais ensemble. Les trois plus récents sont gardés.
#    $1 = racine du dépôt, $2 = répertoire git commun, $3 = flux de ci_extraire
#    → stdout : le dossier des exécutables du venv ; code ≠ 0 si échec
ci_venv_preparer() {
  local racine="$1" commun="$2" flux="$3" installs cle dossier bin py rep args f
  installs=$(ci_installations_python < "$flux")
  [ -z "$installs" ] && { echo "✗ aucune installation Python dans ci.yml : rien pour aligner un venv" >&2; return 2; }
  cle=$( {
    printf '%s\n' "$installs"
    python --version 2>&1
    while IFS=$'\t' read -r rep args; do
      [ "$rep" = "-" ] && rep=""
      for f in $(printf '%s\n' "$args" | grep -oE '(-r|--requirement)[= ]+[^ ]+' | sed -E 's/^(-r|--requirement)[= ]+//'); do
        ci_requirements_suivis "$racine${rep:+/$rep}/$f"
      done
    done <<< "$installs"
  } | sha256sum | cut -c1-12)
  dossier="$commun/rejeu-venv/$cle"
  bin="$dossier/Scripts"; [ -d "$dossier/bin" ] && bin="$dossier/bin"
  if [ ! -f "$dossier/.complet" ]; then
    echo "· venv aligné sur le lot : construction ($cle) — une fois par jeu de dépendances" >&2
    rm -rf "$dossier"
    python -m venv "$dossier" >&2 || return 2
    bin="$dossier/Scripts"; [ -d "$dossier/bin" ] && bin="$dossier/bin"
    py="$bin/python"
    "$py" -m pip install -q --upgrade pip >&2 || return 2
    while IFS=$'\t' read -r rep args; do
      [ "$rep" = "-" ] && rep=""
      # shellcheck disable=SC2086  # les arguments de pip, tels que ci.yml les écrit
      (cd "$racine${rep:+/$rep}" && "$py" -m pip install -q $args) >&2 || return 2
    done <<< "$installs"
    : > "$dossier/.complet"
  fi
  touch "$dossier/.complet"
  # shellcheck disable=SC2012  # noms de dossiers à nous, sans blanc
  ls -1t "$commun/rejeu-venv" 2>/dev/null | tail -n +4 | while read -r f; do rm -rf "${commun:?}/rejeu-venv/$f"; done
  echo "$bin"
}

#  Le contenu d'un fichier de requirements et de ceux qu'il inclut (`-r`).
ci_requirements_suivis() {
  [ -f "$1" ] || { echo "absent:$1"; return; }
  cat "$1"
  local inclus
  for inclus in $(grep -oE '^[[:space:]]*(-r|--requirement)[= ]+[^ #]+' "$1" | sed -E 's/^[[:space:]]*(-r|--requirement)[= ]+//'); do
    ci_requirements_suivis "$(dirname "$1")/$inclus"
  done
}

# ── Cas d'autotest — appelés par `ci_replay_selftest`, avec son `t` ─────────
ci_prevol_cas() {
  t "version — égale"                 "$(ci_version_etat node '"22"' 22.11.0)" ""
  t "version — python, mineure égale" "$(ci_version_etat python "'3.12'" 3.12.7)" ""
  t "version — plus récente : notée"  "$(ci_version_etat node '"22"' 24.20.0)" "NOTE node 24.20.0, plus récent que la CI (22)"
  t "version — python 3.14 contre 3.12 : notée, pas refusée" \
    "$(ci_version_etat python '"3.12"' 3.14.3)" "NOTE python 3.14.3, plus récent que la CI (3.12)"
  #  Le cas du 24/09/2026 : le Node 20 de `/usr/local/bin` masquait le 22.
  t "version — plus ancienne : refus" "$(ci_version_etat node '"22"' 20.18.0)" \
    "REFUS node 20.18.0 plus ancien que la CI (22) : installer node 22"
  t "version — 3.9 n'est pas plus récent que 3.12" "$(ci_version_etat python 3.12 3.9.1 | cut -c1-5)" "REFUS"
  #  🔴 Le cas zéro : pas de version lue, pas de rejeu.
  t "version — introuvable : refus"   "$(ci_version_etat node '"22"' "")" "REFUS node introuvable sur le poste (CI : 22)"
  t "playwright — présent"            "$(ci_playwright_etat 1248 oui)" ""
  t "playwright — absent : la commande qui répare" "$(ci_playwright_etat 1248 non)" \
    "REFUS Chromium 1248 de Playwright absent du poste · réparer : (cd front && npx playwright install chromium)"
  t "playwright — révision illisible : refus, jamais OK" "$(ci_playwright_etat "" oui | cut -c1-5)" "REFUS"
  t "venv — aucun annoncé"            "$(ci_venv_etat "" c:/python)" ""
  t "venv — celui qui répond"         "$(ci_venv_etat c:/v c:/v)" ""
  t "venv — le Python du poste répond à sa place" "$(ci_venv_etat c:/v c:/python314 | cut -c1-5)" "REFUS"
  t "installations — les quatre formes de ci.yml" "$(printf '@@STEP\tlint\t-\tA\trun\t-\t-\t-\n@@RUN\npip install ruff==0.15.8\n@@END\n@@STEP\tlint\t-\tB\trun\t-\t-\t-\n@@RUN\npython -m pip install reuse==6.2.0\npython -m reuse lint\n@@END\n@@STEP\ttest\t-\tC\trun\tapi\t-\t-\n@@RUN\npip install -r requirements-dev.txt\n@@END\n@@STEP\tx\t-\tD\trun\t-\t-\t-\n@@RUN\n# pip install rien\necho pip install non\n@@END\n' \
    | ci_installations_python | paste -sd'|' -)" "-	ruff==0.15.8|-	reuse==6.2.0|api	-r requirements-dev.txt"
  #  🔴 Un `wait` NU attend aussi le veilleur du verrou (#2225), qui ne finit
  #  qu'avec le rejeu : le pré-vol ne rendait plus la main (24/10/2026).
  t "aucun wait nu dans le rejeu (le veilleur ne finit qu'avec lui)" \
    "$(cat scripts/poste/rejouer-ci.sh scripts/lib/lib-ci-prevol.sh scripts/lib/lib-ci-execution.sh \
        scripts/lib/lib-ci-orchestration.sh 2>/dev/null | grep -cE '^[^#]*(^|[;&|{ ])wait[[:space:]]*($|[;&|}])')" "0"
  #  Le vrai fichier : au moins l'installation des dépendances de l'API — sans
  #  elle, un venv « aligné » n'aurait rien de l'API.
  if [ -f .github/workflows/ci.yml ]; then
    t "installations — ci.yml réel porte requirements-dev" \
      "$(ci_extraire < .github/workflows/ci.yml | ci_installations_python | grep -c 'requirements-dev')" "1"
  fi
}
