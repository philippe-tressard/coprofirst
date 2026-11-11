#!/usr/bin/env bash
# =============================================================================
#  conduire-mep.sh — le conducteur de MEP, versionné (#2631)
#
#  Du lot vérifié jusqu'à la production constatée, sans geste de mémoire :
#    1. le lot (PR vers `dev`) : fusionné quand ses checks sont verts ET que
#       GitHub dit `CLEAN` — jamais pendant `UNKNOWN` ;
#    2. la VERSION du train posée sur `dev`, calculée de `main` et des préfixes des
#       commits du train (`feat` → mineure, `!` → majeure, sinon correctif) : un lot
#       n'emporte plus de numéro ;
#    3. une seule PR `dev → main`, titrée de cette version ; ses checks verts et
#       `CLEAN`, hors de la fenêtre de bascule de la nuit ;
#    4. après la fusion : `dev` recréée depuis `main`, les PR qui visaient `dev`
#       ramenées dessus — reciblées, ou ROUVERTES si GitHub les a fermées (#2619) ;
#       une PR fermée à la main reste fermée, et le journal la nomme (#2688) ;
#    5. « Déployé: <sha> » attendu sur le nœud ACTIF, puis `precheck-mep.sh
#       --post-mep`, puis la veille de sécurité relancée sur `main`.
#
#  REPRISE. Chaque étape vérifie son fait avant d'agir, et l'état (PR `dev → main`,
#  PR suivies) est écrit dans le répertoire git commun : un conducteur tué reprend
#  là où il en était en le relançant avec les mêmes arguments. Un verrou empêche
#  deux conducteurs ; celui d'un conducteur mort se reprend seul.
#
#  Les DÉCISIONS sont des fonctions pures de `scripts/lib/lib-mep-conduite.sh`,
#  éprouvées par `--selftest` dans le job `test-scripts`. Ce script mesure et agit.
#
#  Usage :
#    bash scripts/poste/conduire-mep.sh --lot <n°|-> --titre "<préfixe>: {version} — …" \
#         --corps <fichier> [--a-blanc]
#    bash scripts/poste/conduire-mep.sh --selftest
#
#  `--lot -` : rien à fusionner dans `dev` (le train y est déjà). `{version}` est
#  remplacé par la version calculée. `--a-blanc` : tout est mesuré et décidé, la
#  version est même posée dans une copie jetable, mais rien n'est fusionné, poussé,
#  créé, rouvert ni relancé, et aucun état n'est écrit.
# =============================================================================
set -uo pipefail
# shellcheck source=../lib/lib-poste-gnu.sh
. "$(dirname "$0")/../lib/lib-poste-gnu.sh"
poste_gnu_poser "$@"   # macOS : les outils GNU en tête du PATH, comme Git Bash et la CI (#2419)

RACINE_DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [ "${1:-}" = "--selftest" ]; then
  exec bash "$RACINE_DEPOT/scripts/lib/lib-mep-conduite.sh" --selftest
fi
cd "$RACINE_DEPOT" || exit 1
# shellcheck source=../lib/lib-mep-conduite.sh
. "$RACINE_DEPOT/scripts/lib/lib-mep-conduite.sh"   # décisions ; charge lib-verdicts-mep (rang, parité)
. "$RACINE_DEPOT/scripts/lib/lib-depot.sh"          # répertoire commun, comptes des checks

. "$RACINE_DEPOT/scripts/lib/lib-role.sh"           # les nœuds : une table, jamais recopiée
RPI1="${RPI1:-$(noeud_ssh rpi1)}"
RPI2="${RPI2:-$(noeud_ssh rpi2)}"
DELAI_CHECKS_MIN=${DELAI_CHECKS_MIN:-90}     # la CI d'une PR : ~20 min, « Images » comprise
DELAI_DEPLOYE_MIN=${DELAI_DEPLOYE_MIN:-60}   # images de la CI ~15 min, secours local à 30 min
PAUSE_S=${PAUSE_S:-60}
ESSAIS_DEV=${ESSAIS_DEV:-24}; PAUSE_DEV_S=${PAUSE_DEV_S:-5}   # suppression asynchrone de dev : 2 min au plus (#2676)

