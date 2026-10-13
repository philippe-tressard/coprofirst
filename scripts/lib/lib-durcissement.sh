#!/bin/bash
# =============================================================================
#  lib-durcissement.sh — Ce que le durcissement système d'un nœud doit DIRE,
#  et le jugement de ce qu'il dit réellement (#1917, #1918)
#
#  Module SOURCÉ par `scripts/installation/durcir-noeud.sh`, jamais exécuté :
#  pas de bit x (`lib-*.sh` sont en 100644). Son self-test, `durcissement_selftest`,
#  est lancé par `durcir-noeud.sh --selftest`, branché au job CI `test-scripts`.
#
#  ── POURQUOI ─────────────────────────────────────────────────────────────────
#
#  Le durcissement des deux nœuds (sshd, ufw, fail2ban, mises à jour
#  automatiques) n'avait pour seule trace qu'un script local d'avril 2026, jamais
#  versionné, et des blocs à recopier dans `docs/restauration-complete.md` — où
#  sshd ne figurait pas. Confronté aux nœuds le 13/10/2026, il s'est révélé
#  SANS EFFET sur le point qui compte : `PasswordAuthentication no` était écrit
#  dans `hardening.conf`, mais `50-cloud-init.conf` (posé par l'image Raspberry
#  Pi OS) dit `yes` et passe avant lui dans l'ordre alphabétique. sshd retient
#  la PREMIÈRE valeur lue : les deux nœuds acceptaient le mot de passe depuis
#  six mois, et rien ne le voyait, parce que ce qu'on regardait était le
#  FICHIER posé, pas la configuration servie (#1918).
#
#  D'où les deux règles de ce module :
#    1. le fichier de durcissement sshd se nomme `01-…` : il se lit en premier ;
#    2. chaque jugement porte sur la configuration EFFECTIVE (`sshd -T`,
#       `ufw show added`, `fail2ban-client get`, `apt-config dump`), jamais sur
#       un fichier — et une lecture vide rend INCONNU, jamais CONFORME.
#
#  Fonctions PURES : elles reçoivent un texte et rendent un verdict, sans rien
#  lire ni écrire. Les verdicts :
#    CONFORME · ECART:<ce qui manque> · INCONNU:<pourquoi>
# =============================================================================

#: Réseau local d'où SSH est admis. Le port 22 n'est JAMAIS ouvert au-delà :
#: l'administration passe par le LAN, le public par le tunnel Cloudflare.
DURCISSEMENT_LAN="192.168.1.0/24"

#: Le fichier de durcissement sshd. Préfixe `01-` : sshd lit `sshd_config.d/*.conf`
#: par ordre alphabétique et retient la PREMIÈRE valeur de chaque mot-clé —
#: `50-cloud-init.conf` l'emportait sur `hardening.conf` (#1918).
DURCISSEMENT_SSHD_FICHIER=/etc/ssh/sshd_config.d/01-hostachy-durcissement.conf
#: L'ancien fichier (avril 2026) : mêmes valeurs, mais lu APRÈS 50-cloud-init.
#: Il est retiré une fois le nouveau validé — deux sources d'une même règle
#: finissent par diverger.
DURCISSEMENT_SSHD_HERITE=/etc/ssh/sshd_config.d/hardening.conf

#: Les réglages sshd voulus — source UNIQUE : le fichier posé s'en déduit, et le
#: jugement aussi (en minuscules, comme `sshd -T` les écrit).
DURCISSEMENT_SSHD="PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
X11Forwarding no
MaxAuthTries 3"

#: Les règles ufw voulues, dans l'ORDRE où elles se posent : SSH du LAN d'abord,
#: pour qu'aucune activation ne coupe la session qui administre.
DURCISSEMENT_UFW="allow from $DURCISSEMENT_LAN to any port 22 proto tcp
allow 80/tcp
allow 443/tcp
allow 443/udp"

#: fail2ban sur sshd : 5 essais, 1 h de bannissement — ce qui tourne depuis
#: avril sur les deux nœuds. `bantime` se lit en secondes chez fail2ban-client.
DURCISSEMENT_F2B_MAXRETRY=5
DURCISSEMENT_F2B_BANTIME=3600
DURCISSEMENT_F2B_FICHIER=/etc/fail2ban/jail.d/5hostachy.conf

#: Mises à jour automatiques : listes ET installation chaque jour. Les ORIGINES
#: restent celles de `50unattended-upgrades` de Debian (Debian + sécurité), à
#: l'identique sur les deux nœuds ; le noyau et le firmware Raspberry Pi n'y sont
#: pas — C30 le dit, la mise à jour reste manuelle (skill infra-rpi).
DURCISSEMENT_APT_FICHIER=/etc/apt/apt.conf.d/20auto-upgrades
DURCISSEMENT_APT='APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";'

