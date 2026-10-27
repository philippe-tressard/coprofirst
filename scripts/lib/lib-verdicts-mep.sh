#!/bin/bash
# =============================================================================
#  lib-verdicts-mep.sh — Fonctions de DÉCISION pures de precheck-mep.sh
#
#  Module SOURCÉ, jamais exécuté : pas de bit x (le job CI « Bits d'exécution
#  versionnés » attend 100644 sur les `lib-*.sh`).
#
#  POURQUOI. `precheck-mep.sh` a dépassé 500 lignes en recevant le point 0f
#  (11/08/2026) et son propre contrôle 0b a refusé le push — le troisième
#  découpage imposé par ce garde-fou dans la même journée, et le plus mérité :
#  c'est le fichier du pré-check qui s'est fait arrêter par le pré-check.
#
#  Même frontière que `lib-verdicts.sh` (côté check-reliability.sh) : les
#  fonctions PURES — aucun SSH, docker, écriture ni sudo — et le self-test qui
#  les éprouve, seul moyen de tester une décision de MEP sans les deux RPi.
#
#  DEUX MODULES ET NON UN SEUL, délibérément : ces deux jeux de décisions n'ont
#  aucune fonction commune et changent pour des raisons différentes (les
#  invariants d'une MEP d'un côté, ceux de la surveillance continue de l'autre).
#  Les fusionner créerait un module que deux scripts modifieraient sans se voir.
#
#  Règle pour toute fonction ajoutée ici : rendre INCONNU sur une mesure
#  manquante ou aberrante, jamais un vert (`standards/04-fiabilite-des-controles.md`).
# =============================================================================

# ── Fonctions de décision, PURES et sous self-test ───────────────────────────

#  La parité d'IMAGES (#511) vit dans son propre module : elle sert aussi à
#  health-watch et à auto-deploy, qui ne chargent pas les verdicts du pré-check.
# shellcheck source=./lib-parite.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-parite.sh"
#  Les images servies (points 12 et 18) — extraites le 04/10/2026, ce fichier
#  étant à son plafond de 500 lignes.
# shellcheck source=./lib-images-servies.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-images-servies.sh"

verdict_http() {           # $1 = code HTTP observé
  case "$1" in
    200) echo OK ;;
    000|"") echo INCONNU ;;
    *) echo FAIL ;;
  esac
}

verdict_role() {           # $1/$2 = .active des 2 nœuds, $3/$4 = nb conteneurs
  local a1=$1 a2=$2 c1=$3 c2=$4
  [ -z "$a1" ] || [ -z "$a2" ] || [ -z "$c1" ] || [ -z "$c2" ] && { echo INCONNU; return; }
  [ "$a1" != "$a2" ] && { echo FAIL; return; }          # flags divergents
  [ "$c1" -gt 0 ] && [ "$c2" -gt 0 ] && { echo FAIL; return; }   # split-brain
  [ "$c1" -eq 0 ] && [ "$c2" -eq 0 ] && { echo FAIL; return; }   # personne ne sert
  #  Le flag doit désigner le nœud qui porte réellement les conteneurs.
  if [ "$c1" -gt 0 ]; then [ "$a1" = "rpi1" ] && echo OK || echo FAIL
  else [ "$a1" = "rpi2" ] && echo OK || echo FAIL
  fi
}

verdict_standby() {       # $1 = .active (qui DIT être l'actif), $2/$3 = conteneurs rpi1/rpi2
  #  Le standby est désigné par le DRAPEAU, pas supposé. Première version : elle
  #  vérifiait « rpi2 porte 0 conteneur », en dur — donc elle criait au split-brain
  #  le lendemain matin, la bascule de 02:00 ayant fait de rpi2 l'actif (09/08/2026).
  #  Un contrôle qui suppose lequel des deux nœuds est actif ne survit pas à la
  #  première bascule, c'est-à-dire à une nuit.
  [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ] && { echo INCONNU; return; }
  case "$2$3" in (*[!0-9]*) echo INCONNU; return ;; esac
  if [ "$1" = "rpi1" ]; then [ "$3" -eq 0 ] && echo OK || echo FAIL
  elif [ "$1" = "rpi2" ]; then [ "$2" -eq 0 ] && echo OK || echo FAIL
  else echo INCONNU; fi
}

