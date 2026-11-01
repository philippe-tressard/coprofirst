#!/bin/bash
# =============================================================================
#  export-hors-site.sh — Copie hors site de la dernière sauvegarde 5Hostachy
#
#  POURQUOI ce script existe (constat du 04/08/2026) :
#    Les sauvegardes de 03:00 sont produites par APScheduler DANS le conteneur
#    API, donc uniquement sur le nœud ACTIF, dans le volume Docker `backups`
#    que `bascule.sh` ne réplique PAS (il ne synchronise que uploads et
#    whatsapp_auth). Le rôle alternant chaque nuit, chaque RPi n'accumulait
#    qu'un jour sur deux, et `_rotate_backups()` ne voit que les fichiers
#    LOCAUX : les 7 versions conservées couvraient ~14 jours À TROUS, et aucun
#    nœud n'avait la sauvegarde de la veille.
#    Surtout : 100 % des archives vivaient sur deux machines posées au même
#    endroit, sur la même box et la même alimentation. Un `docker volume rm`,
#    un rançongiciel ou un sinistre emportait la base, les uploads ET toutes
#    les sauvegardes d'un seul coup. Cf. standards/06-donnees-et-integrite.md
#    §6 : une sauvegarde qui partage le destin de la production n'en est pas une.
#
#  CE QU'IL FAIT — exécuté depuis le POSTE (Git Bash), pas depuis un RPi :
#    1. Détermine le nœud source par son COMPORTEMENT (qui répond réellement
#       sur /api/health en LAN), et non en lisant le drapeau `.active` — cf.
#       standards/04 §10. Un `.active` peut mentir ; une API qui répond, non.
#    2. Tire la plus récente archive de ce nœud par un CONTENEUR JETABLE monté
#       en lecture seule sur le volume des sauvegardes — ni sudo, ni règle
#       sudoers, ni installation sur les nœuds (ni rsync ni scp : Git for
#       Windows n'embarque pas rsync).
#    3. La VÉRIFIE : empreinte identique à la source, gzip intact, puis l'export
#       vérifié de la base qu'elle porte (chaque table compte les lignes que son
#       manifeste annonce), relu sur le poste — une copie à nous, jamais la base
#       de production.
#    3 bis. Copie de même la dernière archive du REGISTRE des installations
#       (`plateforme/`, chez la référence seulement — #1896), sans que son
#       verdict touche celui de la copropriété.
#    4. Fait tourner les copies locales (N versions).
#    5. Poste son rapport sur `POST /api/admin/maintenance/rapport`
#       (tache=export_hors_site) — le canal cron qui existe déjà, avec sa clé
#       `x-maintenance-key`. Aucun second canal, aucune seconde table.
#
#  CE QU'IL NE FAIT PAS — et c'est délibéré :
#    Il ne touche JAMAIS la base de production, ni en lecture. Il ne lit que des
#    fichiers `.tar.gz` déjà clos.
#
#  ⚠ PORTÉE DE CETTE PROTECTION : le poste est au MÊME DOMICILE que les deux
#    RPi. Cette copie protège de la perte d'un nœud, d'un `docker volume rm`
#    et d'un rançongiciel visant les RPi — PAS de l'incendie ni du vol. Une
#    seconde destination réellement distante reste à ajouter ; la variable
#    EXPORT_DEST et la boucle de vérification sont écrites pour l'accueillir
#    sans réécriture.
#
#  LANCEMENT — MANUEL, depuis le poste, quand il est allumé :
#    • raccourci « Sauvegarde hors site 5Hostachy » sur le Bureau, ou
#    • double-clic sur `scripts/poste/export-hors-site.cmd` (Windows) ou
#      `scripts/poste/export-hors-site.command` (Mac), ou
#    • depuis Git Bash :   bash /c/Dev/5hostachy/scripts/poste/export-hors-site.sh
#      depuis le Terminal du Mac : bash /Volumes/Data/Dev/5hostachy/scripts/poste/export-hors-site.sh
#
#    Sur le Mac, le raccourci du Bureau est un LIEN vers le `.command` du dépôt :
#    il suit ce qui est versionné au lieu d'en garder une copie.
#
#    ⚠ Ces trois chemins ont changé le 15/08/2026 (#350, rangement de
#      l'outillage) : le raccourci du Bureau pointait toujours sur la racine du
#      dépôt et ne lançait plus rien. Un point d'entrée qui vit HORS du dépôt
#      n'est réparé par aucun `git mv` — si ce script est redéplacé, le
#      raccourci est à repointer à la main. Aucun contrôle ne le vérifie
#      encore : c'est l'objet du ticket #377.
#
#    Le poste n'étant pas allumé en permanence, ce script n'est PAS planifié :
#    une tâche quotidienne sur une machine éteinte échoue plus souvent qu'elle
#    ne réussit, et une alerte qui crie tous les jours finit ignorée — c'est
#    ainsi qu'un contrôle meurt (standards/07 §5). Le rythme est donc laissé à
#    l'utilisateur, et c'est l'ÂGE de la dernière copie que l'application
#    surveille : l'onglet Admin → Maintenance affiche la tâche
#    `export_hors_site`, et le contrôle de 06:00 alerte au-delà d'une semaine
#    sans copie fraîche. Un oubli se voit ; il ne se devine pas.
#
#  Configuration — variables d'environnement (toutes optionnelles) :
#    EXPORT_DEST      répertoire de destination   (défaut : /c/Backup → C:\Backup ;
#                                                  sur le Mac, /Volumes/Data/Backup)
#    EXPORT_KEEP      versions conservées         (défaut : 2)
#    EXPORT_SSH_USER  compte SSH sur les RPi      (défaut : ptressard)
#
#  ⚠ NE PAS pointer EXPORT_DEST dans C:\Dev\5hostachy : c'est un dépôt git, et
#    une archive de plusieurs centaines de Mo dans l'arbre de travail pollue
#    chaque `git status` et chaque diff, gitignorée ou non.
#
#  Test sans effet de bord : bash scripts/poste/export-hors-site.sh --selftest
# =============================================================================
set -uo pipefail
# shellcheck source=../lib/lib-poste-gnu.sh
. "$(dirname "$0")/../lib/lib-poste-gnu.sh"
poste_gnu_poser "$@"   # macOS : les outils GNU en tête du PATH, comme Git Bash et la CI (#2419)