LOT=""; TITRE=""; CORPS=""; A_BLANC=""
while [ $# -gt 0 ]; do
  case "$1" in
    --lot)     LOT=${2:-}; shift 2 ;;
    --titre)   TITRE=${2:-}; shift 2 ;;
    --corps)   CORPS=${2:-}; shift 2 ;;
    --a-blanc) A_BLANC=1; shift ;;
    *) echo "argument inconnu : $1 (voir l'en-tête)"; exit 2 ;;
  esac
done
[ -n "$LOT" ] && [ -n "$TITRE" ] && [ -f "$CORPS" ] || {
  echo "usage : conduire-mep.sh --lot <n°|-> --titre \"…{version}…\" --corps <fichier> [--a-blanc]"; exit 2; }

dire() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
stop() { dire "STOP — $*"; exit 1; }
g()    { timeout -k 5 60 gh "$@" </dev/null; }
sur()  { timeout 25 ssh -o BatchMode=yes -o ConnectTimeout=8 "$1" "$2" 2>/dev/null; }
#  Un geste qui ÉCRIT (GitHub, dépôt distant, état) passe par ici : à blanc, il se dit.
agir() { local quoi=$1; shift
  if [ -n "$A_BLANC" ]; then dire "À BLANC — $quoi"; return 0; fi
  dire "$quoi"; "$@"; }

# ── Verrou et état, dans le répertoire git commun ────────────────────────────
COMMUN=$(dossier_git_commun) || stop "répertoire git introuvable"
VERROU="$COMMUN/conduite-mep.verrou"; ETAT="$COMMUN/conduite-mep.etat"
etat_lire()   { sed -n "s/^$1=//p" "$ETAT" 2>/dev/null | tail -1; }
etat_ecrire() { [ -n "$A_BLANC" ] && return 0; printf '%s=%s\n' "$1" "$2" >> "$ETAT"; }
if [ -z "$A_BLANC" ]; then
  PID_LU=$(cat "$VERROU" 2>/dev/null); VIVANT=non
  [ -n "$PID_LU" ] && kill -0 "$PID_LU" 2>/dev/null && VIVANT=oui
  case "$(verdict_verrou "$PID_LU" "$VIVANT")" in
    REFUSER)   stop "un conducteur tourne déjà (pid $PID_LU)" ;;
    REPRENDRE) dire "verrou du conducteur $PID_LU, mort : repris" ;;
  esac
  echo $$ > "$VERROU"; trap 'rm -f "$VERROU"' EXIT
fi

# ── Mesures ──────────────────────────────────────────────────────────────────
lire_version() { git show "$1:front/package.json" 2>/dev/null | grep -m1 '"version"' | cut -d'"' -f4; }
etat_pr()      { g pr view "$1" --json state,baseRefName --jq '.state + " " + .baseRefName' 2>/dev/null; }
checks_pr()    { g pr view "$1" --json statusCheckRollup,mergeStateStatus \
                   --jq "[$COMPTES_CHECKS_JQ, .mergeStateStatus] | map(tostring) | join(\" \")" 2>/dev/null; }
synchroniser() { timeout -k 5 60 git fetch -q origin --prune 2>/dev/null || dire "fetch en échec — la suite lit l'état d'avant"; }