#  Retard sur l'upstream : compter les commits ne suffit PAS à décider.
#  Les PR sont fusionnées en SQUASH : `main` ne partage aucun commit avec `dev`,
#  si bien que rapatrier `main` par un merge empilait tout l'historique à chaque
#  tour (30 commits affichés dans la PR du 09/08/2026). La routine est désormais
#  de RÉALIGNER `dev` sur `main` après chaque fusion — le clone est alors « en
#  retard » sur `origin/dev` sans qu'aucun contenu ne lui manque.
#
#  ⚠️ Ne PAS comparer son propre arbre à `origin/dev` : dès le premier commit
#  suivant, les arbres diffèrent légitimement et le contrôle refuse tout. Vécu
#  immédiatement après avoir écrit cette correction-là. Ce qu'il faut établir est
#  asymétrique : `origin/dev` n'apporte-t-il RIEN que nous n'ayons déjà ?
#  Deux conditions, toutes deux nécessaires :
#    • `origin/dev` et `origin/main` ont le même contenu (le retard n'est que
#      l'historique pré-squash) ;
#    • notre HEAD descend de `origin/main` (donc nous avons bien ce contenu).
#  Un contrôle qui crie au loup à chaque livraison finit contourné, et c'est le
#  contournement qui devient l'habitude (socle 04 §18).
# $3 = état de la branche AMONT : present | absent | inconnu (défaut : present)
#
# 🔴 CE POINT NE POUVAIT PLUS ÊTRE VERT APRÈS UNE FUSION (27/08/2026).
# Le dépôt supprime la branche à la fusion de la PR. `origin/dev` disparaît donc,
# `git rev-list HEAD..origin/dev` rend une chaîne vide, et le point concluait
# INCONNU — ce qui est honnête sur la MESURE (« je n ai pas pu compter ») mais
# faux sur le FAIT : il n y a rien à rattraper, la branche n existe plus.
#
# Conséquence pratique : le pré-check ne pouvait plus passer, donc le hook
# `pre-push` refusait le premier push suivant chaque fusion — l état le plus
# courant du dépôt. Un contrôle dont le vert est inatteignable finit par se
# contourner, et c est le troisième de la journée (C21, `visudo -c`, celui-ci).
#
# ⚠️ « Absente » n est OK QUE si l on descend de `origin/main`. Une branche
# amont absente sur un clone qui a divergé reste un FAIL : c est alors une
# dérive, pas un post-fusion.
#  $4 — RÉÉCRITURE DÉCLARÉE (#616, 29/08/2026). Voir `verdict_reecriture` pour ce
#  que cette valeur vaut et ce qui l'établit ; ici on ne fait que la consommer.
#
#  🔴 Pourquoi ce quatrième cas existe. Le point 0d prescrit textuellement de
#  RETIRER un bump surnuméraire (« reset --soft puis push --force-with-lease »).
#  Une fois le remède appliqué, `origin/dev` porte un commit que HEAD n'a plus, et
#  0a le comptait comme un retard : corriger 0d faisait échouer 0a, et les deux ne
#  pouvaient pas être verts en même temps avant le push. Or `.githooks/pre-push`
#  exige une trace de pré-check vert. La seule issue était `SKIP_PRECHECK=1` —
#  désarmer VINGT-QUATRE contrôles pour en contourner un qui a tort.
#
#  C'est le §25 du socle : « un contrôle dont le vert est INATTEIGNABLE finit par
#  se contourner ». Et c'est la deuxième fois sur ce fichier — #318 l'avait déjà
#  corrigé sur le point 0c.
verdict_clone() {          # $1 = commits de retard, $2 = upstream sans apport (oui/non)
                           # $3 = état de l'amont (present/absent/inconnu)
                           # $4 = réécriture déclarée ET recouverte (oui/non/inconnu/'')
  case "${3:-present}" in
    inconnu) echo INCONNU; return ;;
    absent)  [ "${2:-non}" = "oui" ] && echo OK || echo FAIL; return ;;
  esac
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ "$1" -eq 0 ] && { echo OK; return; }
  [ "${2:-non}" = "oui" ] && { echo OK; return; }
  #  Le retard n'est PAS un réalignement post-squash. Reste la réécriture
  #  volontaire — mais seulement si elle est déclarée et prouvée sans perte.
  case "${4:-}" in
    oui)     echo OK ;;
    inconnu) echo INCONNU ;;
    *)       echo FAIL ;;
  esac
}