#  La destination par défaut suit le poste : C:\Backup sous Windows, le disque
#  Data sur le Mac — hors de /Volumes/Data/Dev, où vivent les dépôts (01/11/2026).
case "$(uname -s)" in
  Darwin) EXPORT_DEST="${EXPORT_DEST:-/Volumes/Data/Backup}" ;;
  *)      EXPORT_DEST="${EXPORT_DEST:-/c/Backup}" ;;
esac
#  🔴 DEUX, et pas quatorze (12/09/2026, demandé à l'écran). Une archive pèse
#  ~100 Mo : quatorze en font 1,4 Go sur le poste, pour une série dont on ne
#  restaure jamais que la dernière — ou l'avant-dernière si la dernière est
#  suspecte. Le rattrapage se borne à la même valeur (`archives_a_rattraper`) :
#  on ne tire pas ce qu'on effacerait aussitôt.
EXPORT_KEEP="${EXPORT_KEEP:-2}"
EXPORT_SSH_USER="${EXPORT_SSH_USER:-ptressard}"
#  `lib-role.sh` (table des nœuds) et `lib-rapport.sh` vivent à la racine du
#  dépôt : ils servent aussi aux scripts de cron, qui n'ont pas bougé (#337).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

#  Les DÉCISIONS pures vivent dans un module sourcé (#775, 05/09/2026) :
#  elles s'éprouvent par `--selftest` sans les deux RPi. Ce script garde ce
#  qui touche au réseau, au disque et à l'orchestration.
source "$(dirname "$0")/../lib/lib-export-hors-site.sh"
#  Les GESTES partagés par les deux séries (transfert, relecture d'un export,
#  copie du registre) vivent à côté depuis #1896 : ce script orchestre.
source "$(dirname "$0")/../lib/lib-export-hors-site-copie.sh"


# ─────────────────────────────────────────────────────────────────────────────
#  SELF-TEST — exécuté en CI (job test-scripts), aucun effet de bord.
# ─────────────────────────────────────────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  #  Les cas d'essai vivent à côté (`lib-export-hors-site.selftest.sh`) : ce
  #  script est au-dessus du plafond de modularité, et le garde-fou a refusé
  #  qu'il grossisse encore. Ce qui reste ici est l'orchestration.
  source "$SCRIPT_DIR/scripts/lib/lib-export-hors-site.selftest.sh"
