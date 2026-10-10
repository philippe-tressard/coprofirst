#!/usr/bin/env bash
# =============================================================================
#  lib-precheck-lot.sh — les points du LOT, avant le push : 0a à 0g, 15 et 16
#
#  Extraits de `precheck-mep.sh` le 25/09/2026 (#1282) : le mode `--post-mep`
#  ne doit PAS les exécuter, et le fichier était à 500 lignes pile — son propre
#  point 0b en refusait la moindre ligne de plus. La coupe suit la nature des
#  contrôles : ceux-ci jugent le LOT qui part (clone, CI, bump, brief, rejeu),
#  les suivants jugent la PRODUCTION. Après la fusion, les premiers échouent par
#  construction — c'était le faux « MEP NON AUTORISÉE » d'une MEP réussie.
#
#  ⚠️ Ce module n'est PAS autonome : il emploie `rapporter`, les `verdict_*`,
#  `GIT_DEPOT` et les bibliothèques sourcées par son appelant. Le corps est
#  déplacé tel quel, sans une ligne changée : c'est ce qui rend la coupe sûre.
# =============================================================================

precheck_points_lot() {
# 0a — clone à jour
git fetch origin --quiet 2>/dev/null
BRANCHE=$(git rev-parse --abbrev-ref HEAD)
RETARD=$(git rev-list --count "HEAD..origin/$BRANCHE" 2>/dev/null)
#  « Identique » = MÊME ARBRE. Un retard sur des commits dont le contenu est déjà
#  chez nous est le réalignement post-squash ; un retard sur du contenu absent est
#  la dérive que ce point existe pour attraper.
#  `origin/dev` n'apporte rien que `origin/main` n'ait déjà, ET nous descendons
#  de `origin/main` : le retard est le réalignement post-squash, pas une dérive.
#  La branche amont peut avoir été SUPPRIMÉE à la fusion de la PR : `origin/dev`
#  disparaît alors, et il n'y a rien à rattraper. On distingue donc les trois
#  états — présente, absente, indéterminable — au lieu de lire une mesure vide
#  comme un INCONNU.
if git rev-parse --verify --quiet "origin/$BRANCHE" >/dev/null 2>&1; then AMONT=present
elif git rev-parse --verify --quiet origin/main >/dev/null 2>&1; then AMONT=absent
else AMONT=inconnu; fi
if [ "$AMONT" = "absent" ]; then
  #  Rien à comparer à l'amont : ce qui compte est de descendre de `origin/main`.
  git merge-base --is-ancestor origin/main HEAD 2>/dev/null && IDENT=oui || IDENT=non
elif git diff --quiet "origin/$BRANCHE" origin/main 2>/dev/null && git merge-base --is-ancestor origin/main HEAD 2>/dev/null; then IDENT=oui; else IDENT=non; fi
if [ "$AMONT" = "absent" ]; then
  DETAIL0A="origin/$BRANCHE supprimée à la fusion — HEAD descend d'origin/main"
  [ "$IDENT" = "oui" ] || DETAIL0A="origin/$BRANCHE absente ET le clone a divergé d'origin/main"
elif [ "${RETARD:-0}" != "0" ] && [ "$IDENT" = "oui" ]; then
  DETAIL0A="retard=$RETARD commit(s) sans apport (réalignement post-squash)"
else
  DETAIL0A="retard=${RETARD:-?} commit(s)"
fi
#  ── Réécriture volontaire de la branche, déclarée (#616) ────────────────────
#  Le point 0d prescrit de RETIRER un bump surnuméraire ; une fois fait,
#  `origin/$BRANCHE` porte un commit que HEAD n'a plus, et 0a le comptait comme
#  un retard. Corriger 0d faisait donc échouer 0a, sans que les deux puissent
#  être verts avant le push — et la seule issue était de désarmer les 24 points.
#
#  Format de `.git/reecriture-dev`, même forme datée que `.git/erreur-corrigee` :
#      commit: 601477b
#      137cab0
#
#  ⚠️ Déclarer ne suffit PAS. On vérifie que les commits déclarés sont exactement
#  ceux qui manquent, et surtout que **chaque fichier qu'ils touchent a été
#  réécrit par HEAD** : c'est ce recouvrement, et lui seul, qui prouve qu'aucun
#  contenu n'est perdu. Sans lui, ce serait une case à cocher pour écraser le
#  travail d'une autre session.
DECL0A=""; DECL0A_SHAS=""; MANQUANTS0A=""; NON_RECOUVERTS=""
if [ -f "$GIT_DEPOT/reecriture-dev" ] && [ "$AMONT" = "present" ]; then
  #  Le parsing vit dans `lib-reecriture.sh`, où il est éprouvé — CRLF, lignes
  #  vides et sha tronqués s'y traitent, et aucun de ces défauts ne lève.
  DECL0A=$(lire_declaration_reecriture "$GIT_DEPOT/reecriture-dev" | sed -n 1p)
  DECL0A_SHAS=$(lire_declaration_reecriture "$GIT_DEPOT/reecriture-dev" | sed -n 2p)
  MANQUANTS0A=$(git rev-list "HEAD..origin/$BRANCHE" 2>/dev/null | cut -c1-7 | tr '
' ' ')
  #  Un fichier touché par un commit retiré et que HEAD n'a pas réécrit depuis
  #  la base commune : son apport serait PERDU. La mesure vit dans
  #  `lib-reecriture.sh`, où elle est éprouvée sur un dépôt jetable.
  if NON_RECOUVERTS=$(fichiers_non_recouverts "origin/$BRANCHE"); then :; else
    #  Mesure impossible (pas de base commune) : on ne conclut pas.
    DECL0A_SHAS=""; MANQUANTS0A=""
  fi
fi
REECR0A=$(verdict_reecriture "${DECL0A:-}" "${HEAD_COURT0A:-$(git rev-parse --short HEAD 2>/dev/null)}"                              "${DECL0A_SHAS:-}" "${MANQUANTS0A:-}" "${NON_RECOUVERTS:-}")
case "$REECR0A" in
  oui) DETAIL0A="retard=$RETARD commit(s) RETIRÉ(S) volontairement et déclaré(s) — rien de perdu (fichiers tous réécrits par HEAD)" ;;
  inconnu) DETAIL0A="$DETAIL0A — déclaration de réécriture incomplète" ;;
  *) [ -n "$DECL0A$DECL0A_SHAS" ] && DETAIL0A="$DETAIL0A — déclaration de réécriture REFUSÉE${NON_RECOUVERTS:+ (perdrait :${NON_RECOUVERTS})}" ;;