verdict_bumps() {          # $1 = nombre de commits `chore(version)` du lot
                           # $2 = version dans origin/main · $3 = version dans HEAD
  #  Un lot porte UN bump, et un seul, posé en DERNIER.
  #
  #  Le 11/08/2026, la PR #297 en portait deux : `bump v2.49.1` puis
  #  `bump v2.50.0`. La v2.49.1 n'a JAMAIS été servie — j'avais bumpé en croyant
  #  le lot fini, les retours ont continué, j'ai rebumpé par-dessus. L'historique
  #  annonce donc une version qui n'a jamais existé en production : un commit qui
  #  décrit un fait faux, comme la PR vide de la #294.
  #
  #  La consigne « commit dédié » existait déjà et n'a pas suffi : elle ne disait
  #  pas « un seul, et en dernier ». Quand le lot repart, la conduite est de
  #  RÉÉCRIRE le bump (reset --soft puis push --force-with-lease), pas d'en
  #  empiler un second — `dev` n'est pas protégée et le force-push y est déjà le
  #  geste normal après chaque squash.
  #
  #  ZÉRO n'est pas un échec mais un ÉCART : un lot sans bump se déploie quand
  #  même, et c'est P3 qui devient incapable de prouver que le déploiement a eu
  #  lieu — la version servie serait identique avant et après. Visible, toléré.
  #
  #  ⚠️ $2 et $3 ajoutés le 11/08/2026 (#308). Compter les commits `chore(version)`
  #  mesure le SYMPTÔME attendu — la forme du message — et non le FAIT : la
  #  version qui sera servie. Un bump replié dans un commit fonctionnel faisait
  #  donc répondre « aucun bump : la version servie sera identique », phrase
  #  fausse alors que `front/package.json` passait bien de 2.52.1 à 2.52.2.
  #  C'est la règle 3 de la skill `mep-precheck`, enfreinte par un point du
  #  pré-check. La forme reste contrôlée — DEUX bumps restent un échec, c'est le
  #  défaut d'origine — mais le zéro se juge désormais sur les versions elles-mêmes.
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  #  Deux bumps ou plus : défaut de forme, tranché avant tout le reste.
  [ "$1" -ge 2 ] && { echo FAIL; return; }
  #  Versions non mesurables → INCONNU, jamais un vert par défaut.
  { [ -z "$2" ] || [ -z "$3" ]; } && { echo INCONNU; return; }
  #  Le FAIT : la version servie change-t-elle ? Si oui, P3 pourra le prouver,
  #  que le bump ait eu son commit dédié ou non.
  [ "$2" != "$3" ] && { echo OK; return; }
  #  Versions identiques : P3 ne pourra rien prouver. Y compris avec UN commit
  #  `chore(version)` — un bump annoncé qui ne change pas la version est le même
  #  mensonge que la PR vide de la #294, pas un vert.
  echo ECART
}

