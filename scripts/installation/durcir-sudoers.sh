#!/bin/bash
# =============================================================================
#  durcir-sudoers.sh — Pose la MÊME règle sudo sur les deux nœuds (#302)
#
#  Usage :
#    bash durcir-sudoers.sh --selftest        # éprouve les décisions, ne touche rien
#    bash durcir-sudoers.sh --etat            # LECTURE SEULE : que porte chaque nœud ?
#    bash durcir-sudoers.sh --dry-run         # montre ce qui serait fait
#    bash durcir-sudoers.sh --appliquer       # installe (demande confirmation)
#    bash durcir-sudoers.sh --nettoyer        # retire les fichiers hérités
#
#  Toutes ces commandes acceptent `--noeud <ip>` pour ne viser QU'UN nœud, et
#  c'est ainsi qu'il faut s'en servir : le STANDBY d'abord, vérifier, puis
#  l'actif. Sans filtre, une règle mauvaise abîme les deux moitiés de la paire
#  dans la même seconde — c'est-à-dire exactement ce que la paire existe pour
#  éviter. Une IP inconnue fait ÉCHOUER le script, elle ne le fait pas boucler
#  sur rien en annonçant un succès.
#
#  ⚠️ À N'EXÉCUTER QU'AVEC UNE SESSION ROOT OUVERTE EN PARALLÈLE sur le nœud
#  visé. Une règle sudoers invalide rend `sudo` inutilisable, donc le nœud
#  inadministrable autrement que par cette session déjà ouverte — ou un clavier.
#
#  L'ORDRE EST LE GARDE-FOU PRINCIPAL, pas une préférence de style :
#    1. installer la règle unique et la vérifier (`visudo -c`) ;
#    2. VÉRIFIER SUR LE NŒUD que les commandes nécessaires passent encore ;
#    3. seulement alors, retirer les fichiers hérités.
#  Retirer `010_pi-nopasswd` avant que la nouvelle règle ne fonctionne rendrait
#  le compte incapable de piloter `cloudflared` : la bascule de 02:00 échouerait,
#  et le tunnel peut alors rester éteint des DEUX côtés — c'est l'incident du
#  30/07/2026. `--nettoyer` est donc une commande séparée, jamais enchaînée
#  automatiquement après `--appliquer`.
#
#  Ce script ne ferme PAS l'escalade de privilèges : `ptressard` est dans le
#  groupe `docker`, ce qui est déjà un équivalent root, antérieur et nécessaire
#  au déploiement. Il réduit la surface et rétablit la SYMÉTRIE — c'est la
#  divergence qui a coûté une nuit sur deux de copie hors site le 09/08/2026.
# =============================================================================
set -uo pipefail

#  `lib-sudoers.sh` est resté à la racine du dépôt (#337).
REPO=$(cd "$(dirname "$0")/../.." && pwd)
# shellcheck source=../lib/lib-sudoers.sh
. "$REPO/scripts/lib/lib-sudoers.sh"
#  L'image du conteneur jetable (#2962) : lue dans `infra/Dockerfile.utilitaire`.
# shellcheck source=../lib/lib-image-utilitaire.sh
. "$REPO/scripts/lib/lib-image-utilitaire.sh"
UTIL=$(image_utilitaire) || UTIL=""

if [ "${1:-}" = "--selftest" ]; then
  sudoers_selftest
  exit $?
fi
#  Sans image lisible, les gestes par conteneur jetable lanceraient `docker run` sur
#  une image vide : on s'arrête avant le premier.
[ -n "$UTIL" ] || { echo "ERREUR : image utilitaire illisible (infra/Dockerfile.utilitaire) — rien n'est fait." >&2; exit 1; }

TOUS_NOEUDS="192.168.1.222 192.168.1.223"

#  `--noeud <ip>` peut suivre la commande : on le retire des arguments avant de
#  lire l'action, pour que l'ordre des deux n'ait pas d'importance.
FILTRE=""
ARGS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --noeud) FILTRE="${2:-}"; shift 2 || shift ;;
    *)       ARGS="$ARGS $1"; shift ;;
  esac
