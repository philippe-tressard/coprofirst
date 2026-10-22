#!/bin/bash
# =============================================================================
#  lib-collecte.sh — le snippet exécuté sur CHAQUE nœud par check-reliability.sh
#
#  Module SOURCÉ (mode 100644), jamais exécuté directement. Extrait de
#  `check-reliability.sh` le 11/08/2026 : ce fichier repassait au-dessus du
#  plafond de modularité de 500 lignes en recevant le motif d'extraction des
#  rapports, et le garde-fou de rang 1 refuse qu'il grossisse.
#
#  Dépend de constantes définies par l'APPELANT, avant le source :
#    $LOG_WARN_MB · $MAINT_LOG · $RAPPORTS_MOTIF (ce dernier vient de
#    lib-verdicts.sh, qui doit donc être sourcé en premier).
#
#  ⚠️ Ce fichier définit du CODE SOUS FORME DE CHAÎNE. `bash -n lib-collecte.sh`
#  ne vérifie donc PAS ce que les nœuds exécuteront — il ne voit qu'une chaîne.
#  C'est `verdicts_selftest` qui passe `bash -n` sur la chaîne ASSEMBLÉE, et
#  c'est le seul contrôle qui regarde ce code-là. Ne pas le retirer.
# =============================================================================

# ── Snippet de collecte exécuté sur chaque nœud (local + peer) ───────────────
# ⚠ Assemblé AVANT le gate --selftest, et ce n'est pas un rangement cosmétique.
# Le 11/08/2026 ce bloc a référencé $R en sortant des quotes ('"$R"'), c'est-à-dire
# dans le shell qui ASSEMBLE la chaîne — où $R n'existe pas, n'ayant jamais existé
# ailleurs que dans le snippet lui-même. Sous `set -u`, l'assemblage tue le script
# avant son premier contrôle : check-reliability n'a plus tourné du tout sur le
# nœud actif, et seule la version périmée du standby a pu le signaler. `bash -n` ne
# voyait rien (la syntaxe est valide) et `--selftest` rendait la main avant d'y
# arriver : CI verte sur un script mort. Le gate est donc passé APRÈS, pour que la
# CI paie le prix de l'assemblage exactement comme la production.
# Émet des lignes key=value. Tout est tolérant aux erreurs (jamais d'exit ≠ 0).
#
# 🔴 CETTE CHAÎNE EST ENTRE GUILLEMETS SIMPLES : une apostrophe écrite à
# l'intérieur, même dans un commentaire, la ferme. L'assemblage reste du shell
# valide côté local et devient invalide côté distant — le défaut du 11/08/2026,
# reproduit à l'identique le 19/08 en y ajoutant un commentaire en français.
# `verdicts_selftest` l'attrape (« COLLECT assemblé est du shell INVALIDE »).
# Toute explication va donc ICI, au-dessus ; en dessous, on écrit sans apostrophe.
#
# ── Le motif d'extraction des scripts planifiés (C18) ────────────────────────
# Il doit rester IDENTIQUE à celui de `scripts_cites()` dans `lib-points-entree.sh`,
# la version pure et testée (que `crontab_scripts` emploie). `verdicts_selftest` échoue si les deux
# divergent — il ne s'agit pas d'un vœu, mais d'un contrôle.
#
# ⚠️ Pourquoi la barre oblique est dans la classe : #337 a rangé les scripts dans
# `/opt/5hostachy/scripts/exploitation/` le 15/08/2026, et la classe ne l'admettait
# pas. L'extraction rendait donc du VIDE sur les deux nœuds, et C18 a répondu
# « Crontabs root INCONNUS » quatre jours durant. Il l'a dit — INCONNU jamais OK,
# la règle a tenu — mais un INCONNU répété se lit « pas cette fois », jamais
# « mort depuis quatre jours ».
#
# ── Les conteneurs comptés (`containers=`) : ceux de l'APPLICATION (DI-7b) ────
# Sous PostgreSQL, la réplique de la base tourne en permanence sur le standby :
# compter « tout hostachy » y ferait voir un split-brain à C2 et C4. La commande
# vient de `lib-applicatifs.sh`, insérée telle quelle (concaténée hors des
# apostrophes) — le pair n'a pas à porter le module pour être mesuré.
. "$(dirname "${BASH_SOURCE[0]}")/lib-applicatifs.sh"
COLLECT='
R=/opt/5hostachy
echo "host=$(hostname)"
echo "active=$(cat $R/.active 2>/dev/null | tr -d "[:space:]")"
echo "containers=$('"$COMPTER_APPLICATIFS"')"
echo "cf_active=$(systemctl is-active cloudflared 2>/dev/null)"
echo "cf_enabled=$(systemctl is-enabled cloudflared 2>/dev/null)"
echo "head=$(git -C $R rev-parse --short HEAD 2>/dev/null)"
echo "origin_head=$(git -C $R rev-parse --short origin/main 2>/dev/null)"
echo "git_root_ok=$(git -C $R rev-parse HEAD >/dev/null 2>&1 && echo yes || echo no)"
echo "disk=$(df / | awk "NR==2{print \$5}" | tr -d %)"
echo "ntp=$(timedatectl show -p NTPSynchronized --value 2>/dev/null)"
echo "lock=$([ -f $R/.bascule-lock ] && stat -c %Y $R/.bascule-lock || echo 0)"
# Quand health-watch a-t-il NETTOYÉ un verrou orphelin pour la derniere fois,
# et combien de fois en tout ? C12 ne peut pas le lire sur le fichier :
# health-watch l EFFACE au-dela de VERROU_STALE_S, et C12 ne passe que toutes
# les 15 min — le verrou a donc toujours disparu avant d etre signalable
# (12/09/2026, #915). On observe donc l ACTE, qui laisse une trace datee, et non
# l objet, qui n en laisse aucune. Meme motif que le point 13 du pre-check, qui
# se verifie par « Alerte envoyee » et non par « Email KO ».
#
# ⚠️ On rapporte un FAIT BRUT (un horodatage, un compte) : la fraicheur est
# decidee par verdict_verrou_orphelin(), pure et eprouvee. Et aucune apostrophe
# ici — ces lignes sont DANS la chaine simple-quotee.
# Le journal de la DERNIERE bascule executee sur ce noeud, depuis son marqueur
# de debut. C26 y verifie que le verrou a ete pose AVANT la premiere action —
# la verification PAR L EXECUTION que #915 reclamait, la forme du script etant
# deja verifiee par `test_verrou_bascule.py`.
# ⚠️ Encode en base64 : ces lignes contiennent des accents, des fleches et des
# retours a la ligne, et elles voyagent dans un `parse` qui decoupe sur `=`.
BL=/var/log/hostachy-bascule.log
if [ -f "$BL" ]; then
  echo "bascule_journal=$(awk "/===== Bascule [a-z0-9]+ /{n=NR} END{print n}" "$BL" | { read d; [ -n "$d" ] && [ "$d" -gt 0 ] && tail -n "+$d" "$BL" | head -60 | base64 -w0; })"
