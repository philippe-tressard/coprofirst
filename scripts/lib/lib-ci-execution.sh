#!/bin/bash
# =============================================================================
#  lib-ci-execution.sh — JOUER les étapes du rejeu, côte à côte (#2224)
#
#  Module SOURCÉ par `rejouer-ci.sh`, jamais exécuté (pas de bit x). Il porte ce
#  qui touche au poste : lancer une étape, relancer un e2e tombé sur une cause
#  du poste, l'ordonnanceur des couloirs. Les DÉCISIONS (phases, couloirs,
#  priorité, budget) sont pures et vivent dans `lib-ci-orchestration.sh`.
#
#  Une étape tourne dans son propre dossier (`$TMP/e/<idx>`) : son corps, son
#  `env:`, sa sortie, ses sauts, son verdict. Rien de partagé entre deux étapes
#  qui tournent ensemble — c'est ce qui permet de les lancer en arrière-plan et
#  de n'en AFFICHER les lignes qu'à la fin de la phase, dans l'ordre de ci.yml.
#
#  Variables lues (posées par `rejouer-ci.sh`) : RACINE, TMP, SHA_COURT, CHARGE,
#  ECHECS, JOURNAL_RELANCES, PLAFOND_RELANCE_E2E, BUDGET, T_DEBUT, SHA_COURT,
#  VERROU_REJEU, ECRIT.
# =============================================================================

#  Une commande dans le répertoire d'une étape, avec l'`env:` de son job.
#    $1 = rép, $2 = fichier `env`, puis la commande
ci_dans_etape() {
  (
    cd "$RACINE${1:+/$1}" || exit 127
    local fichier_env="$2" kv cle val
    shift 2
    while IFS= read -r kv; do
      [ -z "$kv" ] && continue
      cle=${kv%%:*}
      val=${kv#*: }
      val=${val%\"}; val=${val#\"}
      val=${val%\'}; val=${val#\'}
      export "$cle=$val"
    done < "$fichier_env"
    "$@" < /dev/null
  )
}

#  ── Relance des e2e tombés sur une cause propre au poste (#1809, #1989) ─────
#  La règle est `ci_relance_e2e` (lib-ci-e2e.sh) : une seule relance, des seuls
#  tests tombés, nommée sur la ligne de l'étape et JOURNALISÉE — date, lot,
#  charge, workers, tests, cause (`ci_cause_relance`) —, pour qu'on la mesure.
#  Sortie vide : pas de relance, ou relance rouge (sa sortie s'ajoute alors à
#  celle de l'étape).
ci_relancer_si_cause_poste() { # $1 = dossier de l'étape, $2 = code → détail, ou vide
  local d="$1" tombes cause
  [ "$(ci_relance_e2e "$2" "$(ci_sert_par_vite < "$d/corps")" "$PLAFOND_RELANCE_E2E" \
       < "$d/sortie")" = oui ] || return 0
  tombes=$(ci_tests_tombes < "$d/sortie")
  cause=$(ci_cause_relance < "$d/sortie")
  if ci_dans_etape "$(<"$d/rep")" "$d/env" npx playwright test --last-failed > "$d/relance" 2>&1 \
     && ! grep -q "optimized dependencies changed" "$d/relance"; then
    printf '%s\t%s\tcharge=%s\tworkers=%s\t%s\tcause=%s\n' "$(date '+%F %T')" "$SHA_COURT" \
      "${CHARGE:-?}" "${E2E_WORKERS:-défaut}" "$(printf '%s' "$tombes" | paste -sd '|' -)" \
      "$cause" >> "$JOURNAL_RELANCES"
    echo "relancé, vert : $(printf '%s' "$tombes" | paste -sd ';' -) — $cause"
  else
    { echo; echo "── Relance ($cause), rouge elle aussi ──"; cat "$d/relance"; } >> "$d/sortie"
  fi
}

#  Joue UNE étape et écrit son verdict dans `$d/res` :
#    1ʳᵉ ligne `VERDICT<TAB>détail`, puis ce qui s'affiche sous la ligne ;
#    `$d/duree`, `$d/nb_sauts`, `$d/nb_relances` pour les comptes.
#  Tourne en arrière-plan : n'écrit QUE dans son dossier (et dans ECHECS, sous
#  un nom qui lui est propre).
ci_executer_etape() {          # $1 = dossier de l'étape
  local d="$1" job etape code verdict relance duree t0 sauts n_sauts
  job=$(<"$d/job"); etape=$(<"$d/etape")
  : > "$d/sauts"
  t0=$EPOCHSECONDS
  #  Les tests SAUTÉS se nomment (#1734) : le crochet de `api/tests/conftest.py`
  #  les consigne dans ce fichier — un par étape, les étapes tournant ensemble.
  #  L'étape tourne sous surveillance : longue ET muette, elle est figée (#2270).
  REJEU_SAUTS="$d/sauts" ci_dans_etape "$(<"$d/rep")" "$d/env" bash -e "$d/corps" > "$d/sortie" 2>&1 &
  local pid_etape=$! pid_veille
  ci_surveiller_etape "$d" "$pid_etape" > /dev/null 2>&1 &
  pid_veille=$!
  wait "$pid_etape"
  code=$?
  kill "$pid_veille" 2>/dev/null
  verdict=$(ci_requalifier "$code" < "$d/sortie")
  [ -s "$d/gel" ] && verdict="INCONNU $(<"$d/gel")"
  relance=$(ci_relancer_si_cause_poste "$d" "$code")
  [ -n "$relance" ] && { verdict=OK; ci_tests_tombes < "$d/sortie" | grep -c . > "$d/nb_relances"; }
  duree=$(( EPOCHSECONDS - t0 ))
  echo "$duree" > "$d/duree"
  echo $(( EPOCHSECONDS - T_DEBUT )) > "$d/fin"   # pour « la minute du premier rouge »
  case "$verdict" in
    OK)       sauts=$(ci_resumer_sauts < "$d/sauts")
              n_sauts=${sauts%% *}
              echo "${n_sauts:-0}" > "$d/nb_sauts"
              printf 'OK\t%s\n' "${duree}s${sauts:+ — $sauts}${relance:+ — $relance}" > "$d/res" ;;
    INCONNU*) printf 'INCONNU\t%s\n' "${verdict#INCONNU } (${duree}s)" > "$d/res" ;;
    *)        mkdir -p "$ECHECS"
              cp "$d/sortie" "$ECHECS/$job-${d##*/}.log"
              { printf 'FAIL\t%s\n' "code $code (${duree}s)"
                sed 's/^/      │ /' "$d/sortie" | tail -15
                echo "      │ … sortie complète : $ECHECS/$job-${d##*/}.log"; } > "$d/res" ;;
  esac
  return 0
}