# attendre_fusionnable n° [une] → 0 quand FUSIONNER ; STOP sur un rouge ou un état bloquant
attendre_fusionnable() {
  local n=$1 une=${2:-} i v mesure precedent=""
  for ((i = 0; i < DELAI_CHECKS_MIN * 60 / PAUSE_S; i++)); do
    mesure=$(checks_pr "$n"); read -r NB COURS ROUGES ETAT_GH <<<"$mesure"
    v=$(verdict_fusion "${NB:-}" "${COURS:-}" "${ROUGES:-}" "${ETAT_GH:-}")
    [ "$v $mesure" != "$precedent" ] && dire "PR #$n : ${NB:-?} check(s), ${COURS:-?} en cours, ${ROUGES:-?} rouge(s), état ${ETAT_GH:-?} → $v"
    precedent="$v $mesure"
    case "$v" in
      FUSIONNER) return 0 ;;
      STOP)      stop "PR #$n non fusionnable (${ROUGES:-?} rouge(s), état ${ETAT_GH:-?})" ;;
    esac
    [ -n "$une" ] && return 1
    sleep "$PAUSE_S"
  done
  stop "PR #$n : délai de $DELAI_CHECKS_MIN min dépassé"
}

# fusionner n° — squash, puis le FAIT : l'état MERGED relu, pas le code de retour
fusionner() {
  local n=$1 i
  agir "fusion de la PR #$n (squash)" g pr merge "$n" --squash || stop "fusion de #$n refusée"
  [ -n "$A_BLANC" ] && return 0
  for i in 1 2 3 4 5 6 7 8 9 10; do
    [ "$(etat_pr "$n" | cut -d' ' -f1)" = MERGED ] && { dire "PR #$n MERGED"; return 0; }
    sleep 15
  done
  stop "PR #$n : MERGED non constaté après la fusion"
}

# lire_dev — le sha de `dev` sur GitHub, `absent` si la lecture réussit sans la trouver,
#  vide si le dépôt distant ne répond pas (jamais lu comme « absente »).
lire_dev() {
  local l
  l=$(timeout 30 git ls-remote --heads origin dev 2>/dev/null) || { echo ""; return; }
  [ -z "$l" ] && echo absent || echo "${l%%[[:space:]]*}"
}

# recreer_dev — `dev` supprimée : recréée sur origin/main par l'API (le hook `pre-push`
#  refuse un push sans trace de pré-check, et il n'y a rien à vérifier), puis RELUE.
recreer_dev() {
  local m; m=$(git rev-parse origin/main)
  agir "dev absente : recréée sur origin/main (${m:0:8})" \
    g api -X POST "repos/{owner}/{repo}/git/refs" -f ref=refs/heads/dev -f sha="$m" --jq .ref >/dev/null \
    || stop "recréation de dev refusée par GitHub"
  [ -n "$A_BLANC" ] && return 0
  [ "$(lire_dev)" = "$m" ] || stop "dev relue après sa recréation : « $(lire_dev) », attendu ${m:0:8}"
  synchroniser
}

# assurer_dev — avant le train et avant chaque reciblage : `dev` doit exister.
assurer_dev() {
  case "$(lire_dev)" in
    "")     stop "dépôt distant muet : dev illisible" ;;
    absent) recreer_dev ;;
  esac
}

# fermeture_pr n° → « closedAt derniers » : l'heure de la dernière fermeture, et les deux
#  derniers événements de la PR parmi fermeture, suppression de sa base et réouverture
#  (`fermee_par_suppression` dit ce qu'on y lit). Vide si GitHub ne répond pas.
fermeture_pr() {
  g api graphql -F owner='{owner}' -F name='{repo}' -F n="$1" -f query='
    query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){pullRequest(number:$n){
      closedAt timelineItems(last:2,itemTypes:[CLOSED_EVENT,BASE_REF_DELETED_EVENT,REOPENED_EVENT]){nodes{__typename}}}}}' \
    --jq '.data.repository.pullRequest|(.closedAt // "-")+" "+([.timelineItems.nodes[].__typename]|join("+"))' 2>/dev/null
}