else
  echo "bascule_journal="
fi
HWL=/var/log/hostachy-health-watch.log
if [ -f "$HWL" ]; then
  echo "orphelins=$(grep -c -E "bascule-lock orphelin" "$HWL" 2>/dev/null || echo 0)"
  _od=$(grep -E "bascule-lock orphelin" "$HWL" 2>/dev/null | tail -1 | cut -c2-20)
  echo "orphelin_dernier=$([ -n "$_od" ] && date -d "$_od" +%s 2>/dev/null || echo 0)"
else
  # Journal absent : le contrôle ne peut pas mesurer. INCONNU, jamais OK.
  echo "orphelins=inconnu"
  echo "orphelin_dernier=inconnu"
fi
# Un build auto-deploy est-il EN COURS sur ce nœud ? Le verrou est le fait
# lui-même — `auto-deploy.sh` le tient du début du build jusqu a la fin, et C1
# s en sert pour ne pas crier au loup pendant les trois minutes où Caddy rend
# 503 parce que son amont redémarre (01/09/2026). La sonde est celle du
# failover (#1997) : SONDE_DEPLOIEMENT, écrite une fois dans lib-verrou.sh.
# ⚠️ Aucune apostrophe ci-dessus, et ce n est pas du style : ces lignes sont DANS
# la chaîne simple-quotée, une apostrophe nue la refermerait (avertissement plus
# haut dans ce fichier — et je viens de m y reprendre).
'"$SONDE_DEPLOIEMENT"'
echo "deploiement=$DEP"
BIG=""; for l in /var/log/hostachy-*.log; do [ -f "$l" ] || continue; sz=$(( $(stat -c %s "$l")/1048576 )); [ "$sz" -ge '"$LOG_WARN_MB"' ] && BIG="$BIG $(basename $l):${sz}M"; done
echo "biglogs=$BIG"
echo "deploylog_owner=$(stat -c %U /var/log/hostachy-deploy.log 2>/dev/null || echo missing)"
#  🔴 Ce que lit auto-deploy : le .env, et QUI peut le lire (C28, #1138).
#  Le 22/09/2026 il est passe root:root a la bascule — plus de build sur le
#  standby, et plus d alerte non plus, puisqu elle y cherche le SMTP.
#  Un seul stat, trois champs : les separer ferait trois appels qui peuvent
#  ne pas voir le meme fichier.
echo "envdroits=$(stat -c %U:%G:%a $R/.env 2>/dev/null || echo :: )"
#  C29 (#1109) : les NOMS des cles du .env, jamais leurs valeurs. Le 21/09/2026
#  les deux noeuds ne portaient pas le meme jeu, et rien ne les comparait.
echo "envcles=$(cut -d= -f1 $R/.env 2>/dev/null | grep -E "^[A-Za-z_][A-Za-z0-9_]*$" | sort -u | tr "[:space:]" " ")"
#  Le DERNIER verdict de build d auto-deploy. Il ecrit une ligne par tick ; celle
#  qui porte ECHEC du build dit que le code est aligne et pas les images — la
#  parite git n est pas la parite d image (C27).
echo "deploy_dernier=$(tail -40 /var/log/hostachy-deploy.log 2>/dev/null | grep -E "^\[" | tail -1 | tr -d "\"" | cut -c1-160)"
echo "reliability_last=$(tail -3000 /var/log/hostachy-reliability.log 2>/dev/null | grep -oE "check-reliability \([0-9-]{10} [0-9:]{8}\)" | tail -1 | tr -d "()" | cut -d" " -f2-)"
echo "buildcache=$(docker system df --format "{{.Type}}|{{.Size}}" 2>/dev/null | grep -i "^Build Cache" | cut -d"|" -f2 | tr -d " ")"
# Date du dernier rapport de maintenance EN BASE, pour ce nœud — la seconde sonde
# de C19. Lue par l'\''API in-process, donc elle ne répond que sur l'\''ACTIF.
# Sur le standby la chaîne est vide, et C19 le traduit en INCONNU au lieu de
# conclure à une divergence.
# $R reste DANS les quotes : il appartient au snippet (défini plus haut), pas au
# shell qui assemble. Seules les CONSTANTES du script (LOG_WARN_MB, MAINT_LOG)
# justifient une sortie de quotes : elles ne vivent que côté assembleur.
# Et aucune apostrophe dans ces commentaires : ils sont DANS la chaîne, et une
# apostrophe nue la referme — sinon écrire le motif échappé, comme plus haut.
MK=$(grep -E "^MAINTENANCE_KEY=" $R/.env 2>/dev/null | cut -d= -f2- | tr -d "\"'"'"' \r")
REP=""
if [ -n "$MK" ]; then
  REP=$(curl -s --max-time 8 -w "|%{http_code}" -H "x-maintenance-key: $MK" \
    "http://localhost/api/admin/maintenance/dernier-rapport?tache=maintenance" 2>/dev/null)
fi
# Le marqueur `ok:` est posé UNIQUEMENT quand le curl a rendu 200. Sans lui, une
# carte vide se confond avec « demande impossible » — et cette confusion a rendu
# C19 muet le 11/08/2026 sur le cas meme que ce contrôle devait attraper (#305).
#
# Le motif vient de lib-verdicts.sh, injecté ici depuis le shell assembleur : une
# SEULE definition sert la collecte et son self-test. Ecrit a la main, il oubliait
# le Z final des horodatages ISO et ne pouvait jamais correspondre — la carte
# revenait vide quoi que rende API. Un motif recopie est un motif qui diverge.
# (Aucune apostrophe ici : ce bloc vit DANS une chaîne à quotes simples.)
case "$REP" in
  *"|200") echo "rapports=ok:$(echo "$REP" | tr -d "\" " | grep -oE "'"$RAPPORTS_MOTIF"'" | tr "\n" ";")" ;;
  *)       echo "rapports=" ;;
