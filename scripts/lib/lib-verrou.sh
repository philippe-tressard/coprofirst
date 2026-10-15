#!/usr/bin/env bash
#  Le VERROU de bascule — `.bascule-lock`, posé et relâché sur les deux nœuds.
#
#  Extrait de `bascule.sh` le 12/09/2026 : le geste y était écrit CINQ fois, et le
#  plafond de modularité a refusé la correction qui le rendait symétrique. La
#  coupe suit la nature de l'objet — un verrou partagé entre deux machines, que
#  tout script d'exploitation touchant au rôle doit savoir poser.
#
#  ## Ce que le verrou protège
#
#  `auto-deploy.sh` tourne toutes les cinq minutes sur les DEUX nœuds et décide
#  d'après `.active`. Pendant une bascule, ce fichier est en train de changer :
#  `action_auto_deploy` rend « attendre » dès qu'elle voit le verrou, **quel que
#  soit le rôle lu**. C'est la seule coordination entre les deux crons.
#
#  L'appelant fournit `$REPO`, `$PEER_IP`, `$SSH_CMD`, `run` et `log`.

#  ── Le verrou de bascule, posé et relâché des DEUX côtés ────────────────────
#
#  🔴 Il ne l'était que sur le PEER jusqu'au 12/09/2026 — split-brain en
#  production (#915, et `project_split_brain_verrou_bascule`). Le nœud exposé est
#  celui qui BASCULE : son rôle change, donc son propre `auto-deploy` peut lire un
#  `.active` périmé et démarrer les conteneurs.
#
#  En fonctions parce que le geste apparaissait CINQ fois, et que ses deux moitiés
#  doivent rester accordées sur chacun des cinq chemins, rollback compris —
#  `test_verrou_bascule.py` en vérifie la symétrie.
#  ⚠️ Sans `run` ni `set -e` : appelée depuis les chemins d'ABANDON, où elle doit
#  aboutir même si le peer est injoignable. Un verrou local jamais relâché
#  laisserait ce nœud sans aucun déploiement, en silence.
verrou_liberer() {
  $SSH_CMD ptressard@"$PEER_IP" "rm -f /opt/5hostachy/.bascule-lock" 2>/dev/null || true
  rm -f "$REPO/.bascule-lock" 2>/dev/null || true
}

#  🔴 Le `trap` est armé PAR la pose, et c'est la règle la plus déployée :
#  `health-watch.sh` et `MaJ-Hostachy.sh` le font tous deux depuis toujours
#  (`touch` puis `trap 'rm -f …' EXIT`). `bascule.sh` était le seul à libérer son
#  verrou à la main, sur cinq chemins — et c'est exactement ce qui permet d'en
#  oublier un. Une sortie imprévue (`set -e`, `kill`) le relâche désormais aussi.
#
#  ⚠️ Le `trap` remplace les libérations dispersées, il ne s'y ajoute pas :
#  `verrou_liberer` reste appelable pour dire « la bascule est finie » au journal,
#  et elle est idempotente (`rm -f`).
verrou_poser() {
  run "$SSH_CMD ptressard@$PEER_IP 'touch /opt/5hostachy/.bascule-lock'"
  run "touch $REPO/.bascule-lock"
  trap verrou_liberer EXIT
  log "  → Lock bascule posé sur les DEUX nœuds (libération garantie à la sortie)."
}

#  Une opération LONGUE (la bascule des données, DI-7c : export puis import,
#  plusieurs minutes) rafraîchit son verrou entre deux étapes : passé
#  `VERROU_STALE_S`, health-watch le croirait orphelin et l'effacerait, et
#  rebasculerait un site qu'on a coupé exprès. Sans `run` : un pair injoignable
#  à cet instant ne doit pas interrompre l'opération — le verrou local suffit à
#  ce nœud, et celui du pair n'a que quelques minutes.
verrou_prolonger() {
  touch "$REPO/.bascule-lock" 2>/dev/null || true
  $SSH_CMD ptressard@"$PEER_IP" "touch /opt/5hostachy/.bascule-lock" 2>/dev/null || true
}

