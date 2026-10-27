#!/bin/bash
# =============================================================================
#  lib-ci-verrou.sh — Qui tient le rejeu de la CI, qui attend, et l'orphelin
#
#  Module SOURCÉ par `lib-ci-replay.sh` (donc par `rejouer-ci.sh`), par
#  `etat-rejeu.sh` et par `file-rejeu.sh` ; exécuté seulement pour son
#  `--selftest` (job `test-scripts`). Pas de bit x.
#
#  POURQUOI (#2225, 24/10/2026). Un seul rejeu à la fois sur le poste (#1417),
#  25 à 50 min chacun, et plusieurs sessions se le disputent. Ce jour-là : deux
#  sessions lancées à la même minute ; une session qui a pris le verrou sans
#  passer par la file ; et un rejeu dont la tâche avait été tuée, mais dont le
#  script, sans parent, a tenu le verrou 20 min — le verrou ne contenait qu'un
#  pid, et personne ne savait à qui il était. Ce module dit QUI tient le
#  verrou, OÙ il en est, QUI attend, et arrête un rejeu dont le lanceur a
#  disparu.
#
#  CE QUI VIT DANS LE RÉPERTOIRE GIT COMMUN (les worktrees le partagent) :
#    rejeu-ci.verrou/           le verrou : `mkdir` atomique (#1417)
#      pid                      le rejeu qui le tient — SEUL juge de la propriété (#1808)
#      proprietaire             la fiche : worktree, branche, sha, départ, jobs, libellé, ancre
#      battement                l'étape en cours, depuis quand, son rang, les étapes extraites
#      pouls                    l'heure, réécrite toutes les REJEU_POULS_S par le veilleur
#    rejeu-ci.file/<clé>.<pid>  un ticket par rejeu qui attend (`--attendre`) : la clé
#                               (horodatage en ns) fait l'ORDRE, le pid l'IDENTITÉ
#    rejeu-ci-file.log          chaque geste du coordinateur (reprise, passer devant,
#                               retrait), daté, avec son motif
#
#  DEUX RÈGLES qui ne se négocient pas :
#   - jamais un kill du processus d'une AUTRE session : le veilleur n'arrête
#     que le rejeu qui l'a lancé et ses descendants ;
#   - un verrou dont le pid VIT ne se reprend qu'explicitement, avec un motif
#     (`file-rejeu.sh reprendre`) ; seul un pid MORT se reprend seul, comme avant.
# =============================================================================

#: Intervalle du veilleur et de l'attente en file (secondes).
REJEU_POULS_S=${REJEU_POULS_S:-10}
#: Au-delà, un pouls ou un ticket qu'on ne rafraîchit plus est FIGÉ (secondes).
REJEU_SEUIL_FIGE_S=${REJEU_SEUIL_FIGE_S:-180}
#: Une attente en file qui dépasse ceci abandonne, sans rien rejouer (secondes).
REJEU_ATTENTE_MAX_S=${REJEU_ATTENTE_MAX_S:-14400}

ci_dossier_commun() {      # → le répertoire git COMMUN (REJEU_DOSSIER_COMMUN l'impose : tests)
  if [ -n "${REJEU_DOSSIER_COMMUN:-}" ]; then printf '%s\n' "$REJEU_DOSSIER_COMMUN"; return; fi
  (cd "$(git rev-parse --git-common-dir 2>/dev/null || echo .git)" && pwd)
}