#  La ligne d'une étape. Le verdict et le job en TÊTE, le nom en queue :
#  `printf` compte des OCTETS, et une colonne de largeur fixe contenant
#  « Modularité » se décalerait d'autant d'accents.
ci_ligne() {                    # $1 = verdict, $2 = job, $3 = étape, $4 = détail
  local icone
  case "$1" in
    OK) icone="✓" ;; FAIL) icone="✗" ;; INCONNU) icone="?" ;; *) icone="·" ;;
  esac
  printf "%s %-7s %-15s %s%s\n" "$icone" "$1" "$2" "$3" "${4:+  — $4}"
}

#  Affiche le verdict d'une étape jouée (ou posée d'emblée : PRÉP, INCONNU).
ci_afficher_etape() {           # $1 = dossier de l'étape
  local d="$1" verdict detail ligne premiere=oui
  [ -f "$d/res" ] || return 0
  #  Des `read`, jamais `cat` ni `tail` : une fourche coûte ~50 ms sous Windows,
  #  et ce rapport en ferait une par étape.
  while IFS= read -r ligne || [ -n "$ligne" ]; do
    if [ "$premiere" = oui ]; then
      IFS=$'\t' read -r verdict detail <<< "$ligne"
      ci_ligne "$verdict" "$(<"$d/job")" "$(<"$d/etape")" "$detail"
      premiere=non
    else
      printf '%s\n' "$ligne"
    fi
  done < "$d/res"
}

ci_horloge() { local s=$(( EPOCHSECONDS - T_DEBUT )); printf '%d:%02d' $((s / 60)) $((s % 60)); }

#  Arrête des étapes en cours. Sous Windows, un `kill` ne descend pas jusqu'au
#  python ou au node qu'une étape a lancé : `taskkill /T` prend l'arbre.
ci_arreter_pids() {            # $@ = pids des sous-shells des étapes
  local p w
  for p in "$@"; do
    w=""; [ -r "/proc/$p/winpid" ] && w=$(<"/proc/$p/winpid")
    [ -n "$w" ] && taskkill //F //T //PID "$w" > /dev/null 2>&1
    kill "$p" 2>/dev/null
  done
  for p in "$@"; do wait "$p" 2>/dev/null; done
  return 0
}

