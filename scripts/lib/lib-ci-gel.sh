#!/bin/bash
# =============================================================================
#  lib-ci-gel.sh — Un rejeu ne se FIGE plus en silence (#2270)
#
#  Module SOURCÉ par `lib-ci-replay.sh`, jamais exécuté (pas de bit x). Ses cas
#  d'autotest (`ci_gel_cas`) tournent dans `rejouer-ci.sh --selftest`.
#
#  POURQUOI (27-28/10/2026). Quatre rejeux complets se sont figés des heures
#  sans rouge ni message — verrou vivant, pouls frais, étape inchangée —, leurs
#  workers pytest à CPU nul : 44 min, 58 min, 5 h 46. Chacun suivait de près un
#  rejeu interrompu ou un pytest lancé hors rejeu, et des arbres pytest de
#  graines anciennes vivaient encore six heures après la mort de leur lanceur,
#  tenant connexions et schémas sur le PostgreSQL partagé.
#  L'arrêt d'une étape PAR le rejeu emporte bien son arbre (`ci_arreter_pids`,
#  reproduit le 28/10) ; ce qui échappe, c'est l'arbre dont le lanceur meurt
#  sans trap — un outil arrêté, une fenêtre fermée : sous Windows, `taskkill /T`
#  ne retrouve plus des enfants dont le parent est mort.
#  Trois réponses, de la plus tôt à la plus tard :
#    1. le pré-vol REFUSE un arbre pytest orphelin, avec la commande qui
#       l'arrête : un refus en quelques secondes au lieu d'un gel de six heures ;
#    2. une étape à la fois LONGUE (au-delà de son plafond, tiré de sa durée
#       mesurée) et MUETTE (sortie inchangée) est déclarée figée : arrêtée,
#       INCONNU, le verrou rendu ;
#    3. au gel, `pg_stat_activity` de la base des tests est relevé dans la
#       sortie de l'étape — la cause se lit au lieu de se supposer.
#  Les décisions sont pures ; les sondes ne font que lire ; le seul geste est
#  l'arrêt de l'étape figée, qui appartient au rejeu.
# =============================================================================

#: Plafond d'une étape sans durée mesurée, et plancher de tout plafond (s).
CI_GEL_PLAFOND_INCONNU=3600
CI_GEL_PLANCHER=1200
#: Facteur appliqué à la durée mesurée : une étape lente sous la charge des
#: sessions voisines a déjà pris 3,5 fois sa durée (self-tests, 1 830 s).
CI_GEL_FACTEUR=4
#: Silence exigé, en plus du plafond, avant de déclarer le gel (s).
CI_GEL_SILENCE="${REJEU_GEL_SILENCE_S:-900}"
#: Intervalle de la surveillance (s).
CI_GEL_INTERVALLE="${REJEU_GEL_INTERVALLE_S:-30}"

# ── Décisions (PURES) ───────────────────────────────────────────────────────
#  Les racines d'arbres pytest ORPHELINS. Une racine : le plus haut processus
#  d'une chaîne de pythons dont l'un lance pytest (le lanceur du venv est un
#  python qui en lance un autre). Orpheline : son parent n'existe plus — ou
#  c'est init (ppid 0 ou 1), où Linux rattache un orphelin. Les workers de
#  xdist n'ont pas « pytest » dans leur ligne : ils partent avec leur racine.
#    stdin « pid<TAB>ppid<TAB>nom<TAB>ligne de commande » de TOUS les processus
#    → « pid<TAB>ligne tronquée », une par racine
ci_pytest_orphelins() {
  awk -F'\t' '
    function python(n) { return tolower(n) ~ /^(python[0-9.]*|pytest)(\.exe)?$/ }
    { par[$1] = $2; nom[$1] = $3; cmd[$1] = $4; ordre[NR] = $1 }
    END {
      for (i = 1; i <= NR; i++) {
        p = ordre[i]
        if (!python(nom[p]) || cmd[p] !~ /(^|[ \/\\])(-m +)?pytest([ .]|$)/) continue
        q = p; d = 0
        while ((par[q] in nom) && python(nom[par[q]]) && d < 10) { q = par[q]; d++ }
        if (q in vu) continue
        vu[q] = 1
        if (par[q] == 0 || par[q] == 1 || !(par[q] in nom))
          printf "%s\t%s\n", q, substr(cmd[p], 1, 100)
      }
    }'
}

