#!/bin/bash
# =============================================================================
#  lib-ci-arbre.selftest.sh — Les cas de `lib-ci-arbre.sh --selftest` (#2270)
#
#  Sourcé par `lib-ci-arbre.sh --selftest` seulement (job `test-scripts`). Les
#  décisions pures sur des tables écrites ici, puis le COMPORTEMENT sur de vrais
#  processus : un arbre tué d'un coup, l'appelant épargné, et — sous Windows —
#  l'arbre dont la racine est morte (`kill -9`), le cas qui a laissé deux arbres
#  pytest vivants six heures.
# =============================================================================

ci_arbre_selftest() {
  local st=0 vd p r s tab trouve avant sortie
  t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$3] obtenu=[$2]"; st=1; }; }
  vd=$(mktemp -d)

  # ── Descendants : la fermeture par ppid ──────────────────────────────────
  #            pid ppid début nom ligne
  tab=$(printf '%s\n' \
    $'10\t1\t100\tbash.exe\trejouer-ci.sh' \
    $'20\t10\t110\tbash.exe\trejouer-ci.sh' \
    $'30\t20\t120\tpython.exe\tpython -m pytest tests' \
    $'31\t30\t121\tpython.exe\tpython -c import sys;exec(eval(sys.stdin.readline()))' \
    $'40\t10\t130\tnode.exe\tvite' \
    $'50\t1\t100\tother.exe\tautre')
  t "descendants — l'arbre, la racine exclue" \
    "$(printf '%s\n' "$tab" | ci_proc_descendants 10 | sort -n | tr '\n' ' ')" "20 30 31 40 "
  t "descendants — une feuille n'en a pas" "$(printf '%s\n' "$tab" | ci_proc_descendants 31)" ""
  #  La racine MORTE (absente de la table) : c'est le cas d'un `kill -9` du rejeu.
  tab=$(printf '%s\n' $'20\t10\t110\tbash.exe\tx' $'30\t20\t120\tpython.exe\ty' $'60\t1\t100\tz.exe\tz')
  t "descendants — racine absente de la table : retrouvés par le ppid" \
    "$(printf '%s\n' "$tab" | ci_proc_descendants 10 | sort -n | tr '\n' ' ')" "20 30 "
  #  Windows recycle les pid : un enfant plus VIEUX que son père lui renvoie à un pid recyclé.
  tab=$(printf '%s\n' $'10\t1\t500\tneuf.exe\tx' $'20\t10\t100\tvieux.exe\ty' $'30\t10\t600\tenfant.exe\tz')
  t "descendants — pid recyclé : l'enfant plus vieux que son père n'est pas à lui" \
    "$(printf '%s\n' "$tab" | ci_proc_descendants 10)" "30"
  tab=$(printf '%s\n' $'20\t10\t90\ta.exe\tx' $'30\t10\t150\tb.exe\ty' $'40\t10\t900\tc.exe\tz')
  t "descendants — fenêtre de vie du rejeu : avant sa mort seulement" \
    "$(printf '%s\n' "$tab" | ci_proc_descendants 10 100 500)" "30"
  t "descendants — un cycle ne tourne pas" \
    "$(printf '%s\n' $'1\t2\t5\ta\tx' $'2\t1\t5\tb\ty' | ci_proc_descendants 1 | tr '\n' ' ')" "2 "
  t "ancêtres — jusqu'au premier absent" \
    "$(printf '%s\n' $'30\t20\t1\ta\tx' $'20\t10\t1\tb\ty' $'10\t999\t1\tc\tz' | ci_proc_ancetres 30 | tr '\n' ' ')" "30 20 10 "

  # ── Les restes d'un rejeu mort ───────────────────────────────────────────
  #  La table du 28/10 : un rejeu tué laisse un sous-shell (sa ligne de commande),
  #  un pytest, ses workers ; et une session de terminal ordinaire dont le père
  #  (l'explorateur) n'existe plus non plus.
  tab=$(printf '%s\n' \
    $'200\t100\t1000\tbash.exe\tbash.exe scripts/poste/rejouer-ci.sh --attendre' \
    $'210\t200\t1010\tpython.exe\tpython.exe -m pytest tests -n 12' \
    $'211\t210\t1011\tpython.exe\tpython.exe -c "import sys;exec(eval(sys.stdin.readline()))"' \
    $'300\t5000\t1000\texplorer.exe\texplorer.exe' \
    $'310\t300\t1020\tbash.exe\tbash.exe' \
    $'320\t310\t1030\tpython.exe\tpython -m pytest tests/test_un.py' \
    $'400\t1\t900\tbash.exe\tbash.exe scripts/poste/rejouer-ci.sh' \
    $'500\t999\t9990\tpython.exe\tpython -m pytest jeune')
  t "orphelins — le sous-shell du rejeu mort est une racine (son père 100 n'existe plus)" \
    "$(printf '%s\n' "$tab" | ci_proc_orphelins 10000 60 | cut -f1 | tr '\n' ' ')" "200 "
  t "orphelins — pytest d'un terminal vivant : jamais (père présent)" \
    "$(printf '%s\n' "$tab" | ci_proc_orphelins 10000 60 | cut -f1 | grep -cx '320')" "0"
  t "orphelins — l'explorateur n'a pas le motif : pas une racine" \
    "$(printf '%s\n' "$tab" | ci_proc_orphelins 10000 60 | cut -f1 | grep -cx '300')" "0"
  t "orphelins — un processus de moins de 60 s n'est pas jugé (père tout juste parti)" \
    "$(printf '%s\n' "$tab" | ci_proc_orphelins 10000 60 | cut -f1 | grep -cx '500')" "0"
  t "orphelins — avec un âge minimal nul, il l'est" \
    "$(printf '%s\n' "$tab" | ci_proc_orphelins 10000 0 | cut -f1 | grep -cx '500')" "1"
  t "orphelins — un père de pid 1 (init, Linux) : adopté, pas orphelin" \
    "$(printf '%s\n' "$tab" | ci_proc_orphelins 10000 60 | cut -f1 | grep -cx '400')" "0"
  t "orphelins — pid recyclé : le père a le pid mais naît APRÈS l'enfant" \
    "$(printf '%s\n' $'900\t800\t100\tpython.exe\tpython -m pytest t' $'800\t1\t200\tbash.exe\tbash' \
        | ci_proc_orphelins 10000 60 | cut -f1)" "900"
  t "orphelins — table vide : aucun" "$(printf '' | ci_proc_orphelins 10000 60)" ""

  # ── Sur de VRAIS processus : l'arbre se tue d'un coup, l'appelant est épargné ──
  tab=$(ci_proc_table)
  t "table — contient ce shell"     "$(printf '%s\n' "$tab" | awk -F'\t' -v p="$(ci_winpid $$)" '$1 == p' | grep -c .)" "1"
  t "table — cinq colonnes"         "$(printf '%s\n' "$tab" | awk -F'\t' 'NF != 5' | grep -c .)" "0"
  rm -f "$vd/r" "$vd/s"
  bash -c 'bash -c "echo \$\$ > \"$1/r\"; sleep 60 & echo \$! > \"$1/s\"; wait" & wait' _ "$vd" & p=$!
  for _ in $(seq 1 25); do [ -s "$vd/r" ] && [ -s "$vd/s" ] && break; sleep 0.2; done
  r=$(cat "$vd/r"); s=$(cat "$vd/s")
  sleep 1                  # un exec change le pid Windows d'un shell : on le relève une fois stable
  ci_proc_tuer avec "$(ci_winpid "$p")" "" >/dev/null 2>&1
  sleep 0.5
  t "tuer — l'arbre entier est tombé (fils et petit-fils)" \
    "$(kill -0 "$r" 2>/dev/null && echo vivant; kill -0 "$s" 2>/dev/null && echo vivant)" ""
  t "tuer — l'appelant a survécu" "$(echo vivant)" "vivant"
  #  `sous` ne tue pas la racine ; `epargnes` protège une branche.
  rm -f "$vd/r" "$vd/s"
  bash -c 'sleep 60 & echo $! > "$1/s"; sleep 60 & echo $! > "$1/r"; wait' _ "$vd" & p=$!
  for _ in $(seq 1 25); do [ -s "$vd/r" ] && [ -s "$vd/s" ] && break; sleep 0.2; done
  r=$(cat "$vd/r"); s=$(cat "$vd/s")
  sleep 1
  ci_proc_tuer sous "$(ci_winpid "$p")" "$(ci_winpid "$s")" >/dev/null 2>&1
  sleep 0.5
  t "tuer sous — la racine reste" "$(kill -0 "$p" 2>/dev/null && echo vivant)" "vivant"
  t "tuer sous — la branche épargnée reste" "$(kill -0 "$s" 2>/dev/null && echo vivant)" "vivant"
  t "tuer sous — l'autre branche est tombée" "$(kill -0 "$r" 2>/dev/null && echo vivant)" ""
  kill "$p" "$s" 2>/dev/null; wait "$p" 2>/dev/null

  # ── Windows : l'arbre sans racine (le `kill -9` du 28/10) ─────────────────
  if ci_orphelins_possibles; then
    rm -f "$vd/r" "$vd/s"
    #  Le « pytest » est un python endormi dont la ligne de commande porte le motif.
    bash -c 'bash -c "python -c \"import time; time.sleep(90)\" -m pytest orphelin-de-test & echo \$! > \"$1/s\"; wait" & echo $! > "$1/r"; wait' _ "$vd" & p=$!
    for _ in $(seq 1 40); do [ -s "$vd/r" ] && [ -s "$vd/s" ] && break; sleep 0.2; done
    sleep 1.5
    kill -9 "$p" 2>/dev/null                       # aucun trap, aucune propreté : la mort réelle
    sleep 1
    trouve=$(ci_proc_table | ci_proc_orphelins "$(date +%s)" 0 | grep -c 'orphelin-de-test')
    t "orphelins réels — l'arbre du rejeu tué à vif est retrouvé" "$([ "$trouve" -ge 1 ] && echo retrouve)" "retrouve"
    #  Le motif est restreint à CE test : le self-test ne doit pas tuer les vrais restes d'un autre rejeu.
    avant=$(ci_proc_table | grep -c 'orphelin-de-test')
    ( CI_ORPHELINS_MOTIF='orphelin-de-test'; CI_ORPHELINS_AGE_MIN_S=0; ci_orphelins_traiter signaler ) >/dev/null 2>&1
    t "orphelins réels — le mode « signaler » ne tue rien" "$(ci_proc_table | grep -c 'orphelin-de-test')" "$avant"
    sortie=$( ( CI_ORPHELINS_MOTIF='orphelin-de-test'; CI_ORPHELINS_AGE_MIN_S=0; ci_orphelins_traiter tuer ) 2>&1 )
    sleep 0.5
    t "orphelins réels — tués, plus aucun ne porte le motif de ce test"       "$(ci_proc_table | awk -F'	' '$5 ~ /time\.sleep\(90\)" -m pytest orphelin-de-test/ && $4 ~ /python/' | grep -c .)" "0"
    t "orphelins réels — le compte rendu dit combien d'arbres sont tombés"       "$(printf '%s
