#!/bin/bash
# =============================================================================
#  lib-sudoers.sh — Composition et vérification de la règle sudo des nœuds
#
#  Module SOURCÉ, jamais exécuté : pas de bit x (le job CI « Bits d'exécution
#  versionnés » attend 100644 sur les `lib-*.sh`).
#
#  POURQUOI CE MODULE. Les règles `sudo` des deux nœuds ont été posées à la main,
#  nœud par nœud — donc elles ont divergé, et personne ne pouvait le voir : chaque
#  nœud a l'air normal vu de lui-même (#302). Cette divergence a un coût mesuré :
#  la copie hors site échouait UNE NUIT SUR DEUX (09/08/2026), la permission dont
#  elle dépendait n'existant que sur un nœud, et le rôle alternant chaque nuit.
#
#  La règle vit désormais ICI, versionnée, et `durcir-sudoers.sh` l'installe à
#  l'identique partout. C'est la seule façon de rendre vraie la phrase « les deux
#  nœuds sont configurés pareil » — la même leçon que C18 pour les crontabs.
#
#  ⚠️ CE QUE CE MODULE NE FAIT PAS, et qu'il ne faut pas croire qu'il fait.
#  Il ne ferme PAS l'escalade de privilèges. `ptressard` appartient au groupe
#  `docker` sur les deux nœuds, ce qui est déjà un équivalent root
#  (`docker run -v /:/host`), antérieur et nécessaire au modèle de déploiement —
#  c'est écrit noir sur blanc dans `export-hors-site.sh`. Ce module réduit la
#  surface et rétablit la symétrie ; annoncer autre chose serait un faux vert.
# =============================================================================

#: Fichier unique qui portera la règle, sur les deux nœuds.
SUDOERS_CIBLE=/etc/sudoers.d/5hostachy

#: Fichiers hérités à retirer APRÈS installation de la règle unique.
#:   010_pi-nopasswd  — livré par Raspberry Pi OS, `NOPASSWD: ALL` (rpi1)
#:   bascule          — la règle qui a donné son nom à #302 (rpi2), et qui ne
#:                      correspondait même pas à l'usage documenté : `sudo bash
#:                      <script>` exécute /usr/bin/bash, pas le script.
#:   ptressard, ptressard-extra — posés à la main, contenu divergent (rpi2)
SUDOERS_HERITES="010_pi-nopasswd bascule ptressard ptressard-extra"