#  Le verdict du pré-vol sur ces racines. Elles n'appartiennent à aucun rejeu
#  vivant : la commande est donnée, le pré-vol ne tue rien (`lib-ci-verrou.sh`,
#  « jamais un kill du processus d'une AUTRE session »).
#    stdin = sortie de `ci_pytest_orphelins` · $1 = windows oui|non → "" | motif
ci_orphelins_etat() {
  local pids n
  pids=$(awk -F'\t' 'NF { printf "%s%s", (n++ ? " " : ""), $1 }')
  [ -z "$pids" ] && { echo ""; return; }
  n=$(printf '%s\n' "$pids" | wc -w)
  if [ "${1:-non}" = oui ]; then
    echo "$n arbre(s) pytest orphelin(s) (pid $pids) : leur lanceur est mort, ils tiennent la base des tests et figeraient pytest · arrêter : for p in $pids; do taskkill //T //F //PID \$p; done"
  else
    echo "$n arbre(s) pytest orphelin(s) (pid $pids) : leur lanceur est mort, ils tiennent la base des tests et figeraient pytest · arrêter : kill $pids"
  fi
}

#  Le plafond d'une étape, de sa durée mesurée (vide : jamais mesurée).
ci_plafond_etape() {           # $1 = durée mesurée (s) → plafond (s)
  case "${1:-}" in
    ''|*[!0-9]*) echo "$CI_GEL_PLAFOND_INCONNU"; return ;;
  esac
  local p=$(( $1 * CI_GEL_FACTEUR ))
  [ "$p" -lt "$CI_GEL_PLANCHER" ] && p=$CI_GEL_PLANCHER
  echo "$p"
}

#  Figée : au-delà de son plafond ET muette depuis le silence exigé. Une étape
#  longue qui écrit encore travaille ; une étape muette sous son plafond aussi.
ci_gel_verdict() {             # $1 = écoulé · $2 = silence · $3 = plafond · $4 = silence exigé → fige|continue
  if [ "$1" -ge "$3" ] && [ "$2" -ge "$4" ]; then echo fige; else echo continue; fi
}

# ── Sondes (lecture seule) ───────────────────────────────────────────────────
#  Tous les processus, au format de `ci_pytest_orphelins`. Sous Windows, la
#  table MSYS ne voit pas les pythons natifs lancés par un python : on lit
#  celle du système.
ci_table_systeme() {
  if command -v powershell.exe > /dev/null 2>&1; then
    powershell.exe -NoProfile -Command \
      "Get-CimInstance Win32_Process | ForEach-Object { '{0}\`t{1}\`t{2}\`t{3}' -f \$_.ProcessId, \$_.ParentProcessId, \$_.Name, ((\$_.CommandLine + '') -replace '\s+', ' ') }" \
      2>/dev/null | tr -d '\r'
  else
    ps -eo pid=,ppid=,comm=,args= 2>/dev/null \
      | awk '{ c = $4; for (i = 5; i <= NF; i++) c = c " " $i; printf "%s\t%s\t%s\t%s\n", $1, $2, $3, c }'
  fi
}

#  L'activité de la base des tests, au moment du gel : qui attend quoi.
ci_activite_base() {
  python - "${TESTS_BASE_URL:-}" 2>&1 <<'PYTHON' | tr -d '\r'
import sys
try:
    import psycopg
    url = sys.argv[1].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, connect_timeout=5) as c:
        lignes = c.execute(
            "SELECT pid, state, wait_event_type, wait_event,"
            " extract(epoch FROM now() - coalesce(xact_start, query_start))::int,"
            " left(regexp_replace(query, '\\s+', ' ', 'g'), 90)"
            " FROM pg_stat_activity WHERE datname = current_database()"
            " AND pid <> pg_backend_pid() ORDER BY 5 DESC NULLS LAST LIMIT 30"
        ).fetchall()
    print(f"{len(lignes)} connexion(s) à la base des tests")
    for l in lignes:
        print("  pid=%s %s attente=%s/%s depuis=%ss · %s" % l)
except Exception as erreur:
    print("pg_stat_activity illisible : " + (str(erreur).strip().splitlines() or ["?"])[0][:160])
PYTHON
}

