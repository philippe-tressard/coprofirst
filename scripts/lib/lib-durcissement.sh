#!/bin/bash
# =============================================================================
#  lib-durcissement.sh — Ce que le durcissement système d'un nœud doit DIRE,
#  et le jugement de ce qu'il dit réellement (#1917, #1918)
#
#  Module SOURCÉ par `scripts/installation/durcir-noeud.sh` (qui POSE) et par
#  `lib-ssh-mot-de-passe.sh` (C38 de `check-reliability.sh`, qui SURVEILLE en
#  continu, #1941), jamais exécuté : pas de bit x (`lib-*.sh` sont en 100644).
#  Son self-test, `durcissement_selftest`, est lancé par `durcir-noeud.sh
#  --selftest`, branché au job CI `test-scripts`.
#
#  ── POURQUOI ─────────────────────────────────────────────────────────────────
#
#  Le durcissement des deux nœuds (sshd, ufw, fail2ban, mises à jour
#  automatiques ; la sortie en liste blanche depuis #2367) n'avait pour seule trace qu'un script local d'avril 2026, jamais
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

#: La SORTIE en liste blanche (#2367) — source UNIQUE : les règles ufw de l'hôte,
#: la chaîne DOCKER-USER des conteneurs et le jugement de S5 s'en déduisent
#: (`lib-durcissement-sortant.sh`). Une ligne : `portée|règle|ce qui sort par là`.
#:   portée  `hote` : le nœud seul (OUTPUT) · `tous` : le nœud ET ses conteneurs
#:           (OUTPUT et DOCKER-USER — les conteneurs ne sortent pas par OUTPUT) ;
#:   règle   la forme CANONIQUE de `ufw show added`, sans `ufw ` : c'est elle que le
#:           jugement compare (ufw réécrit `allow out proto tcp to X port 22` en
#:           `allow out to X port 22 proto tcp`).
#: S'y ajoute, par `durcissement_sortant_regles`, une règle `tous` par nœud de
#: ROLE_TABLE (`lib-role.sh`) : le pair — SSH de la bascule, réplication
#: PostgreSQL (un conteneur), sondes HTTP du LAN.
#: ⚠️ ufw ne nomme pas un hôte : la liste est faite de PORTS, et 443 reste ouvert
#: vers tout — GitHub, Docker Hub, l'IA, WhatsApp n'ont pas d'adresses fixes. Ce
#: qu'elle ferme : tout autre port (un reverse shell sur 4444, un relais sur 25,
#: un tunnel SSH ailleurs que chez GitHub). Inventaire mesuré : issue #2367.
DURCISSEMENT_UFW_SORTANT="tous|allow out 53|DNS : les résolveurs que la box annonce (9.9.9.9, 1.1.1.2, la box)
hote|allow out 67/udp|DHCP : le renouvellement du bail auprès de la box (mesuré)
hote|allow out 123/udp|NTP : systemd-timesyncd, pool Debian
tous|allow out 80/tcp|apt en http (deb.debian.org, archive.raspberrypi.com) ; les apt-get des images construites en secours (#1758)
tous|allow out 443/tcp|HTTPS : ghcr.io et GitHub, Docker Hub, apt https (Docker, Cloudflare, NodeSource), sondes du site et DoH, IA, WhatsApp (mesuré), registre
hote|allow out 7844|tunnel Cloudflare : QUIC en udp (mesuré), http2 en tcp en repli
tous|allow out 587/tcp|SMTP d'OVH (MAIL_PORT) : courriels de l'API, alertes des scripts
tous|allow out 993/tcp|IMAP d'OVH : relève des réponses par courriel
hote|allow out to 140.82.112.0/20 port 22 proto tcp|git fetch par SSH (remote git@github.com) : plages « git » de api.github.com/meta
hote|allow out to 192.30.252.0/22 port 22 proto tcp|idem
hote|allow out to 185.199.108.0/22 port 22 proto tcp|idem
hote|allow out to 143.55.64.0/20 port 22 proto tcp|idem"

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

# ── sshd : ce que le nœud OFFRE réellement au client (C38, #1941) ────────────
#  `sshd -T` dit la configuration ; il faut root, et il ne dit rien d'un `Match`
#  qui ne s'appliquerait qu'au LAN. La sonde de `check-reliability.sh` demande la
#  méthode `none` (`ssh_noeud_sonde_auth_cmd`) : le serveur la refuse en NOMMANT
#  ce qu'il accepte — « Permission denied (publickey) ». C'est le comportement,
#  vu du client, sans rien tenter.
#: Les méthodes que coupent `PasswordAuthentication no` et
#: `KbdInteractiveAuthentication no` (DURCISSEMENT_SSHD), sous le nom que sshd
#: donne au client. `keyboard-interactive` porte le mot de passe par PAM.
DURCISSEMENT_SSH_METHODES_PROSCRITES="password keyboard-interactive"

#  $1 = ce qu'a écrit la sonde (stderr compris) → la liste des méthodes offertes
#  (« publickey,password »), vide si la réponse n'en porte pas.
durcissement_ssh_methodes_offertes() {
  printf '%s\n' "${1:-}" | sed -n 's/.*Permission denied (\([^)]*\)).*/\1/p' | tail -n 1
}

#  $1 = code de retour de la sonde (vide : non lancée) · $2 = ce qu'elle a écrit
durcissement_ssh_sonde_verdict() {
  local rc=${1:-} sortie=${2:-} offertes m proscrites=""
  #  La sonde exécute `true` : rendre 0, c'est être ENTRÉ sans s'authentifier.
  [ "$rc" = 0 ] && { echo "ECART:connexion acceptée sans aucune authentification"; return 0; }
  offertes=$(durcissement_ssh_methodes_offertes "$sortie")
  if [ -z "$offertes" ]; then
    case "$sortie" in
      '') echo "INCONNU:aucune réponse (code ${rc:-non lancée})" ;;
      *"Host key verification failed"*)
          echo "INCONNU:clé d'hôte non vérifiée — rien ne dit que c'est le nœud qui a répondu" ;;
      *)  echo "INCONNU:réponse sans liste de méthodes (code ${rc:-?}) : $(printf '%s' "$sortie" | tr '\n' ' ' | cut -c1-120)" ;;
    esac
    return 0
  fi
  for m in $DURCISSEMENT_SSH_METHODES_PROSCRITES; do
    case ",$offertes," in *",$m,"*) proscrites="$proscrites${proscrites:+,}$m" ;; esac
  done
  if [ -n "$proscrites" ]; then echo "ECART:$proscrites offert (méthodes : $offertes)"; else echo CONFORME; fi
}

