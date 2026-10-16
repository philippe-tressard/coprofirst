#!/bin/bash
# =============================================================================
#  lib-export-hors-site.sh — les DÉCISIONS de la copie hors site (module à sourcer)
#
#  POURQUOI ce module existe (05/09/2026, #775) :
#    `export-hors-site.sh` a reçu la passe de rattrapage sur le second nœud et le
#    relevé de continuité de la série — de la fonctionnalité, pas du gras. Il est
#    passé de 498 à 588 lignes, et le garde-fou de modularité (rang 1) a refusé
#    qu'il grossisse.
#
#    ⚠️ C'est un découpage de MODULARITÉ, et il faut l'appeler par son nom : il
#    ne supprime aucune duplication. La factorisation du même jour est ailleurs —
#    `transferer_archive`, écrite une fois pour les deux passes, et restée dans
#    le script parce qu'elle fait du réseau.
#
#  Ce module ne contient QUE des fonctions pures : ni SSH, ni docker, ni
#  écriture, ni lecture de fichier. C'est ce qui les rend éprouvables par
#  `--selftest` sans les deux RPi — le motif inauguré par `boot-role-guard.sh`
#  et étendu depuis à toute décision d'infra.
#
#  Usage :   source "$(dirname "$0")/../lib/lib-export-hors-site.sh"
#  Test  :   bash scripts/poste/export-hors-site.sh --selftest
#
#  ⚠️ CE MODULE N'A PAS DE `--selftest` À LUI, et ce n'est pas un oubli : ses
#  fonctions sont éprouvées par celui du script appelant, qui les source. Lui en
#  poser un vide — ou l'inscrire tel quel dans la CI — rendrait 0 sans rien
#  mesurer : un faux vert, exactement ce que `standards/04` §1 interdit. Le jour
#  où ce module servira à un second appelant, il prendra son propre bloc.
# =============================================================================

# ── Quel nœud sert réellement ? ──────────────────────────────────────────────
# Entrées : les codes HTTP obtenus sur http://<ip>/api/health de chaque nœud.
# On ne lit PAS `.active` : ce drapeau a déjà divergé en production (26/07/2026,
# neuf FAIL consécutifs), et il peut désigner un nœud qui ne sert rien. La
# sauvegarde de 03:00 est produite par le conteneur API — donc par le nœud qui
# RÉPOND, par définition. On interroge le fait, pas sa déclaration.
decider_source() { # $1=code_rpi1 $2=code_rpi2 → rpi1|rpi2|split-brain|aucun
  local c1="${1:-000}" c2="${2:-000}"
  if [ "$c1" = "200" ] && [ "$c2" = "200" ]; then echo "split-brain"; return 0; fi
  if [ "$c1" = "200" ]; then echo "rpi1"; return 0; fi
  if [ "$c2" = "200" ]; then echo "rpi2"; return 0; fi
  echo "aucun"
}

# ── L'archive contient-elle bien l'export de la base ? ───────────────────────
# Prend le LISTING déjà produit, et ne fait aucune E/S — parce que la version
# « en ligne » de ce test était fausse de deux façons (04/08/2026) :
#   • `tar -tzf … | grep -qx <entrée>` : `grep -q` sort dès le premier match et
#     ferme le tube ; `tar` meurt alors en SIGPIPE, et `set -o pipefail` propage
#     cet échec. Le test rendait donc « absent » sur une archive qui contenait
#     l'entrée — un faux négatif silencieux sur le contrôle le plus important ;
#   • une comparaison par sous-chaîne ferait passer `uploads/<entrée>` pour
#     l'entrée. Le nom doit correspondre à la ligne ENTIÈRE.
# Une seule question pour toute entrée cherchée.
# `deploiement/standard/mise-a-jour.sh` en porte une COPIE DÉCLARÉE
# (l'archive d'une réplique n'emporte pas `scripts/lib`) : le même tube y était
# revenu le 10/10/2026 (#1820). `test_deploiement_standard.py` exige deux corps
# identiques.
listing_contient() { # $1=listing tar · $2=entrée exacte → oui|non
  case $'\n'"${1:-}"$'\n' in
    *$'\n'"${2:?entrée cherchée manquante}"$'\n'*) echo "oui" ;;
    *)                                              echo "non" ;;
  esac
}

# ── L'EXPORT vérifié de la base (DI-7b, #1781) ───────────────────────────────
# La base PostgreSQL n'a pas de fichier : `api/app/utils/backup.py` met dans
# l'archive son export vérifié (P2-7), sous ce nom — même valeur que
# `backup.NOM_EXPORT_BASE`, tenue par `test_sauvegarde_base_serveur.py`.
NOM_EXPORT_BASE="base-export.tar.gz"

