#!/bin/bash
# =============================================================================
#  lib-verdicts.sh — Fonctions de DÉCISION pures de check-reliability.sh
#
#  Module SOURCÉ, jamais exécuté : pas de bit x (le job CI « Bits d'exécution
#  versionnés » attend 100644 sur les `lib-*.sh`, et un bit x y serait trompeur).
#
#  POURQUOI CE FICHIER. `check-reliability.sh` a dépassé 500 lignes et le
#  garde-fou de modularité a refusé le push en y ajoutant C19 (11/08/2026), à
#  raison. La frontière n'est pas arbitraire : ces fonctions sont les seules du
#  script à être PURES — aucun SSH, aucun docker, aucune écriture, aucun sudo —
#  et ce sont exactement celles que `--selftest` éprouve. C'est le pattern
#  inauguré par `boot-role-guard.sh --selftest` (15/07/2026) : isoler la décision
#  de la collecte est le seul moyen de tester une décision d'infra sans les deux
#  RPi.
#
#  Le self-test vit ICI, avec le code qu'il éprouve : le laisser chez l'appelant
#  permettait de modifier une fonction sans relire son contrat — et c'est le
#  contrat qui dit ce que « INCONNU, jamais OK » veut dire pour chacune.
#  `bash check-reliability.sh --selftest` reste la commande ; le job CI ne change pas.
#
#  Règle pour toute fonction ajoutée ici : rendre INCONNU sur une mesure manquante
#  ou aberrante, jamais un vert (`standards/04-fiabilite-des-controles.md`).
# =============================================================================

#  `http_code` vivait ici — elle est dans `lib-sonde.sh` depuis le 01/09/2026,
#  où elle est écrite UNE fois pour les trois scripts qui la sondaient.