# ── La règle, composée à partir du besoin RÉEL des scripts ───────────────────
# Chaque ligne est justifiée par un appelant versionné. Une permission sans
# appelant se retire ; une permission dont l'appelant disparaît doit être
# retirée avec lui (`standards/02` §5).
#
# `systemctl` est borné à l'unité `cloudflared` : sans cette borne, la règle
# autoriserait `systemctl start` de n'importe quelle unité, donc l'exécution de
# n'importe quel service — une escalade complète sous couvert de « redémarrer le
# tunnel ».
#
# ✅ `rsync` EST PARTI le 31/08/2026 (#582), et c'est la fin du chantier.
# `sudo rsync` sans borne de chemin EST une escalade root complète — rsync écrit
# où il veut, `/etc/sudoers.d/` et `/root/.ssh/` compris. La règle avait l'air
# bornée à un outil ; elle ne l'était pas.
#
# Elle servait à `bascule.sh`, qui l'appelait trois fois pour installer uploads,
# WhatsApp auth et la base dans les volumes du peer. Les trois passent par un
# conteneur jetable (`lib-volumes.sh`), qui n'ouvre aucun privilège nouveau : le
# compte est déjà dans le groupe `docker`.
#
# 🔴 LE RETRAIT A ATTENDU UNE PREUVE D'EXÉCUTION, PAS UNE PREUVE DE CODE.
# « Zéro appel dans `bascule.sh` » et « zéro appel exécuté » sont deux faits
# différents : la phase 4 ne tourne qu'à 02:00. Retirer la règle avant aurait
# supprimé le chemin de repli de la seule phase non éprouvée — et la plus
# délicate des trois, celle qui porte le `--delete` sur la base. La preuve
# attendue, lue dans le journal de la bascule du 31/08/2026 à 02:02:26 :
#
#     → DB installée dans le volume peer (conteneur jetable, sans sudo).
#     ===== Bascule terminée : rpi1 est maintenant actif =====
#
# ⚠️ Retirer la règle du DÉPÔT ne la retire pas des NŒUDS. Elle y reste jusqu'à
# `bash scripts/installation/durcir-sudoers.sh` ; d'ici là `--etat` la signale
# comme divergente, ce qui est exactement ce qu'on veut lire.
# ⚠️ Le heredoc ci-dessous n'est PAS quoté — il doit substituer $u. Donc aucun
# accent grave dans son corps : il y ouvrirait une substitution de commande.
# Vécu le 12/08/2026, « is-active: command not found » à chaque appel — et le
# fichier composé s'en trouvait tronqué sans que rien ne le signale.
sudoers_regle() {  # $1 = compte visé (défaut : ptressard)
  local u="${1:-ptressard}"
  cat <<REGLE
# 5Hostachy — permissions élevées des nœuds. NE PAS ÉDITER À LA MAIN.
# Source unique : lib-sudoers.sh, installé par durcir-sudoers.sh.
# Toute modification faite ici sera écrasée, et divergera d'un nœud à l'autre —
# c'est précisément ce que ce fichier existe pour empêcher (#302).

# Tunnel Cloudflare — bascule.sh, health-watch.sh, boot-role-guard.sh.
# Borné à l'unité : sans cela, toute unité systemd serait démarrable en root.
$u ALL=(root) NOPASSWD: /usr/bin/systemctl start cloudflared
$u ALL=(root) NOPASSWD: /usr/bin/systemctl stop cloudflared
$u ALL=(root) NOPASSWD: /usr/bin/systemctl restart cloudflared
$u ALL=(root) NOPASSWD: /usr/bin/systemctl enable cloudflared
$u ALL=(root) NOPASSWD: /usr/bin/systemctl disable cloudflared
#  Pas de is-active ni is-enabled : ils sont appelés SANS sudo (bascule.sh
#  l. 92, boot-role-guard.sh, lib-collecte.sh) — l'état d'une unité se lit sans
#  privilège. Les autoriser serait une permission sans appelant.

# Lecture du crontab root — lib-collecte.sh (C18 compare les deux nœuds).
# En LECTURE seule : « crontab -l » et rien d'autre, sinon on autoriserait
# « crontab <fichier> », donc l'exécution de n'importe quoi en root.
$u ALL=(root) NOPASSWD: /usr/bin/crontab -l

# Ici vivait la regle NOPASSWD sur /usr/bin/rsync, la surface la plus large
# de ce fichier. Retirée le 31/08/2026, après qu'une bascule ait exercé les trois
# phases converties. Ne pas la remettre pour « dépanner » : un rsync privilégié
# sans borne de chemin rend le compte équivalent à root.
REGLE
}

# ── Décisions PURES, éprouvées par --selftest ────────────────────────────────

# Une règle installée est-elle conforme à la règle attendue ?
# Rend OK · DIFFERENT · ABSENT · INCONNU — jamais un vert par défaut.
sudoers_conformite() {  # $1 = contenu lu sur le nœud, $2 = contenu attendu
  [ -z "${2:-}" ] && { echo INCONNU; return; }      # rien à comparer : on ne sait pas
  case "${1:-}" in
    "__ABSENT__") echo ABSENT; return ;;
    "__ILLISIBLE__"|"") echo INCONNU; return ;;
  esac
  [ "$1" = "$2" ] && echo OK || echo DIFFERENT
}

# Peut-on retirer les fichiers hérités ? SEULEMENT si la règle unique est en
# place et conforme. L'ordre n'est pas un détail de style : retirer d'abord
# `010_pi-nopasswd` sur un nœud dont la nouvelle règle n'est pas installée rend
# le compte incapable de piloter cloudflared — donc la bascule de 02:00 échoue,
# et le tunnel peut rester éteint des deux côtés (incident du 30/07).
sudoers_peut_nettoyer() {  # $1 = verdict de conformité
  [ "${1:-}" = "OK" ] && echo oui || echo non
}