# geste_pour n° etat base → le geste de `geste_pr_suivie`. Une PR FERMÉE se juge sur
#  quand et par quoi elle l'a été, face à l'heure de fusion du train (#2688) : fermée à
#  la main, ou une mesure illisible, elle rend LAISSER et personne n'y touche.
geste_pour() {
  local n=$1 st=${2:-} base=${3:-} ferme="" derniers=""
  [ "$st" = CLOSED ] && read -r ferme derniers <<<"$(fermeture_pr "$n")"
  geste_pr_suivie "$st" "$base" "$ferme" "${FUSION_LE:-}" "$derniers"
}

# ramener_pr n° — une PR suivie revient sur `dev`, et le FAIT se relit (#2676) : un
#  reciblage refusé arrête le conducteur en nommant la PR, il ne continue jamais.
ramener_pr() {
  local n=$1 st base
  read -r st base <<<"$(etat_pr "$n")"
  [ "$(verdict_recible "${st:-}" "${base:-}")" = OK ] && return 0
  case "$(geste_pour "$n" "${st:-}" "${base:-}")" in
    ROUVRIR)  agir "PR #$n fermée par la suppression de dev : rouverte" g pr reopen "$n" >/dev/null \
                || stop "PR #$n : réouverture refusée — la rouvrir et la recibler sur dev à la main" ;;
    RECIBLER) ;;
    LAISSER)  return 0 ;;   # fermée autrement que par la suppression de dev : on n'y touche pas
    *)        stop "PR #$n : état illisible (« ${st:-?} ${base:-?} »)" ;;
  esac
  assurer_dev
  agir "PR #$n reciblée sur dev (elle visait ${base:-?})" g pr edit "$n" --base dev >/dev/null \
    || stop "PR #$n : reciblage sur dev refusé par GitHub — elle vise ${base:-?}"
  [ -n "$A_BLANC" ] && return 0
  read -r st base <<<"$(etat_pr "$n")"
  [ "$(verdict_recible "${st:-}" "${base:-}")" = OK ] || stop "PR #$n : relue « ${st:-?} vers ${base:-?} » après reciblage"
}

# poser_version cible — commit `chore(version)` sur origin/dev, dans une copie JETABLE
#  (jamais la copie de qui coordonne). `npm version` réécrit les deux fichiers et les
#  trois lignes du projet ; le diff le vérifie avant de pousser — le bump au `sed` a
#  menti sur deux dépendances le 15/09/2026.
poser_version() {
  local cible=$1 tmp diff
  tmp=$(mktemp -d)/copie
  git worktree add -q --detach "$tmp" origin/dev || stop "copie jetable impossible"
  #  La copie est DÉTACHÉE : ce qu'on y committe sans le pousser n'atteint aucune
  #  branche, et elle se retire sans `--force` ni remise partagée.
  jeter() { git -C "$tmp" -c commit.gpgsign=false commit -q -am "jetable" >/dev/null 2>&1
            git worktree remove "$tmp" 2>/dev/null || dire "copie jetable laissée en place : $tmp"; }
  (cd "$tmp/front" && npm version "$cible" --no-git-tag-version --ignore-scripts >/dev/null 2>&1) \
    || { jeter; stop "npm version $cible a échoué"; }
  diff=$(git -C "$tmp" diff --numstat | tr '\t' ' ' | tr '\n' ';')
  case "$diff" in
    "2 2 front/package-lock.json;1 1 front/package.json;") ;;   # le projet, en tête et à la racine du lock
    *) jeter; stop "le bump touche autre chose que les lignes de version : $diff" ;;
  esac
  dire "version $cible posée dans la copie jetable : $diff"
  git -C "$tmp" -c commit.gpgsign=false commit -q -am "chore(version): bump v$cible

