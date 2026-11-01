#!/usr/bin/env bash
# =============================================================================
#  file-rejeu.sh — Les gestes du coordinateur sur la file du rejeu (#2225)
#
#  POURQUOI (24/10/2026). La file des MEP était tenue de vive voix par une
#  session de coordination, et rien ne l'imposait : une session a pris le
#  verrou hors file. Depuis, `rejouer-ci.sh --attendre` dépose un ticket et
#  démarre à son tour ; ce script permet au coordinateur de RÉORDONNER la file
#  et de la nettoyer, sans toucher au processus de personne. Chaque geste est
#  journalisé (`rejeu-ci-file.log`, répertoire git commun).
#
#  Usage :
#    bash scripts/poste/file-rejeu.sh                    # l'état (etat-rejeu.sh)
#    bash scripts/poste/file-rejeu.sh devant <pid>       # ce ticket passe en tête
#    bash scripts/poste/file-rejeu.sh retirer <pid>      # un ticket mort
#    bash scripts/poste/file-rejeu.sh retirer <pid> --meme-vivant
#                                                        # le rejeu en attente s'arrête alors de lui-même
#    bash scripts/poste/file-rejeu.sh purger             # tous les tickets morts
#    bash scripts/poste/file-rejeu.sh reprendre "<motif>"
#        # un verrou ORPHELIN (lanceur disparu, pouls figé) ou périmé — jamais un
#        # verrou actif ; le processus d'un orphelin n'est pas arrêté
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
FILE="$COMMUN/rejeu-ci.file"
GESTE="${1:-lister}"

pid_valide() { case "${1:-}" in ''|*[!0-9]*) echo "✗ pid attendu (voir etat-rejeu.sh)"; exit 2 ;; esac; }
etat_du_ticket() {         # $1 = pid → vivant|mort|absent
  local ligne; ligne=$(ci_file_lister "$FILE" "$REJEU_SEUIL_FIGE_S" | awk -v p="$1" '{ split($1, a, "."); if (a[2] == p) print $2 }')
  case "$ligne" in oui) echo vivant ;; non) echo mort ;; *) echo absent ;; esac
}

case "$GESTE" in
  lister)
    exec bash "$RACINE_DEPOT/scripts/poste/etat-rejeu.sh" ;;
  devant)
    pid_valide "${2:-}"
    ci_file_passer_devant "$FILE" "$2" || { echo "✗ Aucun ticket pour le pid $2."; exit 1; }
    ci_journal_geste "$COMMUN" devant "pid=$2 · $(ci_fiche_resume "$(ci_file_ticket_de "$FILE" "$2")")"
    echo "✓ Le ticket du pid $2 passe en tête de file." ;;
  retirer)
    pid_valide "${2:-}"
    case "$(etat_du_ticket "$2"):${3:-}" in
      absent:*)        echo "✗ Aucun ticket pour le pid $2."; exit 1 ;;
      vivant:--meme-vivant) ;;
      vivant:*)        echo "✗ Le ticket du pid $2 est VIVANT : son rejeu attend. Le retirer l'arrête (il le"
                       echo "  constate à son prochain pouls) — ajouter --meme-vivant si c'est voulu."; exit 1 ;;
    esac
    ci_journal_geste "$COMMUN" retirer "pid=$2 $(etat_du_ticket "$2") · $(ci_fiche_resume "$(ci_file_ticket_de "$FILE" "$2")")"
    ci_file_retirer "$FILE" "$2"
    echo "✓ Ticket du pid $2 retiré." ;;
  purger)
    n=0
    while read -r nom vivant _; do
      [ "$vivant" = non ] || continue
      ci_journal_geste "$COMMUN" purger "pid=${nom##*.} · $(ci_fiche_resume "$FILE/$nom")"
      ci_file_retirer "$FILE" "${nom##*.}"; n=$((n + 1))
    done <<< "$(ci_file_lister "$FILE" "$REJEU_SEUIL_FIGE_S")"
    echo "✓ $n ticket(s) mort(s) retiré(s)." ;;
  reprendre)
    ci_verrou_reprendre_motive "$COMMUN/rejeu-ci.verrou" "${2:-}" || exit 1 ;;
  *)
    sed -n '/^#  Usage/,/^# ====/p' "$0"; exit 2 ;;
esac