esac
rapporter 0a "$(verdict_clone "${RETARD:-}" "$IDENT" "$AMONT" "$REECR0A")" "Clone à jour sur origin/$BRANCHE" "$DETAIL0A"

# 0b — modularité : rejouer ici ce que la CI refusera
#      Ajouté le 08/08/2026 : trois pushes sont partis alors que le job CI
#      `test-scripts` les rejetait (email.py 656 → 663). Le contrôle existait,
#      il n'était simplement pas dans le chemin qui précède le push.
#      Plafond ABSOLU depuis le 02/10/2026 (#779) : plus de base à comparer.
MOD=$(bash scripts/poste/scripts-ci-modularite.sh 2>&1)
case "$?" in
  0) V0B=OK ;;
  1) V0B=FAIL ;;
  *) V0B=INCONNU ;;
esac
D0B=$(echo "$MOD" | grep -oE '[^ ]+ : [0-9]+ lignes \(plafond [0-9]+\)' | head -1)
rapporter 0b "$V0B" "Modularité (ce que la CI vérifiera)" "${D0B:-aucun fichier au-dessus de son plafond}"

# 0c — la CI de la BRANCHE, pas seulement celle de la PR
#      Ajouté le 09/08/2026 : j'ai annoncé « CI verte » en ne consultant que les
#      checks de la pull request, pendant que trois exécutions sur `dev`
#      échouaient. Une PR verte ne dit rien des pushes qui l'ont précédée.
#      ⚠️ Corrigé le 12/08/2026 (#318) : ce point refusait aussi le push qui
#      CORRIGE l'échec qu'il constate — on ne peut pas prouver que la CI repasse
#      sans pousser, et on ne pouvait pas pousser. La seule issue était
#      `SKIP_PRECHECK=1`, donc désarmer les vingt points pour contourner celui-ci.
#      Un échec porté par un commit dont HEAD DESCEND est dépassé par définition ;
#      les autres bloquent toujours. `echecs_bloquants` tranche, et est testée.
if command -v gh >/dev/null 2>&1; then
  #  Les runs sont rendus du PLUS RÉCENT au plus ancien — cet ordre porte la
  #  moitié de la décision, ne pas le trier.
  RUNS=$(gh run list --branch "$BRANCHE" --limit 5 --json conclusion,headSha \
           --jq '.[] | "\(.conclusion):\(.headSha)"' 2>/dev/null)
  if [ -z "${RUNS:-}" ]; then
    #  `gh` présent mais muet (hors ligne, jeton expiré), ou branche sans
    #  historique : une liste vide se lit comme « aucun échec ». On ne déduit
    #  pas un vert d'une sortie vide (socle 04 §1).
    V0C=INCONNU; DETAIL0C="aucune exécution lisible — état de la CI non mesurable"
  else
    TRIPLETS=""; NB_ECHECS=0
    for run in $RUNS; do
      concl=${run%%:*}; sha=${run#*:}
      [ "$concl" = "failure" ] && NB_ECHECS=$((NB_ECHECS + 1))
      if ! git cat-file -e "${sha}^{commit}" 2>/dev/null; then anc="?"     # absent du clone
      elif [ "$sha" = "$(git rev-parse HEAD)" ]; then anc="non"            # c est HEAD lui-même
      elif git merge-base --is-ancestor "$sha" HEAD 2>/dev/null; then anc="oui"
      else anc="non"
      fi
      TRIPLETS="$TRIPLETS ${concl}:${sha:0:7}:$anc"
    done
    RESTE=$(echecs_bloquants "$TRIPLETS")
    NB0C=${RESTE%% *}; SHAS0C=${RESTE#"$NB0C"}
    V0C=$(verdict_compte "$NB0C" 0)
    if [ "$NB0C" -gt 0 ]; then
      DETAIL0C="$NB0C échec(s) que ce lot ne corrige pas :$SHAS0C"
    elif [ "$NB_ECHECS" -gt 0 ]; then
      DETAIL0C="$NB_ECHECS échec(s), tous dépassés (succès postérieur ou corrigé ici)"
    else
      DETAIL0C="0 échec sur les 5 dernières exécutions"
    fi
  fi
else
  V0C=INCONNU; DETAIL0C="gh absent — état de la CI non mesurable"
fi
rapporter 0c "$V0C" "CI de la branche $BRANCHE" "$DETAIL0C"

# 0d — un seul bump de version par lot, et posé en dernier
#      Ajouté le 11/08/2026 sur remarque de l'utilisateur : la PR #297 portait
#      DEUX `chore(version)` — v2.49.1 puis v2.50.0 — et la v2.49.1 n'a jamais
#      été servie. J'avais bumpé en croyant le lot fini, les retours ont
#      continué, j'ai rebumpé. L'historique annonçait donc une version qui
#      n'a jamais existé en production.
#
#      Le lot = ce que la PR déposera sur `main`, donc `origin/main..HEAD`.
#      `--grep` sur le préfixe conventionnel, ancré : un commit qui MENTIONNE un
#      bump dans son corps ne doit pas être compté.
NB_BUMPS=$(git log origin/main..HEAD --grep='^chore(version)' --oneline 2>/dev/null | wc -l | tr -d ' ')
#  Le FAIT, en plus de la forme : la version qui sera SERVIE change-t-elle ?
#  Compter les commits ne le dit pas — un bump replié dans un commit fonctionnel
#  change bien la version et faisait pourtant conclure « identique » (#308).
lire_version() {  # $1 = révision git
  git show "$1:front/package.json" 2>/dev/null | grep -m1 '"version"' | cut -d'"' -f4
}
V_MAIN=$(lire_version origin/main); V_HEAD=$(lire_version HEAD)
V0D=$(verdict_bumps "${NB_BUMPS:-}" "${V_MAIN:-}" "${V_HEAD:-}")
case "$V0D" in
  OK)    D0D="${V_MAIN:-?} → ${V_HEAD:-?}$(
           [ "$NB_BUMPS" = "1" ] && echo " — $(git log origin/main..HEAD --grep='^chore(version)' --format='%s' 2>/dev/null | head -1)" \
                                 || echo " (bump replié dans un commit fonctionnel, pas de commit dédié)")" ;;
  ECART) D0D="version inchangée (${V_MAIN:-?}) : P3 ne prouvera rien" ;;
  FAIL)  D0D="$NB_BUMPS bumps — n'en garder qu'un : reset --soft puis push --force-with-lease" ;;
  *)     D0D="comptage impossible" ;;
