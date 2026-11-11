#!/usr/bin/env bash
# =============================================================================
#  lib-mep-conduite.sh — les DÉCISIONS du conducteur de MEP (#2631)
#
#  POURQUOI. Jusqu'au 10/11/2026, le conducteur vivait dans le dossier temporaire
#  de la session qui coordonnait : fusion du lot, PR `dev → main`, attente des
#  checks, recréation de `dev`, reciblage, « Déployé », post-check. Il disparaissait
#  avec elle, n'avait aucun autotest, et ses défauts se sont vus le soir même :
#  une fusion lancée pendant que GitHub calculait encore l'état (`UNKNOWN`), une PR
#  en brouillon FERMÉE par la recréation de `dev` (#2619), un arrêt sans reprise,
#  et trois collisions de numéro de version entre lots en file.
#
#  Ce module porte ce que le conducteur DÉCIDE, en fonctions pures : aucun appel
#  réseau, aucun git, aucune écriture. `scripts/poste/conduire-mep.sh` mesure et
#  agit ; ses décisions passent toutes par ici, et `--selftest` les éprouve (job
#  `test-scripts`). Le pré-check en emprunte deux (`mode_version_branche`,
#  `verdict_version_du_lot`) pour ses points 0d et 0g : la règle de la version
#  s'écrit une fois.
#
#  Lancer : bash scripts/lib/lib-mep-conduite.sh --selftest
# =============================================================================

#  `rang_attendu` et `verdict_rang_version` (point 0g) : le rang que le TRAIN
#  annonce se lit comme celui d'un lot — une seule lecture des préfixes.
if ! declare -F rang_attendu >/dev/null 2>&1; then
  # shellcheck source=lib-verdicts-mep.sh
  . "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-verdicts-mep.sh"
fi

#: La fenêtre de nuit où l'on ne fusionne pas dans `main` : la bascule de 02:00
#: (`infra/points-entree/cron-root.crontab`), puis le nouveau standby qui pose ses
#: mises à jour et redémarre (`noyau-standby.sh`), et la maintenance du dimanche à
#: 03:00. Un déploiement pendant qu'un nœud change de rôle part sur l'ancien actif.
#: L'autotest vérifie que la bascule de la crontab tombe bien DANS cette fenêtre.
FENETRE_BASCULE_DEBUT="01:30"
FENETRE_BASCULE_FIN="04:30"

# version_suivante X.Y.Z major|minor|patch → la version qui suit, vide si illisible
version_suivante() {
  local v="${1:-}" rang="${2:-}" ma mi pa
  [[ "$v" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || { echo ""; return; }
  ma=${BASH_REMATCH[1]}; mi=${BASH_REMATCH[2]}; pa=${BASH_REMATCH[3]}
  case "$rang" in
    major) echo "$((ma + 1)).0.0" ;;
    minor) echo "$ma.$((mi + 1)).0" ;;
    patch) echo "$ma.$mi.$((pa + 1))" ;;
    *)     echo "" ;;   # `inconnu` n'est pas un patch par défaut (standards/04 §1)
  esac
}

# decision_version v_main v_dev rang → « POSER x » | « DEJA x » | « REPOSER x » | INCONNU
#  La version que le train doit porter se CALCULE de `main` et des préfixes du train,
#  jamais de ce que `dev` porte déjà : deux lots fusionnés pendant qu'une PR
#  `dev → main` est ouverte font un seul train, et le second peut en élever le rang.
#  `REPOSER` : `dev` porte une autre version (un lot d'avant #2631 l'a posée, ou un
#  lot plus riche est arrivé) — on la remplace par la bonne.
decision_version() {
  local v_main="${1:-}" v_dev="${2:-}" rang="${3:-}" cible
  cible=$(version_suivante "$v_main" "$rang")
  [ -n "$cible" ] && [ -n "$v_dev" ] || { echo INCONNU; return; }
  if [ "$v_dev" = "$cible" ]; then echo "DEJA $cible"
  elif [ "$v_dev" = "$v_main" ]; then echo "POSER $cible"
  else echo "REPOSER $cible"; fi
}

# mode_version_branche branche → TRAIN (dev, main : la PR qui part en production) | LOT
mode_version_branche() {
  case "${1:-}" in
    dev|main) echo TRAIN ;;
    "")       echo INCONNU ;;
    *)        echo LOT ;;
  esac
}