fi

# ─────────────────────────────────────────────────────────────────────────────
#  EXÉCUTION RÉELLE
# ─────────────────────────────────────────────────────────────────────────────

# Table d'adresses : aucune recopie ici — lib-role.sh est la source unique.
# shellcheck source=../lib/lib-role.sh
source "$SCRIPT_DIR/scripts/lib/lib-role.sh"

SSH_CMD="ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new"
STATUT="succes"
MESSAGE=""
DEBUT=$(date -u +%Y-%m-%dT%H:%M:%S)
T0=$SECONDS
ARCHIVE=""
OCTETS=0
INTEGRITE="inconnue"
SOURCE_NOEUD=""

log "===== Export hors site ====="

# ── 1. Quel nœud sert réellement ? ───────────────────────────────────────────
IP1=$(role_ip rpi1); IP2=$(role_ip rpi2)
# curl écrit déjà `000` quand la connexion échoue : un `|| echo "000"` en plus
# concaténait les deux et produisait `000000` dans le journal (vu le 04/08/2026).
# Trompeur à lire, et fragile — la comparaison se fait sur la chaîne exacte.
sonde() { curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://$1/api/health" 2>/dev/null; }
CODE1=$(sonde "$IP1"); CODE2=$(sonde "$IP2")
SOURCE_NOEUD=$(decider_source "$CODE1" "$CODE2")
log "  Sonde LAN : rpi1=$CODE1 rpi2=$CODE2 → source = $SOURCE_NOEUD"

case "$SOURCE_NOEUD" in
  aucun)
    log "ERREUR: aucun nœud ne répond en LAN — rien à exporter."
    log "  → Le site est probablement HS. Voir .claude/skills/infra-rpi."
    exit 1 ;;
  split-brain)
    # Deux nœuds qui servent = deux bases qui divergent. Choisir l'un des deux
    # reviendrait à sauvegarder au hasard une moitié de la vérité, et à écraser
    # la précédente par rotation. On s'abstient, bruyamment.
    log "ERREUR: SPLIT-BRAIN — les deux nœuds répondent. Export annulé."
    log "  → Traiter le split-brain AVANT toute sauvegarde (docker ps sur les 2)."
    exit 1 ;;
esac

SOURCE_IP=$(role_ip "$SOURCE_NOEUD")
SSH_CIBLE="$EXPORT_SSH_USER@$SOURCE_IP"

# ── 2. Repérer et tirer la plus récente archive ──────────────────────────────
# Le point de montage du volume Docker appartient à root : `ptressard` ne peut ni
# le lister ni le lire. On passe par un script root à CHEMIN FIXE, qui n'expose
# que trois verbes et détermine le volume lui-même — voir `export-source.sh`.
#
# ⚠️ Pourquoi pas `NOPASSWD` sur `ls`/`cat`/`sha256sum` : ce serait la lecture de
# n'importe quel fichier en root (`sudo cat /etc/shadow`). Et pourquoi le script
# vit dans /usr/local/sbin et non /opt/5hostachy : ce dernier appartient à
# `ptressard` et `auto-deploy` y réécrit tout — une règle NOPASSWD sur un fichier
# que l'appelant peut réécrire est un accès root complet, pas une permission.
#
# ── Comment on lit les archives : un conteneur jetable, PAS `sudo` ───────────
# Le point de montage du volume appartient à root, mais `ptressard` est déjà dans
# le groupe `docker` sur les deux nœuds — c'est ce qui fait tourner auto-deploy et
# la bascule. Un conteneur monté en LECTURE SEULE sur le volume lit donc les
# archives sans le moindre privilège supplémentaire, et sans mot de passe.
#
# C'est ce qui remplace la dépendance à `sudo` : elle n'existait que sur rpi1
# (règle `010_pi-nopasswd` par défaut de Raspberry Pi OS) et manquait sur rpi2, si
# bien que la copie échouait UNE NUIT SUR DEUX — celles où rpi2 est actif
# (constaté le 09/08/2026, dernière copie réussie le 06/08). La corriger en
# ajoutant une règle sudoers demandait une installation manuelle sur chaque nœud ;
# ceci ne demande rien et vaut pour tout nœud présent ou futur.
#
# Aucun privilège n'est élargi : l'appartenance au groupe `docker` équivaut déjà à
# root, elle est antérieure et nécessaire au modèle de déploiement. On en RETIRE
# une (la règle sudoers devient inutile). Le montage est `:ro` et ne porte que le
# volume des sauvegardes.
LIRE="docker run --rm -v 5hostachy_backups:/b:ro alpine"

