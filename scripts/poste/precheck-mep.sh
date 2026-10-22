#!/usr/bin/env bash
# =============================================================================
#  Pré-check MEP — exécutable, et non plus une liste à dérouler à la main.
#
#  POURQUOI ce script existe. La grille des points vit dans
#  `.claude/skills/mep-precheck` depuis le 02/08/2026, et l'ordre des opérations
#  (pré-check AVANT le push sur dev) dans la banque de mémoire du projet. Les deux
#  étaient justes. Ils ont quand même été enfreints TROIS lots d'affilée les 07 et
#  08/08/2026, au motif que « s'arrêter au push dev » dispenserait du pré-check —
#  alors que `auto-deploy.sh` déploie `origin/main` toutes les 5 minutes : fusionner
#  la PR EST la mise en production.
#
#  C'est la troisième récidive du même défaut de discipline (socle 01 §2). La
#  conclusion du socle s'applique à elle-même : une consigne ne se maintient pas
#  seule. D'où ce script, et le hook `.githooks/pre-push` qui exige sa trace.
#
#  RÈGLES DE CONCEPTION (socle 04) :
#   - un contrôle qui ne peut pas s'exécuter rend INCONNU, jamais OK ;
#   - une sortie vide n'est pas un vert ;
#   - jamais `$(grep -c … || echo 0)` : `grep -c` écrit déjà 0 ET sort en 1, le
#     `||` ajoute une seconde valeur et le test devient inexploitable ;
#   - la base ne se lit que par `psql` dans le conteneur de PostgreSQL, et
#     l'URL de la base (son mot de passe) ne quitte jamais le nœud.
#
#  Usage : bash scripts/poste/precheck-mep.sh   # déroule tous les points
#          bash scripts/poste/precheck-mep.sh --post-mep # APRÈS la fusion : la production seule (#1282)
#          bash scripts/poste/precheck-mep.sh --selftest # éprouve les fonctions de décision
# =============================================================================
set -uo pipefail

SITE="${SITE:-https://5hostachy.fr}"
RPI1="${RPI1:-ptressard@192.168.1.222}"
RPI2="${RPI2:-ptressard@192.168.1.223}"

#: Seuils, tous nommés — un nombre nu dans un test est un seuil qu'on ne peut pas
#: discuter. Cf. socle 04 §18 : un seuil se règle sur le RÉGIME de ce qu'il surveille.
CACHE_BUILD_MAX_GB=40      # régime : le cache servi dans les 24 h, 10 à 11 Go mesurés (#1524) ;
                           # 40 Go = une purge qui ne retire plus rien, comme le 01/10/2026
LOG_MAX_MO=5
BATTEMENT_DEPLOY_MIN=20    # auto-deploy écrit ~12 lignes/h sur le standby

# ── Fonctions de décision PURES ──────────────────────────────────────────────
# Extraites dans `lib-verdicts-mep.sh` le 11/08/2026 : ce fichier a dépassé 500
# lignes en recevant 0f, et son PROPRE point 0b a refusé le push. Le self-test
# est parti avec elles — il est leur contrat.
# shellcheck source=../lib/lib-verdicts-mep.sh
#  Les modules `lib-*.sh` restent à la RACINE du dépôt : ils sont partagés avec
#  les scripts d'exploitation lancés par cron, dont les chemins absolus ne sont
#  pas versionnés (#337). Les déplacer ici couperait la bascule et le failover.
RACINE_DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RACINE_DEPOT" || exit 1   # les contrôles lisent api/, .git/ et front/ en relatif
. "$RACINE_DEPOT/scripts/lib/lib-verdicts-mep.sh"
. "$RACINE_DEPOT/scripts/lib/lib-depot.sh"   # traces : répertoire git DU clone, worktree compris (#1226)
GIT_DEPOT="$(dossier_git)"
MARQUEUR="${MARQUEUR:-$GIT_DEPOT/precheck-mep.ok}"
# shellcheck source=../lib/lib-reecriture.sh
. "$RACINE_DEPOT/scripts/lib/lib-reecriture.sh"