# ── Le site public est-il RÉELLEMENT en panne ? (PURE — testable) ────────────
# Args : code1  code2  deploiement       (deploiement = "oui" / "non" / autre)
#   code1 : première sonde de l'URL publique
#   code2 : seconde sonde, après un délai — "" si l'on n'a pas eu à la faire
#   deploiement : un build d'auto-deploy tient-il son verrou sur l'ACTIF ?
#   bascule : une bascule tient-elle son verrou (`bascule_en_cours`) ?
#   code3 : troisième sonde, nom résolu par un autre chemin — "" si la seconde
#           n'a pas échoué à la résolution
# Échoit : OK · TRANSITOIRE:<code1> · RESOLUTION:<code2> · BASCULE:<code1> ·
#          DEPLOIEMENT:<code1> · KO:<dernier code> · INCONNU
#
# 🔴 POURQUOI (01/09/2026). À 01:21, C1 a envoyé une alerte critique « Site public
# KO (HTTP 503) ». Le site n'était pas en panne : `auto-deploy.sh` recréait les
# conteneurs entre 01:18 et 01:23 — le 503 est la réponse de Caddy pendant que son
# amont redémarre. Une seule occurrence dans 1,8 Mo de journal, et l'exécution
# suivante était verte.
#
# ⚠️ Ce n'est PAS un assouplissement de seuil — la leçon du point 10 (#448) est
# que la tolérance masque. C'est une SECONDE MESURE : un site réellement KO l'est
# encore quelques secondes plus tard, et le reste aux exécutions suivantes.
#
# La preuve que le contrôle avait tort était déjà dans son propre rapport :
# `health-watch.sh`, qui sonde la même URL, re-sonde à 30 s avant de conclure. Il
# a écarté le 503 de 05:42 le même jour — « Site revenu entre les deux checks
# (HTTP 200) — faux positif, pas d'action ». Deux contrôles du même fait, deux
# fiabilités : le plus bruyant est celui qui alerte.
#
# ⚠️ DEPLOIEMENT n'est pas un vert. Un build qui échoue laisse le site KO, et
# l'exécution suivante — quinze minutes plus tard, verrou relâché — le dira en
# FAIL. La dérogation ne survit donc pas à son objet.
#
# 🔴 LA BASCULE EST LA SECONDE OPÉRATION NORMALE QUI COUPE LE SITE (04/09/2026).
#
# Le 04/09 à 02:06, TROIS contrôles ont crié en même temps — site 503, aucun
# conteneur nulle part, cloudflared sur aucun nœud. Les trois décrivaient
# exactement le milieu d'une bascule réussie : entre 02:05:46 (« Cloudflared
# local stoppé ») et 02:06:33 (« URL publique OK »), soit **47 secondes**. Le
# journal de bascule dit 7/7, base intègre, site rétabli.
#
# ⚠️ Le verrou existait DÉJÀ et était DÉJÀ lu : `.bascule-lock`, que C6 examine
# pour dire « opération en cours ». Trois contrôles voisins l'ignoraient. C'est
# le même oubli que le verrou de build avant le 01/09 — écrire un contrôle sans
# relire ce que son voisin a appris, c'est refaire son défaut.
#
# ⚠️ La tolérance est BORNÉE par l'âge du verrou (`LOCK_STALE_MIN`) : une bascule
# figée depuis vingt minutes n'est plus une opération en cours, c'est une panne,
# et le FAIL doit alors partir. Sans cette borne, un verrou oublié rendrait les
# trois contrôles définitivement muets.
#
# 🔴 LE RÉSOLVEUR DU NŒUD N'EST PAS LE SITE (21/10/2026). Le 20/10 à 22:36, les
# deux sondes avaient expiré à la résolution du nom, et rpi2 recevait un 200 à
# la même minute. `$5` est alors une troisième sonde, résolue par un autre
# chemin (`echec_de_resolution`, lib-sonde) : un 200 dit que le site servait —
# WARN, au digest, parce que le chemin DNS du domicile a bien failli. Un échec
# reste le FAIL : la panne de DNS ou de lien du domicile coupe aussi le tunnel.
verdict_site_public() {
  local code1="${1:-}" code2="${2:-}" deploiement="${3:-}" bascule="${4:-}" code3="${5:-}"
  [ -z "$code1" ] && { echo "INCONNU"; return; }
  [ "$code1" = "200" ] && { echo "OK"; return; }
  [ "$code2" = "200" ] && { echo "TRANSITOIRE:$code1"; return; }
  [ "$code3" = "200" ] && { echo "RESOLUTION:${code2:-$code1}"; return; }
  [ "$bascule" = "oui" ] && { echo "BASCULE:$code1"; return; }
  [ "$deploiement" = "oui" ] && { echo "DEPLOIEMENT:$code1"; return; }
  #  On rend le code de la DERNIÈRE sonde : c'est le plus récent, donc l'état à
  #  l'instant de la décision. Vide (sonde impossible) → on garde le précédent.
  echo "KO:${code3:-${code2:-$code1}}"
}

# ── Une bascule est-elle EN COURS ? (PURE — testable) ────────────────────────
#
# Rend "oui" si l'un des deux nœuds porte un `.bascule-lock` récent. « Récent »
# est borné : au-delà de `stale_min`, le verrou est orphelin — une bascule figée
# est une panne, pas une opération en cours, et les contrôles doivent reparler.
#
# ⚠️ Un verrou dont l'horodatage est absent ou illisible (0) ne vaut PAS « en
# cours » : on ne tait un contrôle que sur une preuve, jamais sur une absence.
bascule_en_cours() {  # $1,$2 = mtimes des verrous · $3 = maintenant · $4 = seuil min
  local a="${1:-0}" b="${2:-0}" maintenant="${3:-0}" stale_min="${4:-20}" mtime age
  for mtime in "$a" "$b"; do
    case "$mtime" in ''|*[!0-9]*) continue ;; esac
    [ "$mtime" -le 0 ] && continue
    age=$(( (maintenant - mtime) / 60 ))
    [ "$age" -lt 0 ] && continue
    [ "$age" -lt "$stale_min" ] && { echo "oui"; return; }
  done
  echo "non"
}