# ── Contenus à poser ─────────────────────────────────────────────────────────
durcissement_sshd_contenu() {
  printf '%s\n' "# Posé par scripts/installation/durcir-noeud.sh (#1917) — ne pas éditer à la main."
  printf '%s\n' "# Préfixe 01 : lu AVANT 50-cloud-init.conf, sinon ses valeurs l'emportent (#1918)."
  printf '%s\n' "$DURCISSEMENT_SSHD"
}

durcissement_f2b_contenu() {
  printf '%s\n' "# Posé par scripts/installation/durcir-noeud.sh (#1917)." \
    "[sshd]" "enabled  = true" "port     = ssh" \
    "maxretry = $DURCISSEMENT_F2B_MAXRETRY" "bantime  = $DURCISSEMENT_F2B_BANTIME"
}

# ── sshd : la configuration SERVIE ───────────────────────────────────────────
#  $1 = sortie de `sshd -T` (vide si la lecture a échoué)
durcissement_sshd_verdict() {
  local effectif=${1:-} ecarts="" ligne cle voulu lu
  [ -n "$effectif" ] || { echo "INCONNU:sshd -T illisible (root requis)"; return 0; }
  while IFS= read -r ligne; do
    [ -n "$ligne" ] || continue
    cle=$(printf '%s' "${ligne%% *}" | tr '[:upper:]' '[:lower:]')
    voulu=${ligne#* }
    lu=$(printf '%s\n' "$effectif" | awk -v k="$cle" 'tolower($1)==k {print $2; exit}')
    [ "$lu" = "$voulu" ] || ecarts="$ecarts ${cle}=${lu:-absent}(voulu ${voulu})"
  done <<< "$DURCISSEMENT_SSHD"
  if [ -n "$ecarts" ]; then echo "ECART:${ecarts# }"; else echo CONFORME; fi
}

#  Couper le mot de passe sans clé autorisée enferme dehors : un nœud fraîchement
#  flashé n'a parfois QUE le mot de passe choisi dans Raspberry Pi Imager.
#  $1 = nombre de clés publiques dans ~ptressard/.ssh/authorized_keys
durcissement_sshd_peut_appliquer() {
  case "${1:-}" in
    ''|*[!0-9]*) echo "REFUS:clés autorisées illisibles — on ne coupe pas le mot de passe à l'aveugle" ;;
    0)           echo "REFUS:aucune clé dans authorized_keys — couper le mot de passe fermerait le nœud" ;;
    *)           echo OUI ;;
  esac
}

# ── ufw ──────────────────────────────────────────────────────────────────────
#  Normalise `ufw show added` : une règle par ligne, sans le `ufw ` de tête ni le
#  commentaire (rpi1 a ses règles sans commentaire, rpi2 avec : même règle).
durcissement_ufw_normaliser() {
  printf '%s\n' "${1:-}" | sed -n "s/^ufw //p" | sed "s/ comment '.*'\$//; s/[[:space:]]*\$//"
}

#  $1 = sortie de `ufw show added` → les règles voulues absentes, une par ligne
durcissement_ufw_manquantes() {
  local posees regle
  posees=$(durcissement_ufw_normaliser "${1:-}")
  while IFS= read -r regle; do
    grep -qxF -- "$regle" <<< "$posees" || printf '%s\n' "$regle"
  done <<< "$DURCISSEMENT_UFW"
}

#  Une règle qui ouvre SSH au-delà du LAN (`allow 22`, `allow ssh`, `limit 22/tcp`…).
#  $1 = sortie de `ufw show added` → les règles fautives, une par ligne
durcissement_ufw_ssh_trop_ouvert() {
  durcissement_ufw_normaliser "${1:-}" \
    | grep -E '^(allow|limit)( in)?( .*)? (22(/tcp)?|ssh|OpenSSH)( |$)' \
    | grep -vF "from $DURCISSEMENT_LAN " || true
}

#  Activer ufw sans la règle SSH du LAN couperait la session qui l'active.
#  $1 = sortie de `ufw show added`
#  ⚠️ Jamais `manquantes | grep -q` : grep -q sort au premier motif, l'écrivain
#  prend SIGPIPE et, sous le `pipefail` de durcir-noeud.sh, le tube rend 141 —
#  le refus devenait un OUI (pris par le self-test). On lit, puis on juge : un
#  here-string n'a pas d'écrivain à tuer.
durcissement_ufw_peut_activer() {
  if grep -q 'port 22' <<< "$(durcissement_ufw_manquantes "${1:-}")"; then
    echo "REFUS:la règle SSH du LAN n'est pas posée — activer ufw couperait l'accès"
  else
    echo OUI
  fi
}

