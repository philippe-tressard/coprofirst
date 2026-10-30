#!/bin/bash
# =============================================================================
#  lib-verdicts-sudo.sh — Décisions PURES de C20 et C21 (permissions élevées)
#
#  Module SOURCÉ, jamais exécuté : pas de bit x (le job CI « Bits d'exécution
#  versionnés » attend 100644 sur les `lib-*.sh`).
#
#  POURQUOI CE FICHIER PLUTÔT QUE `lib-verdicts.sh`. Y ajouter C20 et C21 le
#  faisait passer de 424 à 524 lignes, au-dessus du plafond de modularité de 500
#  — exigence de rang 1, sans exception. C'est exactement ce qui avait donné
#  naissance à `lib-collecte.sh` le 11/08/2026, et la frontière est la même : la
#  DÉCISION d'un côté, testable sans les deux RPi ; la collecte de l'autre.
#
#  Le self-test vit ici, avec le code qu'il éprouve — `verdicts_selftest`
#  l'appelle. `bash check-reliability.sh --selftest` reste la seule commande, et
#  le job CI `test-scripts` ne change pas.
# =============================================================================

# ── C20/C21. Permissions élevées : parité entre nœuds, cible réinscriptible ───
# Même famille que C18, et née du même défaut : une divergence entre les deux
# nœuds que personne ne pouvait voir, parce que chacun a l'air normal vu de
# lui-même. C18 l'a établi pour les crontabs ; #302 l'a retrouvé pour les règles
# `sudo`, posées à la main nœud par nœud — donc divergentes par construction.
#
# ⚠️ POURQUOI ON NE COMPARE QUE DES MÉTADONNÉES, jamais le contenu des règles.
# Le snippet de collecte tourne en root en local (cron root) mais en `ptressard`
# sur le peer (SSH). Y lire le contenu supposerait un `NOPASSWD` sur `cat` — donc
# la lecture de n'importe quel fichier en root, `/etc/shadow` compris. C'est très
# exactement la faille que ce contrôle existe pour surveiller : l'ouvrir pour
# pouvoir la surveiller serait absurde. Le raisonnement est déjà écrit dans
# `export-hors-site.sh`, et il avait alors conduit à retirer une règle plutôt
# qu'à en ajouter une.
#
# Le répertoire, lui, est traversable par tous sur les deux nœuds : nom, taille
# et mode de chaque fichier se lisent SANS le moindre privilège. C'est suffisant
# pour voir un fichier présent d'un seul côté, un mode qui s'écarte du 0440 de
# règle, ou un contenu qui a changé de taille. La borne est assumée : deux
# fichiers de même nom, même taille et même mode dont le contenu diffère
# passeraient inaperçus — ce contrôle attrape la divergence de POSE, qui est
# celle qu'on a vécue, pas une édition adroite.
sudo_parite() {  # $1 = inventaire du nœud A, $2 = inventaire du nœud B
  #  Marqueur `ok:` posé par la collecte, et seulement si le répertoire a pu être
  #  listé. Sans lui, deux chaînes vides seraient ÉGALES et le contrôle dirait
  #  « identiques » alors qu'il n'a rien pu mesurer — le cas zéro de
  #  `standards/04-fiabilite-des-controles.md` §2, déjà vécu sur C18.
  case "$1" in ok:*) ;; *) echo INCONNU; return ;; esac
  case "$2" in ok:*) ;; *) echo INCONNU; return ;; esac
  [ "$1" = "$2" ] && echo OK || echo DIVERGENCE
}

# Ce qui diffère entre deux inventaires — pour que le message dise QUOI, et non
# seulement « ça diverge ». Rend les entrées présentes d'un seul côté.
sudo_ecarts() {  # $1 = inventaire A, $2 = inventaire B → "a:1,b:2" | ""
  local a b
  a=$(echo "${1#ok:}" | tr ',' '\n' | grep -v '^$' | sort)
  b=$(echo "${2#ok:}" | tr ',' '\n' | grep -v '^$' | sort)
  comm -3 <(echo "$a") <(echo "$b") 2>/dev/null | tr -d '\t' | sort -u | paste -sd, - | tr -d ' \n'
}