esac
# Crontab ROOT, et root seulement. Le test sur l'\''uid n'\''est pas une précaution
# de style : ce bloc tourne en root en local (cron root) mais en `ptressard` sur le
# peer (SSH). Un `crontab -l` nu y rendrait le crontab de `ptressard` — qui existe,
# donc la commande RÉUSSIRAIT en donnant la mauvaise réponse. Un faux vert par
# succès, le pire des cas.
if [ "$(id -u)" = "0" ]; then CRONRAW=$(crontab -l 2>/dev/null); else CRONRAW=$(sudo -n crontab -l 2>/dev/null); fi
# Motif jumeau de scripts_cites() dans lib-points-entree.sh — voir la note au-dessus
# de COLLECT. La barre oblique dans la classe est indispensable depuis #337.
echo "cronscripts=$(echo "$CRONRAW" | grep -vE "^\s*(#|$)" | grep -oE "/opt/5hostachy/[A-Za-z0-9_./-]+\.sh" | sed "s#.*/##" | sort -u | paste -sd, - | tr -d " \n")"
# ── C20. Inventaire des permissions élevées — METADONNEES SEULES ─────────────
# Nom, taille et mode de chaque fichier, JAMAIS son contenu. Le repertoire est
# traversable par tous, donc ceci se lit sans le moindre privilege : c est ce qui
# permet de comparer les deux noeuds alors que le snippet tourne en root ici et
# en ptressard sur le peer. Lire le contenu a distance supposerait un NOPASSWD
# sur cat, cest-a-dire /etc/shadow — la faille meme quon surveille.
# Le marqueur ok: distingue « mesure faite, rien trouve » de « pas pu mesurer » :
# sans lui, deux repertoires illisibles rendraient deux chaines EGALES, donc un
# faux « identiques » (cas zero, deja vecu sur C14 et C18).
echo "sudofiles=$([ -x /etc/sudoers.d ] && { printf "ok:"; for f in /etc/sudoers.d/*; do [ -e "$f" ] || continue; printf "%s:%s:%s," "$(basename "$f")" "$(stat -c %s "$f" 2>/dev/null)" "$(stat -c %a "$f" 2>/dev/null)"; done; })"
# ── C21. Une permission elevee ne vaut que ce que vaut sa cible ──────────────
# Analyse LOCALE, en root : le peer ne rend rien et son champ vaut INCONNU. Le
# controle couvre quand meme les deux noeuds, puisquil tourne sur chacun deux.
# On rapporte des FAITS BRUTS (les cibles douteuses) ; cest lib-verdicts.sh qui
# conclut, et cest ce qui rend la decision testable sans les deux RPi.
if [ "$(id -u)" = "0" ]; then
  RISK=""
  RULES=$(grep -rhE "NOPASSWD" /etc/sudoers.d/ /etc/sudoers 2>/dev/null | grep -vE "^[[:space:]]*#")
  # Une regle bornee a aucune commande : le cas le plus grave, et le plus discret.
  # On teste LIGNE PAR LIGNE. Un case sur la chaine entiere trouvait NOPASSWD:
  # sur une ligne et ALL sur la suivante (ptressard ALL=(root) NOPASSWD: ...),
  # donc il posait le marqueur des quun noeud portait deux regles nominatives —
  # faux positif permanent, et donc controle incapable de virer au vert.
  # Jumeau teste : sudo_sans_borne(), dans lib-verdicts-sudo.sh. Les deux
  # expressions doivent rester identiques (meme contrainte que le motif de C18).
  RISK=$(echo "$RULES" | sed -n "s/.*NOPASSWD:[[:space:]]*//p" | grep -qE "^ALL([,[:space:]]|$)" && echo ALL || echo "")
  for c in $(echo "$RULES" | grep -oE "/[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)+" | sort -u); do
    [ -e "$c" ] || continue
    M=$(stat -c %A "$c" 2>/dev/null); O=$(stat -c %U "$c" 2>/dev/null); D=$(stat -c %U "$(dirname "$c")" 2>/dev/null)
    BAD=""
    # Cible ou repertoire hors de root : lappelant peut remplacer le code execute.
    [ "$O" = "root" ] || BAD=1
    [ "$D" = "root" ] || BAD=1
    # %A rend 10 caracteres : position 6 = w du groupe, position 9 = w des autres.
    case "$M" in ?????w*) BAD=1 ;; esac
    case "$M" in ????????w*) BAD=1 ;; esac
    [ -n "$BAD" ] && RISK="$RISK $(basename "$c")"
  done
  echo "sudorisk=ok:$RISK"