#  Ce que le point 6 compte comme une erreur de l'API — écrit UNE fois, lu par
#  ses deux requêtes et par son auto-test. Les niveaux de log, et les erreurs de
#  bibliothèque qui écrivent sur stderr SANS niveau (« Fontconfig error: … ») :
#  quinze d'entre elles passaient à chaque démarrage sous « compte=0 » (#1066).
#  Pas de guillemet ni de « $ » ici : le motif traverse SSH entre guillemets.
MOTIF_ERREURS_API='ERROR|CRITICAL|^[A-Za-z][A-Za-z0-9_-]* error:'

if [ "${1:-}" = "--selftest" ]; then
  #  Les auto-tests vivent à part depuis le 20/08/2026 (#511) : ils ne sont
  #  chargés QUE pour `--selftest`, jamais pendant un pré-check réel.
  . "$RACINE_DEPOT/scripts/lib/lib-verdicts-mep-selftest.sh"
  verdicts_mep_selftest
  exit $?
fi

# ── Exécution ────────────────────────────────────────────────────────────────

NB_OK=0; NB_FAIL=0; NB_INCONNU=0; NB_ECART=0
POINTS_INCONNUS=""   # les NUMÉROS des points non mesurés, pour les nommer à la fin
rapporter() {              # $1 = numéro, $2 = verdict, $3 = libellé, $4 = détail
  local icone
  case "$2" in
    OK)      icone="✓"; NB_OK=$((NB_OK+1)) ;;
    ECART)   icone="~"; NB_ECART=$((NB_ECART+1)) ;;
    INCONNU) icone="?"; NB_INCONNU=$((NB_INCONNU+1)); POINTS_INCONNUS="${POINTS_INCONNUS:+$POINTS_INCONNUS, }$1" ;;
    *)       icone="✗"; NB_FAIL=$((NB_FAIL+1)) ;;
  esac
  printf "%s %-3s %-46s %-8s %s\n" "$icone" "$1" "$3" "$2" "${4:-}"
}

#  Un SSH qui échoue rend une chaîne VIDE, que les fonctions de décision
#  traduisent en INCONNU — jamais en OK.
sur() { timeout 25 ssh -o BatchMode=yes -o ConnectTimeout=8 "$1" "$2" 2>/dev/null; }

#  🔴 Cette copie-ci avait DIVERGÉ : ni garde sur la sortie vide, ni timeout par
#  défaut, alors que les deux autres portaient le correctif du 30/07/2026. Le
#  point 1 pouvait donc afficher un code vide, que rien ne distingue d un OK.
# shellcheck source=../lib/lib-sonde.sh
. "$RACINE_DEPOT/scripts/lib/lib-sonde.sh"
. "$RACINE_DEPOT/scripts/lib/lib-applicatifs.sh"   # l'application, la base mise à part (DI-7b)

#  `--post-mep` (#1282) : après la fusion, les points du LOT échouent par
#  construction. Ce mode juge la production seule, ajoute P1 et P3, et
#  n'écrit jamais la trace qui autorise un push.
MODE_POST_MEP=""; [ "${1:-}" = "--post-mep" ] && MODE_POST_MEP=1
echo "═══ $([ -n "$MODE_POST_MEP" ] && echo 'Post-check' || echo 'Pré-check') MEP — $(date '+%Y-%m-%d %H:%M') ═══"
echo

#  ── Points du LOT (0a à 0g, 15, 16) : ils jugent ce qui PART ────────────────
#  Déplacés dans `lib-precheck-lot.sh` le 25/09/2026 (#1282). Après la fusion ils
#  échouent par construction : le mode `--post-mep` ne les lance donc pas.
if [ -z "$MODE_POST_MEP" ]; then
  . "$RACINE_DEPOT/scripts/lib/lib-precheck-lot.sh"
  precheck_points_lot
fi

# 1 — site public
CODE=$(http_code "$SITE/api/health")
rapporter 1 "$(verdict_http "$CODE")" "Site public" "HTTP ${CODE:-?}"