# ── C26. Le verrou a-t-il été posé AVANT la première action ? (PURE) ─────────
#
# 🔴 #915 se terminait sur : « le verrou est la coordination ; elle tient tant
# que la bascule le pose AVANT sa première action — ce que les tests vérifient
# PAR LA FORME DU SCRIPT, PAS PAR SON EXÉCUTION ».
#
# Ce contrôle lit le journal de la DERNIÈRE bascule réellement exécutée et
# vérifie cet ordre sur les faits. C'est la différence entre « le script est
# écrit ainsi » et « il s'est comporté ainsi » : un chemin conditionnel, un
# `set -e` mal placé ou une modification future peuvent séparer les deux.
#
# ⚠️ La première ACTION est l'arrêt des conteneurs du peer — la seule chose que
# la bascule fasse avant la phase 1. Ce qui la précède ne fait que lire.
#
# ⚠️ Deux formulations coexistent dans l'historique : « posé sur le peer »
# (avant #916) et « posé sur les DEUX nœuds » (après). Le motif accepte les
# deux — sinon le contrôle rendrait INCONNU sur toutes les bascules passées et
# on prendrait l'habitude de l'ignorer.
verdict_ordre_bascule() {  # entrée : le journal de la dernière bascule, sur stdin
                           # → OK | TARDIF | INCONNU
  local ligne n=0 n_pose=0 n_action=0
  #  ⚠️ `|| [ -n "$ligne" ]` : sans lui, une dernière ligne SANS saut final est
  #  perdue — et c'est exactement la forme qu'un `tail` ou un journal tronqué
  #  produit. Trouvé par l'auto-test, qui rendait INCONNU sur un journal d'une
  #  seule ligne : le cas le plus court était le seul mal lu.
  while IFS= read -r ligne || [ -n "$ligne" ]; do
    n=$((n + 1))
    case "$ligne" in
      *"Lock bascule posé"*) [ "$n_pose" -eq 0 ] && n_pose=$n ;;
      *"conteneur(s) actif(s)"*|*"[1/7]"*) [ "$n_action" -eq 0 ] && n_action=$n ;;
    esac
  done
  #  Journal vide, tronqué, ou bascule sans pose : on ne SAIT pas. Jamais OK —
  #  c'est le cas zéro, et il est le plus probable ici (rotation du journal).
  [ "$n_pose" -eq 0 ] && { echo INCONNU; return; }
  #  Aucune action relevée : la bascule s'est arrêtée avant, rien à reprocher.
  [ "$n_action" -eq 0 ] && { echo OK; return; }
  [ "$n_pose" -lt "$n_action" ] && echo OK || echo TARDIF
}

# ── C12. Une bascule a-t-elle été TUÉE ? (PURE — testable) ───────────────────
#
# 🔴 C12 mesurait l'ÂGE du verrou, et il ne pouvait donc jamais alerter : à
# 15 min `health-watch` l'EFFACE, et C12 ne passe que toutes les 15 min — le
# fichier avait toujours disparu avant d'être signalable. La fenêtre d'alerte
# était vide, et #915 déclarait pourtant ce garde-fou « acceptable » en s'y
# fiant. C'est le **cas zéro** de `standards/04` §2 : un contrôle qui ne peut pas
# mesurer ne rend pas OK.
#
# On observe donc l'ACTE de nettoyage, qui laisse une trace datée dans le journal
# de `health-watch`, et non l'objet, qui n'en laisse aucune. Même retournement
# que le point 13 du pré-check, qui se vérifie par « Alerte envoyée » plutôt que
# par « Email KO » (`project_canal_alerte_verifiable`).
#
# ⚠️ Un nettoyage n'est pas une panne en cours : c'est la trace d'une bascule ou
# d'une MAJ tuée (coupure, `kill -9`, gel — les trois sont documentés sur rpi2).
# Il vaut WARN, pas FAIL, et seulement s'il est RÉCENT : un nettoyage d'il y a
# trois semaines ne doit pas crier tous les quarts d'heure.
verdict_verrou_orphelin() {  # $1 = epoch du dernier nettoyage · $2 = maintenant
                             # $3 = fenêtre (s) → OK | RECENT:<min> | INCONNU
  local dernier="${1:-}" maintenant="${2:-0}" fenetre="${3:-86400}" age
  #  Journal illisible ou absent : on ne SAIT pas. Jamais OK — c'est précisément
  #  l'erreur que ce contrôle vient de commettre pendant des semaines.
  case "$dernier" in ''|*[!0-9]*) echo INCONNU; return ;; esac
  #  Aucun nettoyage jamais journalisé : c'est un vrai vert, et il est mesuré.
  [ "$dernier" -le 0 ] && { echo OK; return; }
  age=$(( maintenant - dernier ))
  #  Horodatage dans le futur (horloge recalée, C11) : on ne conclut pas.
  [ "$age" -lt 0 ] && { echo INCONNU; return; }
  [ "$age" -lt "$fenetre" ] && echo "RECENT:$(( age / 60 ))" || echo OK
}

