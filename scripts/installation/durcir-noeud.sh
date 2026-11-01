#!/bin/bash
# =============================================================================
#  durcir-noeud.sh — Le durcissement système d'un nœud : sshd, ufw, fail2ban,
#  mises à jour automatiques (#1917, #1918), sortie en liste blanche (#2367)
#
#  Usage, SUR le nœud, en root :
#    bash durcir-noeud.sh --selftest                       # éprouve les décisions, ne touche rien
#    sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --etat       # LECTURE SEULE
#    sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --appliquer  # pose ce qui manque
#    sudo bash /opt/5hostachy/scripts/installation/durcir-noeud.sh --sortant constat|refus|ouvert
#        # la sortie seule : journaliser le hors-liste, le refuser, ou tout rouvrir
#
#  Ce que le script NE fait PAS, et ne fera jamais : écrire le `.env`, poser un
#  secret, une clé ou un jeton. Le reste de la réinstallation d'un nœud — Docker,
#  dépôt, `.env`, base, tunnel, crons, règle sudo — est décrit, dans l'ordre, par
#  `docs/restauration-complete.md`, qui appelle ce script à son étape 4.
#
#  IDEMPOTENT : chaque fichier n'est réécrit que s'il diffère, chaque règle ufw
#  n'est ajoutée que si elle manque. Le relancer sur un nœud conforme ne change
#  rien. Jamais de `ufw reset` : sur un nœud en service, il effacerait des
#  règles qu'on n'a pas vues avant de les reposer.
#
#  ⚠️ `--appliquer` change la configuration de sshd : garder une SECONDE session
#  SSH ouverte sur le nœud jusqu'à la fin, et vérifier qu'une NOUVELLE connexion
#  par clé passe avant de la fermer. Le STANDBY d'abord, puis l'actif.
#
#  Chaque verdict porte sur la configuration EFFECTIVE (`sshd -T`, `ufw show
#  added`, `fail2ban-client`, `apt-config dump`) et non sur un fichier posé :
#  c'est en lisant le fichier qu'on a cru, d'avril à octobre 2026, que le mot de
#  passe était coupé (#1918). Les décisions vivent dans `lib-durcissement.sh`.
# =============================================================================
set -uo pipefail

REPO=$(cd "$(dirname "$0")/../.." && pwd)
# shellcheck source=../lib/lib-durcissement.sh
. "$REPO/scripts/lib/lib-durcissement.sh"
#  `poser` (écriture idempotente d'un fichier root) : partagée avec le contrôle des
#  correctifs d'une installation standard (`deploiement/standard/correctifs-systeme.sh`).
# shellcheck source=../../deploiement/standard/lib-installation.sh
. "$REPO/deploiement/standard/lib-installation.sh"

if [ "${1:-}" = "--selftest" ]; then
  durcissement_selftest
  exit $?
fi

COMPTE=ptressard
CLES_AUTORISEES=/home/$COMPTE/.ssh/authorized_keys
#: Fichier hérité de l'ancienne procédure, présent sur un seul nœud : ses
#: `Allowed-Origins` s'AJOUTENT aux origines de Debian, il ne restreint rien.
APT_HERITE=/etc/apt/apt.conf.d/50unattended-upgrades-hostachy

log() { printf '%s\n' "$*"; }

# ── Lectures de l'état effectif ──────────────────────────────────────────────
#  Les lecteurs (`durcissement_lire_*`) et les quatre verdicts sur l'état SERVI
#  (`durcissement_etat_*`) vivent dans `lib-durcissement.sh` depuis le
#  30/10/2026 : l'audit de sécurité nocturne (`audit-securite.sh`, S5) les
#  rejoue chaque nuit en root, et les recopier aurait fait deux lectures de la
#  même configuration destinées à diverger.
compter_cles() {
  #  Absent → 0 (un nœud neuf sans clé) ; illisible → rien (on ne sait pas).
  [ -e "$CLES_AUTORISEES" ] || { echo 0; return; }
  [ -r "$CLES_AUTORISEES" ] || return 0
  grep -cE '^(ssh-|ecdsa-|sk-)' "$CLES_AUTORISEES"
}