# verdict_version_du_lot v_base v_head → OK | FAIL | INCONNU
#  Depuis #2631, un lot ne porte PAS de numéro : le conducteur le pose au moment de
#  la MEP. Un lot qui en porte un recrée la collision du 10/11 (3.79.0, deux fois
#  3.81.0) — chaque fusion du précédent l'obligeait à le reposer.
#  On compare à la BASE COMMUNE du lot et de `main`, jamais à `main` : une branche
#  partie avant la MEP précédente a la version d'avant, et elle n'a rien bumpé —
#  la première écriture le lui reprochait (rejouée sur #2665, 11/11).
verdict_version_du_lot() {
  [ -n "${1:-}" ] && [ -n "${2:-}" ] || { echo INCONNU; return; }
  [ "$1" = "$2" ] && echo OK || echo FAIL
}

# titre_avec_version titre version → le titre, `{version}` remplacé par vX.Y.Z ; vide sans marque
#  Le titre de la PR `dev → main` devient le commit du squash sur `main` : il doit
#  porter la version que le conducteur a calculée, pas celle qu'on a crue.
titre_avec_version() {
  local titre="${1:-}" v="${2:-}"
  [ -n "$v" ] || { echo ""; return; }
  case "$titre" in *"{version}"*) echo "${titre//\{version\}/v$v}" ;; *) echo "" ;; esac
}

# verdict_titre_train rang_du_titre rang_du_train → OK | FAIL | INCONNU
#  Le squash sur `main` ne garde que le titre : un `fix:` sur un train qui apporte
#  un `feat` ferait lire un correctif à 0g et aux notes de version.
verdict_titre_train() {
  case "${1:-}:${2:-}" in
    *inconnu*|:*|*:) echo INCONNU ;;
    *) [ "$1" = "$2" ] && echo OK || echo FAIL ;;
  esac
}

# verdict_fusion nb_checks en_cours rouges etat_github → FUSIONNER | ATTENDRE | STOP
#  🔴 `UNKNOWN` n'est pas un état : c'est GitHub qui calcule encore. Le conducteur du
#  10/11 fusionnait sur la seule fin des checks ; la fusion ne se décide plus que sur
#  `CLEAN`. Une mesure vide fait attendre — le délai de l'appelant tranche.
verdict_fusion() {
  local nb="${1:-}" cours="${2:-}" rouges="${3:-}" etat="${4:-}"
  case "$nb$cours$rouges" in ""|*[!0-9]*) echo ATTENDRE; return ;; esac
  [ "$rouges" -gt 0 ] && { echo STOP; return; }
  { [ "$nb" -eq 0 ] || [ "$cours" -gt 0 ]; } && { echo ATTENDRE; return; }
  case "$etat" in
    CLEAN)                   echo FUSIONNER ;;
    UNKNOWN|"")              echo ATTENDRE ;;
    *)                       echo STOP ;;   # BLOCKED, DIRTY, BEHIND, UNSTABLE, DRAFT…
  esac
}

# minutes_hhmm HH:MM → minutes depuis minuit, vide si illisible
minutes_hhmm() {
  [[ "${1:-}" =~ ^([0-9]{1,2}):([0-9]{2})$ ]] || { echo ""; return; }
  echo $((10#${BASH_REMATCH[1]} * 60 + 10#${BASH_REMATCH[2]}))
}

# dans_fenetre HH:MM [debut fin] → oui | non | inconnu (bornes : début inclus, fin exclue)
dans_fenetre() {
  local m d f
  m=$(minutes_hhmm "${1:-}"); d=$(minutes_hhmm "${2:-$FENETRE_BASCULE_DEBUT}")
  f=$(minutes_hhmm "${3:-$FENETRE_BASCULE_FIN}")
  [ -n "$m" ] && [ -n "$d" ] && [ -n "$f" ] || { echo inconnu; return; }
  if [ "$d" -le "$f" ]; then
    { [ "$m" -ge "$d" ] && [ "$m" -lt "$f" ]; } && echo oui || echo non
  else   # fenêtre qui passe minuit
    { [ "$m" -ge "$d" ] || [ "$m" -lt "$f" ]; } && echo oui || echo non
  fi
}

# heure_cron_bascule fichier_crontab → HH:MM de `bascule.sh`, vide si absente ou non quotidienne
heure_cron_bascule() {
  local ligne mn hr
  ligne=$(grep -E '^[0-9]+ [0-9]+ \* \* \* [^ ]*/bascule\.sh' "${1:-/dev/null}" 2>/dev/null | head -1)
  [ -n "$ligne" ] || { echo ""; return; }
  read -r mn hr _ <<<"$ligne"
  printf '%02d:%02d\n' "$hr" "$mn"
}

# instant_num 2026-11-11T13:19:01Z → 20261111131901, vide si ce n'est pas cette forme
#  Les instants de GitHub (UTC, à la seconde) se comparent en nombres ; une autre forme
#  ne se compare pas — elle rend vide, et l'appelant ne décide rien dessus.
instant_num() {
  [[ "${1:-}" =~ ^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z$ ]] || { echo ""; return; }
  echo "${BASH_REMATCH[1]}${BASH_REMATCH[2]}${BASH_REMATCH[3]}${BASH_REMATCH[4]}${BASH_REMATCH[5]}${BASH_REMATCH[6]}"
}

# fermee_par_suppression derniers → oui | non
#  `derniers` : les deux derniers événements de la PR parmi fermeture, suppression de sa
#  base et réouverture, joints par `+`. GitHub qui ferme une PR dont la base disparaît
#  écrit `BaseRefDeletedEvent` puis `ClosedEvent`, à une seconde d'écart (#2619, relu le
#  11/11) — l'ordre des deux n'est pas exigé. Une fermeture à la main n'a pas le premier ;
#  une PR rouverte puis refermée a `ReopenedEvent` devant sa fermeture.
fermee_par_suppression() {
  case "${1:-}" in
    BaseRefDeletedEvent+ClosedEvent|ClosedEvent+BaseRefDeletedEvent) echo oui ;;
    *) echo non ;;
  esac
}