#  ── L'ordonnanceur ──────────────────────────────────────────────────────────
#  Joue le plan, `BUDGET` étapes à la fois. Une étape part quand son précédent
#  dans le couloir est fini ; parmi celles qui le peuvent, la première du plan :
#  la phase COURANTE d'abord (le plus long couloir en tête), puis — sur un
#  créneau libre — la phase SUIVANTE, par ANTICIPATION : pytest tourne pendant
#  que build-frontend et test-scripts jouent leurs étapes rapides.
#  Quand la phase courante est finie, ses lignes s'affichent dans l'ordre de
#  ci.yml ; un rouge (sans `--tout`, `ci_suite_apres_phase`) arrête alors tout,
#  et les étapes anticipées sont ARRÊTÉES et comptées non jouées : on ne paie
#  pas 25 min de pytest pour un rouge de Modularité. Chaque rouge s'annonce DÈS
#  qu'il tombe, une ligne ; une étape d'une phase lente, quand elle finit.
#    $1 = fichier du plan (`ci_plan`), $2 = tout oui|non
#    → ARRET = la phase après laquelle le rejeu s'est arrêté, ou vide
ci_jouer() {
  local plan="$1" tout="$2" ph idx couloir prec reste i choisi fini_pid en_cours=0 verdict
  local courante="" suivante="" p
  local -a attente=() ordre=(reprise rapide lente)
  local -A phase_de=() precedent=() fini=() pid_de=() a_faire=() echecs=()
  while IFS=$'\t' read -r ph idx couloir prec reste; do
    [ -z "$idx" ] && continue
    attente+=("$idx"); phase_de[$idx]=$ph; precedent[$idx]=$prec
    a_faire[$ph]=$(( ${a_faire[$ph]:-0} + 1 ))
  done < "$plan"
  ARRET=""
  _ci_phase_suivante() {       # $1 = phase → la suivante qui a des étapes, ou vide
    local apres=non q
    [ -z "$1" ] && apres=oui
    for q in "${ordre[@]}"; do
      [ "$apres" = oui ] && [ "${a_faire[$q]:-0}" -gt 0 ] && { echo "$q"; return; }
      [ "$q" = "$1" ] && apres=oui
    done
  }
  _ci_annoncer() {             # $1 = phase devenue courante
    echo "── Phase $1 : $(awk -F'\t' -v p="$1" '$1 == p' "$plan" | grep -c .) étape(s), à $(ci_horloge) ──"
  }
  courante=$(_ci_phase_suivante "")
  [ -z "$courante" ] && return 0
  suivante=$(_ci_phase_suivante "$courante")
  _ci_annoncer "$courante"
  while [ ${#attente[@]} -gt 0 ] || [ "$en_cours" -gt 0 ]; do
    while [ "$en_cours" -lt "$BUDGET" ] && [ ${#attente[@]} -gt 0 ]; do
      choisi=""
      for i in "${!attente[@]}"; do
        idx=${attente[$i]}
        case "${phase_de[$idx]}" in "$courante"|"$suivante") ;; *) continue ;; esac
        prec=${precedent[$idx]}
        if [ "$prec" = "-" ] || [ -n "${fini[$prec]:-}" ]; then choisi=$i; break; fi
      done
      [ -z "$choisi" ] && break
      idx=${attente[$choisi]}
      attente=("${attente[@]:0:$choisi}" "${attente[@]:$((choisi + 1))}")
      #  Le pouls du verrou (#2225) : la dernière étape lancée, dans le parent —
      #  le compteur d'étapes ne survivrait pas au sous-shell.
      ci_battement "$VERROU_REJEU" "$(<"$TMP/e/$idx/job") · $(<"$TMP/e/$idx/etape")" "$ECRIT"
      ci_executer_etape "$TMP/e/$idx" &
      pid_de[$!]=$idx
      en_cours=$((en_cours + 1))
    done
    if [ "$en_cours" -eq 0 ]; then
      #  Rien ne tourne et rien ne peut partir : un précédent qui ne viendra pas.
      #  Défaut du plan — jamais un vert : les étapes restantes sont INCONNU.
      for idx in "${attente[@]}"; do
        printf 'INCONNU\tnon jouée : son précédent dans le couloir n’a pas tourné (défaut du plan)\n' > "$TMP/e/$idx/res"
      done
      break
    fi
    fini_pid=""
    wait -n -p fini_pid "${!pid_de[@]}" 2>/dev/null
    [ -z "$fini_pid" ] && continue
    idx=${pid_de[$fini_pid]}
    unset "pid_de[$fini_pid]"
    fini[$idx]=1
    en_cours=$((en_cours - 1))
    ph=${phase_de[$idx]}
    a_faire[$ph]=$(( a_faire[$ph] - 1 ))
    [ -f "$TMP/e/$idx/res" ] || printf 'INCONNU\tl’étape s’est arrêtée sans verdict\n' > "$TMP/e/$idx/res"
    IFS=$'\t' read -r verdict _ < "$TMP/e/$idx/res"
    if [ "$verdict" = FAIL ]; then
      echecs[$ph]=$(( ${echecs[$ph]:-0} + 1 ))
      echo "  ✗ rouge à $(ci_horloge) : $(<"$TMP/e/$idx/job") — $(<"$TMP/e/$idx/etape")"
    elif [ "$ph" != rapide ]; then
      echo "  · fini à $(ci_horloge) : $(<"$TMP/e/$idx/job") — $(<"$TMP/e/$idx/etape") — $verdict ($(<"$TMP/e/$idx/duree")s)"
    fi
    #  La phase courante est-elle finie ? Son rapport, puis on continue ou non.
    while [ -n "$courante" ] && [ "${a_faire[$courante]:-0}" -eq 0 ]; do
      for p in $(awk -F'\t' -v p="$courante" '$1 == p { print $2 }' "$plan" | sort); do
        ci_afficher_etape "$TMP/e/$p"
      done
      if [ "$(ci_suite_apres_phase "${echecs[$courante]:-0}" "$tout")" = arreter ] \
         && [ -n "$suivante" ]; then
        ARRET=$courante
        if [ "$en_cours" -gt 0 ]; then
          echo "  · $en_cours étape(s) anticipée(s) de la phase $suivante arrêtée(s) — non jouée(s)"
          ci_arreter_pids "${!pid_de[@]}"
          for p in "${pid_de[@]}"; do rm -f "$TMP/e/$p/res" "$TMP/e/$p/duree" "$TMP/e/$p/nb_sauts" "$TMP/e/$p/nb_relances"; done
        fi
        return 0
      fi
      courante=$suivante
      [ -z "$courante" ] && break
      suivante=$(_ci_phase_suivante "$courante")
      _ci_annoncer "$courante"
    done
  done
  return 0
}

#  ── Le journal des durées (#2224) ───────────────────────────────────────────
#  Une ligne par étape jouée, puis une ligne de BILAN par rejeu (job `@rejeu`) —
#  complet ou partiel, vert, rouge, INCONNU, interrompu ou refusé au pré-vol —,
#  dans le répertoire git COMMUN : la mesure ne dépend plus des journaux épars
#  des sessions. `scripts/poste/mesurer-rejeux.py` le lit. Colonnes (TSV) :
#    date · rejeu · sha · worktree · job · étape · durée (s) · verdict · fin (s
#    depuis le début du rejeu ; pour le bilan, la durée totale)
#  Rotation simple : au-delà du plafond, le journal devient `.1` (un seul gardé).
CI_JOURNAL_PLAFOND=5000000
ci_journaliser() {             # $1 = journal, $2 = verdict du rejeu, $3 = portée
  local j="$1" d verdict date rejeu wt total
  date=$(date '+%F %T')
  rejeu="$(date -d "@$T_DEBUT" '+%Y%m%d-%H%M%S' 2>/dev/null || echo "$T_DEBUT")-$$"
  wt=${RACINE##*/}
  total=$(( EPOCHSECONDS - T_DEBUT ))
  [ -f "$j" ] && [ "$(wc -c < "$j")" -gt "$CI_JOURNAL_PLAFOND" ] && mv -f "$j" "$j.1"
  {
    for d in "$TMP"/e/*/; do
      d=${d%/}
      [ -f "$d/duree" ] && [ -f "$d/res" ] && [ -f "$d/fin" ] || continue
      IFS=$'\t' read -r verdict _ < "$d/res"
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$date" "$rejeu" "$SHA_COURT" "$wt" \
        "$(<"$d/job")" "$(<"$d/etape")" "$(<"$d/duree")" "$verdict" "$(<"$d/fin")"
    done
    printf '%s\t%s\t%s\t%s\t@rejeu\t%s\t%s\t%s\t%s\n' "$date" "$rejeu" "$SHA_COURT" "$wt" \
      "$3" "$total" "$2" "$total"
  } >> "$j"
  return 0
}