esac
rapporter 0d "$V0D" "Un seul bump de version dans le lot" "$D0D"

# 0g — le RANG du bump correspond à ce que le lot apporte (07/09/2026)
#      Le point 0d compte les bumps ; il ne regardait pas leur RANG, et six des
#      dix-huit derniers lots en portaient un faux, tous surévalués. Le « pourquoi »
#      complet vit avec les deux fonctions, dans `lib-verdicts-mep.sh`.
SUJETS=$(git log origin/main..HEAD --format='%s%n%b' 2>/dev/null | grep -v '^chore(version)')
V0G=$(verdict_rang_version "$(rang_attendu "$SUJETS")" "${V_MAIN:-}" "${V_HEAD:-}")
case "$V0G" in
  OK)    D0G="${V_MAIN:-?} → ${V_HEAD:-?} — $(rang_attendu "$SUJETS"), conforme aux préfixes du lot" ;;
  ECART) D0G="version inchangée : rien à juger (0d le dit déjà)" ;;
  FAIL)  D0G="le lot annonce un $(rang_attendu "$SUJETS"), or ${V_MAIN:-?} → ${V_HEAD:-?} — corriger le bump, ou le préfixe s'il ment" ;;
  *)     D0G="rang non calculable" ;;
esac
rapporter 0g "$V0G" "Rang du bump conforme à ce que le lot apporte" "$D0G"