done
# shellcheck disable=SC2086
set -- $ARGS

if ! NOEUDS=$(sudoers_noeuds_cibles "$FILTRE" "$TOUS_NOEUDS"); then
  echo "Nœud inconnu : '$FILTRE'. Nœuds connus : $TOUS_NOEUDS" >&2
  exit 2
fi
[ -n "$FILTRE" ] && echo "→ Ce lancement ne vise QUE $FILTRE."
SSH="ssh -o BatchMode=yes -o ConnectTimeout=10"
COMPTE=ptressard
ATTENDU=$(sudoers_regle "$COMPTE")

log() { printf '%s\n' "$*"; }

# Lit la règle installée sur un nœud. Rend un marqueur explicite plutôt qu'une
# chaîne vide : « je n'ai pas pu lire » n'est pas « le fichier est vide ».
#
# 🔴 DEUX VOIES DE LECTURE, et la seconde n'est pas un luxe (27/08/2026).
# La première (`sudo -n cat`) ne fonctionne que sur un nœud QUI N'EST PAS ENCORE
# DURCI : dès que la règle unique est en place, `cat` n'y est plus NOPASSWD — et
# c'est voulu, l'y ajouter rendrait tout le disque lisible en root. Le script se
# retrouvait alors incapable de relire ce qu'il venait d'écrire : conformité
# INCONNU pour toujours, donc `--nettoyer` bloqué à jamais et C20 jamais vert.
# Un outil qui ne peut plus mesurer l'état qu'il vient de poser n'achève pas son
# travail — il l'abandonne au milieu, dans l'état le plus fragile des trois.
#
# La seconde voie passe par un conteneur jetable : `ptressard` est dans le groupe
# `docker`, ce qui est déjà un équivalent root (voir l'avertissement en tête de
# `lib-sudoers.sh`). Elle n'ouvre donc AUCUN privilège nouveau — c'est le canal
# qui a servi à installer le fichier.
lire_regle() {  # $1 = ip
  local sortie
  sortie=$($SSH "$COMPTE@$1" "sudo -n cat $SUDOERS_CIBLE 2>/dev/null \
    || docker run --rm -v /etc/sudoers.d:/s:ro $UTIL cat /s/${SUDOERS_CIBLE##*/} 2>/dev/null \
    || { [ -e $SUDOERS_CIBLE ] && echo __ILLISIBLE__ || echo __ABSENT__; }" 2>/dev/null)
  printf '%s' "${sortie:-__ILLISIBLE__}"
}