# Quels nœuds cette invocation vise-t-elle ?
#
# 🔴 UN NŒUD À LA FOIS, et ce n'est pas une préférence de style. Poser la même
# règle sudoers sur les DEUX moitiés d'une paire HA dans la même seconde, c'est
# renoncer à ce que la paire apporte : si la règle est mauvaise, les deux nœuds
# le deviennent ensemble. La discipline est déjà celle des points d'entrée
# (`verifier-points-entree.sh` : « installer reste un geste explicite, un nœud à
# la fois ») ; elle manquait ici.
#
# Un filtre qui ne correspond à AUCUN nœud connu rend une liste vide ET un code
# d'erreur : sans cela, une IP mal tapée ferait boucler sur rien et le script
# annoncerait un succès sans avoir rien touché (`standards/04` §2, cas zéro).
sudoers_noeuds_cibles() {  # $1 = filtre (vide = tous), $2 = liste connue
  local filtre="${1:-}" connus="${2:-}" n
  [ -z "$connus" ] && return 1
  if [ -z "$filtre" ]; then printf '%s' "$connus"; return 0; fi
  for n in $connus; do
    [ "$n" = "$filtre" ] && { printf '%s' "$n"; return 0; }
  done
  return 1
}

# Cette commande est-elle exécutable SANS MOT DE PASSE ?
#
# 🔴 `sudo -n -l <cmd>` ne répond PAS à cette question, et je l'ai cru
# (27/08/2026). Il répond « ce compte peut-il lancer cette commande », mot de
# passe compris — donc il rend 0 pour `docker` sur un nœud durci, où `docker`
# n'est plus NOPASSWD mais reste couvert par la ligne `(ALL : ALL) ALL`. La
# sonde annonçait « AUTORISÉE » sur exactement ce que le durcissement venait de
# fermer : un faux vert sur la mesure qui compte.
#
# La seule source fiable est la LISTE des lignes NOPASSWD que `sudo -n -l`
# imprime. On la lit, on n'interroge pas commande par commande.
sudoers_est_nopasswd() {  # $1 = sortie de `sudo -n -l`, $2 = commande cherchée
  [ -z "${1:-}" ] && return 1          # rien lu : on ne conclut pas
  grep -q "NOPASSWD:.*${2}" <<<"$1"
}

# La surface NOPASSWD réellement en place, une commande par ligne — c'est ce
# qu'on compare au versionné, et ce que C20 doit remonter.
sudoers_surface_nopasswd() {  # $1 = sortie de `sudo -n -l`
  printf '%s
' "${1:-}" | sed -n 's/.*NOPASSWD: *//p' | sed 's/[[:space:]]*$//' | sort
}