# C21 — une règle NOPASSWD ne vaut que ce que vaut la cible qu'elle désigne.
# La collecte (locale, root) rapporte les cibles dont le fichier OU le répertoire
# n'appartient pas à root, ou reste inscriptible par groupe/autres — plus le
# marqueur `ALL` si une règle n'est bornée à aucune commande.
#
# C'est le fait de #302 : une règle qui a l'air scopée à un script, alors que le
# compte appelant peut réécrire ce script. La permission porte sur un CHEMIN, pas
# sur le code qu'il contiendra au moment de l'exécution.
# Une règle NOPASSWD est-elle bornée à AUCUNE commande ? Rend "ALL" ou "".
#
# 🔴 CE CONTRÔLE NE POUVAIT PLUS JAMAIS ÊTRE VERT (trouvé le 27/08/2026, en
# traitant #302). La collecte testait :
#
#     case "$RULES" in *NOPASSWD:*ALL*) RISK="ALL" ;; esac
#
# `$RULES` est MULTILIGNE, et `case` compare la chaîne ENTIÈRE : « NOPASSWD: »
# vient d une ligne, « ALL » de la suivante — `ptressard ALL=(root) NOPASSWD:
# …` en contient un au début. Dès qu un nœud portait DEUX règles nominatives,
# le marqueur se posait tout seul. Il était juste tant que le blanc-seing
# existait vraiment ; il est devenu un faux positif à la seconde où on l a
# retiré, c est-à-dire au moment précis où le contrôle devait enfin servir.
#
# ⚠️ Un contrôle en WARN dont personne ne peut obtenir le vert finit par se lire
# comme un décor. Ici il aurait masqué le retour d un vrai `NOPASSWD: ALL`.
#
# ⚠️ L expression ci-dessous est RECOPIÉE dans le snippet de `lib-collecte.sh`,
# qui ne peut sourcer aucun module (il s exécute sur le peer par SSH). Les deux
# doivent rester identiques — même contrainte que le motif de C18, déjà notée
# là-bas. C est ce self-test qui éprouve la forme.
sudo_sans_borne() {  # $1 = lignes NOPASSWD → "ALL" | ""
  local _nopasswd; _nopasswd=$(echo "${1:-}" | sed -n 's/.*NOPASSWD:[[:space:]]*//p')
  grep -qE '^ALL([,[:space:]]|$)' <<<"$_nopasswd" && echo ALL || echo ""
}

verdict_sudo_risque() {  # $1 = champ collecté → OK | RISQUE | INCONNU
  #  Le peer ne rend rien (il n'est pas root) : INCONNU, jamais OK. Ce contrôle
  #  couvre quand même les deux nœuds, puisqu'il tourne sur chacun d'eux.
  case "$1" in ok:*) ;; *) echo INCONNU; return ;; esac
  [ -z "$(echo "${1#ok:}" | tr -d ' ')" ] && echo OK || echo RISQUE
}

# ── Self-test des décisions de C20 et C21 ────────────────────────────────────
# Appelé par `verdicts_selftest` (lib-verdicts.sh) : une seule commande pour
# l'utilisateur et pour la CI. `st_fail` appartient à l'appelant — ces tests
# l'incrémentent comme les autres, donc un échec ici fait échouer le tout.

# ── C24. La surface accordée EST-ELLE celle que le dépôt compose ? (PURE) ────
# Args : reelle  attendue    (deux listes « cmd|cmd|… », triées, séparateur |)
# Échoit : OK · EN_TROP:<liste> · MANQUANTES:<liste> · ECART:<en trop>/<manq> · INCONNU
#
# 🔴 POURQUOI (01/09/2026). Le 31/08, la règle `NOPASSWD: /usr/bin/rsync` — un
# rsync privilégié sans borne de chemin, donc une escalade root complète — a été
# retirée du dépôt (#582), avec un commentaire disant « c est la fin du chantier ».
# Elle est restée installée sur les DEUX machines : `durcir-sudoers.sh` n avait
# jamais été rejoué. Vingt-quatre heures, et vingt-trois contrôles au vert.
#
# ⚠️ C20 ne pouvait pas le voir : il compare les deux nœuds ENTRE EUX, et deux
# nœuds identiquement périmés lui semblent parfaits. C est exactement le trou que
# C22 comble pour les points d entrée — la même leçon, un objet plus loin.
#
# EN_TROP est le cas dangereux (une permission que le dépôt ne veut plus) ;
# MANQUANTES casse un geste (la bascule perdrait cloudflared). Les deux sont dits.
verdict_sudo_surface() {
  local reelle="${1:-}" attendue="${2:-}"
  #  Une surface vide n est pas « aucune permission » : c est une mesure qui n a
  #  pas eu lieu. Et une attendue vide veut dire que le dépôt n est pas lisible.
  { [ -z "$reelle" ] || [ -z "$attendue" ]; } && { echo "INCONNU"; return; }
  [ "$reelle" = "$attendue" ] && { echo "OK"; return; }

  local trop="" manq="" c
  local IFS='|'
  for c in $reelle;   do [ -n "$c" ] && case "|$attendue|" in *"|$c|"*) ;; *) trop="$trop$c, " ;; esac; done
  for c in $attendue; do [ -n "$c" ] && case "|$reelle|"   in *"|$c|"*) ;; *) manq="$manq$c, " ;; esac; done
  unset IFS
  trop="${trop%, }"; manq="${manq%, }"

  if [ -n "$trop" ] && [ -n "$manq" ]; then echo "ECART:$trop/$manq"
  elif [ -n "$trop" ]; then echo "EN_TROP:$trop"
  elif [ -n "$manq" ]; then echo "MANQUANTES:$manq"
  else
    #  Mêmes éléments, chaîne différente : un tri ou un espace diverge. Ce n est
    #  pas un vert — on ne compare plus la même chose que ce qu on croit.
    echo "INCONNU"
  fi
}