# 2 et 3 — rôle actif cohérent, pas de split-brain
A1=$(sur "$RPI1" 'cat /opt/5hostachy/.active')
A2=$(sur "$RPI2" 'cat /opt/5hostachy/.active')
C1=$(sur "$RPI1" "$COMPTER_APPLICATIFS")
C2=$(sur "$RPI2" "$COMPTER_APPLICATIFS")
rapporter 2 "$(verdict_role "$A1" "$A2" "$C1" "$C2")" "Rôle actif cohérent et conforme au réel" \
          "rpi1='${A1:-?}'/${C1:-?}c  rpi2='${A2:-?}'/${C2:-?}c"
rapporter 3 "$(verdict_standby "${A1:-}" "${C1:-}" "${C2:-}")" "Pas de split-brain"           "actif déclaré=${A1:-?} — conteneurs rpi1=${C1:-?} rpi2=${C2:-?}"

#  L'actif est déduit du réel, pas du flag : c'est lui qui porte les conteneurs
#  de l'APPLICATION (la réplique de la base vit sur le standby, DI-7b).
if [ "${C1:-0}" != "0" ]; then ACTIF="$RPI1"; STANDBY="$RPI2"; else ACTIF="$RPI2"; STANDBY="$RPI1"; fi
#  P1 et P3 : ils ont besoin de l'actif, déduit juste au-dessus.
if [ -n "$MODE_POST_MEP" ]; then
  . "$RACINE_DEPOT/scripts/lib/lib-precheck-post.sh"
  precheck_points_post
fi

# 4 — Le `.env` de l'actif désigne la base PostgreSQL. Jugé SUR
#     le nœud : seul le verdict revient, jamais l'URL (`base_configuree`,
#     lib-replication). La santé de la base elle-même est le point 22.
. "$RACINE_DEPOT/scripts/lib/lib-replication.sh"
CONF4=$(sur "$ACTIF" "$(declare -f moteur_de_url verdict_base_configuree cle_env_fichier base_configuree); base_configuree /opt/5hostachy/.env")
rapporter 4 "$(verdict_precheck_base "${CONF4:-}")" "Base configurée (.env de l'actif)" "${CONF4:-?}"

# 22 — Réplication PostgreSQL (DI-7b, #1781) : un primaire sur l'actif, une
#      réplique qui reçoit le journal sur le standby. Aucune base nulle part est
#      un échec. Collecte et décision : `lib-replication.sh`, les mêmes que C37 —
#      un pré-check qui jugerait autrement divergerait.
#  (lib-replication.sh est chargé au point 4.)
#  Séparés par « | » : `read` fusionne les blancs consécutifs (tabulation
#  comprise), et un champ vide décalerait les suivants.
champs_replication() {  # $1 = nœud → « present|recovery|flux|retard|recepteur| »
  local brut
  brut=$(sur "$1" "$COLLECT_REPLICATION")
  [ -n "$brut" ] || { echo ""; return; }
  for c in pg_present pg_recovery pg_flux pg_retard pg_recepteur; do
    printf '%s|' "$(printf '%s\n' "$brut" | sed -n "s/^$c=//p")"
  done
}
IFS='|' read -r RA1 RA2 RA3 RA4 RA5 <<< "$(champs_replication "$ACTIF")"
IFS='|' read -r RS1 RS2 RS3 RS4 RS5 <<< "$(champs_replication "$STANDBY")"
V22=$(verdict_precheck_replication "${RA1:-}" "${RA2:-}" "${RA3:-}" "${RA4:-}" "${RA5:-}"                                    "${RS1:-}" "${RS2:-}" "${RS3:-}" "${RS4:-}" "${RS5:-}")
rapporter 22 "$V22" "Réplication PostgreSQL" "actif: base=${RA1:-?} réplique=${RA2:-?} flux=${RA3:-?} retard=${RA4:-?}o · standby: base=${RS1:-?} réplique=${RS2:-?} réception=${RS5:-?}"