Posée par scripts/poste/conduire-mep.sh depuis les préfixes du train (#2631).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || { jeter; stop "commit du bump impossible"; }
  #  Avance rapide seulement : si `dev` a bougé entre-temps, le push est refusé et la
  #  reprise recalcule la version sur le nouveau train.
  agir "push du bump v$cible sur dev" env SKIP_PRECHECK=1 git -C "$tmp" push -q origin HEAD:refs/heads/dev \
    || { jeter; stop "push du bump refusé (dev a bougé ?) — relancer"; }
  jeter
  [ -z "$A_BLANC" ] && synchroniser
  return 0
}

dire "═══ Conduite de MEP$([ -n "$A_BLANC" ] && echo " — À BLANC (rien n’est écrit)") ═══"
synchroniser
PR_MAIN=$(etat_lire pr_main)
ETAT_MEMO=""; [ -n "$PR_MAIN" ] && ETAT_MEMO=$(etat_pr "$PR_MAIN" | cut -d' ' -f1)
ETAPE=$(etape_reprise "$ETAT_MEMO")
[ -n "$PR_MAIN" ] && dire "état mémorisé : PR dev → main #$PR_MAIN ${ETAT_MEMO:-?} → reprise : $ETAPE"

if [ "$ETAPE" = TRAIN ]; then
  assurer_dev
  # ── 1. Le lot ──
  TITRE_LOT=""
  if [ "$LOT" != "-" ]; then
    read -r ST BASE <<<"$(etat_pr "$LOT")"
    [ "${BASE:-}" = dev ] || stop "la PR #$LOT vise « ${BASE:-?} », pas dev"
    case "${ST:-}" in
      MERGED) dire "lot #$LOT déjà fusionné dans dev" ;;
      OPEN)   TITRE_LOT=$(g pr view "$LOT" --json title --jq .title)
              attendre_fusionnable "$LOT"; fusionner "$LOT"; sleep 15; synchroniser ;;
      *)      stop "lot #$LOT dans l'état « ${ST:-illisible} »" ;;
    esac
  fi
  # ── 2. La version du train ──
  V_MAIN=$(lire_version origin/main); V_DEV=$(lire_version origin/dev)
  #  À blanc, le lot n'est pas fusionné : son titre deviendra le sujet du squash.
  SUJETS=$( { git log origin/main..origin/dev --format='%s%n%b'; [ -n "$A_BLANC" ] && printf '%s\n' "$TITRE_LOT"; } \
              | grep -v '^chore(version)')
  RANG=$(rang_attendu "$SUJETS")
  read -r GESTE CIBLE <<<"$(decision_version "$V_MAIN" "$V_DEV" "$RANG")"
  dire "train : main=${V_MAIN:-?} dev=${V_DEV:-?} rang=$RANG → ${GESTE:-?} ${CIBLE:-}"
  case "$GESTE" in
    POSER|REPOSER) poser_version "$CIBLE" ;;
    DEJA) ;;
    *) stop "version du train incalculable (main=${V_MAIN:-?}, rang=$RANG)" ;;
  esac
  #  Les points 0d et 0g, rejugés sur ce qui part : le rang de la version posée.
  [ "$(verdict_rang_version "$RANG" "$V_MAIN" "$CIBLE")" = OK ] || stop "0g : $V_MAIN → $CIBLE ne correspond pas au rang $RANG"
  # ── 3. Une seule PR dev → main ──
  TITRE_FINAL=$(titre_avec_version "$TITRE" "$CIBLE")
  [ -n "$TITRE_FINAL" ] || stop "le titre doit porter la marque {version}"
  [ "$(verdict_titre_train "$(rang_attendu "$TITRE_FINAL")" "$RANG")" = OK ] \
    || stop "le titre annonce un $(rang_attendu "$TITRE_FINAL"), le train un $RANG — c'est le titre qui devient le commit de main"
  for n in $(g pr list --base main --state open --json number,headRefName --jq '.[]|select(.headRefName!="dev")|.number'); do
    agir "PR #$n vise main : reciblée sur dev (une seule PR vers main, celle de dev)" g pr edit "$n" --base dev >/dev/null
  done
  PR_MAIN=$(g pr list --base main --head dev --state open --json number --jq '.[0].number // empty')
  if [ -z "$PR_MAIN" ]; then
    if [ -n "$A_BLANC" ]; then dire "À BLANC — création de la PR dev → main « $TITRE_FINAL »"
    else PR_MAIN=$(g pr create --base main --head dev --title "$TITRE_FINAL" --body-file "$CORPS" | grep -oE '[0-9]+$')
         [ -n "$PR_MAIN" ] || stop "création de la PR dev → main impossible"; dire "PR dev → main #$PR_MAIN créée"; fi
  else
    agir "PR dev → main #$PR_MAIN : titre « $TITRE_FINAL »" g pr edit "$PR_MAIN" --title "$TITRE_FINAL" --body-file "$CORPS" >/dev/null
  fi
  etat_ecrire pr_main "$PR_MAIN"
  #  Les PR qui visent `dev` MAINTENANT : la fusion du train les recible ou les ferme.
  SUIVIES=$(g pr list --base dev --state open --limit 100 --json number --jq '[.[].number]|map(tostring)|join(" ")')
  etat_ecrire suivies "$SUIVIES"
  dire "PR suivies (visent dev) : ${SUIVIES:-aucune}"
  # ── 4. Fusion du train, hors de la fenêtre de bascule ──
  if [ -n "$PR_MAIN" ]; then
    if [ -n "$A_BLANC" ]; then attendre_fusionnable "$PR_MAIN" une || true
    else attendre_fusionnable "$PR_MAIN"; fi
  fi
  [ "$(dans_fenetre "$(date +%H:%M)")" = non ] \
    || stop "fenêtre de bascule ($FENETRE_BASCULE_DEBUT-$FENETRE_BASCULE_FIN) : relancer après $FENETRE_BASCULE_FIN, la reprise lit l'état"
  #  Le commit de `dev` qui part : c'est lui que la suppression asynchrone laisse lisible.
  [ -n "$PR_MAIN" ] && DEV_AVANT=$(g pr view "$PR_MAIN" --json headRefOid --jq .headRefOid) && etat_ecrire dev_avant "$DEV_AVANT"
  [ -n "$PR_MAIN" ] && fusionner "$PR_MAIN"