# ── Un seul rejeu à la fois (#1417, 28/09/2026) ─────────────────────────────
#  Deux rejeux simultanés se sabotent — serveurs e2e sur la même machine,
#  délais d'hydratation dépassés sous la charge — et chacun rend alors des
#  échecs qui ne parlent pas de son lot. C'est arrivé deux fois le 27/09, entre
#  deux sessions : la consigne « un seul rejeu à la fois » ne suffisait pas.
ci_verrou_etat() {         # $1 = pid lu dans le verrou · $2 = vivant oui|non → libre|occupe|orphelin (PURE)
  [ -z "${1:-}" ] && { echo libre; return; }
  [ "${2:-non}" = oui ] && echo occupe || echo orphelin
}
#  #1808 (10/10/2026) : un verrou a DISPARU sous un rejeu vivant. La reprise
#  d'un orphelin faisait `rm -rf` sur un verrou relu AVANT — entre-temps, un
#  autre rejeu pouvait l'avoir reposé —, et les traps le retiraient sans
#  regarder à qui il était. Deux règles, et le script n'en a pas d'autre :
ci_verrou_liberer() {      # $1 = verrou · $2 = pid qui libère → retiré seulement s'il est à lui
  [ "$(cat "$1/pid" 2>/dev/null)" = "$2" ] && rm -rf "$1"
  return 0
}
ci_verrou_reprendre() {    # $1 = verrou · $2 = pid orphelin lu → 0 libre | 1 il a changé de main
  local cote="$1.repris.$$"   # `mv` est atomique : on juge ce qu'on a DÉPLACÉ, pas ce qu'on a lu
  mv -T "$1" "$cote" 2>/dev/null || return 0
  [ "$(cat "$cote/pid" 2>/dev/null)" = "$2" ] && { rm -rf "$cote"; return 0; }
  mv -T "$cote" "$1" 2>/dev/null ||                  # rendu à son propriétaire
    echo "⚠ verrou vivant laissé dans $cote : un troisième rejeu a pris la place" >&2
  return 1
}
#  Le pid relu après écriture : un verrou déplacé pendant ce temps n'est pas à nous (#1808).
ci_verrou_poser() {        # $1 = verrou · $2 = pid → 0 pris | 1 tenu par un autre
  mkdir "$1" 2>/dev/null && echo "$2" > "$1/pid" 2>/dev/null \
    && [ "$(cat "$1/pid" 2>/dev/null)" = "$2" ]
}

# ── Lire une fiche « clé=valeur » ────────────────────────────────────────────
ci_champ() {               # $1 = fichier · $2 = clé (constante du code) → valeur, vide si absente
  sed -n "s/^$2=//p" "$1" 2>/dev/null | tail -1
}
ci_ecrire_atomique() {     # $1 = fichier, contenu sur stdin — jamais lu à moitié écrit
  cat > "$1.tmp.$$" 2>/dev/null && mv -f "$1.tmp.$$" "$1" 2>/dev/null
}
#  La fiche d'un rejeu : la même pour le verrou et pour un ticket de la file.
ci_fiche() {               # $1 = pid · $2 = ancre · $3 = jobs (vide : tous) → stdout
  printf 'pid=%s\nancre=%s\nworktree=%s\nbranche=%s\nsha=%s\ndepart=%s\njobs=%s\nlibelle=%s\n' \
    "$1" "$2" "$(git rev-parse --show-toplevel 2>/dev/null)" \
    "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" "$(git rev-parse --short HEAD 2>/dev/null)" \
    "$(date +%s)" "${3:-tous}" "$(printf '%s' "${REJEU_PROPRIETAIRE:-}" | tr -d '\r\n\t' | cut -c1-120)"
}
ci_verrou_signer() {       # $1 = verrou · $2 = fiche — le départ est celui du verrou, pas de l'inscription
  { printf '%s\n' "$2" | sed 's/^depart=/inscrit=/'; echo "depart=$(date +%s)"; } \
    | ci_ecrire_atomique "$1/proprietaire"
  date +%s | ci_ecrire_atomique "$1/pouls"
}
#  Appelé à chaque étape : rang compté ici, pour que l'appelant n'ait qu'une ligne.
_CI_ETAPE_RANG=0
ci_battement() {           # $1 = verrou · $2 = job · étape · $3 = étapes extraites
  _CI_ETAPE_RANG=$((_CI_ETAPE_RANG + 1))
  printf 'etape=%s\ndepuis=%s\nrang=%s\nextraites=%s\n' "$2" "$(date +%s)" "$_CI_ETAPE_RANG" \
    "${3:-?}" | ci_ecrire_atomique "$1/battement"
  return 0
}

