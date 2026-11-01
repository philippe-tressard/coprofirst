#!/bin/bash
# =============================================================================
#  lib-durcissement-sortant.selftest.sh — le self-test de la sortie en liste
#  blanche (#2367), à part : avec lui, lib-durcissement-sortant.sh passait les
#  500 lignes. SOURCÉ par `durcissement_selftest` (`durcir-noeud.sh --selftest`,
#  job CI `test-scripts`), jamais exécuté.
# =============================================================================
#  Les sorties sont RÉELLES : `ufw show added`, `ufw status verbose` et
#  `iptables -S DOCKER-USER` d'un banc ufw 0.36.2-9 (Debian 13, la version des
#  nœuds) où `durcir-noeud.sh --sortant` a posé la liste, le 01/11/2026 ;
#  `iptables -S FORWARD` et DOCKER-USER vide relevés sur rpi2 le même jour.
durcissement_sortant_selftest() {
  local st=0 r x
  v() {  # $1 libellé · $2 verdict attendu (préfixe, ou valeur exacte) · $3 obtenu
    if [ "${3%%:*}" = "$2" ] || [ "$3" = "$2" ]; then echo "PASS  $1 → ${3%%:*}"
    else echo "FAIL  $1  attendu=$2 obtenu=$3"; st=1; fi
  }
  echo "== self-test lib-durcissement-sortant =="

  local ENTRANT="Added user rules (see 'ufw status' for running firewall):
ufw allow from 192.168.1.0/24 to any port 22 proto tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp"
  local L53="ufw allow out 53 comment 'sortie 2367'"
  local L993="ufw allow out 993/tcp comment 'sortie 2367'"
  local LISTE="$L53
ufw allow out 67/udp comment 'sortie 2367'
ufw allow out 123/udp comment 'sortie 2367'
ufw allow out 80/tcp comment 'sortie 2367'
ufw allow out 443/tcp comment 'sortie 2367'
ufw allow out 7844 comment 'sortie 2367'
ufw allow out 587/tcp comment 'sortie 2367'
$L993
ufw allow out to 140.82.112.0/20 port 22 proto tcp comment 'sortie 2367'
ufw allow out to 192.30.252.0/22 port 22 proto tcp comment 'sortie 2367'
ufw allow out to 185.199.108.0/22 port 22 proto tcp comment 'sortie 2367'
ufw allow out to 143.55.64.0/20 port 22 proto tcp comment 'sortie 2367'
ufw allow out to 192.168.1.222 comment 'sortie 2367'
ufw allow out to 192.168.1.223 comment 'sortie 2367'"
  local A_CONSTAT="$ENTRANT
$LISTE
ufw allow out log to any"
  local A_REFUS="$ENTRANT
$LISTE"
  local S_OUVERT="Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), deny (routed)
New profiles: skip"
  local S_REFUS="${S_OUVERT/allow (outgoing)/reject (outgoing)}"
  local FW="-P FORWARD DROP
-A FORWARD -j DOCKER-USER
-A FORWARD -j DOCKER-FORWARD
-A FORWARD -j ufw-before-logging-forward
-A FORWARD -j ufw-before-forward"
  local DU_VIDE="-N DOCKER-USER"
  local DU_TETE='-N DOCKER-USER
-A DOCKER-USER -o br-+ -j RETURN
-A DOCKER-USER -o docker0 -j RETURN
-A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
-A DOCKER-USER -p tcp -m tcp --dport 53 -j RETURN
-A DOCKER-USER -p udp -m udp --dport 53 -j RETURN
-A DOCKER-USER -p tcp -m tcp --dport 80 -j RETURN
-A DOCKER-USER -p tcp -m tcp --dport 443 -j RETURN
-A DOCKER-USER -p tcp -m tcp --dport 587 -j RETURN
-A DOCKER-USER -p tcp -m tcp --dport 993 -j RETURN
-A DOCKER-USER -d 192.168.1.222/32 -j RETURN
-A DOCKER-USER -d 192.168.1.223/32 -j RETURN
-A DOCKER-USER -m conntrack --ctstate NEW -m limit --limit 3/min --limit-burst 10 -j LOG --log-prefix "[SORTANT CONTENEUR] "'
  local DU_CONSTAT="$DU_TETE
-A DOCKER-USER -j RETURN"
  local DU_REFUS="$DU_TETE
-A DOCKER-USER -j REJECT --reject-with icmp-port-unreachable"

  #  La liste elle-même : chaque règle se traduit, le bloc est en ASCII.
  r=$(while IFS= read -r x; do durcissement_sortant_iptables_de "$x"; done < <(durcissement_sortant_regles hote) | grep -c '^?')
  v "liste : chaque règle se traduit pour iptables" 0 "$r"
  v "liste : forme inconnue refusée" "?" "$(durcissement_sortant_iptables_de "allow out from any port 4444" | cut -c1)"
  v "liste : bloc after.rules en ASCII (ufw plante sinon)" 0 \
    "$(durcissement_sortant_bloc refus | LC_ALL=C grep -c '[^ -~]')"
  v "liste : le pair est déclaré (ROLE_TABLE)" 2 \
    "$(durcissement_sortant_regles conteneurs | grep -c '^allow out to 192\.168\.1\.22[23]$')"
  v "liste : git par SSH réservé à l'hôte" 0 "$(durcissement_sortant_regles conteneurs | grep -c 'port 22')"
  v "liste : DOCKER-USER attendu = banc (constat)" OUI \
    "$( [ "$(durcissement_sortant_docker_user constat)" = "$(grep '^-A' <<< "$DU_CONSTAT")" ] && echo OUI || echo NON)"

  #  Les modes.
  v "mode : production du 01/11 (ouvert)" ouvert "$(durcissement_sortant_mode "$S_OUVERT" "$ENTRANT")"
  v "mode : constat" constat "$(durcissement_sortant_mode "$S_OUVERT" "$A_CONSTAT")"
  v "mode : refus" refus "$(durcissement_sortant_mode "$S_REFUS" "$A_REFUS")"
  v "mode : deny vaut refus" refus "$(durcissement_sortant_mode "${S_OUVERT/allow (outgoing)/deny (outgoing)}" "$A_REFUS")"

  #  Le verdict — la production du 01/11/2026, puis chaque mode.
  v "verdict : les deux nœuds au 01/11 (ouvert)" OUVERT \
    "$(durcissement_sortant_verdict "$S_OUVERT" "$ENTRANT" "$DU_VIDE" "$FW")"
  v "verdict : constat complet" "CONSTAT:" "$(durcissement_sortant_verdict "$S_OUVERT" "$A_CONSTAT" "$DU_CONSTAT" "$FW")"
  r=$(durcissement_sortant_verdict "$S_OUVERT" "$(grep -vxF "$L993" <<< "$A_CONSTAT")" "$DU_CONSTAT" "$FW")
  v "verdict : constat, une règle manquante" OUI "$( [[ $r == *"manquantes=[allow out 993/tcp]"* ]] && echo OUI || echo "$r")"
  r=$(durcissement_sortant_verdict "$S_OUVERT" "$A_CONSTAT" "$DU_VIDE" "$FW")
  v "verdict : constat sans DOCKER-USER (bloc absent)" OUI "$( [[ $r == *conteneurs-non-journalisés* ]] && echo OUI || echo "$r")"
  v "verdict : refus servi" CONFORME "$(durcissement_sortant_verdict "$S_REFUS" "$A_REFUS" "$DU_REFUS" "$FW")"
  v "verdict : refus, Docker a laissé un RETURN derrière" CONFORME \
    "$(durcissement_sortant_verdict "$S_REFUS" "$A_REFUS" "$DU_REFUS
-A DOCKER-USER -j RETURN" "$FW")"
  #  LES FAUTES INJECTÉES.
  v "faute : allow out to any (hôte ouvert à tout)" ECART \
    "$(durcissement_sortant_verdict "$S_REFUS" "$A_REFUS
ufw allow out to any" "$DU_REFUS" "$FW")"
  v "faute : un port ajouté à la main" ECART \
    "$(durcissement_sortant_verdict "$S_REFUS" "$A_REFUS
ufw allow out 4444/tcp" "$DU_REFUS" "$FW")"
  v "faute : le constat laissé en mode refus" ECART "$(durcissement_sortant_verdict "$S_REFUS" "$A_CONSTAT" "$DU_REFUS" "$FW")"
  v "faute : refus, conteneurs en constat" ECART "$(durcissement_sortant_verdict "$S_REFUS" "$A_REFUS" "$DU_CONSTAT" "$FW")"
  v "faute : refus, une acceptation ajoutée à DOCKER-USER" ECART \
    "$(durcissement_sortant_verdict "$S_REFUS" "$A_REFUS" "$DU_REFUS
-A DOCKER-USER -j ACCEPT" "$FW")"
  v "faute : refus, Docker passé devant DOCKER-USER" ECART \
    "$(durcissement_sortant_verdict "$S_REFUS" "$A_REFUS" "$DU_REFUS" "$(grep -vxF -- '-A FORWARD -j DOCKER-USER' <<< "$FW")")"
  v "faute : refus, une règle manquante" ECART \
    "$(durcissement_sortant_verdict "$S_REFUS" "$(grep -vxF "$L53" <<< "$A_REFUS")" "$DU_REFUS" "$FW")"
  v "faute : retour arrière inachevé (conteneurs refusés)" ECART \
    "$(durcissement_sortant_verdict "$S_OUVERT" "$A_REFUS" "$DU_REFUS" "$FW")"
  v "un deny out ne se juge pas hors liste" "CONSTAT:" "$(durcissement_sortant_verdict "$S_OUVERT" "$A_CONSTAT
ufw deny out 25/tcp" "$DU_CONSTAT" "$FW")"
  #  LE CAS ZÉRO.
  v "zéro : ufw illisible" INCONNU "$(durcissement_sortant_verdict "" "" "" "")"
  v "zéro : refus, iptables illisible" INCONNU "$(durcissement_sortant_verdict "$S_REFUS" "$A_REFUS" "" "")"
  v "zéro : ufw inactif" OUVERT "$(durcissement_sortant_verdict "Status: inactive" "$A_REFUS" "" "")"

  #  after.rules : posé, reposé à l'identique, remplacé, retiré.
  local APRES="# fin d'after.rules
*filter
COMMIT" a1 a2
  a1=$(durcissement_sortant_apres_regles "$APRES" "$(durcissement_sortant_bloc constat)")
  a2=$(durcissement_sortant_apres_regles "$a1" "$(durcissement_sortant_bloc constat)")
  v "after.rules : bloc posé une fois" 1 "$(grep -cxF "$DURCISSEMENT_SORTANT_DEBUT" <<< "$a1")"
  v "after.rules : reposer ne change rien" OUI "$( [ "$a1" = "$a2" ] && echo OUI || echo NON)"
  v "after.rules : refus remplace constat" 1 \
    "$(durcissement_sortant_apres_regles "$a1" "$(durcissement_sortant_bloc refus)" | grep -c 'REJECT')"
  v "after.rules : retiré, le fichier d'origine" OUI \
    "$( [ "$(durcissement_sortant_apres_regles "$a1" "")" = "$APRES" ] && echo OUI || echo NON)"

  #  Le journal — la forme du noyau (nf_log), relevée sur un `[UFW BLOCK]` réel.
  local J="[UFW BLOCK] IN=eth0 OUT= MAC=01:00:5e:00:00:01:80:7d:3a:13:74:a8:08:00 SRC=192.168.1.12 DST=224.0.0.1 LEN=32 TOS=0x00 PREC=0x00 TTL=1 ID=3 PROTO=2
[UFW ALLOW] IN= OUT=eth0 SRC=192.168.1.223 DST=203.0.113.9 LEN=60 TOS=0x00 PREC=0x00 TTL=64 ID=1 DF PROTO=TCP SPT=40000 DPT=4444 WINDOW=64240 RES=0x00 SYN URGP=0
[UFW ALLOW] IN= OUT=eth0 SRC=192.168.1.223 DST=203.0.113.9 LEN=60 TOS=0x00 PREC=0x00 TTL=64 ID=2 DF PROTO=TCP SPT=40002 DPT=4444 WINDOW=64240 RES=0x00 SYN URGP=0
[UFW BLOCK] IN= OUT=eth0 SRC=192.168.1.223 DST=224.0.0.22 LEN=40 TOS=0x00 PREC=0x00 TTL=1 ID=0 DF PROTO=2
[SORTANT CONTENEUR] IN=br-29c0f5a2142a OUT=eth0 PHYSIN=veth1a2b3c MAC=aa:bb SRC=172.19.0.3 DST=198.51.100.7 LEN=60 TOS=0x00 PREC=0x00 TTL=63 ID=9 DF PROTO=TCP SPT=51000 DPT=5222 WINDOW=64240 RES=0x00 SYN URGP=0"
  local resume
  resume=$(durcissement_sortant_resume_journal "$J" "172.19.0.3 hostachy_whatsapp
172.19.0.2 hostachy_api")
  v "journal : l'entrant refusé n'est pas une sortie" 0 "$(grep -c '224\.0\.0\.1 ' <<< "$resume")"
  v "journal : deux sorties vers 4444 comptées ensemble" "2 203.0.113.9 4444/tcp hôte" "$(head -n 1 <<< "$resume")"
  v "journal : un conteneur nommé" 1 "$(grep -c '198.51.100.7 5222/tcp hostachy_whatsapp' <<< "$resume")"
  v "journal : sans port (IGMP)" 1 "$(grep -c '224.0.0.22 2 hôte' <<< "$resume")"
  v "journal : vide, rien" "" "$(durcissement_sortant_resume_journal "" "")"

  #  Les nuits vertes et la décision de refuser.
  local N_VERT="═══════════ audit-securite (2026-11-02 04:06:14) — rpi2, HEAD x ═══════════
[ OK ] S5 Sortie sur rpi2 : en constat — $DURCISSEMENT_SORTANT_PHRASE_VERTE (nuit verte)"
  local N_ROUGE="═══════════ audit-securite (2026-11-03 04:06:14) — rpi2, HEAD x ═══════════
[WARN] S5 Sortie sur rpi2 : en constat — 1 destination(s) hors liste en 24 h : 2 203.0.113.9 4444/tcp hôte"
  v "nuits : trois vertes" 3 "$(durcissement_sortant_nuits_vertes "$N_VERT
$N_VERT
$N_VERT")"
  v "nuits : la dernière rouge remet à zéro" 0 "$(durcissement_sortant_nuits_vertes "$N_VERT
$N_VERT
$N_ROUGE")"
  v "nuits : comptées depuis la rouge" 1 "$(durcissement_sortant_nuits_vertes "$N_VERT
$N_ROUGE
$N_VERT")"
  v "nuits : journal vide" 0 "$(durcissement_sortant_nuits_vertes "")"
  v "nuits : le passage en cours ne compte pas" 2 "$(durcissement_sortant_nuits_vertes "$N_VERT
$N_VERT
${N_VERT%%$'
'*}")"
  v "refuser : constat vert, standby, 3 nuits" OUI "$(durcissement_sortant_peut_refuser "CONSTAT:" "" 3 rpi1 rpi2)"
  v "refuser : sur l'actif" REFUS "$(durcissement_sortant_peut_refuser "CONSTAT:" "" 3 rpi2 rpi2)"
  v "refuser : 2 nuits seulement" REFUS "$(durcissement_sortant_peut_refuser "CONSTAT:" "" 2 rpi1 rpi2)"
  v "refuser : une sortie hors liste" REFUS \
    "$(durcissement_sortant_peut_refuser "CONSTAT:" "2 203.0.113.9 4444/tcp hôte" 3 rpi1 rpi2)"
  v "refuser : directement depuis ouvert" REFUS "$(durcissement_sortant_peut_refuser "OUVERT:x" "" 3 rpi1 rpi2)"
  v "refuser : constat incomplet" REFUS "$(durcissement_sortant_peut_refuser "CONSTAT:manquantes=[x];" "" 3 rpi1 rpi2)"
  v "refuser : rôle illisible" REFUS "$(durcissement_sortant_peut_refuser "CONSTAT:" "" 3 "" rpi2)"
  v "refuser : déjà en refus, réparer" OUI "$(durcissement_sortant_peut_refuser CONFORME "x" 0 rpi2 rpi2)"

  [ "$st" -eq 0 ] && echo "lib-durcissement-sortant : tous les cas passent."
  return "$st"
}