# 0f — titre et descriptif de PR préparés AVANT le push
#      Ajouté le 11/08/2026, sur demande de l'utilisateur, après deux oublis dans
#      la même journée — dont le second APRÈS s'être fait reprendre sur le
#      premier. La consigne existe dans la skill `avant-commit` ; elle n'a pas
#      tenu. Même remède que 0d : un contrôle, pas un rappel.
#
#      Format attendu de `.git/pr-brief.md` — première ligne `commit: <sha>`,
#      puis le titre en `# …`, puis le corps :
#          commit: 6055161
#          # feat(admin): …
#          ### Ce qui change
#          …
BRIEF="$GIT_DEPOT/pr-brief.md"
if [ -f "$BRIEF" ]; then
  BRIEF_SHA=$(head -1 "$BRIEF" | grep -oE '[0-9a-f]{7,40}')
  BRIEF_CORPS=$(tail -n +3 "$BRIEF" | grep -cvE '^\s*$')
else
  BRIEF_SHA=""; BRIEF_CORPS=""
fi
HEAD_COURT=$(git rev-parse --short HEAD 2>/dev/null)
V0F=$(verdict_brief "${BRIEF_SHA:-}" "${HEAD_COURT:-?}" "${BRIEF_CORPS:-}")
case "$V0F" in
  OK)      D0F="$(sed -n 2p "$BRIEF" | cut -c1-60)…" ;;
  FAIL)    if [ -n "$BRIEF_SHA" ] && [ "$BRIEF_SHA" != "$HEAD_COURT" ]; then
             D0F="brief écrit pour $BRIEF_SHA, or c'est $HEAD_COURT qui part"
           else D0F="descriptif trop court ($BRIEF_CORPS ligne(s)) — un titre n'est pas un descriptif"; fi ;;
  *)       D0F="aucun $BRIEF — rédiger titre et descriptif AVANT de pousser" ;;