# ── Empreinte des scripts planifiés dans un crontab (PURE — testable) ────────
# Rend la liste TRIÉE et dédoublonnée des scripts `/opt/5hostachy/*.sh` invoqués,
# séparés par des virgules — ou une chaîne vide si le crontab est illisible.
#
# On compare volontairement le SEUL ensemble de scripts, pas les horaires : deux
# nœuds peuvent écrire `*/5` et `2,7,12,…` pour la même cadence, et un contrôle
# qui hurlerait là-dessus serait exactement le faux positif qu'on vient de retirer
# de C16. La borne est donc assumée (§12 du socle) : ce contrôle attrape « un
# script planifié d'un seul côté », pas « planifié à un rythme différent ».
#  🔴 LA BARRE OBLIQUE DANS LA CLASSE, ajoutée le 19/08/2026.
#
#  Elle manquait, et #337 avait rangé les scripts dans
#  `/opt/5hostachy/scripts/exploitation/` le 15/08 : le motif ne pouvait plus
#  correspondre à rien. C18 a répondu « Crontabs root INCONNUS » quatre jours
#  durant, sur les deux nœuds — le seul contrôle qui rend vraie la phrase « cron
#  root identique sur les 2 nœuds » de `CLAUDE.md` ne mesurait plus rien.
#
#  ⚠️ Cette fonction ÉTAIT testée, et ses tests passaient : leurs fixtures
#  employaient l'ancienne arborescence à plat. Un test dont les données décrivent
#  un monde disparu vérifie la fonction contre elle-même. Les fixtures couvrent
#  désormais les DEUX formes, et c'est la nouvelle qui sert de cas zéro.
crontab_scripts() {  # $1 = texte brut du crontab → "a.sh,b.sh" | ""
  #  Le motif vit dans `scripts_cites` (lib-points-entree.sh), que C6 partage
  #  depuis #1546 : une seule écriture pure, comparée au jumeau de la collecte.
  echo "$1" | scripts_cites \
    | sed 's#.*/##' | sort -u | paste -sd, - | tr -d ' \n'
}

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-horodatage.sh"   # age_min_epoch
# ── Âge du dernier battement horodaté d'un log (minutes) ─────────────────────
# Rend -1 si aucun horodatage exploitable : INCONNU, jamais « récent ».
beat_age_min() {  # $1 = "AAAA-MM-JJ HH:MM:SS" (peut être vide), $2 = epoch de réf.
  local ts="$1" now="${2:-$(date +%s)}" e
  [ -n "$ts" ] || { echo -1; return; }
  e=$(date -d "$ts" +%s 2>/dev/null)
  [ -n "$e" ] || { echo -1; return; }
  age_min_epoch "$e" "$now"   # l'heure double d'octobre ne rend plus d'âge négatif (#2232)
}