etat() {
  log "═══ État des permissions élevées ═══"
  for ip in $NOEUDS; do
    log "── $ip"
    if ! $SSH "$COMPTE@$ip" true 2>/dev/null; then
      log "   INJOIGNABLE — état INCONNU, aucune conclusion"
      continue
    fi
    #  Métadonnées seulement : le répertoire est traversable par tous, les
    #  contenus non. Même raisonnement que C20 — lire les règles à distance
    #  supposerait un NOPASSWD sur `cat`, c'est-à-dire la faille surveillée.
    log "   fichiers : $($SSH "$COMPTE@$ip" "ls /etc/sudoers.d/ 2>/dev/null | tr '\n' ' '" 2>/dev/null)"
    log "   règle 5hostachy : $(sudoers_conformite "$(lire_regle "$ip")" "$ATTENDU")"
    #  Sondes de PERMISSION, et surtout PAS d'exécution.
    #
    #  ⚠️ `sudo -n <cmd> && echo OK || echo refusé` est un piège, et je suis
    #  tombé dedans en écrivant ce script : `systemctl is-active` rend 3 quand
    #  l'unité est arrêtée — ce qui est le cas normal de cloudflared sur le
    #  STANDBY. La sonde annonçait donc « refusé » sur une permission qui
    #  existait. Confondre « la commande a échoué » et « la permission est
    #  refusée » est la même faute que déduire un vert d'une sortie vide.
    #
    #  `sudo -l <cmd>` répond sur la PERMISSION seule, sans rien exécuter : 0 si
    #  le compte peut lancer cette commande, ≠0 sinon. C'est aussi la seule
    #  sonde utilisable pour `systemctl start`, qu'on ne peut évidemment pas
    #  essayer sur un standby — ce serait provoquer un split-brain pour vérifier
    #  qu'on a le droit d'en provoquer un.
    #  ⚠️ On lit la LISTE une fois, puis on conclut dessus — `sudo -n -l <cmd>`
    #  répondrait « oui » pour tout ce que la ligne `(ALL : ALL) ALL` couvre,
    #  mot de passe compris (voir `sudoers_est_nopasswd`).
    local liste; liste=$($SSH "$COMPTE@$ip" "sudo -n -l 2>/dev/null" 2>/dev/null)
    if [ -z "$liste" ]; then
      log "   surface NOPASSWD : INCONNUE (sudo -n -l muet) — aucune conclusion"
    else
      log "   surface NOPASSWD réelle :"
      sudoers_surface_nopasswd "$liste" | sed 's/^/     · /'
      #  `rsync` reste INTERROGÉ après son retrait (#582) : `--etat` doit dire
      #  « NON » sur un nœud durci, et « oui » sur un nœud pas encore repassé.
      #  Ne plus le demander ferait disparaître la seule trace de la dérive.
      for c in "/usr/bin/systemctl start cloudflared" "/usr/bin/crontab -l" "/usr/bin/rsync"; do
        printf '   sans mot de passe %-32s ' "$c"
        sudoers_est_nopasswd "$liste" "$c" && echo "oui" || echo "NON"
      done
    fi
  done
}

appliquer() {  # $1 = "oui" pour écrire réellement
  for ip in $NOEUDS; do
    log "── $ip"
    if ! $SSH "$COMPTE@$ip" true 2>/dev/null; then
      log "   INJOIGNABLE — ignoré (aucune modification partielle)"; continue
    fi
    if [ "$1" != "oui" ]; then
      log "   [dry-run] installerait $SUDOERS_CIBLE ($(printf '%s' "$ATTENDU" | wc -l) lignes)"
      continue
    fi
    #  Écriture en deux temps : un fichier temporaire VALIDÉ par visudo, puis
    #  une installation atomique. `visudo -cf` est le seul contrôle qui dise si
    #  le fichier est acceptable AVANT qu'il ne casse sudo.
    if printf '%s\n' "$ATTENDU" | $SSH "$COMPTE@$ip" "cat > /tmp/5hostachy.sudoers && \
         sudo -n visudo -cf /tmp/5hostachy.sudoers >/dev/null && \
         sudo -n install -o root -g root -m 0440 /tmp/5hostachy.sudoers $SUDOERS_CIBLE && \
         sudo -n visudo -c >/dev/null && rm -f /tmp/5hostachy.sudoers" 2>/dev/null; then
      log "   installée et validée (visudo -c global OK)"
    else
      log "   ÉCHEC — règle NON installée. Vérifier depuis la session root ouverte."
      $SSH "$COMPTE@$ip" "rm -f /tmp/5hostachy.sudoers" 2>/dev/null
      return 1
    fi
    log "   conformité relue : $(sudoers_conformite "$(lire_regle "$ip")" "$ATTENDU")"
  done
}