else
  echo "sudorisk="
fi

# La SURFACE accordée au compte de service, triée et aplatie — la matière de C24.
# Elle se compare à ce que `sudoers_regle` compose dans le dépôt : C20 ne compare
# que les deux nœuds ENTRE EUX, donc deux nœuds identiquement périmés lui semblent
# parfaits. C est exactement ce qui est arrivé du 31/08 au 01/09/2026 : la règle
# NOPASSWD sur rsync — une escalade root complète — était retirée du dépôt, et
# toujours installée sur les DEUX machines. Vingt-trois contrôles au vert.
if [ "$(id -u)" = "0" ]; then
  SURF=$(grep -rhE "^ptressard[[:space:]]+.*NOPASSWD:" /etc/sudoers.d/ /etc/sudoers 2>/dev/null | grep -vE "^[[:space:]]*#")
else
  # Le peer est collecté en tant que ptressard, pas root : `sudo -n -l` liste
  # ses propres droits SANS mot de passe, et rend la même surface.
  SURF=$(sudo -n -l 2>/dev/null | grep "NOPASSWD:")
fi
echo "sudosurface=$(printf "%s" "$SURF" | sed -n "s/.*NOPASSWD:[[:space:]]*//p" | sed "s/[[:space:]]*$//" | sort -u | tr "\\n" "|")"
'