#  Couper le mot de passe sans clé autorisée enferme dehors : un nœud fraîchement
#  flashé n'a parfois QUE le mot de passe choisi dans Raspberry Pi Imager.
#  $1 = nombre de clés publiques dans authorized_keys du compte d'exploitation
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
#  Les règles SORTANTES n'ouvrent rien à l'entrée : `allow out to <GitHub> port 22`
#  (git, #2367) était lue « SSH hors LAN » ; elles se jugent dans lib-durcissement-sortant.
#  $1 = sortie de `ufw show added` → les règles fautives, une par ligne
durcissement_ufw_ssh_trop_ouvert() {
  durcissement_ufw_normaliser "${1:-}" \
    | grep -vE '^[a-z]+ out( |$)' \
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

# ── Les lectures de l'état EFFECTIF (effets de bord : lecture seule, root) ───
#  Vides si impossibles : le verdict dit alors INCONNU. Partagées par
#  `durcir-noeud.sh` (--etat, --appliquer) et par l'audit de sécurité nocturne
#  (`audit-securite.sh`, S5) : une seule lecture de chaque configuration servie.
durcissement_lire_sshd()         { sshd -T 2>/dev/null; }
durcissement_lire_ufw_etat()     { command -v ufw >/dev/null && ufw status verbose 2>/dev/null; }
durcissement_lire_ufw_ajoutees() { command -v ufw >/dev/null && ufw show added 2>/dev/null; }
durcissement_lire_f2b()          { command -v fail2ban-client >/dev/null && fail2ban-client get sshd "$1" 2>/dev/null; }
#  Le nombre d'adresses BANNIES à l'instant par la prison sshd (vide : muet) —
#  un chiffre d'activité, pas un verdict : il se lit dans la ligne de S5.
durcissement_lire_f2b_bannies()  {
  command -v fail2ban-client >/dev/null && fail2ban-client status sshd 2>/dev/null \
    | sed -n 's/.*Currently banned:[[:space:]]*\([0-9]*\).*/\1/p'
}

#  La sortie (#2367) : ses décisions et ses lectures vivent à part — ce module
#  passerait sinon les 500 lignes.
# shellcheck source=lib-durcissement-sortant.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib-durcissement-sortant.sh"

durcissement_etat_sshd() { durcissement_sshd_verdict "$(durcissement_lire_sshd)"; }
durcissement_etat_ufw()  { durcissement_ufw_verdict "$(durcissement_lire_ufw_etat)" "$(durcissement_lire_ufw_ajoutees)"; }
durcissement_etat_f2b()  { durcissement_f2b_verdict "$(durcissement_lire_f2b maxretry)" "$(durcissement_lire_f2b bantime)"; }
durcissement_etat_apt()  {
  local dump rc
  dump=$(apt-config dump 2>/dev/null); rc=$?
  durcissement_apt_verdict "$rc" "$dump"
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
  #  C38 — la sonde, telle que ssh l'écrit (rc 255 : refusé).
  local P="compte@10.0.0.2: Permission denied"
  v "sonde : publickey seul (les deux nœuds depuis le 14/10)" CONFORME \
    "$(durcissement_ssh_sonde_verdict 255 "$P (publickey).")"
  v "sonde : publickey et GSSAPI" CONFORME \
    "$(durcissement_ssh_sonde_verdict 255 "$P (publickey,gssapi-keyex,gssapi-with-mic).")"
  #  LA FAUTE INJECTÉE : les deux nœuds d'avril à octobre 2026 (#1918).
  v "sonde : publickey,password (#1918)" ECART \
    "$(durcissement_ssh_sonde_verdict 255 "$P (publickey,password).")"
  v "sonde : mot de passe par PAM" ECART \
    "$(durcissement_ssh_sonde_verdict 255 "$P (publickey,keyboard-interactive).")"
  v "sonde : password en premier" ECART "$(durcissement_ssh_sonde_verdict 255 "$P (password,publickey).")"
  v "sonde : entrée sans authentification" ECART "$(durcissement_ssh_sonde_verdict 0 "")"
  v "sonde : bannière avant le refus" CONFORME "$(durcissement_ssh_sonde_verdict 255 "Avis : accès réservé.
$P (publickey).")"
  v "sonde : « passwordless » n'est pas password" CONFORME \
    "$(durcissement_ssh_sonde_verdict 255 "$P (publickey,passwordless).")"
  #  LE CAS ZÉRO : ni réponse ni liste → jamais CONFORME.
  v "sonde : aucune réponse" INCONNU "$(durcissement_ssh_sonde_verdict 124 "")"
  v "sonde : non lancée" INCONNU "$(durcissement_ssh_sonde_verdict "" "")"
  v "sonde : nœud injoignable" INCONNU \
    "$(durcissement_ssh_sonde_verdict 255 "ssh: connect to host 10.0.0.2 port 22: Connection timed out")"
  v "sonde : clé d'hôte inconnue" INCONNU \
    "$(durcissement_ssh_sonde_verdict 255 "Host key verification failed.")"
  v "sonde : méthodes lues" "publickey,password" \
    "$(durcissement_ssh_methodes_offertes "$P (publickey,password).")"

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
ufw allow 80/tcp comment 'web'
ufw allow 443/tcp comment 'web chiffré'
ufw allow 443/udp comment 'quic'"
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
  #  rpi2 le 01/11/2026, sortie en constat (#2367) : la règle SORTANTE vers GitHub
  #  sur le port 22 a été lue « SSH ouvert hors LAN » — l'audit l'aurait dit FAIL.
  v "ufw : règle SORTANTE vers le port 22 (git, #2367)" CONFORME "$(durcissement_ufw_verdict "$S_ACTIF" "$U_RPI2
ufw allow out to 140.82.112.0/20 port 22 proto tcp comment 'sortie 2367'
ufw allow out to 192.168.1.222 comment 'sortie 2367'
ufw allow out log to any")"
  v "ufw : 'allow in 22/tcp' reste vu" ECART "$(durcissement_ufw_verdict "$S_ACTIF" "$U_RPI1
ufw allow in 22/tcp")"
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

  #  La lecture du compte des bannies, sur la sortie réelle de fail2ban-client.
  v "fail2ban : adresses bannies lues" 3 "$(fail2ban-client() { printf 'Status for the jail: sshd\n|- Filter\n|  |- Currently failed:\t1\n`- Actions\n   |- Currently banned:\t3\n   |- Total banned:\t42\n'; }; durcissement_lire_f2b_bannies; unset -f fail2ban-client)"

  # shellcheck source=lib-durcissement-sortant.selftest.sh
  . "$(dirname "${BASH_SOURCE[0]}")/lib-durcissement-sortant.selftest.sh"
  durcissement_sortant_selftest || st=1

  [ "$st" -eq 0 ] && echo "lib-durcissement : tous les cas passent."
  return "$st"
}