# ── Le geste : surveiller UNE étape, l'arrêter si elle est figée ────────────
#  Tourne en arrière-plan à côté de l'étape ; s'éteint avec elle. Au gel :
#  `$d/gel` porte le motif, la sortie reçoit l'activité de la base, puis
#  l'étape est arrêtée avec son arbre.
ci_surveiller_etape() {        # $1 = dossier de l'étape · $2 = pid de l'étape
  local d="$1" pid="$2" t0=$EPOCHSECONDS plafond silence
  plafond=$(ci_plafond_etape "$(cat "$d/mesuree" 2>/dev/null)")
  while kill -0 "$pid" 2>/dev/null; do
    sleep "$CI_GEL_INTERVALLE"
    silence=$(( EPOCHSECONDS - $(stat -c %Y "$d/sortie" 2>/dev/null || echo "$EPOCHSECONDS") ))
    [ "$(ci_gel_verdict $(( EPOCHSECONDS - t0 )) "$silence" "$plafond" "$CI_GEL_SILENCE")" = fige ] || continue
    echo "figée : $(( (EPOCHSECONDS - t0) / 60 )) min (plafond $(( plafond / 60 )) min), muette depuis $(( silence / 60 )) min — arrêtée" > "$d/gel"
    { echo; echo "── Gel (#2270) : activité de la base des tests ──"
      ci_dans_etape "$(<"$d/rep")" "$d/env" ci_activite_base; } >> "$d/sortie" 2>&1
    ci_arreter_pids "$pid"
    return 0
  done
}

# ── Cas d'autotest — appelés par `ci_replay_selftest`, avec son `t` ─────────
ci_gel_cas() {
  local table
  #  Le cas du 28/10 : un lanceur bash mort, le python du venv, le python réel
  #  qui lance pytest, deux workers xdist. Une seule racine : le lanceur du venv.
  table=$(printf '%s\n' \
    "10	1	bash.exe	bash rejouer-ci.sh" \
    "20	999	python.exe	C:/v/Scripts/python.exe -m pytest tests/ -q -n 12" \
    "21	20	python.exe	C:/Python312/python.exe -m pytest tests/ -q -n 12" \
    "22	21	python.exe	python -c import sys;exec(eval(sys.stdin.readline()))" \
    "23	21	python.exe	python -c import sys;exec(eval(sys.stdin.readline()))")
  t "orphelins — l'arbre du venv dont le lanceur est mort : une racine" \
    "$(printf '%s\n' "$table" | ci_pytest_orphelins | cut -f1)" "20"
  #  Un pytest VIVANT (lancé par un bash présent) n'est jamais un orphelin.
  t "orphelins — un pytest au lanceur vivant n'en est pas" \
    "$(printf '%s\n' "10	1	bash.exe	bash" "30	10	python.exe	python -m pytest -q" | ci_pytest_orphelins)" ""
  t "orphelins — rattaché à init (Linux) : orphelin" \
    "$(printf '%s\n' "40	1	python3	/usr/bin/python3 /usr/bin/pytest tests" | ci_pytest_orphelins | cut -f1)" "40"
  t "orphelins — un mot voisin n'est pas pytest" \
    "$(printf '%s\n' "50	999	python.exe	python scripts/ci/pytest-resume.py" | ci_pytest_orphelins)" ""
  t "orphelins — un bash qui nomme pytest n'en est pas une racine" \
    "$(printf '%s\n' "60	999	bash.exe	bash -c pytest -q" | ci_pytest_orphelins)" ""
  #  🔴 Le cas zéro : aucune table, aucun orphelin — et le verdict est vide.
  t "orphelins — table vide" "$(printf '' | ci_pytest_orphelins)" ""
  t "orphelins — aucun : rien à dire" "$(printf '' | ci_orphelins_etat oui)" ""
  t "orphelins — la commande Windows prend l'arbre" \
    "$(printf '20\tx\n70\ty\n' | ci_orphelins_etat oui | sed 's/.*arrêter : //')" \
    'for p in 20 70; do taskkill //T //F //PID $p; done'
  t "orphelins — ailleurs, kill" "$(printf '20\tx\n' | ci_orphelins_etat non | sed 's/.*arrêter : //')" "kill 20"
  t "plafond — jamais mesurée" "$(ci_plafond_etape '')" "3600"
  t "plafond — étape courte : le plancher" "$(ci_plafond_etape 60)" "1200"
  t "plafond — pytest (521 s)" "$(ci_plafond_etape 521)" "2084"
  t "plafond — mesure illisible : comme jamais mesurée" "$(ci_plafond_etape 5x)" "3600"
  t "gel — longue ET muette" "$(ci_gel_verdict 2100 900 2084 900)" "fige"
  t "gel — longue mais elle écrit" "$(ci_gel_verdict 9000 30 2084 900)" "continue"
  t "gel — muette sous son plafond" "$(ci_gel_verdict 1500 1500 2084 900)" "continue"
  #  La sonde réelle sur ce poste : la table n'est jamais vide (ce shell y est).
  t "table système — lue, et elle contient ce shell" \
    "$([ "$(ci_table_systeme | grep -c .)" -gt 1 ] && echo oui || echo non)" "oui"
}