# C30 (#1378) : ce que le noeud sait de ses mises a jour systeme. La collecte
# vit avec ses verdicts, dans `lib-mises-a-jour.sh` ; elle rejoint ici la chaine
# executee sur les deux noeuds, et donc le `bash -n` de `verdicts_selftest`.
. "$(dirname "${BASH_SOURCE[0]}")/lib-mises-a-jour.sh"
COLLECT="$COLLECT$COLLECT_MAJ"

# C6 (#1546) : les bits d'exécution des scripts que lancent crons et unité. La
# liste se DÉRIVE de `infra/points-entree/` (relais suivis) dans le shell qui
# assemble — elle était recopiée ici, et six noms sur sept avaient disparu
# depuis le 16/08/2026 : la boucle ne mesurait rien et rendait « ok ». Mesure,
# dérivation et décision vivent avec leurs épreuves dans `lib-points-entree.sh`,
# qui doit donc être sourcé AVANT ce module.
COLLECT="$COLLECT$(fragment_bits_exec "$(scripts_a_mesurer "$(dirname "${BASH_SOURCE[0]}")/../..")")"

# C31 (#1586) : la date de la derniere SONDE de health-watch. Ce qu il ecrit, ce
# que la collecte en lit et ce que C31 en conclut vivent ensemble, dans
# `lib-health-watch.sh` ; `healthwatch_verdicts` y est donc defini aussi.
. "$(dirname "${BASH_SOURCE[0]}")/lib-health-watch.sh"
COLLECT="$COLLECT$COLLECT_HW"