sudo_selftest() {
  echo "-- C20 : parité des permissions élevées entre les 2 nœuds --"
  sp() {  # $1 = libellé, $2 = attendu, $3 = inventaire A, $4 = inventaire B
    local got; got=$(sudo_parite "$3" "$4")
    [ "$got" = "$2" ] && echo "PASS  $1 → $got" \
      || { echo "FAIL  $1  attendu=$2 obtenu=$got"; st_fail=1; }
  }
  sp "inventaires identiques" OK \
     "ok:010_proxy:211:440,README:1068:440" "ok:010_proxy:211:440,README:1068:440"
  #  Le cas de #302 : un fichier posé sur un seul nœud.
  sp "un fichier d un seul côté" DIVERGENCE \
     "ok:010_proxy:211:440,bascule:56:644" "ok:010_proxy:211:440"
  #  Le mode s écarte du 0440 de règle — même fichier, même taille.
  sp "même fichier, mode différent" DIVERGENCE \
     "ok:ptressard:141:440" "ok:ptressard:141:644"
  #  LE CAS ZÉRO, celui qui a déjà fait mentir C18 et C14 : sans le marqueur
  #  `ok:`, deux répertoires illisibles rendent deux chaînes vides — ÉGALES.
  #  « Je n ai rien pu lire des deux côtés » n est pas « les deux sont pareils ».
  sp "aucun des deux n a pu être listé" INCONNU "" ""
  sp "un seul des deux a pu être listé" INCONNU "ok:README:1068:440" ""
  sp "inventaire vide mais MESURÉ (aucun fichier)" OK "ok:" "ok:"
  echo "-- C21 : une règle sans borne, et rien d autre --"
  b() {  # $1 = libellé, $2 = attendu, $3 = lignes
    local got; got=$(sudo_sans_borne "$3")
    if [ "$got" = "$2" ]; then echo "PASS  $1 → '$got'"
    else echo "FAIL  $1  attendu='$2' obtenu='$got'"; SUDO_ST=1; fi
  }
  b "un vrai blanc-seing"       "ALL" "ptressard ALL=(ALL) NOPASSWD: ALL"
  b "blanc-seing en tête de liste" "ALL" "ptressard ALL=(ALL) NOPASSWD: ALL, /usr/bin/ls"
  #  🔴 LE FAUX POSITIF QUI A COÛTÉ SON VERT À CE CONTRÔLE : deux règles
  #  nominatives, aucune sans borne — et l ancien `case` répondait ALL.
  b "deux règles bornées"       ""    "ptressard ALL=(root) NOPASSWD: /usr/bin/crontab -l
ptressard ALL=(root) NOPASSWD: /usr/bin/rsync"
  b "une seule règle bornée"    ""    "ptressard ALL=(root) NOPASSWD: /usr/bin/rsync"
  b "aucune règle"              ""    ""

  echo "-- C20 : ce qui diverge --"
  E=$(sudo_ecarts "ok:a:1:440,b:2:440" "ok:a:1:440")
  [ "$E" = "b:2:440" ] && echo "PASS  écart nommé → '$E'" \
    || { echo "FAIL  écart attendu='b:2:440' obtenu='$E'"; st_fail=1; }
  E=$(sudo_ecarts "ok:a:1:440" "ok:a:1:440")
  [ -z "$E" ] && echo "PASS  aucun écart → chaîne vide" \
    || { echo "FAIL  écart attendu='' obtenu='$E'"; st_fail=1; }
  echo "-- C21 : une permission élevée vaut sa cible --"
  sr() {  # $1 = libellé, $2 = attendu, $3 = champ collecté
    local got; got=$(verdict_sudo_risque "$3")
    [ "$got" = "$2" ] && echo "PASS  $1 → $got" \
      || { echo "FAIL  $1  attendu=$2 obtenu=$got"; st_fail=1; }
  }
  sr "aucune cible réinscriptible"        OK      "ok:"
  sr "mesuré, rien à signaler (espaces)"  OK      "ok:   "
  #  Le fait de #302 : la cible est un script que le compte appelant réécrit.
  sr "cible réinscriptible par l appelant" RISQUE "ok: bascule.sh"
  #  Une règle bornée à aucune commande — le cas le plus grave, et le plus discret.
  sr "règle sans borne de commande"       RISQUE "ok: ALL"
  sr "plusieurs cibles"                   RISQUE "ok: ALL bascule.sh"
  #  Le peer n est pas root : il ne peut pas mesurer. INCONNU, jamais OK — sinon
  #  le nœud le moins surveillé serait celui qui rassure le plus.
  sr "non mesurable (peer, non-root)"     INCONNU ""
  sr "sortie sans marqueur de mesure"     INCONNU "bascule.sh"

  echo "-- C24 : la surface installée est celle du dépôt --"
  ss() {  # $1 = libellé, $2 = attendu, $3 = réelle, $4 = attendue-par-le-dépôt
    local got; got=$(verdict_sudo_surface "$3" "$4")
    [ "$got" = "$2" ] && echo "PASS  $1 → $got"       || { echo "FAIL  $1  attendu=$2 obtenu=$got"; st_fail=1; }
  }
  _ATT="ATTENDUE"
  ss "conforme au dépôt"                  OK "$_ATT" "$_ATT"
  #  🔴 Le fait du 01/09/2026 : rsync retiré du dépôt, resté sur les machines.
  ss "une permission EN TROP (rsync)"     "EN_TROP:/usr/bin/rsync"      "/usr/bin/crontab -l|/usr/bin/rsync|" "/usr/bin/crontab -l|"
  #  L autre sens : la bascule perdrait cloudflared, et rien ne le dirait avant
  #  02:00 du matin.
  ss "une permission MANQUANTE"           "MANQUANTES:/usr/bin/systemctl start cloudflared"      "/usr/bin/crontab -l|" "/usr/bin/crontab -l|/usr/bin/systemctl start cloudflared|"
  ss "les deux à la fois"                 "ECART:/usr/bin/rsync//usr/bin/crontab -l"      "/usr/bin/rsync|" "/usr/bin/crontab -l|"
  #  Le cas zéro, deux fois : une mesure absente n est pas « aucune permission »,
  #  et un dépôt illisible n est pas « rien d attendu ». INCONNU, jamais OK.
  ss "surface non mesurée"                INCONNU "" "$_ATT"
  ss "dépôt non composable"               INCONNU "$_ATT" ""
  ss "les deux vides"                     INCONNU "" ""
  #  Mêmes éléments, ordre différent : le tri a divergé quelque part, donc on ne
  #  compare plus ce qu on croit comparer. Surtout pas un vert.
  ss "mêmes éléments, ordre différent"    INCONNU "/usr/bin/b|/usr/bin/a|" "/usr/bin/a|/usr/bin/b|"
}