#  $1 = sortie de `ufw status verbose` · $2 = sortie de `ufw show added`
durcissement_ufw_verdict() {
  local etat=${1:-} ajoutees=${2:-} ecarts="" m t
  [ -n "$etat" ] || { echo "INCONNU:ufw illisible (absent, ou root requis)"; return 0; }
  grep -q '^Status: active' <<< "$etat" || ecarts="$ecarts inactif;"
  grep -q 'deny (incoming)' <<< "$etat" || ecarts="$ecarts entrant-non-refusé-par-défaut;"
  m=$(durcissement_ufw_manquantes "$ajoutees" | paste -sd ',' -)
  [ -z "$m" ] || ecarts="$ecarts manquantes=[$m];"
  t=$(durcissement_ufw_ssh_trop_ouvert "$ajoutees" | paste -sd ',' -)
  [ -z "$t" ] || ecarts="$ecarts ssh-hors-LAN=[$t];"
  if [ -n "$ecarts" ]; then echo "ECART:${ecarts# }"; else echo CONFORME; fi
}

# ── fail2ban ─────────────────────────────────────────────────────────────────
#  $1 = `fail2ban-client get sshd maxretry` · $2 = `… get sshd bantime`
#  (vides si la prison n'existe pas ou si le service ne répond pas)
durcissement_f2b_verdict() {
  local essais=${1:-} duree=${2:-}
  [ -n "$essais$duree" ] || { echo "INCONNU:prison sshd absente ou fail2ban muet"; return 0; }
  if [ "$essais" = "$DURCISSEMENT_F2B_MAXRETRY" ] && [ "$duree" = "$DURCISSEMENT_F2B_BANTIME" ]; then
    echo CONFORME
  else
    echo "ECART:maxretry=${essais:-?}(voulu $DURCISSEMENT_F2B_MAXRETRY) bantime=${duree:-?}(voulu $DURCISSEMENT_F2B_BANTIME)"
  fi
}

# ── Mises à jour automatiques ────────────────────────────────────────────────
#  $1 = code de retour d'`apt-config dump` · $2 = sa sortie
#  Un fichier mal formé fait ÉCHOUER apt-config — c'est l'incident d'avril à
#  septembre 2026 sur rpi2 (cinq mois sans correctif, `apt-daily` « réussi »).
durcissement_apt_verdict() {
  local rc=${1:-} dump=${2:-} ligne ecarts=""
  [ "$rc" = 0 ] || { echo "ECART:configuration apt illisible (apt-config dump rend $rc)"; return 0; }
  [ -n "$dump" ] || { echo "INCONNU:apt-config dump muet"; return 0; }
  while IFS= read -r ligne; do
    grep -qxF -- "$ligne" <<< "$dump" || ecarts="$ecarts ${ligne%% *}"
  done <<< "$DURCISSEMENT_APT"
  if [ -n "$ecarts" ]; then echo "ECART:absent ou différent :${ecarts}"; else echo CONFORME; fi
}