verdict_sondes_maintenance() {
  # $1 = âge (min) de la dernière exécution vue dans le JOURNAL du nœud
  # $2 = âge (min) du dernier rapport de ce nœud EN BASE ("" = aucun)
  # $3 = tolérance (min) entre les deux
  #
  #  DEUX SONDES INDÉPENDANTES, et c'est leur DÉSACCORD qui porte l'information
  #  (`standards/04-fiabilite-des-controles.md`). Chacune prise seule ment par
  #  omission — vécu du 09 au 11/08/2026 :
  #    - le journal disait « la maintenance a tourné » (C17, vert) ;
  #    - la base disait « aucun rapport », et l'écran affichait un badge rouge
  #      que rien ne permettait de distinguer d'une tâche qui n'a pas tourné.
  #  Les deux avaient raison : le script tournait et mourait avant d'envoyer son
  #  rapport, la rotation des journaux ayant délié son propre inode (corrigé en
  #  v2.46.8). Personne ne comparait, donc le seul symptôme était illisible.
  #
  #  Sens de la comparaison : un rapport NETTEMENT plus vieux que la dernière
  #  exécution connue signifie que la chaîne de remontée est rompue. L'inverse
  #  (rapport plus récent que le journal) n'est pas une anomalie : le rapport
  #  peut venir d'un déclenchement manuel depuis l'interface, qui n'écrit pas
  #  dans le journal du nœud.
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  #  Base non interrogeable (standby : aucune API locale) → INCONNU, jamais OK.
  [ "$2" = "-" ] && { echo INCONNU; return; }
  #  Le journal montre une exécution, la base n'a AUCUN rapport de ce nœud.
  [ -z "$2" ] && { echo DIVERGENCE; return; }
  case "$2" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ $(( $2 - $1 )) -gt "$3" ] && echo DIVERGENCE || echo OK
}

# ── Sonde « base » de C19 : que dit la base pour CE nœud ? (PURE — testable) ─
# $1 = concaténation des champs `rapports` collectés sur les deux nœuds
# $2 = nom du nœud cherché
#
# Rend :
#   -       la base n'a pu être interrogée par AUCUN nœud → INCONNU
#   (vide)  la base a répondu, et n'a aucun rapport pour ce nœud → DIVERGENCE
#   date    horodatage du dernier rapport de ce nœud
#
# POURQUOI cette distinction existe. Jusqu'au 11/08/2026 les deux premiers cas
# rendaient la même chaîne vide, et C19 concluait INCONNU dans les deux. Or « la
# base répond : aucun rapport » est très exactement le cas que C19 existe pour
# attraper — il l'a rencontré en production le soir même (journal : maintenance
# il y a 2 j ; base : `"noeuds": {}`) et a répondu INCONNU. Le cas zéro de
# `standards/04-fiabilite-des-controles.md` §2 : une réponse vide est une
# information, pas une absence d'information.
#
# Le marqueur `ok:` est posé par la collecte, et seulement si le curl a rendu
# HTTP 200 — c'est lui qui distingue « demandé » de « pas pu demander ».
sonde_base() {
  case "$1" in
    *ok:*) ;;
    *) echo "-"; return ;;
  esac
  #  L'horodatage ressort tel quel, `Z` compris : il est en UTC, et `date -d` sait
  #  le lire. Le convertir en « AAAA-MM-JJ HH:MM:SS » le ferait interpréter comme
  #  une heure LOCALE — mesuré le 11/08/2026 sur le même rapport : 8 min avec le
  #  `Z`, 128 min sans. Deux heures d'erreur silencieuse sur une tolérance de 12 h.
  echo "$1" | sed 's/ok://g' | tr ';' '\n' \
    | grep -oE "^$2:$RAPPORTS_MOTIF_TS" | head -1 | cut -d: -f2-
}