verdict_brief() {          # $1 = commit du brief, $2 = HEAD, $3 = lignes de corps
  #  Le titre et le descriptif de PR doivent être PRÉPARÉS avant le push, pas
  #  fournis quand on les réclame.
  #
  #  La skill `avant-commit` le prescrit noir sur blanc — « ne pas s'arrêter au
  #  push : enchaîner le titre et le corps de PR sans attendre qu'on les
  #  demande » — et je l'ai oublié DEUX fois le 11/08/2026, la seconde après
  #  m'être fait reprendre sur la première. C'est la démonstration, à trois jours
  #  d'intervalle du même constat sur le bump de version, qu'une consigne écrite
  #  ne se maintient pas seule : seul un contrôle qui échoue le fait.
  #
  #  Le brief est daté par le COMMIT auquel il se rapporte, comme la trace du
  #  pré-check elle-même. Sans cela, un brief rédigé pour le lot précédent
  #  passerait le contrôle en décrivant autre chose — le faux vert par fichier
  #  périmé, cousin de la liste d'exceptions qui ne pourrit pas.
  [ -z "$1" ] && { echo INCONNU; return; }        # brief absent ou illisible
  [ "$1" != "$2" ] && { echo FAIL; return; }      # brief d'un autre lot
  case "$3" in ''|*[!0-9]*) echo INCONNU; return ;; esac
  #  Cinq lignes : de quoi porter un « ce qui change » et un « pourquoi ». En
  #  dessous, ce n'est pas un descriptif, c'est un titre répété.
  [ "$3" -ge 5 ] && echo OK || echo FAIL
}

# ── 0c : un échec de CI que le lot CORRIGE ne doit pas bloquer son push ───────
# Le 12/08/2026, la CI est passée rouge sur un import devenu orphelin. Le commit
# suivant le corrigeait — et 0c a refusé de le pousser, parce qu'il voyait
# l'échec dans les 5 dernières exécutions. Circulaire : on ne peut pas prouver
# que la CI repasse sans pousser, et on ne peut pas pousser tant qu'elle a
# échoué. La seule issue était `SKIP_PRECHECK=1`, c'est-à-dire désarmer les
# vingt points pour contourner celui-ci (#318).
#
# Le contrôle ne distinguait pas deux situations opposées :
#   - l'échec porte sur un commit dont HEAD DESCEND → ce push est le correctif,
#     et le bloquer n'a aucun sens ;
#   - l'échec porte sur autre chose (branche divergente, commit inconnu du clone,
#     ou HEAD lui-même) → là, il doit bloquer.
#
# DEUX façons pour un échec d'être dépassé, et il faut les deux :
#
#   1. un run PLUS RÉCENT a réussi — l'échec appartient au passé, quoi qu'ait
#      fait le lot courant ;
#   2. HEAD descend du commit en échec — le correctif n'est pas encore poussé,
#      donc aucun run plus récent n'existe, mais ce push EST la correction.
#
# La première seule ne suffit pas : c'est précisément la situation du 12/08 au
# matin, où le correctif était commité et rien n'avait encore tourné après
# l'échec. La seconde seule ne suffit pas non plus : les PR sont fusionnées en
# SQUASH puis `dev` est réaligné sur `main`, ce qui DÉTRUIT le lien d'ascendance
# — le contenu est intégré, le commit en échec n'est plus un ancêtre de personne.
# Vécu deux heures après avoir écrit la première version de ce contrôle.
#
# L'appelant fournit les deux mesures (`gh run list` ordonné, et
# `git merge-base --is-ancestor`) : cette fonction reste PURE, donc testable sans
# dépôt ni CI. Une ascendance inconnue compte comme NON dépassée — on ne déduit
# pas un vert d'une mesure qu'on n'a pas pu faire.
echecs_bloquants() {       # $1 = runs « conclusion:sha:oui|non|? », du PLUS RÉCENT
                           #      au plus ancien ; anc = ancêtre strict de HEAD
                           # → « <nombre> <sha bloquants…> »
  local n=0 restants="" e concl sha anc reste vu_succes=0
  for e in $1; do
    [ -n "$e" ] || continue
    concl=${e%%:*}; reste=${e#*:}; sha=${reste%%:*}; anc=${reste#*:}
    if [ "$concl" = "success" ]; then vu_succes=1; continue; fi
    [ "$concl" = "failure" ] || continue          # annulé, en cours… : ni l un ni l autre
    [ "$vu_succes" -eq 1 ] && continue            # (1) un run plus récent a réussi
    [ "$anc" = "oui" ] && continue                # (2) ce push descend de l échec
    n=$((n + 1)); restants="$restants ${sha}"
  done
  echo "$n$restants"
}

verdict_compte() {         # $1 = nombre observé, $2 = maximum toléré
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ "$1" -le "$2" ] && echo OK || echo FAIL
}