# ── Le lanceur existe-t-il encore ? ──────────────────────────────────────────
#  L'ANCRE est l'ancêtre le plus haut du rejeu au départ, avant le pid 1 : le
#  shell que l'outil a lancé, ou celui de la fenêtre de terminal. Quand il
#  meurt, ses descendants sont rattachés ailleurs (pid 1 sous MSYS, mesuré le
#  24/10) : l'ancre n'est plus dans la chaîne. Un rejeu lancé directement par
#  un processus natif (PPID = 1) n'a pas d'ancre : il est « non surveillé », et
#  il le dit — jamais un arrêt sur une absence qu'on ne sait pas mesurer.
ci_ppid_de() {             # $1 = pid → son parent, vide s'il n'existe plus (lecture seule)
  if [ -r "/proc/$1/ppid" ]; then cat "/proc/$1/ppid" 2>/dev/null
  else ps -o ppid= -p "$1" 2>/dev/null | tr -d ' '; fi
}
ci_chaine_ancetres() {     # $1 = pid → ses ancêtres, du parent au dernier avant 1 (lecture seule)
  local p="$1" q n=0
  while [ "$n" -lt 40 ]; do
    q=$(ci_ppid_de "$p")
    case "$q" in ''|*[!0-9]*|0|1) break ;; esac
    printf '%s ' "$q"; p=$q; n=$((n + 1))
  done
  echo
}
ci_ancre() {               # $1 = chaîne d'ancêtres → le plus haut, vide : non surveillable (PURE)
  printf '%s\n' "${1:-}" | awk 'NF { print $NF }'
}
ci_parent_etat() {         # $1 = ancre · $2 = chaîne actuelle → non_surveille|present|disparu (PURE)
  [ -z "${1:-}" ] && { echo non_surveille; return; }
  case " ${2:-} " in *" $1 "*) echo present ;; *) echo disparu ;; esac
}

# ── Arrêter ses PROPRES descendants ──────────────────────────────────────────
#  Bash diffère un signal tant que son enfant au premier plan tourne : un pytest
#  de 10 min garderait le verrou 10 min. On arrête donc les descendants du
#  rejeu, les plus profonds d'abord ; sous Windows, `taskkill /T` emporte aussi
#  les enfants natifs (node, python) que la table MSYS ne voit pas.
ci_descendants() {         # $1 = pid racine · stdin « pid ppid [winpid] » → « pid winpid », profonds d'abord (PURE)
  awk -v r="$1" '
    { par[$1] = $2; w[$1] = ($3 == "" ? "-" : $3); ordre[NR] = $1 }
    END {
      for (i = 1; i <= NR; i++) {
        p = ordre[i]; q = p; d = 0
        while ((q in par) && q != r && d < 60) { q = par[q]; d++ }
        if (q == r && p != r) printf "%d %s %s\n", d, p, w[p]
      }
    }' | sort -k1,1nr -k2,2n | awk '{ print $2, $3 }'
}
ci_table_processus() {     # → « pid ppid winpid » de tous les processus visibles (lecture seule)
  local t
  if t=$(ps -eo pid=,ppid= 2>/dev/null) && [ -n "$t" ]; then
    printf '%s\n' "$t" | awk '{ print $1, $2, "-" }'; return
  fi
  #  MSYS/Cygwin : PID PPID PGID WINPID … — une lettre d'état peut précéder.
  ps -e 2>/dev/null | awk 'NR > 1 { sub(/^[^0-9]+/, ""); print $1, $2, $4 }'
}
ci_arreter_descendants() { # $1 = pid du rejeu · $2 = pid épargné (le veilleur, et les siens) · $3 = table relevée avant
  local table="${3:-}" cibles exclus pid winpid
  [ -n "$table" ] || table=$(ci_table_processus)
  exclus=" $2 $(printf '%s\n' "$table" | ci_descendants "$2" | awk '{ printf "%s ", $1 }')"
  cibles=$(printf '%s\n' "$table" | ci_descendants "$1")
  while read -r pid winpid; do
    [ -z "$pid" ] && continue
    case "$exclus" in *" $pid "*) continue ;; esac
    if [ "${winpid:--}" != "-" ] && command -v taskkill >/dev/null 2>&1; then
      taskkill //T //F //PID "$winpid" >/dev/null 2>&1
    fi
    kill -TERM "$pid" 2>/dev/null
  done <<< "$cibles"
  return 0
}
#  Le veilleur : en arrière-plan, sortie jetée. Il bat le pouls, et si l'ancre a
#  disparu il signe l'arrêt dans le battement, relève les descendants, signale
#  le rejeu (dont le trap TERM sort par `exit`, donc par le trap EXIT qui
#  libère le verrou), puis arrête les descendants relevés AVANT le signal — un
#  rejeu sans trap meurt aussitôt, et ses enfants rattachés ailleurs ne
#  seraient plus les siens. Il recommence tant que le rejeu vit : une étape
#  lancée entre le relevé et le signal y passe aussi. Il s'éteint de lui-même
#  quand le verrou n'est plus au rejeu ou que le rejeu est mort.
ci_veilleur() {            # $1 = verrou · $2 = pid du rejeu · $3 = ancre
  local table
  while kill -0 "$2" 2>/dev/null && [ "$(cat "$1/pid" 2>/dev/null)" = "$2" ]; do
    date +%s | ci_ecrire_atomique "$1/pouls"
    if [ "$(ci_parent_etat "$3" "$(ci_chaine_ancetres "$2")")" = disparu ]; then
      printf 'arret=%s\nmotif=lanceur disparu (ancre %s)\n' "$(date +%s)" "$3" >> "$1/battement"
      table=$(ci_table_processus)
      kill -TERM "$2" 2>/dev/null
      ci_arreter_descendants "$2" "$BASHPID" "$table"
      for _ in 1 2 3 4 5; do
        kill -0 "$2" 2>/dev/null || break
        sleep 1; ci_arreter_descendants "$2" "$BASHPID"
      done
      return 0
    fi
    sleep "$REJEU_POULS_S"
  done
}