# ── Extraction des rapports depuis la réponse de l'API (PURE — testable) ─────
# $1 = corps de la réponse suivi de « |<code HTTP> » (curl -w)
#
# POURQUOI cette fonction existe, et pourquoi le motif est UNE constante.
# Le 11/08/2026, la collecte extrayait les dates avec `"rpi[0-9]": ?"[0-9T:.-]+"`.
# Le `Z` final des horodatages ISO n'était pas dans la classe, donc le motif ne
# pouvait JAMAIS compléter une correspondance : la carte revenait vide quoi que
# rende l'API. C19 en tirait INCONNU en permanence — puis DIVERGENCE en
# permanence une fois #305 « corrigé », ce qui est pire : un contrôle qui crie
# toujours ne dit plus rien, et le rendez-vous de #301 aurait été sans valeur.
#
# `sonde_base` était testée, et juste. Le défaut vivait EN AMONT d'elle, dans le
# tuyau qui la nourrit — exactement là où personne ne regardait, comme le défaut
# d'origine de C19. D'où cette seconde fonction pure : ce qui traduit une réponse
# d'API en entrée de décision se teste, au même titre que la décision.
#
# Le motif est débarrassé de ses guillemets en amont (`tr -d`), ce qui le rend
# injectable tel quel dans la chaîne COLLECT et testable ici — une seule
# définition pour les deux usages.
RAPPORTS_MOTIF_TS='[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}([.][0-9]+)?Z?'
RAPPORTS_MOTIF="rpi[0-9]:$RAPPORTS_MOTIF_TS"

extraire_rapports() {
  case "$1" in
    *"|200") ;;
    *) echo ""; return ;;          # pas de réponse exploitable : PAS de marqueur
  esac
  echo "ok:$(echo "$1" | tr -d '" ' | grep -oE "$RAPPORTS_MOTIF" | tr '\n' ';')"
}

# ── Taille du cache de build Docker en Go entiers (PURE — testable) ──────────
# `docker system df` rend « 64.68GB », « 980MB »… Rend -1 si illisible :
# INCONNU n'est jamais OK (règle 1 du CLAUDE.md).
cache_go() {  # $1 = "64.68GB" → 64 ; "980MB" → 0 ; "" → -1
  local s="$1" n u
  n=$(echo "$s" | grep -oE '^[0-9]+([.][0-9]+)?')
  u=$(echo "$s" | grep -oE '[kKMGT]?B$')
  [ -n "$n" ] && [ -n "$u" ] || { echo -1; return; }
  case "$u" in
    GB)          echo "${n%%.*}" ;;
    TB)          echo $(( ${n%%.*} * 1024 )) ;;
    MB|kB|KB|B)  echo 0 ;;
    *)           echo -1 ;;
  esac
}

# ── Verdict du cache de build (PURE — testable) ──────────────────────────────
# Args : taille en Go (-1 = illisible), seuil → "ok" | "depasse" | "inconnu".
# Séparé de la mesure pour que le CAS ZÉRO soit testable : un cache illisible
# doit rendre INCONNU et non « 0 Go, donc sous le seuil » (règle 1).
cache_verdict() {
  local go="$1" max="$2"
  case "$go" in ''|*[!0-9-]*) echo inconnu; return ;; esac
  [ "$go" -lt 0 ] && { echo inconnu; return; }
  [ "$go" -ge "$max" ] && echo depasse || echo ok
}

# ── Verdict du battement (PURE — testable) ───────────────────────────────────
# Args : âge en minutes (-1 = inconnu), seuil → "ok" | "absent" | "inconnu"
beat_verdict() {
  local age="$1" max="$2"
  case "$age" in ''|*[!0-9-]*) echo inconnu; return ;; esac
  [ "$age" -lt 0 ] && { echo inconnu; return; }
  [ "$age" -le "$max" ] && echo ok || echo absent
}

# ── Que faut-il NOTIFIER de cette exécution ? ────────────────────────────────
#  `verdict_notification` vit dans `lib-notification.sh` depuis le 30/10/2026,
#  à côté de son seul appelant : `audit-securite.sh` source ce module-là sans
#  celui-ci, et le premier audit en production a envoyé son courriel sur une
#  décision vide (« verdict_notification: command not found »).