fi

# ── 5. Après la fusion : dev, les PR suivies, le déploiement ──
synchroniser
M=$(git rev-parse origin/main)
DEV_AVANT=${DEV_AVANT:-$(etat_lire dev_avant)}
SUIVIES=${SUIVIES:-$(etat_lire suivies)}
if [ -n "$A_BLANC" ]; then
  dire "À BLANC — après la fusion : attendre que GitHub supprime dev (${DEV_AVANT:0:8}), au plus $((ESSAIS_DEV * PAUSE_DEV_S)) s, puis la recréer sur main"
  for n in $SUIVIES; do read -r ST BASE <<<"$(etat_pr "$n")"; dire "PR #$n : ${ST:-?} vers ${BASE:-?} — ramenée sur dev et relue"; done
else
  #  GitHub supprime `dev` APRÈS la fusion, quand il veut (#2676) : on attend le fait.
  case "$(attendre_dev_supprimee lire_dev "$ESSAIS_DEV" "$PAUSE_DEV_S" "$DEV_AVANT" "$M")" in
    RECREER)       recreer_dev ;;
    PRETE)         dire "dev déjà recréée sur main (${M:0:8})" ;;
    NON_SUPPRIMEE) dire "⚠ dev non supprimée après $((ESSAIS_DEV * PAUSE_DEV_S)) s : elle porte encore l'historique d'avant le squash — les PR qui la visent restent valides" ;;
    AUTRE)         stop "dev porte un commit inconnu ($(lire_dev | cut -c1-8)) — quelqu'un y a poussé pendant la fusion : vérifier à la main" ;;
    *)             stop "dev illisible après la fusion (dépôt distant muet)" ;;
  esac
  #  L'heure de fusion du train : une PR suivie fermée AVANT elle l'a été à la main (#2688).
  FUSION_LE=""; [ -n "$PR_MAIN" ] && FUSION_LE=$(g pr view "$PR_MAIN" --json mergedAt --jq '.mergedAt // ""' 2>/dev/null)
  dire "train fusionné le ${FUSION_LE:-? (heure illisible : aucune PR fermée ne sera rouverte)}"
  #  Trois passes : GitHub recible lui aussi de façon asynchrone. Une PR qui reste hors de
  #  `dev` à la dernière passe arrête le conducteur, nommée.
  LAISSEES=""
  for passe in 1 2 3; do
    A_RAMENER=""
    for n in $SUIVIES $(g pr list --base main --state open --json number,headRefName --jq '.[]|select(.headRefName!="dev")|.number'); do
      read -r ST BASE <<<"$(etat_pr "$n")"
      [ "$(verdict_recible "${ST:-}" "${BASE:-}")" = OK ] && continue
      if [ "$(geste_pour "$n" "${ST:-}" "${BASE:-}")" = LAISSER ]; then
        case " $LAISSEES " in *" $n "*) ;; *)
          LAISSEES="$LAISSEES $n"
          dire "⚠ PR #$n fermée, mais pas par la suppression de dev après la fusion du train (ou la mesure est illisible) : laissée fermée. Si elle devait revenir : gh pr reopen $n && gh pr edit $n --base dev" ;;
        esac
        continue
      fi
      A_RAMENER="$A_RAMENER $n"
    done
    [ -z "$A_RAMENER" ] && [ "$passe" -ge 2 ] && { dire "PR suivies : toutes sur dev${LAISSEES:+ — laissées fermées :$LAISSEES}"; break; }
    [ -n "$A_RAMENER" ] && [ "$passe" = 3 ] && stop "PR toujours hors de dev :$A_RAMENER"
    for n in $A_RAMENER; do ramener_pr "$n"; done
    sleep 15
  done