# ── Le diagnostic d'un verrou ────────────────────────────────────────────────
#  « orphelin » exige les DEUX : lanceur disparu ET pouls figé. Un lanceur
#  disparu avec un pouls frais, c'est un veilleur en train d'arrêter son rejeu.
ci_rejeu_diagnostic() {    # $1 pid · $2 vivant oui|non · $3 present|disparu|non_surveille · $4 âge du pouls (s, vide : aucun) · $5 seuil (PURE)
  [ -z "${1:-}" ] && { echo libre; return; }
  [ "${2:-non}" = oui ] || { echo perime; return; }
  [ -z "${4:-}" ] && { echo sans_pouls; return; }
  if [ "$4" -gt "${5:-180}" ]; then
    [ "${3:-}" = disparu ] && echo orphelin || echo fige
  else
    [ "${3:-}" = disparu ] && echo arret_en_cours || echo actif
  fi
}
ci_rejeu_diagnostic_dit() { # $1 = diagnostic → la phrase (PURE)
  case "$1" in
    libre)          echo "libre — aucun rejeu ne tourne" ;;
    actif)          echo "actif" ;;
    perime)         echo "périmé — son pid est mort : le prochain rejeu le reprend seul" ;;
    arret_en_cours) echo "arrêt en cours — son lanceur a disparu, le veilleur l'arrête" ;;
    orphelin)       echo "ORPHELIN — lanceur disparu et pouls figé : reprise explicite (file-rejeu.sh reprendre)" ;;
    fige)           echo "FIGÉ — pouls arrêté, lanceur présent : demander à sa session avant toute reprise" ;;
    sans_pouls)     echo "sans pouls — verrou d'un script antérieur à #2225, ou tout juste pris" ;;
    *)              echo "inconnu ($1)" ;;
  esac
}
#  L'âge d'un horodatage, jamais négatif (#2229) : un repère posé APRÈS la lecture de l'heure
#  (une étape qui démarre pendant que `etat-rejeu.sh` s'affiche) donnait « il y a ? ».
ci_age_s() {               # $1 = horodatage · $2 = maintenant → secondes, 0 au minimum ; vide si illisible (PURE)
  case "${1:-}" in ''|*[!0-9]*) return 0 ;; esac
  case "${2:-}" in ''|*[!0-9]*) return 0 ;; esac
  [ "$2" -ge "$1" ] && echo $(($2 - $1)) || echo 0
}
#  Les noms de jobs d'une ligne de commande : tout ce qui n'est pas une option (#2229). La fiche du
#  propriétaire et le filtre du rejeu lisent la même règle — la fiche prenait `$*`, options comprises.
ci_noms_de_jobs() {        # $@ = arguments de rejouer-ci.sh → « job1 job2 » (PURE)
  local a r=""
  for a in "$@"; do case "$a" in --*) ;; *) r="${r:+$r }$a" ;; esac; done
  printf '%s' "$r"
}
ci_duree() {               # $1 = secondes → « 42 s », « 7 min », « 1 h 05 » (PURE)
  case "${1:-}" in ''|*[!0-9]*) echo "?"; return ;; esac
  if [ "$1" -lt 60 ]; then echo "$1 s"
  elif [ "$1" -lt 3600 ]; then echo "$(($1 / 60)) min"
  else printf '%d h %02d\n' $(($1 / 3600)) $((($1 % 3600) / 60)); fi
}
#  Lit le verrou et pose VL_PID, VL_VIVANT, VL_PARENT, VL_AGE_POULS, VL_ETAT, VL_DIAG.
ci_verrou_lire() {         # $1 = verrou (lecture seule)
  local pouls
  VL_PID=$(cat "$1/pid" 2>/dev/null || true); VL_VIVANT=non
  [ -n "$VL_PID" ] && kill -0 "$VL_PID" 2>/dev/null && VL_VIVANT=oui
  VL_PARENT=non_surveille
  [ "$VL_VIVANT" = oui ] && VL_PARENT=$(ci_parent_etat "$(ci_champ "$1/proprietaire" ancre)" \
    "$(ci_chaine_ancetres "$VL_PID")")
  pouls=$(cat "$1/pouls" 2>/dev/null); VL_AGE_POULS=""
  case "$pouls" in ''|*[!0-9]*) ;; *) VL_AGE_POULS=$(( $(date +%s) - pouls )) ;; esac
  VL_ETAT=$(ci_verrou_etat "$VL_PID" "$VL_VIVANT")
  VL_DIAG=$(ci_rejeu_diagnostic "$VL_PID" "$VL_VIVANT" "$VL_PARENT" "$VL_AGE_POULS" "$REJEU_SEUIL_FIGE_S")
}
ci_fiche_resume() {        # $1 = fiche (fichier) → « libellé · branche · sha · worktree »
  local l; l=$(ci_champ "$1" libelle)
  printf '%s%s · %s · %s\n' "${l:+« $l » · }" "$(ci_champ "$1" branche)" "$(ci_champ "$1" sha)" \
    "$(ci_champ "$1" worktree)"
}