verdict_sshd() { durcissement_etat_sshd; }
verdict_ufw()  { durcissement_etat_ufw; }
verdict_f2b()  { durcissement_etat_f2b; }
verdict_apt()  { durcissement_etat_apt; }
verdict_sortant() { durcissement_etat_sortant; }
lire_ufw_etat()     { durcissement_lire_ufw_etat; }
lire_ufw_ajoutees() { durcissement_lire_ufw_ajoutees; }

# ── --etat ───────────────────────────────────────────────────────────────────
#  Code de retour : 0 tout conforme · 1 un écart · 3 rien d'écarté mais un INCONNU.
etat() {
  local rc=0 nom v
  log "═══ Durcissement de $(hostname) — configuration EFFECTIVE ═══"
  [ "$(id -u)" -eq 0 ] || log "⚠️  Pas root : sshd -T, ufw et fail2ban-client ne répondent qu'à root → INCONNU."
  for nom in sshd ufw f2b apt sortant; do
    v=$("verdict_$nom")
    printf '  %-9s %s\n' "$nom" "$v"
    case "$v" in
      ECART:*)   rc=1 ;;
      INCONNU:*) [ "$rc" -eq 1 ] || rc=3 ;;
    esac
  done
  [ -e "$DURCISSEMENT_SSHD_HERITE" ] && log "  hérité    $DURCISSEMENT_SSHD_HERITE présent (lu APRÈS 50-cloud-init : sans effet) — --appliquer le retire"
  [ -e "$APT_HERITE" ] && log "  hérité    $APT_HERITE présent (s'ajoute aux origines Debian, ne restreint rien)"
  log "  clés      $(compter_cles || echo '?') clé(s) dans $CLES_AUTORISEES"
  log "  sorti hors liste en 24 h (nombre, destination, port, qui) :"
  durcissement_sortant_resume | sed 's/^/            /'
  return "$rc"
}

paquets() {
  local manquants="" p
  for p in ufw fail2ban unattended-upgrades; do
    dpkg -s "$p" >/dev/null 2>&1 || manquants="$manquants $p"
  done
  [ -z "$manquants" ] && return 0
  log "── paquets :$manquants"
  # shellcheck disable=SC2086  # liste de paquets, coupée exprès
  apt-get install -y $manquants >/dev/null || { log "   ÉCHEC de l'installation"; return 1; }
}

appliquer_sshd() {
  local decision
  log "── sshd"
  decision=$(durcissement_sshd_peut_appliquer "$(compter_cles)")
  if [ "$decision" != OUI ]; then
    log "   ${decision#REFUS:} → sshd NON modifié."
    log "   Poser d'abord la clé publique du poste dans $CLES_AUTORISEES, puis relancer."
    return 1
  fi
  durcissement_sshd_contenu | poser "$DURCISSEMENT_SSHD_FICHIER" 0644
  case $? in
    0) log "   $DURCISSEMENT_SSHD_FICHIER posé" ;;
    1) log "   $DURCISSEMENT_SSHD_FICHIER déjà à jour" ;;
    *) log "   ÉCHEC d'écriture"; return 1 ;;
  esac
  #  `sshd -t` est le seul contrôle qui dise si la configuration est acceptable
  #  AVANT que le rechargement ne la serve. Refusée → on retire ce qu'on a posé.
  if ! sshd -t; then
    rm -f "$DURCISSEMENT_SSHD_FICHIER"
    log "   🔴 sshd -t refuse la configuration : fichier RETIRÉ, sshd non rechargé."
    return 1
  fi
  if [ -e "$DURCISSEMENT_SSHD_HERITE" ]; then
    rm -f "$DURCISSEMENT_SSHD_HERITE" && log "   $DURCISSEMENT_SSHD_HERITE retiré (remplacé)"
    sshd -t || { log "   🔴 sshd -t refuse après le retrait — NE PAS fermer la session."; return 1; }
  fi
  #  `reload` garde les sessions ouvertes ; seules les nouvelles suivent la règle.
  systemctl reload ssh 2>/dev/null || systemctl reload sshd
  log "   effectif : $(verdict_sshd)"
}