# 5 — WhatsApp : le bridge tourne-t-il, ET sa dernière connexion est-elle
#     postérieure à la dernière fermeture ?
#
#     Le contrôle ne lisait que la dernière ligne de journal. Or un `docker stop`
#     propre n'écrit PAS "Connection closed", et les journaux d'un conteneur
#     arrêté restent lisibles indéfiniment : le bridge stoppé le 14/08/2026 à
#     18h43 était encore rapporté « connecté » cinq heures plus tard, alors
#     qu'aucun message ne pouvait plus partir. On observait l'enregistrement, pas
#     la chose (`standards/04-fiabilite-des-controles.md` §14).
#
#     La surveillance continue, elle, interroge le bridge (`GET /status`) : c'est
#     un fait. Ici on n'a pas la clé d'API, donc on vérifie d'abord le seul fait
#     accessible — le conteneur tourne — avant de faire dire quoi que ce soit aux
#     journaux.
WA_UP=$(sur "$ACTIF" 'docker inspect -f "{{.State.Running}}" hostachy_whatsapp 2>/dev/null')
WA=$(sur "$ACTIF" 'docker logs hostachy_whatsapp --since 24h 2>&1 | grep -oE "WhatsApp connected|Connection closed" | tail -1')
if [ -z "${WA_UP:-}" ]; then
  V5=INCONNU; WA="conteneur introuvable ou hôte injoignable"
elif [ "$WA_UP" != "true" ]; then
  V5=FAIL; WA="le conteneur ne tourne pas — aucun message ne peut partir"
else
  case "$WA" in
    "WhatsApp connected") V5=OK ;;
    "") V5=INCONNU ;;
    *) V5=FAIL ;;
  esac
fi
rapporter 5 "$V5" "Bridge WhatsApp connecté" "dernier état : ${WA:-?}"