# geste_pr_suivie etat base [ferme_le fusion_le derniers] → RIEN | RECIBLER | ROUVRIR | LAISSER | INCONNU
#  Les PR qui visaient `dev` AVANT la fusion du train : la suppression de `dev` par
#  GitHub les recible sur `main`, ou FERME celles qui sont en brouillon (#2619).
#  Après la recréation de `dev`, chacune y revient.
#  🔴 Une PR fermée n'est pas toujours fermée par GitHub : le 11/11, la coordination en a
#  fermé deux À LA MAIN pendant que le train attendait ses checks (leur contenu était
#  entré par une autre), et le conducteur les a rouvertes (#2688). `ROUVRIR` exige donc
#  deux faits : la fermeture n'est pas ANTÉRIEURE à la fusion du train (`fusion_le`, le
#  `mergedAt` de la PR `dev → main`), et elle suit la suppression de la base. Une heure
#  ou une chronologie illisible : `LAISSER` — l'appelant nomme la PR et n'y touche pas.
geste_pr_suivie() {
  local ferme fusion
  case "${1:-}:${2:-}" in
    OPEN:dev)      echo RIEN ;;
    OPEN:*)        echo RECIBLER ;;
    MERGED:*)      echo RIEN ;;
    CLOSED:*)      ferme=$(instant_num "${3:-}"); fusion=$(instant_num "${4:-}")
                   if [ -n "$ferme" ] && [ -n "$fusion" ] && [ "$ferme" -ge "$fusion" ] \
                      && [ "$(fermee_par_suppression "${5:-}")" = oui ]; then echo ROUVRIR
                   else echo LAISSER; fi ;;
    *)             echo INCONNU ;;
  esac
}

# verdict_recible etat base → OK | ECHEC
#  Le FAIT après un reciblage : la PR relue est ouverte sur `dev` (ou a été fusionnée
#  entre-temps). Le code de retour de `gh pr edit` ne suffit pas (#2676).
verdict_recible() {
  case "${1:-}:${2:-}" in
    OPEN:dev|MERGED:*) echo OK ;;
    *)                 echo ECHEC ;;
  esac
}

# decision_dev_apres_fusion sha_lu sha_avant sha_main → ATTENDRE | RECREER | PRETE | AUTRE | INCONNU
#  🔴 GitHub supprime la branche source d'une PR fusionnée de façon ASYNCHRONE
#  (`delete_branch_on_merge`) : lue une seconde après la fusion, `dev` est encore là,
#  sur le commit d'avant. Le premier conducteur réel (v3.86.0, 11/11) l'a lue
#  « présente », n'a rien recréé, et ses sept reciblages ont échoué (#2676).
#  `sha_lu` : un sha, `absent` (lecture réussie, aucune branche), ou vide (illisible).
#  `sha_avant` vide (état d'un conducteur d'avant #2676) : on ne sait pas, on attend.
decision_dev_apres_fusion() {
  case "${1:-}" in
    "")     echo INCONNU; return ;;
    absent) echo RECREER; return ;;
  esac
  if [ -n "${3:-}" ] && [ "$1" = "$3" ]; then echo PRETE           # déjà recréée sur main
  elif [ -z "${2:-}" ] || [ "$1" = "$2" ]; then echo ATTENDRE      # pas encore supprimée
  else echo AUTRE; fi                                              # un commit inconnu y est arrivé
}