verdict_parite() {         # $1/$2 = HEAD des 2 nœuds
  #  🔴 `=` jusqu'au 09/09/2026, donc ÉCART PERMANENT (#854) : deux abréviations
  #  du même commit ne sont pas égales. `memes_hachages` portait déjà la règle.
  case "$(memes_hachages "$1" "$2")" in
    oui) echo OK ;;
    non) echo ECART ;;   # écart = toléré, resync à la bascule
    *)   echo INCONNU ;;
  esac
}

verdict_age_min() {        # $1 = âge en minutes, $2 = âge maximum
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ "$1" -le "$2" ] && echo OK || echo FAIL
}

verdict_cache() {          # $1 = taille brute rendue par docker system df (ex. « 25.26GB »)
  #  ⚠️ Ne JAMAIS lire la 3ᵉ colonne de `docker system df` : pour « Build Cache »,
  #  le type tient en deux mots, donc $3 est le NOMBRE D'ENTRÉES (589 le 08/08) et
  #  non la taille. Mesuré ainsi, le contrôle annonçait « 589 Go » sur un disque qui
  #  n'en fait pas tant — un faux échec produit par le contrôle lui-même.
  [ -z "$1" ] && { echo INCONNU; return; }
  #  ⚠️ L'ordre compte : `*B` capture aussi « 64.1GB ». Le gigaoctet se teste
  #  D'ABORD, sinon tout cache passe pour un cache minuscule — le self-test a
  #  attrapé cette inversion avant la première exécution réelle.
  case "$1" in
    *GB) : ;;
    *MB|*kB|*B) echo OK; return ;;                       # sous le gigaoctet
    *) echo INCONNU; return ;;
  esac
  local go=${1%GB}; go=${go%%.*}
  case "$go" in (*[!0-9]*|"") echo INCONNU; return ;; esac
  [ "$go" -lt "$CACHE_BUILD_MAX_GB" ] && echo OK || echo FAIL
}

verdict_alerte() {         # $1 = âge de la dernière « Alerte envoyée », $2 = âge du dernier [FAIL]
                           # $3 = âge de la dernière EXÉCUTION de check-reliability
                           # $4 = âge maximal toléré pour $3
  #  Le canal n'écrit QUE lorsqu'il a quelque chose à dire : son silence est normal
  #  s'il n'y a rien à signaler. On ne peut donc conclure qu'en croisant les deux.
  #  Les lignes « Email KO » ne servent pas : elles ne sont pas horodatées — constat
  #  du 02/08/2026, où le point a été classé INCONNU alors que l'utilisateur venait
  #  de recevoir deux alertes.
  #
  #  ⚠️ $3 et $4 ajoutés le 11/08/2026 (#306). Le silence a DEUX causes : « rien à
  #  signaler » et « le producteur de FAIL ne tourne plus ». Pendant les 2 h 15 où
  #  check-reliability était mort sur l'actif, ce point a répondu OK deux fois de
  #  suite — zéro FAIL au journal, donc rien à envoyer, donc tout va bien. Il a
  #  autorisé deux MEP en affirmant que le canal d'alerte allait bien, alors que
  #  ce qui l'alimente n'existait plus. Un contrôle qui ne peut pas s'exécuter
  #  rend INCONNU, jamais OK — c'est la première règle de la skill `mep-precheck`,
  #  et c'est un point du pré-check qui l'enfreignait.
  #
  #  La vivacité ne conditionne QUE la conclusion tirée du silence : un échec déjà
  #  écrit prouve que le producteur a tourné, et la suite garde sa logique.
  if [ -z "$2" ]; then
    [ -z "$3" ] && { echo INCONNU; return; }
    case "$3" in (*[!0-9]*) echo INCONNU; return ;; esac
    { [ -z "$4" ] || case "$4" in (*[!0-9]*) true ;; (*) false ;; esac; } && { echo INCONNU; return; }
    [ "$3" -gt "$4" ] && { echo INCONNU; return; }        # producteur muet : on ne sait pas
    echo OK; return                                       # producteur vivant, rien à signaler
  fi
  case "$2" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ -z "$1" ] && { echo FAIL; return; }                  # un échec, aucune alerte : muet
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  #  Cooldown d'une heure : une alerte peut légitimement suivre son échec de 60 min.
  [ "$1" -le $(( $2 + 60 )) ] && echo OK || echo FAIL
}