nettoyer() {
  for ip in $NOEUDS; do
    log "── $ip"
    local verdict; verdict=$(sudoers_conformite "$(lire_regle "$ip")" "$ATTENDU")
    if [ "$(sudoers_peut_nettoyer "$verdict")" != "oui" ]; then
      log "   règle 5hostachy : $verdict → on ne retire RIEN."
      log "   (retirer les héritées avant que la nouvelle règle ne marche coupe"
      log "    le pilotage de cloudflared, donc la bascule de 02:00)"
      continue
    fi
    #  Avant de retirer le filet, on vérifie que le nouveau porte la charge :
    #  ce sont les commandes dont dépendent bascule.sh et health-watch.sh.
    #  Même sonde de PERMISSION qu'en `--etat`, et pour la même raison : on ne
    #  peut pas essayer `systemctl start cloudflared` sur un standby pour
    #  vérifier qu'on en a le droit.
    local ko=0 liste
    liste=$($SSH "$COMPTE@$ip" "sudo -n -l 2>/dev/null" 2>/dev/null)
    if [ -z "$liste" ]; then
      log "   surface NOPASSWD illisible → on ne retire RIEN (INCONNU n est pas OK)."
      continue
    fi
    #  🔴 `rsync` a QUITTÉ cette liste le 31/08/2026 (#582). L'exiger encore
    #  ferait refuser le retrait sur un nœud déjà correct — le contrôle
    #  bloquerait sur l'absence de ce qu'on vient de supprimer.
    for c in "/usr/bin/systemctl start cloudflared" "/usr/bin/systemctl stop cloudflared" "/usr/bin/crontab -l"; do
      sudoers_est_nopasswd "$liste" "$c" || { log "   permission MANQUANTE : $c"; ko=1; }
    done
    [ "$ko" -eq 1 ] && { log "   → on ne retire RIEN."; continue; }
    #  🔴 Le retrait passe par le conteneur jetable, PAS par `sudo -n rm`
    #  (27/08/2026). La permission `rm` que le retrait emploierait est portée
    #  par l'un des fichiers qu'il retire : l'opération se coupait donc le bras
    #  en cours de route, et l'ordre de la liste était le seul garde-fou — un
    #  garde-fou invisible, que le premier réarrangement alphabétique aurait
    #  emporté. Le canal docker ne dépend d'aucune des règles en jeu.
    for f in $SUDOERS_HERITES; do
      $SSH "$COMPTE@$ip" "[ -e /etc/sudoers.d/$f ] &&         docker run --rm -v /etc/sudoers.d:/s $UTIL rm -f /s/$f && echo '   retiré : $f'" 2>/dev/null
    done
    #  🔴 On ne vérifie PAS avec `visudo -c` : il n'est plus NOPASSWD sur un nœud
    #  durci, et son échec se lisait « sudoers cassé » alors qu'il signifiait
    #  « je n'ai pas le droit de vérifier ». TROISIÈME fois que ce script se sert
    #  d'une permission que le durcissement retire — c'est le motif à retenir,
    #  pas les trois cas.
    #
    #  La preuve qui vaut : `sudo -n -l` répond. sudo relit TOUT l'arbre sudoers
    #  à chaque invocation ; s'il répond, c'est qu'il l'a analysé en entier.
    if $SSH "$COMPTE@$ip" "sudo -n -l >/dev/null 2>&1"; then
      log "   sudo répond encore → l'arbre sudoers est valide"
    else
      log "   🔴 sudo NE RÉPOND PLUS. Retirer le fichier par le canal docker :"
      log "      ssh $COMPTE@$ip 'docker run --rm -v /etc/sudoers.d:/s $UTIL rm -f /s/${SUDOERS_CIBLE##*/}'"
    fi
  done
}

case "${1:-}" in
  --etat)      etat ;;
  --dry-run)   log "═══ Simulation (aucune écriture) ═══"; appliquer non ;;
  --appliquer)
    log "⚠️  Une règle sudoers invalide rend le nœud inadministrable."
    log "    Garder une session root ouverte sur CHAQUE nœud pendant l'opération."
    printf '    Continuer ? [oui/NON] '
    read -r reponse
    [ "$reponse" = "oui" ] || { log "Abandon."; exit 1; }
    appliquer oui && log "→ Vérifier avec --etat, puis --nettoyer SEULEMENT si tout est conforme."
    ;;
  --nettoyer)  nettoyer ;;
  *)
    sed -n '3,20p' "$0"
    exit 1
    ;;
esac