fi
A=$(sur "$RPI1" 'cat /opt/5hostachy/.active')
case "$A" in rpi1) ACTIF=$RPI1 ;; rpi2) ACTIF=$RPI2 ;; *) stop "nœud actif illisible (« ${A:-?} »)" ;; esac
dire "actif=$A — attente de « Déployé: ${M:0:8} »"
for ((i = 0; i < DELAI_DEPLOYE_MIN * 60 / PAUSE_S; i++)); do
  D=$(sur "$ACTIF" "grep -o 'Déployé: [0-9a-f]*' /var/log/hostachy-deploy.log 2>/dev/null | tail -1"); D=${D#Déployé: }
  [ "$(memes_hachages "$M" "$D")" = oui ] && { dire "Déployé: $D sur $A"; break; }
  [ -n "$A_BLANC" ] && { dire "À BLANC — dernier « Déployé: » de $A : ${D:-absent} (origin/main ${M:0:8})"; break; }
  sleep "$PAUSE_S"
done
[ -n "$A_BLANC" ] || [ "$(memes_hachages "$M" "${D:-}")" = oui ] || stop "pas de « Déployé: ${M:0:8} » en $DELAI_DEPLOYE_MIN min"
bash scripts/poste/precheck-mep.sh --post-mep; RC_POST=$?
agir "veille de sécurité relancée sur main" g workflow run veille-securite.yml --ref main
[ -z "$A_BLANC" ] && rm -f "$ETAT"
[ "$RC_POST" = 0 ] || stop "post-check en échec (code $RC_POST) — diagnostiquer, ou rollback (skill mep-precheck)"
dire "✓ MEP conduite$([ -n "$A_BLANC" ] && echo ' à blanc') — origin/main ${M:0:8}, version $(lire_version origin/main)"