appliquer_ufw() {
  local regle ajoutees decision
  log "── ufw"
  ufw default deny incoming >/dev/null
  ufw default allow outgoing >/dev/null
  #  Les manquantes, dans l'ordre de DURCISSEMENT_UFW : SSH du LAN d'abord.
  while IFS= read -r regle; do
    [ -n "$regle" ] || continue
    # shellcheck disable=SC2086  # la règle est une suite de mots ufw, coupée exprès
    ufw $regle >/dev/null && log "   ajoutée : $regle"
  done < <(durcissement_ufw_manquantes "$(lire_ufw_ajoutees)")
  ajoutees=$(lire_ufw_ajoutees)
  if ! grep -q '^Status: active' <<< "$(lire_ufw_etat)"; then
    decision=$(durcissement_ufw_peut_activer "$ajoutees")
    if [ "$decision" != OUI ]; then log "   ${decision#REFUS:} → ufw NON activé."; return 1; fi
    ufw --force enable >/dev/null && log "   activé"
  fi
  [ -z "$(durcissement_ufw_ssh_trop_ouvert "$ajoutees")" ] \
    || log "   ⚠️  règle SSH ouverte hors LAN — la retirer à la main (ufw status numbered, ufw delete N)"
  log "   effectif : $(verdict_ufw)"
}

#  La sortie (#2367). $1 = le mode voulu : constat | refus | ouvert ; vide → celui
#  que le nœud sert (`--appliquer` répare, il ne change pas de mode).
#  L'ordre protège le nœud : on ROUVRE d'abord, on FERME en dernier.
appliquer_sortant() {
  local voulu=${1:-} servi regle apres bloc droits decision soi actif
  log "── sortie (liste blanche, #2367)"
  servi=$(durcissement_sortant_mode "$(lire_ufw_etat)" "$(lire_ufw_ajoutees)")
  voulu=${voulu:-$servi}
  case "$voulu" in constat|refus|ouvert) ;; *) log "   mode inconnu : $voulu (constat, refus ou ouvert)"; return 1 ;; esac

  if [ "$voulu" = refus ]; then
    soi=$(role_of "$(hostname)")
    actif=$(tr -d '[:space:]' < "$REPO/.active" 2>/dev/null)
    decision=$(durcissement_sortant_peut_refuser "$(verdict_sortant)" "$(durcissement_sortant_resume)" \
      "$(durcissement_sortant_nuits_vertes "$(cat "$DURCISSEMENT_SORTANT_JOURNAL_AUDIT" 2>/dev/null)")" \
      "$actif" "$soi")
    [ "$decision" = OUI ] || { log "   ${decision#REFUS:} → sortie NON fermée."; return 1; }
  fi

  #  Rouvrir passe AVANT tout le reste : c'est le retour arrière.
  [ "$voulu" = refus ] || ufw default allow outgoing >/dev/null

  #  Les règles de l'hôte. Une règle ajoutée se place en fin de liste : derrière
  #  le constat, elle ne servirait à rien — il se retire, puis se repose en dernier.
  if [ -n "$(durcissement_sortant_manquantes "$(lire_ufw_ajoutees)")" ] || [ "$voulu" != constat ]; then
    ufw delete $DURCISSEMENT_UFW_SORTANT_CONSTAT >/dev/null 2>&1
  fi
  while IFS= read -r regle; do
    [ -n "$regle" ] || continue
    # shellcheck disable=SC2086  # la règle est une suite de mots ufw, coupée exprès
    ufw $regle comment "$DURCISSEMENT_UFW_SORTANT_COMMENTAIRE" >/dev/null && log "   ajoutée : $regle"
  done < <(durcissement_sortant_manquantes "$(lire_ufw_ajoutees)")
  if [ "$voulu" = constat ] && [ "$(durcissement_sortant_mode "" "$(lire_ufw_ajoutees)")" != constat ]; then
    # shellcheck disable=SC2086
    ufw $DURCISSEMENT_UFW_SORTANT_CONSTAT >/dev/null && log "   constat : $DURCISSEMENT_UFW_SORTANT_CONSTAT"
  fi

  #  Les conteneurs : le bloc DOCKER-USER d'after.rules, éprouvé AVANT d'être posé —
  #  un after.rules que iptables-restore refuse ferait échouer le rechargement d'ufw.
  bloc=""
  [ "$voulu" = ouvert ] || bloc=$(durcissement_sortant_bloc "$voulu")
  if [ -n "$bloc" ] && ! iptables-restore --test --noflush <<< "$bloc"; then
    log "   🔴 iptables-restore refuse le bloc DOCKER-USER : after.rules NON modifié."; return 1
  fi
  apres=$(durcissement_sortant_apres_regles "$(cat "$DURCISSEMENT_UFW_APRES")" "$bloc")
  droits=$(stat -c %a "$DURCISSEMENT_UFW_APRES" 2>/dev/null || echo 640)
  printf '%s\n' "$apres" | poser "$DURCISSEMENT_UFW_APRES" "$droits"
  case $? in
    0) if [ -n "$bloc" ]; then log "   $DURCISSEMENT_UFW_APRES : bloc DOCKER-USER posé ($voulu)"
       else log "   $DURCISSEMENT_UFW_APRES : bloc DOCKER-USER retiré"; fi ;;
    1) ;;
    *) log "   ÉCHEC d'écriture de $DURCISSEMENT_UFW_APRES"; return 1 ;;
  esac

  #  Fermer, en dernier.
  [ "$voulu" != refus ] || ufw default reject outgoing >/dev/null
  ufw reload >/dev/null || { log "   🔴 ufw reload a échoué — lire 'ufw status verbose' avant de fermer la session."; return 1; }
  #  Un bloc retiré n'est plus reconstruit par ufw : la chaîne garderait son refus.
  [ -n "$bloc" ] || iptables -F DOCKER-USER 2>/dev/null
  log "   effectif : $(verdict_sortant)"
}