# attendre_dev_supprimee lecteur essais pause sha_avant sha_main
#   → RECREER | PRETE | AUTRE | NON_SUPPRIMEE | INCONNU
#  Le LECTEUR est injecté (une fonction qui rend ce que `decision_dev_apres_fusion`
#  attend) : le conducteur lit le dépôt distant, l'autotest une suite d'observations.
attendre_dev_supprimee() {
  local lecteur=$1 essais=$2 pause=$3 avant=${4:-} main=${5:-} i d=INCONNU
  for ((i = 1; i <= essais; i++)); do
    d=$(decision_dev_apres_fusion "$("$lecteur")" "$avant" "$main")
    case "$d" in ATTENDRE|INCONNU) ;; *) echo "$d"; return ;; esac
    [ "$i" -lt "$essais" ] && sleep "$pause"
  done
  [ "$d" = ATTENDRE ] && echo NON_SUPPRIMEE || echo INCONNU
}

# verdict_verrou pid_lu vivant(oui|non) → PRENDRE | REPRENDRE | REFUSER
#  Un conducteur à la fois ; celui qu'on a tué (pkill, fermeture de la session) laisse
#  un verrou que le suivant REPREND — la reprise lit l'état, elle ne recommence rien.
verdict_verrou() {
  [ -z "${1:-}" ] && { echo PRENDRE; return; }
  [ "${2:-}" = oui ] && echo REFUSER || echo REPRENDRE
}