# ── PURE : l'export compte-t-il les lignes que son manifeste annonce ? ───────
# Lit le RÉSUMÉ que `verifier_export_base` produit (« table lues annoncees » par
# ligne) ; ne fait aucune E/S. → ok | « écarts : … » | inconnue (rien lu)
verdict_export_base() { # $1 = résumé
  local resume=${1:-} ecarts="" t lu annonce n=0
  while read -r t lu annonce; do
    #  #1964 : Python sous Windows écrit en CRLF, et le `\r` restait collé à la
    #  dernière colonne — `1\r` n'égale jamais `1`. Toute copie hors site
    #  échouait depuis le poste.
    annonce=${annonce%$'\r'}
    [ -n "$t" ] || continue
    n=$((n + 1))
    [ "$lu" = "$annonce" ] || ecarts="${ecarts:+$ecarts, }$t $lu/$annonce"
  done <<< "$resume"
  [ "$n" -gt 0 ] || { echo "inconnue"; return 0; }
  [ -z "$ecarts" ] && echo "ok" || echo "écarts : $ecarts"
}

# ── Le nom d'archive annoncé par le nœud est-il acceptable ? ─────────────────
# Ce nom vient d'une machine distante et repart dans une commande exécutée là-bas :
# il est validé en LISTE BLANCHE ancrée (standards/03-securite.md §2), jamais par
# liste noire. Sans cette borne, un nom fabriqué deviendrait un chemin ou une
# commande. C'est aussi ce qui garantit qu'on ne lira jamais autre chose qu'une
# archive de sauvegarde close.
#
# Deux séries, deux préfixes, et pas un de plus : celle de la résidence, à la
# racine du volume, et celle du REGISTRE des installations (#1896), dans son
# sous-dossier — mêmes valeurs que `registre/sauvegarde.PREFIXE` et `.dossier()`,
# tenues par `test_sauvegarde_hors_site_plateforme.py`. Un préfixe hors de cette
# liste est refusé : il viendrait de l'appelant, pas d'une décision.
PREFIXE_RESIDENCE="hostachy_backup_"
PREFIXE_PLATEFORME="plateforme_backup_"
DOSSIER_PLATEFORME="plateforme"
nom_valide() { # $1 = nom candidat · $2 = préfixe (défaut : la résidence) → 0 si acceptable
  local n=${1:-} prefixe=${2:-$PREFIXE_RESIDENCE}
  case "$prefixe" in "$PREFIXE_RESIDENCE"|"$PREFIXE_PLATEFORME") ;; *) return 1 ;; esac
  [ -n "$n" ] || return 1
  [[ "$n" =~ ^${prefixe}[A-Za-z0-9._-]+\.tar\.gz$ ]] || return 1
  case "$n" in */*|*'\'*|*..*) return 1 ;; esac
  return 0
}

# ── L'archive tirée est-elle exploitable ? ───────────────────────────────────
# Quatre conditions, toutes nécessaires. Une archive qu'on n'a pas su vérifier
# n'est PAS déclarée saine : elle renvoie `erreur`, jamais `succes` — un
# contrôle qui ne peut pas s'exécuter rend INCONNU (standards/04 §1), et une
# sauvegarde qu'on croit bonne à tort est pire que pas de sauvegarde du tout.
# `contient_export` : « oui » ou « non ». L'intégrité vient de
# `verdict_export_base` : « ok » ou rien.
verdict_archive() { # $1=octets $2=empreintes_identiques $3=contient_export $4=integrite → statut|message
  local octets="${1:-0}" empreintes="${2:-non}" contient="${3:-non}" integrite="${4:-inconnue}"
  if [ "${octets:-0}" -le 0 ] 2>/dev/null || [ -z "$octets" ]; then
    echo "erreur|Archive vide ou absente après transfert."; return 0
  fi
  if [ "$empreintes" != "oui" ]; then
    echo "erreur|Empreinte SHA-256 différente de la source — transfert tronqué ou altéré."; return 0
  fi
  if [ "$contient" != "oui" ]; then
    echo "erreur|L'archive ne contient pas $NOM_EXPORT_BASE — sauvegarde inexploitable."; return 0
  fi
  if [ "$integrite" = "inconnue" ]; then
    echo "erreur|Intégrité NON vérifiée (export illisible, ou python indisponible) — copie non validée."; return 0
  fi
  if [ "$integrite" != "ok" ]; then
    echo "erreur|Export incohérent dans l'archive : $integrite."; return 0
  fi
  echo "succes|Copie hors site vérifiée ($octets octets, export : chaque table compte ses lignes annoncées)."
}

# ── Quelles copies locales supprimer ? ───────────────────────────────────────
# Reçoit la liste des noms DÉJÀ TRIÉE par ordre chronologique croissant (le nom
# porte l'horodatage : hostachy_backup_YYYYmmdd_HHMMSS_paris.tar.gz (heure de Paris,
# #1611 ; les anciennes, sans `_paris`, sont en UTC) — même convention
# que _rotate_backups() côté API). Rend les noms excédentaires, les plus anciens
# d'abord. `keep <= 0` ne supprime RIEN : une valeur de configuration aberrante
# ne doit jamais effacer les sauvegardes.
archives_a_supprimer() { # $1=keep, liste sur stdin → noms à supprimer
  local keep="${1:-0}" total=0
  local -a noms=()
  while IFS= read -r n; do [ -n "$n" ] && noms+=("$n"); done
  total=${#noms[@]}
  if [ "$keep" -le 0 ] 2>/dev/null; then return 0; fi
  [ "$total" -le "$keep" ] && return 0
  local i
  for ((i = 0; i < total - keep; i++)); do echo "${noms[$i]}"; done
}

# ── Que faut-il rattraper sur l'autre nœud ? ─────────────────────────────────
# 🔴 LE RATTRAPAGE SE BORNE À LA RÉTENTION (12/09/2026, signalé à l'écran).
#
# La passe de rattrapage tirait TOUT ce que l'autre nœud portait et qui manquait
# localement — six archives de ~100 Mo le 12/09 — puis la rotation en supprimait
# les plus anciennes. Autrement dit : télécharger une demi-heure pour effacer.
# Pire, tant que `EXPORT_KEEP` valait 14, rien n'était effacé et la destination
# gonflait indéfiniment.
#
# La règle est simple et se lit d'une phrase : **on ne tire que ce qu'on
# garderait**. On prend l'union (local + distant), on n'en retient que les `keep`
# plus récentes — le nom porte l'horodatage, donc l'ordre alphabétique EST
# l'ordre chronologique, même convention que `archives_a_supprimer` — et on ne
# demande que celles-là qui manquent ici.
#
# ⚠️ `keep <= 0` ne tire RIEN : même garde que la rotation. Une valeur aberrante
# ne doit ni effacer ni téléverser.
archives_a_rattraper() { # $1=keep $2=noms_locaux $3=noms_distants → noms à tirer
  local keep="${1:-0}" locaux="${2:-}" distants="${3:-}" retenues n
  [ "$keep" -gt 0 ] 2>/dev/null || return 0
  retenues=$(printf '%s\n%s\n' "$locaux" "$distants" | grep -v '^[[:space:]]*$' | sort -u | tail -n "$keep")
  while IFS= read -r n; do
    [ -n "$n" ] || continue
    #  Déjà ici : rien à tirer. La comparaison porte sur la ligne ENTIÈRE —
    #  une sous-chaîne confondrait deux archives du même jour.
    case $'\n'"$locaux"$'\n' in *$'\n'"$n"$'\n'*) continue ;; esac
    echo "$n"
  done <<< "$retenues"
}

# ── Quels jours manquent dans la copie hors site ? ───────────────────────────
# 🔴 #775 (05/09/2026) : la bascule de 02:00 change le nœud actif chaque nuit,
# donc la série d'archives est RÉPARTIE sur les deux volumes — relevé ce jour-là,
# rpi1 portait 31/08, 02/09, 04/09 et rpi2 03/09, 05/09. La passe de rattrapage
# va chercher ce qui manque ; cette fonction dit S'IL manque quelque chose.
#
# ⚠️ PURE — aucune E/S : c'est ce qui la rend éprouvable par `--selftest`, sans
# les deux RPi. Le motif du projet pour toute décision d'infra.
jours_manquants() { # $1=jours_a_couvrir $2=date_du_jour(AAAAMMJJ) puis noms sur stdin
  local fenetre="${1:-14}" aujourdhui="${2:-}" noms manquants=""
  noms=$(cat)
  [ -n "$aujourdhui" ] || aujourdhui=$(date +%Y%m%d)
  local i jour debut=1
  # On remonte le temps jour par jour, en partant de la VEILLE : l'archive du
  # jour même n'existe qu'après 02:00, et l'exiger ferait crier le contrôle
  # chaque matin pour un fait normal.
  # 🔴 …SAUF si elle est déjà là (29/09/2026, relevé à l'écran). La rotation
  # garde les `keep` archives les PLUS RÉCENTES, celle du jour comprise : avec
  # deux copies, un export lancé après 02:00 détient J et J-1. Une fenêtre fixée
  # à J-1..J-keep réclamait alors J-2 — que la rotation venait d'effacer — et
  # signalait chaque jour un « jour absent » qui n'en était pas un. La fenêtre
  # commence au jour le plus récent qu'on puisse détenir.
  case "$noms" in *"${PREFIXE_RESIDENCE}${aujourdhui}_"*) debut=0 ;; esac
  for ((i = debut; i < debut + fenetre; i++)); do
    jour=$(date -d "$aujourdhui -$i day" +%Y%m%d 2>/dev/null) || return 0
    case "$noms" in
      *"${PREFIXE_RESIDENCE}${jour}_"*) ;;
      *) manquants="$manquants $jour" ;;
    esac
  done
  echo "${manquants# }"
}