#  ── La PÉREMPTION du verrou — une seule définition, trois lecteurs ──────────
#
#  🔴 Elle était écrite TROIS fois, avec trois seuils, et le quatrième lecteur
#  n'en avait aucune (12/09/2026, #915) :
#
#  | Lecteur | Notion d'orphelin | Seuil | Ce qu'il en fait |
#  |---|---|---|---|
#  | `health-watch.sh` | oui | `LOCK_MAX_AGE_S=900` (15 min) | **supprime** le verrou |
#  | `check-reliability.sh` C12 | oui | `LOCK_STALE_MIN=20` (20 min) | WARN au digest |
#  | `bascule_en_cours` (`lib-verdicts`) | oui | son paramètre `stale_min` | tait trois contrôles |
#  | `auto-deploy.sh` | **AUCUNE** | — | **attend indéfiniment** |
#
#  Deux défauts, et le second annule le garde-fou sur lequel #915 se reposait :
#
#  1. **`auto-deploy` ne connaissait pas la péremption.** Un verrou orphelin le
#     figeait sans limite : plus aucun déploiement, en silence. Il ne se
#     débloquait que parce qu'un AUTRE script — `health-watch` — supprimait le
#     fichier. Un couplage entre deux crons que rien ne disait et que rien ne
#     testait.
#  2. **health-watch supprimait à 15 min, C12 n'alertait qu'à 20.** La fenêtre
#     d'alerte était donc VIDE : le verrou disparaissait toujours avant d'être
#     signalable. Le contrôle était structurellement muet — et #915 le déclarait
#     « acceptable » en s'y fiant (sous le numéro C25, qui ne traite pas ce
#     sujet). C'est le cas zéro de `standards/04` §2 : un contrôle qui ne peut
#     pas mesurer ne rend pas OK, il ne rend rien.
#
#  Le seuil est ici, en SECONDES, parce que c'est la granularité du fichier
#  (`stat -c %Y`) et celle du plus fin des lecteurs. Une bascule dure ~40 s, une
#  MAJ 2 à 5 min : 15 minutes, c'est déjà trois fois le pire cas.
VERROU_STALE_S=${VERROU_STALE_S:-900}

#  Le verrou est-il RÉCENT, donc une opération réellement en cours ? (PURE)
#
#  ⚠️ Un horodatage absent ou illisible rend **"oui"**, et le sens de cette
#  prudence est l'inverse de celui de `bascule_en_cours` : là-bas on ne tait un
#  contrôle que sur une preuve, donc l'inconnu parle ; ici on déciderait de
#  DÉMARRER des conteneurs, donc l'inconnu s'abstient. Le fichier existe — c'est
#  un fait —, seul son âge manque : conclure « périmé » sur une absence de
#  mesure, ce serait rouvrir le split-brain du 12/09 par la porte du contrôle.
verrou_recent() {  # $1 = mtime · $2 = maintenant · $3 = seuil (s) → oui/non
  local mtime="${1:-}" maintenant="${2:-0}" seuil="${3:-$VERROU_STALE_S}" age
  case "$mtime" in ''|*[!0-9]*) echo oui; return ;; esac
  [ "$mtime" -le 0 ] && { echo oui; return; }
  age=$(( maintenant - mtime ))
  #  Horloge en arrière (NTP qui recale, C11) : l'âge négatif n'est pas une
  #  preuve de péremption. On s'abstient, comme ci-dessus.
  [ "$age" -lt 0 ] && { echo oui; return; }
  [ "$age" -lt "$seuil" ] && echo oui || echo non
}

#  ── Le verrou de DÉPLOIEMENT — `.auto-deploy.lock`, tenu par auto-deploy ────
#
#  `auto-deploy.sh` le tient (flock exclusif) de son lancement à sa fin, sur
#  chaque nœud. Trois lecteurs le sondent : C1 (`lib-collecte.sh`, pour ne pas
#  crier au loup pendant un redémarrage de l'API), le FAILOVER (`lib-failover.sh`,
#  #1997 : on ne bascule pas sous un nœud qui se redéploie) et l'ISOLEMENT de
#  l'ancien actif, qui le prend pour ne jamais arrêter un nœud au milieu d'un
#  déploiement qui le relancerait derrière lui.
#
#  La sonde, UNE fois : un verrou PARTAGÉ pris et relâché aussitôt, qui échoue
#  face à l'exclusif du déploiement et ne bloque pas un déploiement qui
#  démarrerait pile ici. Elle s'insère dans une chaîne simple-quotée (la
#  collecte) : AUCUNE apostrophe, et `$R` désigne le dépôt chez le nœud sondé.
#  Elle pose `DEP=oui|non`.
SONDE_DEPLOIEMENT='DEP=non; if command -v flock >/dev/null 2>&1 && [ -f $R/.auto-deploy.lock ]; then ( flock -n -s 9 ) 9<>$R/.auto-deploy.lock 2>/dev/null || DEP=oui; fi'

#  Le DÉBUT du déploiement en cours : `exec 9>` réécrit le fichier du verrou à
#  CHAQUE lancement, même celui qui trouve le verrou pris — son âge ne dit donc
#  rien. Le détenteur marque son début ici, une fois le verrou acquis.
DEBUT_DEPLOIEMENT=.auto-deploy.debut

#  Marquer le début (auto-deploy, MaJ-Hostachy). Lancé en root, un fichier CRÉÉ
#  prend le propriétaire du dépôt : le cron `ptressard` doit pouvoir le réécrire.
marquer_debut_deploiement() {  # $1 = dépôt
  touch "$1/$DEBUT_DEPLOIEMENT" 2>/dev/null || return 0
  [ "$(id -u)" -eq 0 ] && chown --reference="$1" "$1/$DEBUT_DEPLOIEMENT" 2>/dev/null
  return 0
}