# ── Contrat du module ────────────────────────────────────────────────────────
#  Rejeu local de la CI (#319). Le point 0c regarde la CI DISTANTE et PASSÉE ;
#  celui-ci regarde ce qu'on s'apprête à pousser. La trace est écrite par
#  `rejouer-ci.sh` et porte le commit couvert : une trace d'un autre commit ne
#  dit rien de celui-ci, donc INCONNU — jamais OK par ancienneté.
#  La dernière ligne de pytest (#2191) : « 3 passed, 3 errors » contient « passed »,
#  et le point 15 rendait OK sur des tests qui n'avaient pas tourné (un import
#  manquant dans le Python du poste). Une erreur n'est pas un échec du code : la
#  mesure n'a pas eu lieu — INCONNU. Rien de reconnu : INCONNU aussi.
verdict_pytest_resume() {  # $1 = dernière ligne de `pytest -q`
  case "$1" in
    *" failed"*) echo FAIL ;;
    *" error"*|*"no tests ran"*) echo INCONNU ;;
    *" passed"*) echo OK ;;
    *) echo INCONNU ;;
  esac
}

#  Le rejeu mesure le CODE, pas l'historique (#2245) : un reword, un squash ou un
#  réordonnancement de messages change le sha et laisse l'arbre — ce qui a été testé —
#  identique. La trace vaut donc si le sha est le même, OU si l'arbre l'est (`$5` = arbre
#  de la trace, `$6` = arbre de HEAD). Un arbre absent d'un côté (trace d'avant #2245,
#  git muet) ne prouve rien : INCONNU, comme un autre commit.
verdict_rejeu_ci() {       # $1 = sha de la trace, $2 = HEAD, $3 = nb FAIL, $4 = nb INCONNU, $5 = arbre de la trace, $6 = arbre de HEAD
  [ -z "$1" ] || [ -z "$2" ] && { echo INCONNU; return; }
  if [ "$1" != "$2" ]; then
    { [ -n "${5:-}" ] && [ "${5:-}" = "${6:-}" ]; } || { echo INCONNU; return; }
  fi
  case "$3$4" in (*[!0-9]*|"") echo INCONNU; return ;; esac
  [ "$3" -gt 0 ] && { echo FAIL; return; }
  [ "$4" -gt 0 ] && { echo INCONNU; return; }
  echo OK
}

# ── 6 : l'erreur que CE lot corrige ne doit pas bloquer son propre push ───────
# Le 19/08/2026, le point 6 a trouvé un vrai 500 sur `/auth/refresh` — puis a
# refusé le push du correctif pendant une heure, le temps que sa fenêtre se vide.
# Même circularité que 0c avant #318, sur une autre mesure : le contrôle bloquait
# la réparation de ce qu'il constatait, et la seule issue était `SKIP_PRECHECK=1`.
# La leçon de #318 avait été tirée sur UN contrôle, pas sur la CLASSE (#502).
#
# ⚠️ La piste écartée mérite d'être écrite, parce qu'elle paraissait évidente :
# compter depuis le DERNIER DÉPLOIEMENT plutôt que sur une heure fixe. Or
# `auto-deploy.sh` fait `docker compose up -d`, qui ne recrée un conteneur que si
# son image a changé. Un lot qui touche `api/` recrée donc l'API et purge ses
# logs — la fenêtre glissante y est déjà le comportement effectif, elle n'aurait
# rien apporté. Un lot qui ne touche que `front/` laisse le conteneur en place :
# elle aurait alors fait TAIRE des erreurs API réelles que le lot ne corrige pas.
# Aveugle exactement là où le contrôle doit voir, et OK là où la règle 1 impose
# INCONNU. Elle échoue du mauvais côté.
#
# Le remède retenu est celui qui a déjà tenu ici (`check-champs.mjs`,
# `lint:styles`) : le lot DÉCLARE la signature qu'il corrige, et **la déclaration
# meurt avec son objet** — si la signature ne correspond plus à rien, le contrôle
# échoue. Une dérogation qui survit à ce qu'elle couvre redevient l'angle mort
# qu'on ferme.