# ── C23. Les en-têtes de sécurité sont-ils RÉELLEMENT servis ? ───────────────
#: $1 = les en-têtes reçus (sortie brute de `curl -sI`), $2 = la liste attendue
#: (noms séparés par des espaces) → "OK" | "MANQUANT:<liste>" | "INCONNU"
#:
#: 🔴 POURQUOI CE CONTRÔLE EXISTE (20/08/2026)
#:
#: Un contrôle des en-têtes existait — dans `check-stack.sh`. Il a été RETIRÉ du
#: cron de rpi2 le 06/08/2026 parce qu'il y échouait 144 fois par jour. Et il
#: échouait pour une raison précise : il attendait `X-Frame-Options: SAMEORIGIN`
#: là où le Caddyfile dit `DENY`.
#:
#: Autrement dit : le seul contrôle des en-têtes portait une attente FAUSSE, il
#: criait, on l'a fait taire — et depuis, plus rien ne regarde. Un en-tête de
#: sécurité peut disparaître d'un Caddyfile sans que personne ne le sache.
#:
#: ⚠️ Celui-ci ne vérifie que la PRÉSENCE, jamais la valeur. C'est ce qui l'avait
#: tué : une valeur attendue se périme au premier ajustement de configuration,
#: alors qu'un en-tête absent est un fait qui ne se discute pas. Un contrôle qui
#: crie à tort est un contrôle qu'on désarme.
#:
#: 🔴 LE STANDBY N'A RIEN À MESURER, ET CE N'EST PAS UNE PANNE (27/08/2026).
#: Ce contrôle interrogeait `http://localhost/` sur les DEUX nœuds. Or les
#: conteneurs ne tournent que sur l'actif — c'est l'invariant de l'infrastructure,
#: pas un incident. Le standby ne répondait donc jamais, rendait INCONNU toutes
#: les quinze minutes, et un digest partait chaque jour : « En-têtes de sécurité
#: non mesurables ».
#:
#: ⚠️ Un contrôle dont le vert est INATTEIGNABLE finit par se contourner
#: (`standards/04` §25). Celui-ci l'était sur la moitié du parc, par
#: construction. Le rôle est donc un ARGUMENT, et « standby » a son propre
#: verdict : `SANS_OBJET`, qui ne se signale pas.
#:
#: ⚠️ Sur l'ACTIF, en revanche, une absence de réponse reste INCONNU — et là
#: c'est un fait à regarder : le site ne répond plus en local.
# ── C23 bis. La CSP BLOQUANTE porte-t-elle les directives qu'on croit ? ──────
# Args : recus (sortie de `curl -sI`)  directives (séparées par des espaces)
# Échoit : OK · MANQUANT:<liste> · INCONNU
#
# 🔴 POURQUOI (01/09/2026, #536). C23 vérifie que l'en-tête `Content-Security-Policy`
# est PRÉSENT. Il l'était déjà quand la politique ne portait que quatre directives
# inoffensives, et il le resterait si l'une d'elles disparaissait du Caddyfile :
# « présent » ne dit rien de ce qu'il contient.
#
# ⚠️ On vérifie la PRÉSENCE d'une directive, jamais sa VALEUR. C'est ce qui a tué
# le contrôle précédent : `check-stack.sh` attendait `X-Frame-Options: SAMEORIGIN`
# là où le Caddyfile disait `DENY`, il échouait 144 fois par jour, on l'a retiré du
# cron — et plus rien n'a regardé les en-têtes pendant quinze jours. Une attente de
# valeur exacte se périme au premier ajustement légitime.
#
# ⚠️ `^Content-Security-Policy:` avec les deux-points, et c'est le cœur du motif :
# sans eux il attraperait aussi `Content-Security-Policy-Report-Only`, où toutes
# les directives figurent — le contrôle serait vert quoi qu'il arrive au mode
# bloquant, c'est-à-dire exactement l'inverse de ce qu'on lui demande.
verdict_csp_directives() {
  local recus="$1" directives="$2" role="${3:-actif}" ligne manquantes="" d
  #  🔴 LE RÔLE, et il a manqué à la première écriture (constaté en production le
  #  01/09/2026, une heure après la mise en service). Le standby ne sert rien : ce
  #  contrôle y rendait WARN toutes les quinze minutes, sur la moitié du parc, et
  #  le digest quotidien l'emportait.
  #
  #  ⚠️ C'est EXACTEMENT le défaut que le commentaire de C23, juste à côté, décrit
  #  et corrige — « un contrôle dont le vert est inatteignable finit par se
  #  contourner » (`standards/04` §25). Écrire un contrôle voisin sans relire ce
  #  que son voisin a appris, c'est refaire son défaut.
  [ "$role" = "standby" ] && { echo SANS_OBJET; return; }
  [ -z "$recus" ] && { echo INCONNU; return; }
  ligne=$(printf '%s' "$recus" | grep -i "^Content-Security-Policy:" | head -1)
  [ -z "$ligne" ] && { echo INCONNU; return; }
  for d in $directives; do
    grep -q "$d" <<<"$ligne" || manquantes="${manquantes}${manquantes:+,}${d}"
  done
  [ -z "$manquantes" ] && echo OK || echo "MANQUANT:$manquantes"
}