# etape_reprise etat_pr_main(''|OPEN|MERGED|CLOSED) → TRAIN | SUITE
#  La PR `dev → main` mémorisée par un conducteur interrompu dit où reprendre : non
#  fusionnée, on reconduit le train (chaque étape vérifie d'abord son fait) ; fusionnée,
#  on reprend APRÈS la fusion — recréer `dev`, ramener les PR, attendre « Déployé ».
etape_reprise() {
  case "${1:-}" in
    MERGED) echo SUITE ;;
    *)      echo TRAIN ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  echecs=0
  t() {
    local libelle="$1" att="$2" obtenu; shift 2
    obtenu=$("$@")
    if [ "$obtenu" = "$att" ]; then echo "PASS  $libelle → $obtenu"
    else echo "FAIL  $libelle — attendu « $att », obtenu « $obtenu »"; echecs=$((echecs + 1)); fi
  }
  t "patch"                                   3.84.2   version_suivante 3.84.1 patch
  t "mineure remet le correctif à zéro"        3.85.0   version_suivante 3.84.1 minor
  t "majeure"                                  4.0.0    version_suivante 3.84.1 major
  t "rang inconnu : pas de patch par défaut"   ""       version_suivante 3.84.1 inconnu
  t "version illisible"                        ""       version_suivante 3.84 patch
  t "dev sans bump : poser"                    "POSER 3.85.0"   decision_version 3.84.1 3.84.1 minor
  t "dev déjà juste : rien"                    "DEJA 3.85.0"    decision_version 3.84.1 3.85.0 minor
  t "lot d'avant #2631 surévalué : reposer"     "REPOSER 3.84.2" decision_version 3.84.1 3.85.0 patch
  t "second lot plus riche : reposer"          "REPOSER 3.85.0" decision_version 3.84.1 3.84.2 minor
  t "version de dev illisible"                 INCONNU          decision_version 3.84.1 "" minor
  t "rang du train inconnu"                    INCONNU          decision_version 3.84.1 3.84.1 inconnu
  t "branche dev : le train"                   TRAIN   mode_version_branche dev
  t "branche main : le train"                  TRAIN   mode_version_branche main
  t "branche d'un lot"                         LOT     mode_version_branche claude/x
  t "branche illisible"                        INCONNU mode_version_branche ""
  t "lot sans bump"                            OK      verdict_version_du_lot 3.84.1 3.84.1
  t "lot qui porte un bump (collision du 10/11)" FAIL  verdict_version_du_lot 3.84.1 3.85.0
  t "version de la base illisible"             INCONNU verdict_version_du_lot "" 3.84.1
  t "titre : marque remplacée"   "feat(mep): v3.85.0 — conducteur" titre_avec_version "feat(mep): {version} — conducteur" 3.85.0
  t "titre sans marque refusé"                 ""      titre_avec_version "feat(mep): v3.85.0" 3.85.0
  t "titre sans version calculée"              ""      titre_avec_version "feat: {version}" ""
  t "titre du rang du train"                   OK      verdict_titre_train minor minor
  t "titre fix sur un train feat"              FAIL    verdict_titre_train patch minor
  t "rang du titre inconnu"                    INCONNU verdict_titre_train inconnu minor
  t "verts et CLEAN : fusionner"               FUSIONNER verdict_fusion 24 0 0 CLEAN
  t "🔴 verts mais UNKNOWN (10/11) : attendre"  ATTENDRE  verdict_fusion 24 0 0 UNKNOWN
  t "un check en cours"                        ATTENDRE  verdict_fusion 24 1 0 CLEAN
  t "aucun check encore"                       ATTENDRE  verdict_fusion 0 0 0 CLEAN
  t "un rouge : stop"                          STOP      verdict_fusion 24 0 1 UNSTABLE
  t "conflit : stop"                           STOP      verdict_fusion 24 0 0 DIRTY
  t "brouillon : stop"                         STOP      verdict_fusion 24 0 0 DRAFT
  t "mesure vide : attendre, jamais fusionner" ATTENDRE  verdict_fusion "" "" "" ""
  t "02:00 dans la fenêtre"                    oui     dans_fenetre 02:00
  t "01:30 inclus"                             oui     dans_fenetre 01:30
  t "04:30 exclu"                              non     dans_fenetre 04:30
  t "21:15 hors fenêtre"                       non     dans_fenetre 21:15
  t "fenêtre qui passe minuit"                 oui     dans_fenetre 00:10 23:00 01:00
  t "heure illisible"                          inconnu dans_fenetre ""
  CRONTAB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/infra/points-entree/cron-root.crontab"
  H_BASCULE=$(heure_cron_bascule "$CRONTAB")
  t "la bascule de la crontab est lue"         02:00   echo "$H_BASCULE"
  t "🔒 la bascule tombe DANS la fenêtre"       oui     dans_fenetre "$H_BASCULE"
  t "crontab absente : rien de lu"             ""      heure_cron_bascule /nonexistent
  t "PR suivie toujours sur dev"               RIEN     geste_pr_suivie OPEN dev
  t "PR reciblée sur main par la suppression"  RECIBLER geste_pr_suivie OPEN main
  t "PR fusionnée entre-temps"                 RIEN     geste_pr_suivie MERGED dev
  t "état illisible"                           INCONNU  geste_pr_suivie "" ""
  #  Une PR FERMÉE ne se rouvre que sur deux faits : fermée APRÈS la fusion du train, ET
  #  par la suppression de sa base. Les heures sont celles des deux incidents, relues.
  SUPPR="BaseRefDeletedEvent+ClosedEvent"
  t "🔴 brouillon fermé par la suppression de dev (#2619)" ROUVRIR \
    geste_pr_suivie CLOSED dev 2026-11-10T00:11:57Z 2026-11-10T00:11:50Z "$SUPPR"
  t "fermée à la seconde de la fusion, par la suppression" ROUVRIR \
    geste_pr_suivie CLOSED dev 2026-11-10T00:11:50Z 2026-11-10T00:11:50Z "$SUPPR"
  t "les deux événements à la même seconde, dans l'autre ordre" ROUVRIR \
    geste_pr_suivie CLOSED dev 2026-11-10T00:11:57Z 2026-11-10T00:11:50Z "ClosedEvent+BaseRefDeletedEvent"
  t "🔴 fermée À LA MAIN avant la fusion du train (#2688)" LAISSER \
    geste_pr_suivie CLOSED dev 2026-11-11T13:05:40Z 2026-11-11T13:19:01Z ClosedEvent
  t "🔒 fermée avant la fusion : jamais rouverte, quoi que dise la chronologie" LAISSER \
    geste_pr_suivie CLOSED dev 2026-11-11T13:05:40Z 2026-11-11T13:19:01Z "$SUPPR"
  t "fermée à la main APRÈS la fusion : aucune base supprimée" LAISSER \
    geste_pr_suivie CLOSED main 2026-11-11T13:20:00Z 2026-11-11T13:19:01Z ClosedEvent
  t "rouverte par le conducteur, refermée à la main" LAISSER \
    geste_pr_suivie CLOSED dev 2026-11-11T13:35:46Z 2026-11-11T13:19:01Z "ReopenedEvent+ClosedEvent"
  t "heure de fermeture illisible : dans le doute, laisser" LAISSER \
    geste_pr_suivie CLOSED dev "" 2026-11-11T13:19:01Z "$SUPPR"
  t "heure de fusion du train illisible : laisser" LAISSER \
    geste_pr_suivie CLOSED dev 2026-11-11T13:20:00Z "" "$SUPPR"
  t "heure dans une autre forme : laisser"     LAISSER \
    geste_pr_suivie CLOSED dev "2026-11-11 14:20:00" 2026-11-11T13:19:01Z "$SUPPR"
  t "chronologie illisible : laisser"          LAISSER \
    geste_pr_suivie CLOSED dev 2026-11-11T13:20:00Z 2026-11-11T13:19:01Z ""
  t "fermée, rien de mesuré : laisser"         LAISSER  geste_pr_suivie CLOSED main
  t "instant ISO lu en nombre"                 20261111131901 instant_num 2026-11-11T13:19:01Z
  t "instant illisible"                        ""       instant_num "hier"
  t "reciblée : ouverte sur dev"               OK       verdict_recible OPEN dev
  t "🔴 restée sur main (#2676)"                 ECHEC    verdict_recible OPEN main
  t "fusionnée entre-temps"                    OK       verdict_recible MERGED main
  t "toujours fermée"                          ECHEC    verdict_recible CLOSED dev
  t "lecture illisible"                        ECHEC    verdict_recible "" ""
  t "dev absente : recréer"                    RECREER  decision_dev_apres_fusion absent aaa bbb
  t "🔴 dev encore là, sur l'avant : attendre"   ATTENDRE decision_dev_apres_fusion aaa aaa bbb
  t "dev déjà recréée sur main"                PRETE    decision_dev_apres_fusion bbb aaa bbb
  t "dev sur un commit inconnu"                AUTRE    decision_dev_apres_fusion ccc aaa bbb
  t "avant inconnu (état ancien) : attendre"   ATTENDRE decision_dev_apres_fusion aaa "" bbb
  t "lecture illisible"                        INCONNU  decision_dev_apres_fusion "" aaa bbb
  #  Le cas du 11/11, rejoué : `dev` lue présente deux fois, puis supprimée.
  OBS=$(mktemp -d); trap 'rm -rf "$OBS"' EXIT
  lecteur_faux() { local k; k=$(cat "$OBS/k" 2>/dev/null || echo 1); echo $((k + 1)) > "$OBS/k"
                   sed -n "${k}p" "$OBS/suite"; }
  observer() { printf '%s\n' "$@" > "$OBS/suite"; rm -f "$OBS/k"; }
  observer aaa aaa absent
  t "🔴 présente, présente, supprimée → recréer" RECREER attendre_dev_supprimee lecteur_faux 5 0 aaa bbb
  observer aaa aaa aaa
  t "jamais supprimée dans le délai"           NON_SUPPRIMEE attendre_dev_supprimee lecteur_faux 3 0 aaa bbb
  observer "" "" ""
  t "dépôt distant muet"                       INCONNU  attendre_dev_supprimee lecteur_faux 3 0 aaa bbb
  observer aaa "" bbb
  t "recréée par un autre entre deux lectures" PRETE    attendre_dev_supprimee lecteur_faux 5 0 aaa bbb
  t "aucun verrou"                             PRENDRE   verdict_verrou "" ""
  t "verrou d'un conducteur vivant"            REFUSER   verdict_verrou 4242 oui
  t "verrou d'un conducteur tué"               REPRENDRE verdict_verrou 4242 non
  t "PR main mémorisée fusionnée : la suite"   SUITE   etape_reprise MERGED
  t "PR main ouverte : le train"               TRAIN   etape_reprise OPEN
  t "rien de mémorisé : le train"              TRAIN   etape_reprise ""
  t "rang du train lu aux préfixes (feat)"     minor   rang_attendu "$(printf 'fix: a\nfeat(mep) : b')"
  if [ "$echecs" -eq 0 ]; then
    echo "✓ conducteur de MEP : fusion sur CLEAN seulement, fenêtre de bascule, version du train, reprise, PR fermée à la main jamais rouverte."
    exit 0
  fi
  echo "✗ $echecs décision(s) du conducteur en défaut."
  exit 1
fi
