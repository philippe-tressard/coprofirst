#!/usr/bin/env bash
# =============================================================================
#  etat-rejeu.sh — Qui tient le rejeu de la CI, où il en est, qui attend (#2225)
#
#  POURQUOI (24/10/2026). Le verrou du rejeu ne contenait qu'un pid : le
#  coordinateur des sessions a passé des dizaines de minutes à retrouver à qui
#  il était, et un rejeu orphelin l'a tenu 20 min sans que personne le sache.
#  Une commande, lecture seule, dit tout : propriétaire, étape en cours, âge du
#  pouls, durée écoulée, file d'attente, et le diagnostic — dont « orphelin »
#  (lanceur disparu ET pouls figé depuis plus de REJEU_SEUIL_FIGE_S).
#
#  Ne modifie rien. Les gestes sont dans `file-rejeu.sh`.
#  Usage : bash scripts/poste/etat-rejeu.sh
# =============================================================================
set -uo pipefail
# shellcheck source=../lib/lib-poste-gnu.sh
. "$(dirname "$0")/../lib/lib-poste-gnu.sh"
poste_gnu_poser   # macOS : les outils GNU en tête du PATH, comme Git Bash et la CI (#2419)

RACINE_DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RACINE_DEPOT" || exit 2
# shellcheck source=../lib/lib-ci-verrou.sh
. "$RACINE_DEPOT/scripts/lib/lib-ci-verrou.sh"

COMMUN=$(ci_dossier_commun)
VERROU="$COMMUN/rejeu-ci.verrou"
FILE="$COMMUN/rejeu-ci.file"
MAINTENANT=$(date +%s)

il_y_a() {                 # $1 = horodatage → « HH:MM:SS (il y a …) », ou « ? »
  case "${1:-}" in ''|*[!0-9]*) echo "?"; return ;; esac
  echo "$(date -d "@$1" '+%H:%M:%S' 2>/dev/null) (il y a $(ci_duree "$(ci_age_s "$1" "$MAINTENANT")"))"
}

echo "Rejeu de la CI — état au $(date '+%d/%m %H:%M:%S')"
ci_verrou_lire "$VERROU"
echo "Verrou       : $(ci_rejeu_diagnostic_dit "$VL_DIAG")"
if [ -n "$VL_PID" ]; then
  echo "  pid        : $VL_PID ($([ "$VL_VIVANT" = oui ] && echo vivant || echo mort)) · lanceur : $VL_PARENT"
  if [ -f "$VERROU/proprietaire" ]; then
    echo "  tenu par   : $(ci_fiche_resume "$VERROU/proprietaire")"
    echo "  départ     : $(il_y_a "$(ci_champ "$VERROU/proprietaire" depart)") · jobs : $(ci_champ "$VERROU/proprietaire" jobs)"
  else
    echo "  tenu par   : fiche absente — rejeu lancé par un script antérieur à #2225"
  fi
  if [ -f "$VERROU/battement" ]; then
    echo "  étape      : $(ci_champ "$VERROU/battement" etape) — $(ci_champ "$VERROU/battement" rang)/$(ci_champ "$VERROU/battement" extraites) · depuis $(il_y_a "$(ci_champ "$VERROU/battement" depuis)")"
    arret=$(ci_champ "$VERROU/battement" arret)
    [ -n "$arret" ] && echo "  arrêt signé: $(ci_champ "$VERROU/battement" motif) — $(il_y_a "$arret")"
  else
    echo "  étape      : aucune encore (préparation)"
  fi
  echo "  pouls      : $([ -n "$VL_AGE_POULS" ] && echo "il y a $(ci_duree "$VL_AGE_POULS")" || echo absent) (figé au-delà de $(ci_duree "$REJEU_SEUIL_FIGE_S"))"
fi

LISTE=$(ci_file_lister "$FILE" "$REJEU_SEUIL_FIGE_S")
echo "File         : $(printf '%s\n' "$LISTE" | grep -c .) ticket(s), dans l'ordre de passage"
rang=0
while read -r nom vivant age; do
  [ -z "$nom" ] && continue
  pid=${nom##*.}
  resume="$(ci_fiche_resume "$FILE/$nom") — inscrit $(il_y_a "$(ci_champ "$FILE/$nom" depart)")"
  if [ "$vivant" = oui ]; then
    rang=$((rang + 1))
    echo "  $rang. pid $pid — $resume"
  else
    echo "  ✗ pid $pid MORT ou figé (vu il y a $(ci_duree "$age")) — $resume"
    echo "      → bash scripts/poste/file-rejeu.sh retirer $pid"
  fi
done <<< "$LISTE"

case "$VL_DIAG" in
  orphelin) echo "→ Reprise explicite : bash scripts/poste/file-rejeu.sh reprendre \"<motif>\"" ;;
  fige)     echo "→ Demander à la session qui le tient avant tout geste : son lanceur est encore là." ;;
esac
exit 0