# ── La file d'attente ────────────────────────────────────────────────────────
ci_file_cle() {            # → horodatage en ns (en s × 10⁹ si `%N` manque)
  local c; c=$(date +%s%N 2>/dev/null)
  case "$c" in ''|*[!0-9]*) c="$(date +%s)000000000" ;; esac
  echo "$c"
}
ci_file_trier() { sort -t. -k1,1n -k2,2n; }   # noms « clé.pid » sur stdin, ordre d'arrivée (PURE)
ci_ticket_vivant() {       # $1 = pid vivant oui|non · $2 = âge du ticket (s) · $3 = seuil → oui|non (PURE)
  [ "${1:-non}" = oui ] && [ "${2:-999999}" -le "${3:-180}" ] && echo oui || echo non
}
ci_file_rang() {           # $1 = pid · stdin « nom vivant âge » trié → rang parmi les vivants, 0 : absent (PURE)
  awk -v p="$1" '$2 == "oui" { n++; split($1, a, "."); if (a[2] == p) { print n; t = 1; exit } }
                 END { if (!t) print 0 }'
}
ci_file_cle_devant() {     # stdin noms triés → la clé qui passe devant tous (PURE, arithmétique bash)
  local premier; read -r premier || return 1
  echo $(( ${premier%%.*} - 1 ))
}
ci_file_inscrire() {       # $1 = dossier de la file · $2 = pid · $3 = fiche → chemin du ticket
  mkdir -p "$1" 2>/dev/null || return 1
  local t; t="$1/$(ci_file_cle).$2"
  printf '%s\n' "$3" > "$t" 2>/dev/null && echo "$t"
}
ci_file_ticket_de() {      # $1 = dossier · $2 = pid → chemin du ticket, vide s'il a été retiré
  local f
  for f in "$1"/[0-9]*."$2"; do [ -f "$f" ] && { echo "$f"; return; }; done
}
ci_file_retirer() {        # $1 = dossier · $2 = pid
  rm -f "$1"/[0-9]*."$2" 2>/dev/null
  return 0
}
ci_file_noms() {           # $1 = dossier → noms des tickets, triés
  local f
  for f in "$1"/[0-9]*.[0-9]*; do [ -f "$f" ] && printf '%s\n' "${f##*/}"; done | ci_file_trier
}
ci_file_lister() {         # $1 = dossier · $2 = seuil → « nom vivant|mort âge », triés (lecture seule)
  local nom pid age maintenant; maintenant=$(date +%s)
  ci_file_noms "$1" | while read -r nom; do
    pid=${nom##*.}
    age=$(( maintenant - $(stat -c %Y "$1/$nom" 2>/dev/null || echo 0) ))
    printf '%s %s %s\n' "$nom" "$(ci_ticket_vivant "$(kill -0 "$pid" 2>/dev/null && echo oui || echo non)" \
      "$age" "$2")" "$age"
  done
}
ci_file_passer_devant() {  # $1 = dossier · $2 = pid → 0 en tête | 1 ticket introuvable
  local t premier
  t=$(ci_file_ticket_de "$1" "$2"); [ -n "$t" ] || return 1
  premier=$(ci_file_noms "$1" | head -1)
  [ "$premier" = "${t##*/}" ] && return 0
  mv -f "$t" "$1/$(printf '%s\n' "$premier" | ci_file_cle_devant).$2"
}

# ── Prendre son tour ─────────────────────────────────────────────────────────
#  Direct : refusé si le verrou est tenu OU si un ticket vivant attend (le
#  rejeu hors file du 24/10). En attente : on prend quand le verrou est libre
#  et qu'aucun ticket vivant n'est devant soi.
ci_lancement() {           # $1 direct|attendre · $2 libre|occupe|orphelin · $3 tickets vivants DEVANT → prendre|attendre|refuser_occupe|refuser_file (PURE)
  case "$1:$2" in
    direct:occupe)   echo refuser_occupe; return ;;
    attendre:occupe) echo attendre; return ;;
  esac
  if [ "${3:-0}" -gt 0 ]; then [ "$1" = direct ] && echo refuser_file || echo attendre; return; fi
  echo prendre
}
_CI_FILE_ACTIVE=""
ci_rejeu_acquerir() {      # $1 = verrou · $2 = direct|attendre · $3 = ancre · $4 = fiche → 0 pris | 2 refusé
  local v=$1 mode=$2 file liste devant rang decision vu="" debut indice=""
  file="$(dirname "$v")/rejeu-ci.file"; debut=$(date +%s)
  if [ "$mode" = attendre ]; then
    ci_file_inscrire "$file" $$ "$4" >/dev/null || { echo "✗ File du rejeu non inscriptible : $file"; return 2; }
    _CI_FILE_ACTIVE=$file
    trap 'ci_file_retirer "$_CI_FILE_ACTIVE" $$' EXIT
  fi
  while :; do
    if [ "$mode" = attendre ] && [ -z "$(ci_file_ticket_de "$file" $$)" ]; then
      echo "✗ Ticket retiré de la file (file-rejeu.sh) : rien n'a été rejoué, ce n'est pas un succès."
      return 2
    fi
    ci_verrou_lire "$v"
    liste=$(ci_file_lister "$file" "$REJEU_SEUIL_FIGE_S")
    if [ "$mode" = attendre ]; then
      rang=$(printf '%s\n' "$liste" | ci_file_rang $$); devant=$(( rang > 0 ? rang - 1 : 0 ))
    else
      devant=$(printf '%s\n' "$liste" | awk '$2 == "oui"' | grep -c .)
    fi
    decision=$(ci_lancement "$mode" "$VL_ETAT" "$devant")
    case "$decision" in
      refuser_occupe)
        echo "✗ Un autre rejeu tourne déjà (pid $VL_PID) : deux rejeux simultanés se sabotent."
        echo "  Le tient : $(ci_fiche_resume "$v/proprietaire") — $(ci_rejeu_diagnostic_dit "$VL_DIAG")"
        echo "  Attendre son tour : bash scripts/poste/rejouer-ci.sh --attendre · état : bash scripts/poste/etat-rejeu.sh"
        echo "  Rien n'a été rejoué, ce n'est pas un succès."
        return 2 ;;
      refuser_file)
        echo "✗ $devant rejeu(x) attendent leur tour dans la file : passer par --attendre (ordre d'arrivée)."
        echo "  État : bash scripts/poste/etat-rejeu.sh — rien n'a été rejoué, ce n'est pas un succès."
        return 2 ;;
      prendre)
        [ "$VL_ETAT" = orphelin ] && ci_verrou_reprendre "$v" "$VL_PID"   # pid MORT : repris seul
        if ci_verrou_poser "$v" $$; then
          [ -n "$_CI_FILE_ACTIVE" ] && ci_file_retirer "$file" $$
          return 0
        fi
        [ "$mode" = direct ] && {
          echo "✗ Le verrou du rejeu vient d'être pris par un autre rejeu : attendre sa fin."
          return 2; } ;;
    esac
    #  En file : l'attente se surveille elle-même, comme le rejeu.
    if [ "$(ci_parent_etat "$3" "$(ci_chaine_ancetres $$)")" = disparu ]; then
      echo "✗ Le lanceur a disparu pendant l'attente : ticket retiré, rien n'a été rejoué."
      return 2
    fi
    touch -c "$(ci_file_ticket_de "$file" $$)" 2>/dev/null
    if [ "$rang:$VL_PID" != "$vu" ]; then
      vu="$rang:$VL_PID"
      echo "· en file : rang $rang — verrou ${VL_PID:+pid $VL_PID }: $(ci_rejeu_diagnostic_dit "$VL_DIAG")"
    fi
    [ "$VL_DIAG" = orphelin ] && [ -z "$indice" ] && {
      indice=1; echo "  ⚠ verrou orphelin : bash scripts/poste/file-rejeu.sh reprendre \"<motif>\""; }
    if [ $(( $(date +%s) - debut )) -gt "$REJEU_ATTENTE_MAX_S" ]; then
      echo "✗ Attente dépassée ($(ci_duree "$REJEU_ATTENTE_MAX_S")) : ticket retiré, rien n'a été rejoué."
      return 2
    fi
    sleep "$REJEU_POULS_S"
  done
}