esac
rapporter 0f "$V0F" "Titre et descriptif de PR préparés" "$D0F"

# 15 — endpoints orphelins (poste de dev, avant le push)
if [ -d api/tests ]; then
  ORPH=$( (cd api && python -m pytest tests/test_endpoints_orphelins.py -q 2>&1 | tail -1) )
  case "$ORPH" in
    *"passed"*) V15=OK ;;
    *) V15=FAIL ;;
  esac
else
  V15=INCONNU; ORPH="répertoire api/tests introuvable"
fi
rapporter 15 "$V15" "Aucun endpoint orphelin" "$ORPH"

# 16 — la CI rejouée EN LOCAL sur ce commit (#319)
#      Le 12/08/2026, pytest, svelte-check, le build, les six lints du front et
#      les self-tests avaient été rejoués à la main : le seul job non lancé —
#      Ruff — est le seul qui a échoué. La consigne de tout rejouer existe
#      (skill `avant-commit` §7) et n'a pas tenu. `rejouer-ci.sh` EXTRAIT les
#      commandes de ci.yml et écrit sa trace ; ce point la lit.
if [ -f "$GIT_DEPOT/rejeu-ci.ok" ]; then
  #  `SAUTS=` en sixième champ depuis #1734 ; une trace plus ancienne n'en a pas.
  #  Sans ce sixième nom, `R_INC` avalerait le reste de la ligne.
  #  `RELANCES=` en septième depuis #1809 : des e2e relancés sur l'import de Vite.
  read -r R_SHA _ R_OK R_FAIL R_INC R_SAUTS R_REL _ < "$GIT_DEPOT/rejeu-ci.ok"
  R_FAIL=${R_FAIL#FAIL=}; R_INC=${R_INC#INCONNU=}; R_OK=${R_OK#OK=}; R_SAUTS=${R_SAUTS#SAUTS=}
  R_REL=${R_REL#RELANCES=}
else
  R_SHA=""; R_OK="?"; R_FAIL=""; R_INC=""; R_SAUTS=""; R_REL=""
fi
V16=$(verdict_rejeu_ci "${R_SHA:-}" "$(git rev-parse HEAD 2>/dev/null)" "${R_FAIL:-}" "${R_INC:-}")
case "$V16" in
  #  Un saut n'est pas une faute, mais il se DIT (#1734) : ces tests-là, seule la
  #  CI de la PR les joue — et c'est elle qui a vu ce que le rejeu taisait.
  OK)   D16="$R_OK étape(s) rejouée(s) sur ce commit"
        case "${R_SAUTS:-0}" in 0|*[!0-9]*) ;; *) D16="$D16, dont $R_SAUTS test(s) sauté(s) ici — joué(s) par la CI de la PR" ;; esac
        case "${R_REL:-0}" in 0|*[!0-9]*) ;; *) D16="$D16, $R_REL e2e vert(s) à la relance (#1809)" ;; esac ;;
  FAIL) D16="$R_FAIL étape(s) en échec — la CI échouerait" ;;
  *)    D16="lancer \`bash scripts/poste/rejouer-ci.sh\` (trace absente ou d'un autre commit)" ;;
esac
rapporter 16 "$V16" "CI rejouée en local sur ce commit" "$D16"
}