# ── Self-test ────────────────────────────────────────────────────────────────
durcissement_selftest() {
  local st=0
  v() {  # $1 libellé · $2 verdict attendu (préfixe) · $3 obtenu
    if [ "${3%%:*}" = "$2" ]; then echo "PASS  $1 → ${3%%:*}"
    else echo "FAIL  $1  attendu=$2 obtenu=$3"; st=1; fi
  }
  echo "== self-test lib-durcissement =="

  local T_OK="port 22
permitrootlogin no
maxauthtries 3
kbdinteractiveauthentication no
passwordauthentication no
x11forwarding no"
  v "sshd : configuration servie conforme" CONFORME "$(durcissement_sshd_verdict "$T_OK")"
  #  Le cas du 13/10/2026 : hardening.conf disait no, sshd servait yes.
  v "sshd : mot de passe servi (#1918)" ECART \
    "$(durcissement_sshd_verdict "${T_OK/passwordauthentication no/passwordauthentication yes}")"
  v "sshd : X11 servi" ECART "$(durcissement_sshd_verdict "${T_OK/x11forwarding no/x11forwarding yes}")"
  v "sshd : clé absente de la sortie" ECART "$(durcissement_sshd_verdict "${T_OK/maxauthtries 3/}")"
  #  LE CAS ZÉRO : une lecture qui échoue ne dit pas « conforme ».
  v "sshd : sshd -T illisible" INCONNU "$(durcissement_sshd_verdict "")"
  v "sshd : contenu posé = réglages voulus" CONFORME \
    "$(durcissement_sshd_verdict "$(durcissement_sshd_contenu | grep -v '^#' | tr '[:upper:]' '[:lower:]')")"
  v "sshd : fichier lu avant 50-cloud-init" CONFORME \
    "$( [[ "${DURCISSEMENT_SSHD_FICHIER##*/}" < "50-cloud-init.conf" ]] && echo CONFORME || echo ECART)"
  v "sshd : 2 clés autorisées" OUI   "$(durcissement_sshd_peut_appliquer 2)"
  v "sshd : aucune clé autorisée" REFUS "$(durcissement_sshd_peut_appliquer 0)"
  v "sshd : clés illisibles" REFUS "$(durcissement_sshd_peut_appliquer "")"

  #  rpi1 : règles sans commentaire, SSH en dernier ; rpi2 : avec, SSH en premier.
  local U_RPI1="Added user rules (see 'ufw status' for running firewall):
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw allow from 192.168.1.0/24 to any port 22 proto tcp"
  local U_RPI2="Added user rules (see 'ufw status' for running firewall):
ufw allow from 192.168.1.0/24 to any port 22 proto tcp comment 'SSH LAN only'
ufw allow 80/tcp comment 'HTTP Caddy'
ufw allow 443/tcp comment 'HTTPS'
ufw allow 443/udp comment 'QUIC/HTTP3'"
  local S_ACTIF="Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), deny (routed)"
  v "ufw : rpi1 tel qu'en production" CONFORME "$(durcissement_ufw_verdict "$S_ACTIF" "$U_RPI1")"
  v "ufw : rpi2 tel qu'en production" CONFORME "$(durcissement_ufw_verdict "$S_ACTIF" "$U_RPI2")"
  v "ufw : inactif" ECART "$(durcissement_ufw_verdict "Status: inactive" "$U_RPI2")"
  v "ufw : entrant accepté par défaut" ECART \
    "$(durcissement_ufw_verdict "${S_ACTIF/deny (incoming)/allow (incoming)}" "$U_RPI2")"
  v "ufw : 443/udp manquante" ECART "$(durcissement_ufw_verdict "$S_ACTIF" "${U_RPI1/ufw allow 443\/udp/}")"
  v "ufw : SSH ouvert à tous" ECART "$(durcissement_ufw_verdict "$S_ACTIF" "$U_RPI1
ufw allow 22/tcp")"
  v "ufw : 'allow ssh' ouvert à tous" ECART "$(durcissement_ufw_verdict "$S_ACTIF" "$U_RPI1
ufw allow OpenSSH")"
  v "ufw : 2222/tcp n'est pas SSH" CONFORME "$(durcissement_ufw_verdict "$S_ACTIF" "$U_RPI1
ufw allow 2222/tcp")"
  v "ufw : illisible" INCONNU "$(durcissement_ufw_verdict "" "")"
  v "ufw : nœud neuf, activer sans règle SSH" REFUS "$(durcissement_ufw_peut_activer "")"
  v "ufw : règle SSH posée, activer" OUI "$(durcissement_ufw_peut_activer "ufw allow from 192.168.1.0/24 to any port 22 proto tcp")"
  v "ufw : nœud neuf, tout est à poser" CONFORME \
    "$( [ "$(durcissement_ufw_manquantes "" | wc -l)" -eq 4 ] && echo CONFORME || echo ECART)"
  v "ufw : SSH posée en PREMIER" CONFORME \
    "$( [[ "$(durcissement_ufw_manquantes "")" == "allow from "*"port 22"* ]] && echo CONFORME || echo ECART)"

  v "fail2ban : 5 essais, 1 h" CONFORME "$(durcissement_f2b_verdict 5 3600)"
  v "fail2ban : 10 essais" ECART "$(durcissement_f2b_verdict 10 3600)"
  v "fail2ban : prison absente" INCONNU "$(durcissement_f2b_verdict "" "")"

  local A_OK='APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Install-Recommends "0";'
  v "apt : mises à jour quotidiennes" CONFORME "$(durcissement_apt_verdict 0 "$A_OK")"
  v "apt : installation coupée" ECART "$(durcissement_apt_verdict 0 "${A_OK/Upgrade \"1\"/Upgrade \"0\"}")"
  #  rpi2, avril → septembre 2026 : `" 1\;` dans 20auto-upgrades.
  v "apt : fichier mal formé" ECART "$(durcissement_apt_verdict 100 "")"
  v "apt : dump muet" INCONNU "$(durcissement_apt_verdict 0 "")"

  [ "$st" -eq 0 ] && echo "lib-durcissement : tous les cas passent."
  return "$st"
}
