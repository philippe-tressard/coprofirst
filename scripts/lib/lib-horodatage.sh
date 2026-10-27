#!/bin/bash
# =============================================================================
#  lib-horodatage.sh — l'âge d'un horodatage LOCAL, sans âge négatif (#2232)
#
#  Module SOURCÉ (mode 100644) par `lib-verdicts.sh` (check-reliability) et par
#  `precheck-mep.sh` (points 8 et 13).
#
#  ## Le défaut
#
#  Les journaux s'horodatent en heure locale SANS décalage (`[2026-10-25 02:38:49]`),
#  et l'âge se calculait par `date -d "$ts" +%s`. La nuit du passage à l'heure
#  d'hiver, l'heure 02:00-03:00 existe DEUX fois : GNU `date` lit l'horodatage
#  ambigu comme la seconde occurrence (CET), donc UNE HEURE DANS LE FUTUR pour une
#  ligne écrite à la première (CEST). Le post-check de v3.19.0 (25/10/2026, 02:39)
#  a rendu « il y a -58 min » aux points 8 et 13 : INCONNU, jamais un faux vert,
#  mais plus rien de mesuré pendant une heure par an.
#
#  ## La règle
#
#  `age_min_epoch E MAINTENANT` — un repère qui dépasse de plus de 10 min le
#  présent ne peut venir que de cette heure double : on le ramène d'une heure.
#  S'il reste dans le futur, c'est une horloge ou une lecture fausse : -1 (INCONNU).
#  Moins de 10 min d'avance, c'est le décalage d'horloge entre deux nœuds : l'âge
#  est 0, comme avant.
#
#  Les journaux gardent leur forme : un décalage ajouté à l'horodatage changerait
#  les motifs de lecture de tous les consommateurs (`^\[[0-9-]+ [0-9:]+`).
#
#  Self-test : bash scripts/lib/lib-horodatage.sh --selftest (job `test-scripts`).
# =============================================================================

TOLERANCE_HORLOGE_S=600
HEURE_DOUBLE_S=3600

# age_min_epoch E [MAINTENANT] — minutes écoulées depuis E (epoch lu sur un horodatage
# local) ; -1 si E ou MAINTENANT ne sont pas des entiers, ou si E reste dans le futur.
age_min_epoch() {
  local e="${1:-}" now="${2:-$(date +%s)}"
  case "$e" in ""|*[!0-9]*) echo -1; return ;; esac
  case "$now" in ""|*[!0-9]*) echo -1; return ;; esac
  if [ "$e" -gt $(( now + TOLERANCE_HORLOGE_S )) ]; then
    e=$(( e - HEURE_DOUBLE_S ))
    [ "$e" -gt $(( now + TOLERANCE_HORLOGE_S )) ] && { echo -1; return; }
  fi
  echo $(( (now - e) / 60 ))
}

# age_min_releve "E MAINTENANT" — le relevé d'un hôte distant : l'epoch du repère et celui de
# SON présent, lus ensemble sur la même horloge. Vide si le relevé est vide (repère absent).
age_min_releve() {
  [ -n "${1:-}" ] || return 0
  case "$1" in *" "*) ;; *) echo -1; return ;; esac   # un seul champ : l'un des deux `date` a échoué
  age_min_epoch "${1%% *}" "${1##* }"
}

_horodatage_selftest() {
  local echecs=0 TZ=Europe/Paris
  export TZ
  _cas() {  # description attendu obtenu
    if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"
    else echo "FAIL  $1  attendu=$2 obtenu=$3"; echecs=$((echecs + 1)); fi
  }
  local T=1792886400   # 2026-10-25 00:00:00 UTC = 02:00 CEST, début de l'heure double

  #  Le cas du 25/10/2026 : une ligne écrite à 02:30 CEST (00:30 UTC, première occurrence) est lue
  #  comme 02:30 CET (01:30 UTC) : une heure dans le futur. Posé par l'arithmétique, il ne dépend
  #  pas du `date` du poste ; ce que ce `date` fait de l'horodatage ambigu se joue plus bas.
  local reel=$((T + 30 * 60))
  _cas "heure double, 1re occurrence lue comme la 2e (+1 h), 8 min plus tard" 8 "$(age_min_epoch $((reel + 3600)) $((reel + 8 * 60)))"
  _cas "heure double, relevé distant du même cas" 8 "$(age_min_releve "$((reel + 3600)) $((reel + 8 * 60))")"
  #  La seconde occurrence (02:30 CET = 01:30 UTC), lue à 02:38 CET : lue juste, rien à corriger.
  _cas "heure double, 2e occurrence (CET), lue 8 min plus tard" 8 "$(age_min_epoch $((T + 90 * 60)) $((T + 98 * 60)))"
  #  Le `date` réel, quand il honore TZ (GNU/Linux ; celui de Git Bash sous Windows l'ignore :
  #  le saut est alors DIT, il ne passe pas pour un vert).
  if [ "$(TZ=Europe/Paris date -d "@$T" +%z)" = "+0200" ]; then
    local lu; lu=$(date -d "2026-10-25 02:30:00" +%s)
    _cas "date réel : 02:30 ambigu lu puis 8 min plus tard" 8 "$(age_min_epoch "$lu" $((reel + 8 * 60)))"
  else
    echo "SKIP  date réel : ce date ignore TZ=Europe/Paris — la lecture de l'heure ambiguë n'est pas éprouvée ici"
  fi
  #  Hors de l'heure double, rien ne change.
  _cas "ligne ordinaire, 30 min" 30 "$(age_min_epoch $((T - 7200)) $((T - 7200 + 1800)))"
  _cas "ligne du jour même, il y a 0 s" 0 "$(age_min_epoch "$T" "$T")"
  #  Le décalage d'horloge entre deux nœuds reste un âge nul, pas un INCONNU.
  _cas "repère 30 s dans le futur (horloges décalées)" 0 "$(age_min_epoch $((T + 30)) "$T")"

  #  CAS ZÉRO : ce qu'on ne sait pas lire n'est jamais un âge.
  _cas "repère à 2 h dans le futur (ni l'heure double, ni une horloge juste)" -1 "$(age_min_epoch $((T + 7200)) "$T")"
  _cas "repère vide" -1 "$(age_min_epoch "" "$T")"
  _cas "repère non numérique" -1 "$(age_min_epoch "hier" "$T")"
  _cas "présent non numérique" -1 "$(age_min_epoch "$T" "maintenant")"
  _cas "relevé distant vide → vide (repère absent)" "" "$(age_min_releve "")"
  _cas "relevé distant sans epoch lu" -1 "$(age_min_releve " $T")"
  _cas "relevé distant dont date a échoué (une seule valeur)" -1 "$(age_min_releve "$T")"

  if [ "$echecs" -eq 0 ]; then echo "✓ lib-horodatage : tous les cas passent."; return 0; fi
  echo "✗ lib-horodatage : $echecs cas en échec."
  return 1
}

#  Garde « exécuté, pas sourcé ».
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  _horodatage_selftest
  exit $?
fi