# 6 — erreurs API, hors celle que CE lot corrige (#502)
#     Le 19/08/2026 ce point a trouvé un vrai 500 sur `/auth/refresh`, puis a
#     refusé le push du correctif une heure durant — le contrôle bloquait la
#     réparation de ce qu'il constatait. Le lot peut désormais DÉCLARER la
#     signature qu'il corrige, dans `.git/erreur-corrigee` :
#         commit: 6055161
#         auth/refresh
#     La déclaration meurt avec son objet : si la signature ne correspond plus à
#     rien, le point ÉCHOUE (`verdict_erreurs_api`). Le raisonnement complet, et
#     pourquoi la fenêtre glissante depuis le dernier déploiement a été écartée,
#     sont dans `lib-verdicts-mep.sh`.
ERR=$(sur "$ACTIF" 'docker logs hostachy_api --since 1h 2>&1 | grep -cE "'"$MOTIF_ERREURS_API"'"; true')
SIG6=""; SIGC6=""; ECART6=""; DET6="compte=${ERR:-?}"
if [ -f "$GIT_DEPOT/erreur-corrigee" ]; then
  SIGC6=$(sed -n '1s/^commit:[[:space:]]*//p' "$GIT_DEPOT/erreur-corrigee" | tr -d '\r')
  SIG6=$(sed -n '2p' "$GIT_DEPOT/erreur-corrigee" | tr -d '\r')
  #  Le motif est appliqué EN LOCAL sur les lignes rapatriées, jamais injecté
  #  dans la commande SSH : l'oubli des guillemets autour d'un motif distant a
  #  déjà coûté un correctif en trois passes (check-reliability, 11/08/2026).
  LIG6=$(sur "$ACTIF" 'docker logs hostachy_api --since 1h 2>&1 | grep -E "'"$MOTIF_ERREURS_API"'" | head -500; true')
  NBLIG6=$(printf '%s
' "$LIG6" | grep -c . || true)
  #  Moins de lignes rapatriées que comptées = troncature ou mesure partielle :
  #  on ne filtre pas ce qu'on n'a pas lu, `verdict_erreurs_api` rendra INCONNU.
  if [ -n "$SIG6" ] && [ "${NBLIG6:-0}" -ge "${ERR:-0}" ] 2>/dev/null; then
    ECART6=$(printf '%s
' "$LIG6" | grep -cE -- "$SIG6" || true)
  fi
  DET6="$DET6, écartées=${ECART6:-?} par « ${SIG6:-?} » (déclarée pour ${SIGC6:-?})"
fi
#  `HEAD_COURT` vient du point 0f, que `--post-mep` ne lance pas (#1282) : repli sur HEAD.
rapporter 6 "$(verdict_erreurs_api "${ERR:-}" "$ECART6" "$SIGC6" "${HEAD_COURT:-$(git rev-parse --short HEAD 2>/dev/null)}" "$SIG6")"           "Aucune ERROR/CRITICAL (1 h)" "$DET6"

# 7 — bits d'exécution des scripts lancés par cron
#
#     ⚠️ Le glob était `/opt/5hostachy/*.sh` : il ne regardait que la RACINE.
#     Déplacer les scripts dans `scripts/` l'aurait fait ne correspondre à rien —
#     donc « 0 script sans bit d'exécution », donc **OK**. Le contrôle qui
#     garantit que les scripts de cron sont exécutables serait passé au vert
#     précisément parce qu'ils avaient disparu (cas zéro, socle 04 §2).
#
#     Il compte désormais le TOTAL en plus des fautifs : zéro script trouvé n'est
#     pas un succès, c'est un contrôle qui n'a rien mesuré.
LOT7=$(sur "$ACTIF" 'set -- /opt/5hostachy/*.sh /opt/5hostachy/scripts/*/*.sh;        tot=0; ko=0; for f; do [ -f "$f" ] || continue; case "${f##*/}" in lib-*) continue;; esac;        tot=$((tot+1)); [ -x "$f" ] || ko=$((ko+1)); done; echo "$tot $ko"')
TOT7=${LOT7%% *}; SANSX=${LOT7##* }
if [ -z "${LOT7:-}" ] || [ -z "${TOT7:-}" ]; then
  V7=INCONNU; D7="hôte injoignable — rien n'a été mesuré"
elif [ "${TOT7:-0}" -eq 0 ] 2>/dev/null; then
  V7=INCONNU; D7="aucun script trouvé — le chemin de scan est faux, ce n'est pas un succès"
else
  V7=$(verdict_compte "${SANSX:-}" 0); D7="$TOT7 script(s) examiné(s), sans bit x=${SANSX:-?}"
fi
rapporter 7 "$V7" "Scripts cron exécutables" "$D7"

# 8 — battement d'auto-deploy sur le STANDBY (sur l'actif, le silence est normal)
AGE=$(sur "$STANDBY" 'd=$(grep -oE "^\[[0-9-]+ [0-9:]+" /var/log/hostachy-deploy.log 2>/dev/null | tail -1 | tr -d "["); \
      [ -n "$d" ] && echo $(( ( $(date +%s) - $(date -d "$d" +%s) ) / 60 ))')
rapporter 8 "$(verdict_age_min "${AGE:-}" $BATTEMENT_DEPLOY_MIN)" "Battement auto-deploy (standby)" \
          "dernier battement il y a ${AGE:-?} min"

# 9 — e-mails en échec sur 7 jours
#     Sortait INCONNU à CHAQUE exécution : l'historique s'interroge in-process et
#     exigeait une session admin, donc il fallait ouvrir l'écran à la main. Personne
#     ne le faisait — et c'est le seul contrôle qui voit cette classe de défaut, qui
#     s'est reproduite trois fois : un gabarit Jinja qui ne se rend pas part en échec
#     SANS que rien ne remonte à l'expéditeur (l'envoi est une BackgroundTask). Le
#     28/07/2026, six membres du CS n'ont rien reçu, visible nulle part ailleurs.
#
#     Mesuré depuis l'ACTIF, par le canal machine déjà utilisé par les scripts cron
#     (`x-maintenance-key`, cf. lib-collecte.sh) : la route ne rend que des COMPTES
#     et des codes de gabarits, jamais une adresse ni un sujet.
#
#     Le compte n'est lu QUE sur un HTTP 200 — sans cette condition, une réponse
#     vide (clé absente, API muette) se lirait comme « zéro échec », c'est-à-dire un
#     vert obtenu par l'absence de mesure. C'est la leçon de C19, le 11/08/2026.
REP9=$(sur "$ACTIF" 'MK=$(grep -E "^MAINTENANCE_KEY=" /opt/5hostachy/.env 2>/dev/null | cut -d= -f2- | tr -d "\"'"'"' 
");        [ -n "$MK" ] && curl -s --max-time 10 -w "|%{http_code}" -H "x-maintenance-key: $MK"          "http://localhost/api/admin/emails/echecs-recents?jours=7"')
case "${REP9:-}" in
  *"|200") NB9=$(echo "$REP9" | grep -oE '"total"[[:space:]]*:[[:space:]]*[0-9]+' | grep -oE '[0-9]+$')
           CODES9=$(echo "$REP9" | grep -oE '"par_code"[[:space:]]*:[[:space:]]*\{[^}]*\}' | cut -c1-90)
           rapporter 9 "$(verdict_compte "${NB9:-}" 0)" "E-mails sans échec (7 j)"                      "échecs=${NB9:-?}${CODES9:+ — $CODES9}" ;;
  *)       rapporter 9 INCONNU "E-mails sans échec (7 j)"                      "canal machine muet (clé absente ou API injoignable) — vérifier Admin → Modèles e-mail" ;;
esac

# 10 — parité de code entre les 2 nœuds
#  HEAD complet, pas `--short` : git abrège selon la taille du dépôt, et les
#  deux nœuds rendaient le même commit sur 8 et 7 caractères — ÉCART permanent
#  jusqu'au 09/09/2026 (#854, motif dans `lib-parite.memes_hachages`).
H1=$(sur "$RPI1" 'git -C /opt/5hostachy rev-parse HEAD')
H2=$(sur "$RPI2" 'git -C /opt/5hostachy rev-parse HEAD')
rapporter 10 "$(verdict_parite "$H1" "$H2")" "Parité de code actif ⇆ standby" \
          "rpi1=${H1:0:8} rpi2=${H2:0:8} (le standby s'aligne seul sous 5 min — auto-deploy, #448)"

# 11 — auto-deploy de l'actif vivant
PROPRIO=$(sur "$ACTIF" 'stat -c %U /var/log/hostachy-deploy.log 2>/dev/null')
if [ "$PROPRIO" = "ptressard" ]; then V11=OK; elif [ -z "$PROPRIO" ]; then V11=INCONNU; else V11=FAIL; fi
rapporter 11 "$V11" "Auto-deploy de l'actif vivant" "log appartient à ${PROPRIO:-?}"

#  ── Points 12 à 18 : l'exploitation ────────────────────────────────────────
#  Extraits le 20/08/2026, au fil de l'eau : le point 18 (#511) faisait passer
#  ce fichier de 490 à 503 lignes, et le garde-fou de modularité l'a refusé.
#  La coupe suit la nature des contrôles — ceux qui interrogent les DEUX RPi
#  et leurs artefacts d'exploitation (images, journaux, disque, points
#  d'entrée), là où les précédents portent sur le lot et sur l'application.
#  ── Point 19 : les liens que les COURRIELS envoient ────────────────────────
#  Il vit à part parce qu'il mesure autre chose que les précédents : non pas
#  l'état des machines, mais ce qu'un destinataire d'e-mail obtiendra en
#  cliquant. Ajouté le 11/09/2026 après un 404 constaté par l'utilisateur —
#  aucun test de CI ne pouvait le voir, la valeur fautive étant en BASE.
. "$RACINE_DEPOT/scripts/lib/lib-precheck-liens.sh"
precheck_point_liens
. "$RACINE_DEPOT/scripts/lib/lib-precheck-pages.sh"   # 20 — l'ordre du menu servi (#1114)
precheck_point_pages
. "$RACINE_DEPOT/scripts/lib/lib-precheck-legal.sh"   # 21 — les textes légaux servis (#1585)
precheck_point_legal
. "$RACINE_DEPOT/scripts/lib/lib-precheck-pr.sh"      # 23-24 — PR vers main, alertes Dependabot
precheck_point_pr
precheck_point_alertes

. "$RACINE_DEPOT/scripts/lib/lib-precheck-infra.sh"
precheck_points_infra