signature_ancree() {       # $1 = motif déclaré → oui/non
  #  Une signature sans littéral (`.*`, `ERROR`) écarterait TOUT : la déclarer
  #  reviendrait à désarmer le point en croyant l'assouplir. On exige donc un mot
  #  d'au moins 4 caractères qui ne soit pas le niveau de log lui-même.
  local mots m
  [ -n "${1:-}" ] || { echo non; return; }
  mots=$(printf '%s' "$1" | tr -c 'A-Za-z0-9_/' ' ')
  for m in $mots; do
    case "$m" in ERROR|CRITICAL|error|critical) continue ;; esac
    [ "${#m}" -ge 4 ] && { echo oui; return; }
  done
  echo non
}

verdict_erreurs_api() {    # $1 = lignes ERROR/CRITICAL observées
                           # $2 = lignes écartées par la signature ('' si aucune déclaration)
                           # $3 = commit de la déclaration ('' si aucune)
                           # $4 = HEAD
                           # $5 = signature déclarée ('' si aucune)
  case "${1:-}" in ''|*[!0-9]*) echo INCONNU; return ;; esac
  #  Aucune déclaration : comportement d'origine, aucune tolérance.
  if [ -z "${3:-}" ] && [ -z "${5:-}" ]; then
    [ "$1" -eq 0 ] && echo OK || echo FAIL; return
  fi
  #  Déclaration incomplète : on ne devine pas ce qu'elle voulait couvrir.
  { [ -z "${3:-}" ] || [ -z "${5:-}" ] || [ -z "${4:-}" ]; } && { echo INCONNU; return; }
  #  Datée par le commit, comme `.git/pr-brief.md` : une signature laissée par le
  #  lot précédent décrirait une erreur qui n'est plus le sujet.
  [ "$3" != "$4" ] && { echo FAIL; return; }
  [ "$(signature_ancree "$5")" = "oui" ] || { echo FAIL; return; }
  case "${2:-}" in ''|*[!0-9]*) echo INCONNU; return ;; esac
  #  🔴 L'exception qui ne sert plus fait échouer le contrôle : si la signature
  #  déclarée ne correspond à aucune ligne, ou bien l'erreur a disparu — et la
  #  déclaration doit partir — ou bien elle ne visait pas ce qu'on croyait.
  [ "$2" -eq 0 ] && { echo FAIL; return; }
  [ "$2" -gt "$1" ] && { echo INCONNU; return; }
  [ "$(( $1 - $2 ))" -eq 0 ] && echo OK || echo FAIL
}

rang_attendu() {           # $1 = les sujets ET corps des commits du lot
  #  Le rang que le lot ANNONCE, lu dans ses préfixes conventionnels.
  #
  #  ⚠️ C'est ce que le lot dit de lui-même, et non le jugement de qui bumpe.
  #  `feat` déclare une capacité, `!` ou `BREAKING CHANGE` une rupture, tout le
  #  reste — `fix`, `refactor`, `docs`, `test`, `chore`, `perf` — n'en déclare
  #  aucune et vaut donc un patch (`standards/08` §6, en toutes lettres).
  #
  #  Un `fix` qui cache une capacité fera échouer le point 0g : c'est alors le
  #  PRÉFIXE qui est faux, et c'est ce défaut-là qu'il faut corriger. Mesurer le
  #  jugement plutôt que la déclaration aurait rendu le contrôle inutile — il
  #  aurait toujours confirmé celui qui bumpe.
  #
  #  Rien à lire → `inconnu`, jamais `patch` : un rang qu'on ne peut pas calculer
  #  n'est pas un rang par défaut (`standards/04` §1).
  #  ⚠️ L'espace avant le deux-points N'EST PAS optionnel dans le motif : ce dépôt
  #  écrit ses sujets en typographie française — `feat(accès) : lecture seule`.
  #  Mon premier motif exigeait `feat(…):` collé ; le cas zéro l'a pris en défaut
  #  immédiatement, et sans lui AUCUN `feat` du dépôt n'aurait été reconnu — le
  #  point 0g aurait répondu « patch » sur tous les lots, y compris ceux qui
  #  apportent une capacité. Un contrôle qui ne reconnaît jamais rien ne dit rien.
  local sujets="${1:-}"
  [ -z "$sujets" ] && { echo inconnu; return; }
  if printf '%s' "$sujets" | grep -qE '^[a-z]+(\([^)]*\))?! *:|^BREAKING CHANGE'; then
    echo major
  elif printf '%s' "$sujets" | grep -qE '^feat(\([^)]*\))? *:'; then
    echo minor
  else
    echo patch
  fi
}