# On établit d'abord qu'on a PU regarder. Sans cette étape, une panne d'accès rend
# une liste vide, qui se lit comme « aucune sauvegarde » — un KO déguisé en
# constat, exactement ce qu'interdit standards/04 §1. Vécu deux fois : le
# 04/08/2026 (motif développé avant sudo) et le 09/08/2026 (sudo absent sur rpi2).
if ! $SSH_CMD "$SSH_CIBLE" "$LIRE true" >/dev/null 2>&1; then
  if ! $SSH_CMD "$SSH_CIBLE" "docker info" >/dev/null 2>&1; then
    log "ERREUR: docker inaccessible pour $EXPORT_SSH_USER sur $SOURCE_NOEUD — état INCONNU."
    log "        Le compte doit appartenir au groupe docker (id -nG)."
  elif ! $SSH_CMD "$SSH_CIBLE" "docker image inspect alpine" >/dev/null 2>&1; then
    log "ERREUR: image alpine absente sur $SOURCE_NOEUD et non téléchargeable — état INCONNU."
  else
    log "ERREUR: lecture du volume 5hostachy_backups impossible sur $SOURCE_NOEUD — état INCONNU."
  fi
  exit 1
fi

# Ici seulement une liste vide est un FAIT : la lecture a réussi.
ARCHIVE=$($SSH_CMD "$SSH_CIBLE"   "$LIRE sh -c 'ls -1 /b/hostachy_backup_*.tar.gz 2>/dev/null'" 2>/dev/null   | tr -d '
' | sed 's#.*/##' | sort | tail -1)
if [ -z "$ARCHIVE" ]; then
  log "ERREUR: aucune archive sur $SOURCE_NOEUD — la sauvegarde de 03:00 ne produit rien."
  exit 1
fi
# Le nom vient d'une machine distante et repart dans une commande : il est validé
# avant, jamais après. standards/03-securite.md §2 — liste blanche, ancrée.
if ! nom_valide "$ARCHIVE"; then
  log "ERREUR: nom d'archive inattendu sur $SOURCE_NOEUD ('$ARCHIVE') — abandon."
  exit 1
fi
log "  Archive la plus récente sur $SOURCE_NOEUD : $ARCHIVE"

mkdir -p "$EXPORT_DEST" || { log "ERREUR: destination inaccessible ($EXPORT_DEST)."; exit 1; }
LOCAL="$EXPORT_DEST/$ARCHIVE"

# Empreinte à la source AVANT transfert : c'est elle qui prouvera que la copie
# est fidèle. Sans elle, un transfert tronqué produit un fichier plausible.
SHA_SRC=$($SSH_CMD "$SSH_CIBLE" "$LIRE sha256sum '/b/$ARCHIVE'" 2>/dev/null | awk '{print $1}')

if [ -f "$LOCAL" ] && [ "$(sha256sum "$LOCAL" 2>/dev/null | awk '{print $1}')" = "$SHA_SRC" ]; then
  log "  → Déjà présente et identique — transfert ignoré."
else
  log "  Transfert en cours…"
  # Flux via ssh plutôt que rsync/scp : Git for Windows n'embarque pas rsync, et
  # scp ne sait pas élever ses droits sur la source. Le geste vit dans
  # `transferer_archive`, partagé avec la passe de rattrapage.
  if ! transferer_archive "$SOURCE_IP" "$ARCHIVE" "$LOCAL"; then
    log "ERREUR: transfert interrompu."
    exit 1
  fi
fi

OCTETS=$(stat -c%s "$LOCAL" 2>/dev/null || echo 0)
SHA_DST=$(sha256sum "$LOCAL" 2>/dev/null | awk '{print $1}')
EMPREINTES="non"; [ -n "$SHA_SRC" ] && [ "$SHA_SRC" = "$SHA_DST" ] && EMPREINTES="oui"

# ── 3. Vérifier la copie (sur le POSTE — jamais sur la base de production) ───
LISTING=$(tar -tzf "$LOCAL" 2>/dev/null || true)
CONTIENT=$(listing_contient "$LISTING" "$NOM_EXPORT_BASE")

# L'archive porte l'export vérifié de la base (DI-7b). On le relit ici, sans
# rien du projet : chaque table doit compter les lignes que le manifeste annonce.
# Sa restauration, elle, a été éprouvée au nœud avant que la sauvegarde se dise
# réussie (`backup.py`).
if [ "$CONTIENT" = "oui" ]; then
  TMP=$(mktemp -d 2>/dev/null || echo "/tmp/export-hs-$$")
  mkdir -p "$TMP"
  if tar -xzf "$LOCAL" -C "$TMP" "$NOM_EXPORT_BASE" 2>/dev/null; then
    INTEGRITE=$(relire_export "$TMP/$NOM_EXPORT_BASE")
  fi
  rm -rf "$TMP"
fi
log "  Vérification : empreintes=$EMPREINTES base=$CONTIENT intégrité=$INTEGRITE"

VERDICT=$(verdict_archive "$OCTETS" "$EMPREINTES" "$CONTIENT" "$INTEGRITE")
STATUT="${VERDICT%%|*}"
MESSAGE="${VERDICT#*|}"
log "  → $STATUT : $MESSAGE"

# Une copie non validée ne doit pas rester dans la destination : au prochain
# sinistre, elle se présenterait comme une sauvegarde disponible.
if [ "$STATUT" != "succes" ] && [ -f "$LOCAL" ]; then
  mv -f "$LOCAL" "$LOCAL.invalide" 2>/dev/null || true
  log "  → Copie écartée sous $ARCHIVE.invalide (ne pas la prendre pour une sauvegarde)."
fi

# ── 4. Rattrapage sur l'autre nœud (#775) ───────────────────────────────────
#
# Sans cette passe, la copie hors site ne contient qu'une nuit sur deux — et
# personne ne le voit, puisque l'archive du JOUR, elle, est bien là.
#
# ⚠️ Le standby a `docker` et son volume même sans conteneur : même lecture, sans
# privilège supplémentaire. Et cette passe n'échoue JAMAIS le script — l'archive
# du jour est déjà copiée et vérifiée. Un standby injoignable est un rattrapage
# manqué, pas une sauvegarde manquée ; il est dit, et le relevé le montre.
# 🔴 `RPI1_IP`/`RPI2_IP` n'ont JAMAIS existé : ces trois lignes recopiaient à la
# main ce que `lib-role.sh` fournit — et sous `set -u`, la première tuait le
# script ici même, après la copie du jour. La passe de rattrapage n'a donc
# jamais tourné, ni le relevé de continuité (constaté le 06/09/2026 en
# vérifiant #775 en production, pas par un contrôle). Cf. §Garde-fou ci-dessous.
AUTRE_NOEUD=$(role_peer "$SOURCE_NOEUD")
AUTRE_IP=$(role_ip "$AUTRE_NOEUD")
if [ -z "$AUTRE_IP" ]; then
  # Chaîne vide = nœud inconnu de la table. INCONNU, jamais un silence.
  log "    ! Pair de $SOURCE_NOEUD introuvable dans lib-role.sh — rattrapage INCONNU."
  AUTRE_NOEUD=""; AUTRE_IP=""
fi

RATTRAPEES=0
[ -n "$AUTRE_IP" ] && log "  Rattrapage sur $AUTRE_NOEUD ($AUTRE_IP)…"
if [ -z "$AUTRE_IP" ]; then
  : # pair inconnu — déjà dit ci-dessus, ne pas le redire en « injoignable »
elif LISTE_AUTRE=$($SSH_CMD "$EXPORT_SSH_USER@$AUTRE_IP" "$LIRE ls /b" 2>/dev/null); then
  #  🔴 La liste blanche s'applique AVANT l'union : un nom fabriqué ne doit pas
  #  même entrer dans le calcul de ce qu'on garde.
  DISTANTES=""
  for nom in $LISTE_AUTRE; do
    nom_valide "$nom" && DISTANTES="$DISTANTES$nom"$'\n'
  done
  LOCALES=$(ls -1 "$EXPORT_DEST"/hostachy_backup_*.tar.gz 2>/dev/null | xargs -r -n1 basename | sort)
  #  On ne tire QUE ce qu'on garderait : sans cette borne, le rattrapage
  #  téléchargeait six archives que la rotation effaçait juste après.
  A_TIRER=$(archives_a_rattraper "$EXPORT_KEEP" "$LOCALES" "$DISTANTES")
  for nom in $A_TIRER; do
    if transferer_archive "$AUTRE_IP" "$nom" "$EXPORT_DEST/$nom"; then
      RATTRAPEES=$((RATTRAPEES + 1))
      log "    + $nom (absent localement)"
    else
      log "    ! $nom — transfert impossible depuis $AUTRE_NOEUD"
    fi
  done
  [ "$RATTRAPEES" = "0" ] && log "    (rien à rattraper)"
else
  log "    ! $AUTRE_NOEUD injoignable — rattrapage INCONNU, la série peut avoir des trous."
fi

# ── 5. Rotation des copies locales ───────────────────────────────────────────
if [ "$STATUT" = "succes" ]; then
  SUPPRIMEES=0
  while IFS= read -r vieux; do
    [ -n "$vieux" ] || continue
    rm -f "$EXPORT_DEST/$vieux" && SUPPRIMEES=$((SUPPRIMEES + 1))
  done < <(ls -1 "$EXPORT_DEST"/hostachy_backup_*.tar.gz 2>/dev/null | xargs -r -n1 basename | sort | archives_a_supprimer "$EXPORT_KEEP")
  log "  Rotation : $SUPPRIMEES ancienne(s) copie(s) supprimée(s), $EXPORT_KEEP conservée(s)."
fi

# ── 6. Relevé de continuité de la série (#775) ──────────────────────────────
# Le relevé de continuité : il porte sur ce qu'on DÉTIENT, après rattrapage.
#  ⚠️ La fenêtre SUIT la rétention : avec deux copies conservées, réclamer
#  quatorze jours ferait crier ce relevé tous les jours sur un fait normal — et
#  un contrôle qui crie sur du légitime finit désarmé (leçon de C16).
MANQUANTS=$(ls "$EXPORT_DEST" 2>/dev/null | jours_manquants "$EXPORT_KEEP")
if [ -n "$MANQUANTS" ]; then
  log "  ⚠️  Jours absents de la copie hors site ($EXPORT_KEEP derniers) : $MANQUANTS"
fi

# ── 6 bis. Le registre des installations (#1896) ────────────────────────────
# Sa propre série, sur le nœud qui sert ; son verdict ne touche pas STATUT —
# voir `copier_plateforme`.
copier_plateforme "$SOURCE_IP"

# ── 6 ter. Les archives d'affaires échues (#2014) ───────────────────────────
# Toutes, sans rotation ; l'accusé part avec le rapport, qui a la clé.
copier_archives_affaires "$SOURCE_IP"

# ── 7. Rapport à l'API (canal cron existant) ─────────────────────────────────
# La clé est lue sur le nœud, pas recopiée sur le poste : un secret dupliqué est
# un secret à faire tourner deux fois.
# Le dépouillement se fait ICI, pas dans la commande distante : imbriquer des
# apostrophes et des guillemets dans un `tr` passé à ssh produisait une commande
# invalide, et la clé revenait vide alors qu'elle est bien dans le .env
# (04/08/2026). Les codes octaux \042 \047 évitent toute quote dans la source.
LIGNE_CLE=$($SSH_CMD "$SSH_CIBLE" "grep -m1 '^MAINTENANCE_KEY=' /opt/5hostachy/.env" 2>/dev/null || true)
MAINTENANCE_KEY=$(printf '%s' "${LIGNE_CLE#MAINTENANCE_KEY=}" | tr -d '\042\047\r')
if [ -z "$MAINTENANCE_KEY" ]; then
  log "  ⚠ MAINTENANCE_KEY illisible — rapport non enregistré (l'export, lui, a bien eu lieu)."
else
  FIN=$(date -u +%Y-%m-%dT%H:%M:%S)
  # `archive` porte l'horodatage dans son nom : c'est ce que le contrôle de
  # santé relit pour distinguer « l'export tourne » de « la copie est fraîche ».
  # Un export quotidien qui recopie fidèlement la même archive périmée est un
  # faux vert — c'est exactement ce cas que le champ permet de démasquer.
  # Construction et envoi mutualisés (lib-rapport.sh) : trois scripts rendent
  # compte, un seul sait fabriquer la charge utile. La clé, elle, est lue par
  # SSH sur le nœud ci-dessus et non dans un `.env` local — ce script tourne sur
  # le poste, qui n'en a pas.
  #  ⚠ Sourcé AVANT de construire DETAILS : `rapport_echapper` y est utilisé.
  source "$SCRIPT_DIR/scripts/lib/lib-rapport.sh"

  #  `integrite` est un MESSAGE (les écarts de l'export, par table) — donc du
  #  texte libre, qui peut porter tabulations et guillemets.
  #  Le laisser brut fabrique un JSON invalide que l'API rejette en 422 : c'est
  #  ce qui est arrivé à la maintenance hebdomadaire le 16/08/2026, et le compte
  #  rendu perdu aurait été précisément celui d'une sauvegarde corrompue.
  #  `archive_plateforme` et `integrite_plateforme` : lus par le contrôle de la
  #  PLATEFORME (`registre/sauvegarde.py`), jamais par celui de la copropriété.
  DETAILS=$(printf '{"archive":"%s","taille_octets":%s,"integrite":"%s","empreinte_verifiee":"%s","destination":"%s","versions_conservees":%s,"archive_plateforme":"%s","integrite_plateforme":"%s"}' \
    "$(rapport_echapper "$ARCHIVE")" "${OCTETS:-0}" "$(rapport_echapper "${INTEGRITE:-}")" \
    "$EMPREINTES" "$(rapport_echapper "${EXPORT_DEST:-}")" "${EXPORT_KEEP:-0}" \
    "$(rapport_echapper "$PLATEFORME_ARCHIVE")" "$(rapport_echapper "$PLATEFORME_INTEGRITE")")
  rapport_envoyer "http://$SOURCE_IP" "$MAINTENANCE_KEY" \
    "$(rapport_payload export_hors_site "$SOURCE_NOEUD" applicative "$STATUT" \
        "$((SECONDS - T0))" "$DETAILS" \
        "$([ "$STATUT" = "succes" ] || printf '%s' "$MESSAGE")" "$DEBUT" "$FIN")" \
    "Rapport"
  accuser_archives_affaires "http://$SOURCE_IP" "$MAINTENANCE_KEY"
fi

# ── 8. Résumé lisible ────────────────────────────────────────────────────────
# Ce script est lancé à la main, par un humain qui regarde la console : le
# dernier écran doit répondre sans effort à « est-ce que ma sauvegarde est là,
# et est-elle bonne ? ». Un code de sortie ne se lit pas dans une fenêtre qui
# se referme.
echo
if [ "$STATUT" = "succes" ]; then
  echo "  ✅ SAUVEGARDE HORS SITE À JOUR"
  echo "     Archive     : $ARCHIVE"
  echo "     Taille      : $(awk -v o="${OCTETS:-0}" 'BEGIN{printf "%.1f Mo", o/1048576}')"
  echo "     Emplacement : $EXPORT_DEST"
  echo "     Vérifiée    : empreinte identique à la source, export : chaque table compte ses lignes"
  echo "     Source      : $SOURCE_NOEUD ($SOURCE_IP)"
  echo "     Registre    : ${PLATEFORME_ARCHIVE:-—} ($PLATEFORME_INTEGRITE)"
  echo "     Affaires    : $AFFAIRES_RESUME (archives conservées sans rotation)"
else
  echo "  ❌ EXPORT ÉCHOUÉ — AUCUNE COPIE FIABLE N'A ÉTÉ PRODUITE"
  echo "     Motif : $MESSAGE"
  echo "     Ne pas considérer $EXPORT_DEST comme à jour."
fi
echo
log "===== Export hors site terminé : $STATUT ====="
[ "$STATUT" = "succes" ] || exit 1
exit 0