#  La commande envoyée au pair : `libre`, ou `tenu <mtime du début>`.
#  $1 = le dépôt chez le nœud sondé (paramétré pour que l'autotest l'EXÉCUTE).
etat_deploiement_sh() {
  printf 'R=%s; %s; [ "$DEP" = oui ] && echo "tenu $(stat -c %%Y $R/%s 2>/dev/null)" || echo libre' \
    "${1:-/opt/5hostachy}" "$SONDE_DEPLOIEMENT" "$DEBUT_DEPLOIEMENT"
}

#  PURE : ce que dit la sonde du pair → libre | en-cours | bloque | inconnu
#  $1 sortie de ETAT_DEPLOIEMENT_SH (vide = pair injoignable) · $2 maintenant
#  `bloque` : le verrou est tenu depuis plus que `VERROU_STALE_S` — un
#  déploiement qui ne finit pas ne doit pas interdire le failover pour toujours.
#  Début illisible : `verrou_recent` rend « oui » (on s'abstient), comme pour
#  `.bascule-lock` — le verrou est un fait, seul son âge manque.
etat_deploiement() {
  case "${1:-}" in
    libre) echo libre ;;
    tenu*) [ "$(verrou_recent "${1#tenu }" "${2:-0}" "$VERROU_STALE_S")" = oui ] && echo en-cours || echo bloque ;;
    *)     echo inconnu ;;
  esac
}

#  ── C12 — une bascule a-t-elle été TUÉE ? ───────────────────────────────────
#
#  Reçu de `check-reliability.sh` le 12/09/2026 : ce contrôle porte sur le verrou,
#  donc il vit avec lui. Deux raisons de changer, deux fichiers.
#
#  ⚠️ Cette fonction n'est PAS autonome — comme `conformite_verdicts`, elle
#  emploie `ok`, `warn`, `$SELF`, `$PEER` et `verdict_verrou_orphelin`, tous
#  définis par son appelant. Les deux autres consommateurs du module
#  (`auto-deploy`, `health-watch`) ne l'appellent jamais : ils ne prennent que
#  `verrou_recent` et le seuil.
verrou_verdicts() {
  local maintenant pair n t j
  maintenant=$(date +%s)
  #  ── C26 — le verrou a-t-il été posé AVANT la première action ? ────────────
  #  🔴 #915 se terminait sur « les tests le vérifient PAR LA FORME DU SCRIPT,
  #  PAS PAR SON EXÉCUTION ». Celui-ci lit le journal de la dernière bascule
  #  réellement exécutée. La décision est pure : `verdict_ordre_bascule`.
  for pair in "$SELF:${S_bascule_journal:-}" "$PEER:${P_bascule_journal:-}"; do
    n=${pair%%:*}; j=${pair#*:}
    if [ -z "$j" ]; then
      warn "Ordre du verrou sur $n : INCONNU — journal de bascule illisible ou absent"
      continue
    fi
    case "$(printf '%s' "$j" | base64 -d 2>/dev/null | verdict_ordre_bascule)" in
      OK)     ok "Dernière bascule sur $n : verrou posé AVANT la première action" ;;
      TARDIF) fail "Dernière bascule sur $n : verrou posé APRÈS une action — auto-deploy a pu passer entre les deux (#915)" ;;
      *)      warn "Ordre du verrou sur $n : INCONNU — aucune pose relevée dans le journal de la dernière bascule" ;;
    esac
  done
  #  Le NETTOYAGE journalisé — la seule trace qui subsiste, health-watch effaçant
  #  le verrou lui-même.
  for pair in "$SELF:${S_orphelin_dernier:-inconnu}" "$PEER:${P_orphelin_dernier:-inconnu}"; do
    n=${pair%%:*}; t=${pair#*:}
    case "$(verdict_verrou_orphelin "$t" "$maintenant" 86400)" in
      OK)       ok "Aucune bascule tuée sur $n depuis 24 h (trace de nettoyage absente)" ;;
      RECENT:*) warn "Bascule/MAJ TUÉE sur $n il y a $(( (maintenant - t) / 60 )) min — verrou orphelin nettoyé par health-watch (coupure, kill -9 ou gel ?)" ;;
      *)        warn "Bascule tuée sur $n : INCONNU — journal health-watch illisible, le contrôle ne peut pas mesurer" ;;
    esac
  done
  #  Et le verrou PRÉSENT ne dit qu'une chose : une opération est en cours. Son
  #  âge n'est plus signalé ici — c'est health-watch qui le nettoie, et la boucle
  #  ci-dessus qui le rapporte. Deux contrôles sur le même fait, avec deux
  #  seuils, c'est la divergence que ce lot supprime.
  for pair in "$SELF:${S_lock:-0}" "$PEER:${P_lock:-0}"; do
    n=${pair%%:*}; t=${pair#*:}
    case "$t" in ''|*[!0-9]*) continue ;; esac
    [ "$t" -eq 0 ] && continue
    ok ".bascule-lock présent sur $n ($(( (maintenant - t) / 60 )) min — opération en cours)"
  done
}