verdict_rang_version() {   # $1 = rang attendu (major|minor|patch|inconnu)
                           # $2 = version dans origin/main · $3 = version dans HEAD
  #  Le RANG du bump doit correspondre à ce que le lot apporte.
  #
  #      patch  X.Y.Z+1  correction, amélioration mineure, documentation, refactor
  #      minor  X.Y+1.0  fonctionnalité VISIBLE par les utilisateurs
  #      major  X+1.0.0  refonte majeure ou rupture de compatibilité
  #
  #  🔴 Pourquoi ce contrôle (07/09/2026, question de l'utilisateur)
  #
  #  Le point 0d compte les bumps ; il ne regarde pas leur rang. Le relevé des
  #  dix-huit derniers lots en a trouvé SIX au mauvais rang — 3.102.0 (`fix`),
  #  3.106.0 (`fix`), 3.107.0 (`fix`), 3.108.0 et 3.109.0 (`refactor`), 3.112.0
  #  (`docs`) — soit un sur trois, et TOUS dans le même sens : surévalués.
  #
  #  Le sens constant est ce qui rend le défaut coûteux. Un `y` qui avance pour
  #  une correction cesse de dire quoi que ce soit : « minor » ne distingue plus
  #  une capacité nouvelle d'un défaut réparé, et c'est précisément ce que la
  #  numérotation existe pour dire. Personne ne l'a vu parce que personne ne
  #  regardait — le rang était affaire de jugement, jamais de contrôle.
  #
  #  ⚠️ Le rang attendu se lit dans les PRÉFIXES des commits du lot, pas dans le
  #  jugement de qui bumpe : `feat` ou `!`/`BREAKING CHANGE` déclarent une
  #  capacité, le reste n'en déclare pas. C'est faillible — un `fix` peut cacher
  #  une capacité — mais alors le commit est mal préfixé, et c'est ce défaut-là
  #  qu'il faut corriger. Le contrôle mesure ce que le lot DIT de lui-même.
  #
  #  INCONNU plutôt qu'OK dès qu'une des trois entrées manque : un rang qu'on ne
  #  peut pas calculer n'est pas un rang correct (`standards/04` §1).
  local rang="${1:-}" avant="${2:-}" apres="${3:-}"
  [ -z "$rang" ] || [ "$rang" = inconnu ] || [ -z "$avant" ] || [ -z "$apres" ] && { echo INCONNU; return; }
  [ "$avant" = "$apres" ] && { echo ECART; return; }   # aucun bump : 0d le dit déjà

  local xa ya za xb yb zb
  IFS=. read -r xa ya za <<EOF2
$avant
EOF2
  IFS=. read -r xb yb zb <<EOF2
$apres
EOF2
  case "$xa$ya$za$xb$yb$zb" in *[!0-9]*|'') echo INCONNU; return ;; esac

  local reel
  if   [ "$xb" -gt "$xa" ]; then reel=major
  elif [ "$xb" -eq "$xa" ] && [ "$yb" -gt "$ya" ]; then reel=minor
  elif [ "$xb" -eq "$xa" ] && [ "$yb" -eq "$ya" ] && [ "$zb" -gt "$za" ]; then reel=patch
  else echo FAIL; return ; fi   # version qui recule ou saute plusieurs rangs

  [ "$reel" = "$rang" ] && echo OK || echo FAIL
}