sudoers_selftest() {
  local st=0 got
  c() {  # $1 = libellé, $2 = attendu, $3 = lu, $4 = attendu(contenu)
    got=$(sudoers_conformite "$3" "$4")
    if [ "$got" = "$2" ]; then echo "PASS  $1 → $got"
    else echo "FAIL  $1  attendu=$2 obtenu=$got"; st=1; fi
  }
  echo "== self-test lib-sudoers =="
  c "règle conforme"                 OK        "abc" "abc"
  c "règle divergente"               DIFFERENT "abc" "abd"
  c "fichier absent du nœud"         ABSENT    "__ABSENT__" "abc"
  #  LE CAS ZÉRO : une lecture qui échoue rend une chaîne vide. Sans ce
  #  traitement, deux vides seraient ÉGAUX et le contrôle dirait « conforme »
  #  sur un nœud qu'il n'a pas pu lire (`standards/04` §2).
  c "lecture impossible"             INCONNU   "__ILLISIBLE__" "abc"
  c "lecture vide"                   INCONNU   "" "abc"
  c "règle attendue non composable"  INCONNU   "abc" ""

  n() {  # $1 = libellé, $2 = attendu, $3 = verdict
    got=$(sudoers_peut_nettoyer "$3")
    if [ "$got" = "$2" ]; then echo "PASS  $1 → $got"
    else echo "FAIL  $1  attendu=$2 obtenu=$got"; st=1; fi
  }
  #  On ne retire les anciens fichiers QUE sur une règle installée et conforme.
  n "nettoyage après règle conforme" oui "OK"
  n "règle divergente : on ne touche à rien" non "DIFFERENT"
  n "règle absente : on ne touche à rien"    non "ABSENT"
  n "état inconnu : on ne touche à rien"     non "INCONNU"

  echo "-- la règle composée est-elle valide et complète ? --"
  #  🔴 D'ABORD : la règle a-t-elle été composée SANS incident ?
  #
  #  Le heredoc de `sudoers_regle` n'est pas quoté — il doit substituer $u — donc
  #  un accent grave dans son corps ouvre une substitution de commande. L'avertis-
  #  sement est écrit au-dessus de la fonction depuis le 12/08/2026, où il avait
  #  produit « is-active: command not found » et un fichier TRONQUÉ sans que rien
  #  ne le signale.
  #
  #  ⚠️ Il s'est reproduit le 31/08/2026, dans un commentaire ajouté par ce lot-ci.
  #  Les onze contrôles qui suivent étaient tous VERTS : ils vérifient ce que la
  #  règle CONTIENT, et la substitution n'avait mangé qu'un commentaire. Elle
  #  aurait tout aussi bien pu manger une ligne de permission.
  #
  #  Une consigne écrite trois lignes au-dessus de la fonction n'a pas suffi —
  #  deux fois. On mesure donc les deux faces : le symptôme (rien sur la sortie
  #  d'erreur) et la cause (aucun accent grave dans le corps du heredoc).
  local err_regle; err_regle=$(sudoers_regle ptressard 2>&1 >/dev/null)
  if [ -n "$err_regle" ]; then
    echo "FAIL  la composition a ecrit sur la sortie d erreur : $err_regle"
    echo "      → substitution de commande dans le heredoc (accent grave ?)"
    st=1
  else
    echo "PASS  la regle se compose sans rien ecrire sur la sortie d erreur"
  fi
  #  ⚠️ Le motif de début est ANCRÉ sur la ligne entière. Sans cela, la ligne de
  #  ce sed — qui contient elle aussi « cat <<REGLE » — ouvrait une SECONDE plage
  #  qui balayait le self-test, lequel parle des accents graves en en écrivant.
  #  La sonde se lisait elle-même et échouait sur son propre commentaire.
  local corps; corps=$(sed -n '/^  cat <<REGLE$/,/^REGLE$/p' "${BASH_SOURCE[0]}")
  if [ -z "$corps" ]; then
    #  Cas zéro : sans corps lu, l'absence d'accent grave ne prouve rien.
    echo "FAIL  corps du heredoc introuvable — controle inoperant, pas OK"; st=1
  elif grep -q '`' <<<"$corps"; then
    echo "FAIL  accent grave dans le heredoc : il ouvre une substitution"; st=1
  else
    echo "PASS  aucun accent grave dans le corps du heredoc"
  fi

  local regle; regle=$(sudoers_regle ptressard)
  for besoin in "systemctl start cloudflared" "systemctl stop cloudflared" \
                "crontab -l"; do
    if grep -q -- "$besoin" <<<"$regle"; then
      echo "PASS  besoin couvert : $besoin"
    else
      echo "FAIL  besoin NON couvert : $besoin"; st=1
    fi
  done
  #  🔴 Et le contrôle INVERSE : la règle composée ne doit PLUS accorder rsync.
  #  Sans lui, un copier-coller le rétablirait et tous les autres contrôles
  #  resteraient verts — ils vérifient ce qui est COUVERT, jamais ce qui ne doit
  #  plus l'être. Un contrôle qui ne cherche que des présences ne voit pas une
  #  régression par ajout (`standards/04`).
  #  ⚠️ On cherche une ligne de PERMISSION, pas une mention : le commentaire qui
  #  explique le retrait nomme forcément la commande retirée. Un motif trop large
  #  échouait dessus — et aurait fait retirer l'explication pour obtenir du vert,
  #  c'est-à-dire supprimer la trace de la décision pour satisfaire le contrôle.
  if grep -qE '^[^#]*NOPASSWD:.*rsync' <<<"$regle"; then
    echo "FAIL  la regle accorde encore rsync (escalade root complete, #582)"; st=1
  else
    echo "PASS  la regle n accorde plus rsync"
  fi
  #  Une règle sans borne d'unité autoriserait toute unité systemd : c'est le
  #  défaut que ce fichier existe pour ne pas reproduire.
  if grep -qE '^[a-z]+ ALL=\(root\) NOPASSWD: /usr/bin/systemctl (start|stop|restart|enable|disable)$' <<<"$regle"; then
    echo "FAIL  une règle systemctl n est bornée à AUCUNE unité"; st=1
  else
    echo "PASS  toute règle systemctl est bornée à une unité"
  fi
  #  `NOPASSWD: ALL` ne doit jamais réapparaître dans la règle composée.
  if grep -qE 'NOPASSWD:[[:space:]]*ALL' <<<"$regle"; then
    echo "FAIL  la règle contient NOPASSWD: ALL"; st=1
  else
    echo "PASS  aucune règle sans borne de commande"
  fi

  echo "-- NOPASSWD : « peut » n'est pas « peut sans mot de passe » --"
  #  Sortie réelle d'un nœud durci : la ligne `(ALL : ALL) ALL` couvre TOUT avec
  #  mot de passe, et c'est elle qui faisait dire « AUTORISÉE » à l'ancienne sonde.
  #
  #  ⚠️ Elle porte encore `/usr/bin/rsync`, et c'est VOULU : c'est l'état d'un
  #  nœud qui n'a pas été repassé depuis le 31/08/2026. Ce témoin éprouve le
  #  LECTEUR, pas la politique — et il éprouve précisément le cas que
  #  `durcir-sudoers.sh --etat` doit savoir signaler. Le remplacer par une sortie
  #  déjà conforme ferait disparaître le seul cas où l'on vérifie que la dérive
  #  se voit.
  local sortie_durcie="User ptressard may run the following commands on n1:
    (ALL : ALL) ALL
    (root) NOPASSWD: /usr/bin/systemctl start cloudflared
    (root) NOPASSWD: /usr/bin/crontab -l
    (root) NOPASSWD: /usr/bin/rsync"
  p() {  # $1 = libellé, $2 = attendu(oui/non), $3 = commande
    if sudoers_est_nopasswd "$sortie_durcie" "$3"; then got=oui; else got=non; fi
    if [ "$got" = "$2" ]; then echo "PASS  $1 → $got"
    else echo "FAIL  $1  attendu=$2 obtenu=$got"; st=1; fi
  }
  p "rsync est sans mot de passe"          oui "/usr/bin/rsync"
  p "crontab -l est sans mot de passe"     oui "/usr/bin/crontab -l"
  #  LE CAS QUI COMPTE : couvert par `(ALL : ALL) ALL`, donc exécutable — mais
  #  AVEC mot de passe. L'ancienne sonde répondait « autorisée » ici.
  p "docker n est PAS sans mot de passe"   non "/usr/bin/docker"
  p "rm n est PAS sans mot de passe"       non "/usr/bin/rm"
  #  Et le cas zéro : rien lu ne vaut pas « rien d autorisé ».
  if sudoers_est_nopasswd "" "/usr/bin/rsync"; then
    echo "FAIL  sortie vide traitée comme une permission"; st=1
  else
    echo "PASS  sortie vide : aucune conclusion"
  fi
  got=$(sudoers_surface_nopasswd "$sortie_durcie" | tr '
' '|')
  if [ "$got" = "/usr/bin/crontab -l|/usr/bin/rsync|/usr/bin/systemctl start cloudflared|" ]; then
    echo "PASS  surface NOPASSWD extraite → 3 entrées"
  else
    echo "FAIL  surface NOPASSWD  obtenu=$got"; st=1
  fi

  echo "-- le filtre de nœud --"
  f() {  # $1 = libellé, $2 = attendu, $3 = filtre, $4 = connus
    if got=$(sudoers_noeuds_cibles "$3" "$4"); then :; else got="__ERREUR__"; fi
    if [ "$got" = "$2" ]; then echo "PASS  $1 → $got"
    else echo "FAIL  $1  attendu=$2 obtenu=$got"; st=1; fi
  }
  f "sans filtre : les deux"        "1.1.1.1 2.2.2.2" ""        "1.1.1.1 2.2.2.2"
  f "un nœud nomme"                 "2.2.2.2"         "2.2.2.2" "1.1.1.1 2.2.2.2"
  #  LE CAS ZÉRO du filtre : une IP inconnue ne doit pas rendre une liste vide
  #  avec un code 0 — le script boucherait sur rien et conclurait au succès.
  f "IP inconnue : ERREUR, pas vide" "__ERREUR__"     "9.9.9.9" "1.1.1.1 2.2.2.2"
  f "aucun nœud connu : ERREUR"      "__ERREUR__"     ""        ""

  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  return $st
}