' "$sortie" | grep -c 'arbre(s) de rejeu mort tué')" "1"
  else
    echo "SKIP  orphelins réels — hors Windows, init adopte les orphelins (cas couvert par les tables ci-dessus)"
  fi
  rm -rf "$vd"
  # ── macOS (#2419) : l'âge lu dans `etime`, le nom dans la ligne de commande ──
  t "ps BSD — mm:ss, jours, chemin à espaces" \
    "$(printf '%s\n' '  42     1    01:05 /bin/bash scripts/poste/rejouer-ci.sh' \
                     '  43    42 2-03:04:05 /Applications/Un Outil.app/x -v' \
                     ' 44 42 00:00 /opt/homebrew/bin/python3.12 -m pytest tests' \
       | ci_ps_bsd_lire 1000000 | tr '\t' '|')" \
    "$(printf '%s\n' '42|1|999935|bash|/bin/bash scripts/poste/rejouer-ci.sh' \
                     '43|42|816155|Un|/Applications/Un Outil.app/x -v' \
                     '44|42|1000000|python3.12|/opt/homebrew/bin/python3.12 -m pytest tests')"
  #  Le défaut d'origine : une colonne d'âge illisible (mot-clé refusé, ligne décalée).
  t "ps BSD — âge illisible : la ligne est écartée, jamais datée de l'epoch" \
    "$(printf '%s\n' '  1     0 /sbin/launchd    /sbin/launchd' | ci_ps_bsd_lire 1000000)" ""
  if [ "$(uname -s)" = Darwin ]; then
    t "ps BSD — la table réelle porte ce shell, d'un âge plausible" \
      "$(ci_proc_table | awk -F'\t' -v p=$$ -v now="$(date +%s)" '$1 == p { print (now - $3 >= 0 && now - $3 < 86400 * 365) ? "oui" : "non" }')" "oui"
  fi
  #  Le cas zéro : une table illisible n'est pas « aucun processus ».
  t "table — illisible : code ≠ 0, jamais une table vide" \
    "$(PATH=/nonexistent ci_proc_table >/dev/null 2>&1 && echo ok || echo illisible)" "illisible"

  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  return $st
}