# ── C25. Un script TIERS est-il servi dans la page publique ? ────────────────
#
# 🔴 Pourquoi (#701, 02/09/2026). Le relevé CSP a trouvé
# `https://static.cloudflareinsights.com/beacon.min.js` chargé sur chaque page.
# **Aucun `<script>` du dépôt ne le référence** : il est injecté par Cloudflare,
# à l'arête, APRÈS notre origine. Le dépôt ne peut donc rien en dire, et aucun
# contrôle de code ne pouvait le voir — seule une mesure de ce qu'un NAVIGATEUR
# reçoit le montre.
#
# Décision de l'utilisateur : le couper (Cloudflare → Web Analytics). Ce contrôle
# est ce qui rend la décision durable — sinon, réactiver l'option d'un clic
# remettrait un tiers sur le chemin de chaque résident sans que rien ne le dise.
#
# ⚠️ Il mesure la page PUBLIQUE, depuis le nœud, avec un en-tête `Accept: text/html`
# — Cloudflare n'injecte que dans du HTML rendu à un navigateur. Mesurer
# `localhost` ne verrait jamais rien : l'injection a lieu en aval de l'origine.
# C'est `standards/04` §14 : observer la chose, pas son enregistrement.
#
# ⚠️ Le motif porte sur des HÔTES, pas sur « toute URL absolue » : le site en sert
# légitimement (les polices Google, déclarées dans la CSP). Un contrôle qui crie
# sur du légitime finit désarmé.
verdict_script_tiers() {
  local html="$1" hotes="$2" role="${3:-actif}" trouves="" h
  #  Le standby ne sert rien : rien à observer chez lui.
  [ "$role" = "standby" ] && { echo SANS_OBJET; return; }
  #  🔴 CAS ZÉRO. Une page vide n'est pas une page sans tiers : c'est une mesure
  #  qui n'a pas eu lieu. Rendre OK ici, c'est le faux vert que `standards/04` §1
  #  interdit — et celui que ce dépôt a déjà produit quatre fois.
  [ -z "$html" ] && { echo INCONNU; return; }
  for h in $hotes; do
    grep -qF "$h" <<<"$html" && trouves="${trouves}${trouves:+,}${h}"
  done
  [ -z "$trouves" ] && echo OK || echo "TIERS:$trouves"
}

verdict_entetes_securite() {
  local recus="$1" attendus="$2" role="${3:-actif}" manquants="" nom
  #  Le standby ne sert rien : il n'y a pas d'en-tête à constater chez lui.
  [ "$role" = "standby" ] && { echo SANS_OBJET; return; }
  #  Aucune réponse sur l'actif : on n'a rien constaté. INCONNU, jamais OK.
  [ -z "$recus" ] && { echo INCONNU; return; }
  case "$recus" in
    *HTTP*) : ;;
    *) echo INCONNU; return ;;
  esac
  for nom in $attendus; do
    #  Les en-têtes HTTP sont insensibles à la casse : `curl` rend ce que le
    #  serveur envoie, et Caddy peut changer de casse d'une version à l'autre.
    grep -qi "^${nom}:" <<<"$recus" || manquants="${manquants}${manquants:+,}${nom}"
  done
  [ -z "$manquants" ] && echo OK || echo "MANQUANT:$manquants"
}