#  Les gestes du coordinateur (file-rejeu.sh) se journalisent : qui, quoi, pourquoi.
ci_journal_geste() {       # $1 = dossier commun · $2 = geste · $3 = détail
  printf '%s	%s	%s	par=%s
' "$(date '+%F %T')" "$2" "$3"     "${REJEU_PROPRIETAIRE:-$(git rev-parse --show-toplevel 2>/dev/null)}" >> "$1/rejeu-ci-file.log"
}
#  Le trap TERM du rejeu. Il s'exécute DANS la commande en cours, redirections
#  comprises : reçu pendant une étape, son message part dans la sortie de
#  l'étape, que le trap EXIT efface (mesuré le 24/10). L'arrêt se consigne donc
#  aussi au journal de la file, qui survit au verrou.
ci_rejeu_arrete() {        # $1 = verrou
  local motif; motif=$(ci_champ "$1/battement" motif)
  ci_journal_geste "$(dirname "$1")" arret \
    "pid=$$ · étape=$(ci_champ "$1/battement" etape) · ${motif:-signal reçu}"
  echo "✗ Rejeu arrêté (${motif:-signal reçu}) — rien de conclu." >&2 2>/dev/null
}
#  La reprise EXPLICITE d'un verrou : orphelin ou périmé seulement, motif
#  obligatoire, journalisée. Le processus d'un orphelin vit encore : il n'est
#  PAS arrêté ici, la commande est donnée à qui reprend.
ci_verrou_reprendre_motive() { # $1 = verrou · $2 = motif → 0 repris | 1 refusé
  [ "${#2}" -ge 10 ] || { echo "✗ Motif obligatoire (10 caractères au moins) : il est journalisé."; return 1; }
  ci_verrou_lire "$1"
  case "$VL_DIAG" in
    orphelin|perime) ;;
    *) echo "✗ Reprise refusée : le verrou est $(ci_rejeu_diagnostic_dit "$VL_DIAG")."; return 1 ;;
  esac
  ci_journal_geste "$(dirname "$1")" reprendre     "pid=$VL_PID $VL_DIAG · $(ci_fiche_resume "$1/proprietaire") · motif=$2"
  ci_verrou_reprendre "$1" "$VL_PID" || { echo "✗ Le verrou a changé de main pendant la reprise."; return 1; }
  echo "✓ Verrou repris (journal : $(dirname "$1")/rejeu-ci-file.log)."
  [ "$VL_DIAG" = orphelin ] && echo "  ⚠ le processus $VL_PID vit encore ; l'arrêter est un geste à faire à la main : kill $VL_PID"
  return 0
}

# ── Self-test ────────────────────────────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  # shellcheck source=lib-ci-verrou.selftest.sh
  . "$(dirname "${BASH_SOURCE[0]}")/lib-ci-verrou.selftest.sh"
  ci_verrou_selftest
  exit $?
fi