appliquer_f2b() {
  log "── fail2ban"
  durcissement_f2b_contenu | poser "$DURCISSEMENT_F2B_FICHIER" 0644
  case $? in
    0) log "   $DURCISSEMENT_F2B_FICHIER posé" ;;
    1) log "   $DURCISSEMENT_F2B_FICHIER déjà à jour" ;;
    *) log "   ÉCHEC d'écriture"; return 1 ;;
  esac
  systemctl enable --now fail2ban >/dev/null 2>&1
  fail2ban-client reload >/dev/null 2>&1 || systemctl restart fail2ban
  local i; for i in 1 2 3 4 5; do [ "$(verdict_f2b)" = CONFORME ] && break; sleep 2; done
  log "   effectif : $(verdict_f2b)"
}

appliquer_apt() {
  log "── mises à jour automatiques"
  printf '%s\n' "$DURCISSEMENT_APT" | poser "$DURCISSEMENT_APT_FICHIER" 0644
  case $? in
    0) log "   $DURCISSEMENT_APT_FICHIER posé" ;;
    1) log "   $DURCISSEMENT_APT_FICHIER déjà à jour" ;;
    *) log "   ÉCHEC d'écriture"; return 1 ;;
  esac
  systemctl enable --now apt-daily.timer apt-daily-upgrade.timer >/dev/null 2>&1
  log "   effectif : $(verdict_apt)"
}

appliquer() {
  local rc=0
  [ "$(id -u)" -eq 0 ] || { log "--appliquer s'exécute en root (sudo bash $0 --appliquer)."; exit 2; }
  log "⚠️  sshd va être reconfiguré. Garder une SECONDE session SSH ouverte sur ce nœud,"
  log "    et vérifier qu'une nouvelle connexion par clé passe avant de la fermer."
  printf '    Continuer ? [oui/NON] '
  read -r reponse
  [ "$reponse" = oui ] || { log "Abandon."; exit 1; }
  paquets        || rc=1
  appliquer_sshd || rc=1
  appliquer_ufw  || rc=1
  appliquer_sortant || rc=1
  appliquer_f2b  || rc=1
  appliquer_apt  || rc=1
  log ""
  etat || rc=1
  return "$rc"
}

case "${1:-}" in
  --etat)      etat ;;
  --appliquer) appliquer ;;
  --sortant)
    [ -n "${2:-}" ] || { log "--sortant constat|refus|ouvert"; exit 2; }
    [ "$(id -u)" -eq 0 ] || { log "--sortant s'exécute en root (sudo bash $0 --sortant $2)."; exit 2; }
    appliquer_sortant "${2:-}" ;;
  *)           sed -n '3,12p' "$0"; exit 2 ;;
esac