# C17 : la date de la derniere marque de fin d hygiene de maintenance.sh. Ce
# qu il ecrit, ce que la collecte en lit et ce que C17 en conclut vivent
# ensemble, dans `lib-maintenance-trace.sh` ; la collecte recopiait ici un detail
# d une etape (« Garde-fou »), que #1524 a fait disparaitre (05/10/2026).
# Dependance de l APPELANT : $MAINT_LOG.
. "$(dirname "${BASH_SOURCE[0]}")/lib-maintenance-trace.sh"
COLLECT="$COLLECT$(collecte_maintenance "$MAINT_LOG")"

# C37 (#1781) : la replication PostgreSQL — role de la base, repliques, retard.
# Collecte, decision et constats vivent ensemble, dans `lib-replication.sh` ;
# `replication_verdicts` y est donc defini aussi.
. "$(dirname "${BASH_SOURCE[0]}")/lib-replication.sh"
COLLECT="$COLLECT$COLLECT_REPLICATION"

# C32 (#1593) : les ports TCP a l ecoute sur toutes les interfaces. La mesure,
# la liste blanche declaree et la decision vivent ensemble, dans
# `lib-ports-ecoute.sh` ; `ports_ecoute_verdicts` y est donc defini aussi.
. "$(dirname "${BASH_SOURCE[0]}")/lib-ports-ecoute.sh"
COLLECT="$COLLECT$COLLECT_PORTS"

# C33 (#1609) et C34 (#1592) : des copies laissees a cote de l original — des
# `.env*` a la racine du depot deploye, des bases autres que la base de l API
# dans le volume de donnees (listage d un repertoire par un conteneur jetable en
# lecture seule : la base n est jamais ouverte). Mesure, listes blanches et
# decision vivent ensemble, dans `lib-fichiers-parasites.sh`. Dependance de
# l APPELANT : $REPO.
. "$(dirname "${BASH_SOURCE[0]}")/lib-fichiers-parasites.sh"
COLLECT="$COLLECT$(collecte_env_copies "$REPO")$(collecte_db_volume)"

# C36 (#1588) : le journal d acces de Caddy (fichier du volume `caddy_logs`,
# anonyme) est-il ecrit, et combien d erreurs serveur en 24 h ? Mesure et
# decision vivent ensemble, dans `lib-journal-acces.sh`.
. "$(dirname "${BASH_SOURCE[0]}")/lib-journal-acces.sh"
COLLECT="$COLLECT$COLLECT_ACCES"

# C35 (#1648) : la pile de bureau est-elle revenue ? Paquets de la liste proscrite
# (ecrite UNE fois, dans `lib-paquets-proscrits.sh`, que `alleger-noeud.sh`
# relit), cible systemd par defaut, APT::Install-Recommends. Mesure et decision
# vivent ensemble dans ce module.
. "$(dirname "${BASH_SOURCE[0]}")/lib-paquets-proscrits.sh"
COLLECT="$COLLECT$(collecte_paquets_proscrits)"

# C39 (#2115) : le jeton du tunnel est-il EN CLAIR dans l unite cloudflared ?
# La collecte ne rend qu un verdict (clair / absent), jamais un extrait de l unite :
# le jeton ne quitte pas le noeud. Mesure et decision vivent ensemble, dans
# `lib-jeton-tunnel-clair.sh`.
. "$(dirname "${BASH_SOURCE[0]}")/lib-jeton-tunnel-clair.sh"
COLLECT="$COLLECT$(collecte_jeton_tunnel)"
