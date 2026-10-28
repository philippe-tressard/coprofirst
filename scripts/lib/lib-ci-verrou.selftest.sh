#!/bin/bash
# =============================================================================
#  lib-ci-verrou.selftest.sh — Les cas de `lib-ci-verrou.sh --selftest` (#2225)
#
#  Sourcé par `lib-ci-verrou.sh --selftest` seulement (job `test-scripts`).
#  Les décisions pures, puis le COMPORTEMENT sur des processus et des fichiers
#  réels, dans un dossier jetable : un lanceur tué dont le veilleur arrête le
#  rejeu, une file servie dans l'ordre d'arrivée, un rejeu hors file refusé.
# =============================================================================

ci_verrou_selftest() {
  local st=0 vd f p r s w
  t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$3] obtenu=[$2]"; st=1; }; }
  vd=$(mktemp -d)

  # ── Le verrou (#1417, #1808) — cas déplacés de lib-ci-replay.sh ──────────
  t "verrou — absent : libre"              "$(ci_verrou_etat "" non)" "libre"
  t "verrou — pid vivant : occupé"          "$(ci_verrou_etat 4242 oui)" "occupe"
  t "verrou — pid mort : orphelin, repris"  "$(ci_verrou_etat 4242 non)" "orphelin"
  mkdir "$vd/v" && echo 111 > "$vd/v/pid"; ci_verrou_liberer "$vd/v" 222
  t "verrou — libéré par un autre : gardé"  "$([ -d "$vd/v" ] && echo garde || echo retire)" "garde"
  ci_verrou_liberer "$vd/v" 111
  t "verrou — libéré par son pid : retiré"  "$([ -d "$vd/v" ] && echo garde || echo retire)" "retire"
  mkdir "$vd/v" && echo 111 > "$vd/v/pid"
  t "reprise — l'orphelin lu : retiré"      "$(ci_verrou_reprendre "$vd/v" 111 && echo repris; [ -d "$vd/v" ] && echo present)" "repris"
  mkdir "$vd/v" && echo 333 > "$vd/v/pid"
  t "reprise — le verrou a changé de main"  "$(ci_verrou_reprendre "$vd/v" 111 || echo refus; cat "$vd/v/pid")" "refus
333"
  t "reprise — rien de mis de côté"         "$(ls -A "$vd" | grep -c repris)" "0"
  t "poser — tenu par un autre : refusé"    "$(ci_verrou_poser "$vd/v" 444 && echo pris || echo refus)" "refus"
  rm -rf "$vd/v"
  t "poser — libre : pris, pid écrit"       "$(ci_verrou_poser "$vd/v" 444 && cat "$vd/v/pid")" "444"
  rm -rf "$vd/v"
  #  Le script ne retire le verrou QUE par ces fonctions : un `rm` direct sur
  #  lui est le défaut même de #1808.
  f="$(dirname "${BASH_SOURCE[0]}")/../poste/rejouer-ci.sh"
  t "rejouer-ci.sh — aucun rm direct du verrou" "$(grep -cE 'rm [^#]*VERROU_REJEU' "$f")" "0"
  t "rejouer-ci.sh — le tour se prend par la règle" \
    "$(grep -v '^[[:space:]]*#' "$f" | grep -c 'ci_rejeu_acquerir')" "1"
  #  #2270 : sortir du rejeu emporte son arbre, et arrêter une étape passe par la fermeture par ppid.
  t "rejouer-ci.sh — l'arbre est tué à la sortie, avant de rendre le verrou"     "$(grep -v '^[[:space:]]*#' "$f" | grep -c "ci_proc_tuer sous .*; ci_verrou_liberer")" "1"
  t "ci_arreter_pids — passe par ci_proc_tuer, plus par un taskkill //T seul"     "$(grep -v '^[[:space:]]*#' "$(dirname "${BASH_SOURCE[0]}")/lib-ci-execution.sh" | grep -c 'ci_proc_tuer avec')" "1"
  t "rejouer-ci.sh — le veilleur est lancé"  "$(grep -v '^[[:space:]]*#' "$f" | grep -c 'ci_veilleur ')" "1"
  #  Le battement part de l'ORDONNANCEUR, au lancement de chaque étape (#2224) :
  #  les étapes tournent côte à côte, et rejouer-ci.sh n'en lance plus aucune.
  t "ordonnanceur — un battement par étape lancée" \
    "$(grep -v '^[[:space:]]*#' "$(dirname "${BASH_SOURCE[0]}")/lib-ci-execution.sh" | grep -c 'ci_battement ')" "1"

  # ── Le lanceur : chaîne, ancre, état ─────────────────────────────────────
  t "ancre — le plus haut de la chaîne"     "$(ci_ancre '12 34 56 ')" "56"
  t "ancre — chaîne vide : aucune"          "$(ci_ancre '')" ""
  t "parent — sans ancre : non surveillé"   "$(ci_parent_etat '' '12 34')" "non_surveille"
  t "parent — ancre dans la chaîne"         "$(ci_parent_etat 56 '12 34 56 ')" "present"
  t "parent — ancre sortie de la chaîne"    "$(ci_parent_etat 56 '12 ')" "disparu"
  t "parent — 5 n'est pas 56"               "$(ci_parent_etat 5 '12 56 ')" "disparu"
  #  Sur de VRAIS processus : un enfant voit son lanceur, puis le perd.
  ( sleep 20 & echo $! > "$vd/enfant"; wait ) & p=$!
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$vd/enfant" ] && break; sleep 0.2; done
  r=$(cat "$vd/enfant" 2>/dev/null)
  t "processus — le lanceur est dans la chaîne" "$(ci_parent_etat "$p" "$(ci_chaine_ancetres "$r")")" "present"
  kill -TERM "$p" 2>/dev/null; wait "$p" 2>/dev/null
  t "processus — lanceur tué : disparu"     "$(ci_parent_etat "$p" "$(ci_chaine_ancetres "$r")")" "disparu"
  kill "$r" 2>/dev/null

  #  Les descendants, la table et le coup de grâce : `lib-ci-arbre.sh --selftest` (#2270).

  # ── Le veilleur : lanceur tué → rejeu ET ses descendants arrêtés ─────────
  #  P lance R, qui lance S. Le verrou est à R. P tué, le veilleur doit arrêter
  #  R et S — et rien d'autre.
  rm -f "$vd/r" "$vd/s"
  bash -c 'bash -c "echo \$\$ > \"$1/r\"; sleep 30 & echo \$! > \"$1/s\"; wait" & wait' _ "$vd" & p=$!
  for _ in $(seq 1 25); do [ -s "$vd/r" ] && [ -s "$vd/s" ] && break; sleep 0.2; done
  r=$(cat "$vd/r"); s=$(cat "$vd/s")
  mkdir "$vd/v" && echo "$r" > "$vd/v/pid"
  ( REJEU_POULS_S=1; ci_veilleur "$vd/v" "$r" "$p" ) >/dev/null 2>&1 & w=$!
  sleep 1.5
  t "veilleur — lanceur présent : rien arrêté" "$(kill -0 "$r" 2>/dev/null && echo vivant)" "vivant"
  t "veilleur — il bat le pouls"            "$([ -s "$vd/v/pouls" ] && echo oui)" "oui"
  kill -TERM "$p" 2>/dev/null
  for _ in $(seq 1 30); do kill -0 "$w" 2>/dev/null || break; sleep 0.2; done
  sleep 0.5
  t "veilleur — lanceur tué : rejeu arrêté"  "$(kill -0 "$r" 2>/dev/null && echo vivant || echo arrete)" "arrete"
  t "veilleur — et son descendant"           "$(kill -0 "$s" 2>/dev/null && echo vivant || echo arrete)" "arrete"
  t "veilleur — l'arrêt est signé"           "$(ci_champ "$vd/v/battement" motif | cut -c1-17)" "lanceur disparu ("
  kill "$w" "$r" "$s" 2>/dev/null; rm -rf "$vd/v"

  # ── Le veilleur : le rejeu meurt À VIF (kill -9, aucun trap) → ses restes tombent (#2270) ──
  #  C'est ce qui a laissé deux arbres pytest vivants six heures. Le lanceur, lui, vit
  #  toujours : seul le rejeu disparaît, sans libérer son verrou.
  if ci_orphelins_possibles; then
    rm -f "$vd/s2"
    bash -c 'python -c "import time; time.sleep(90)" -m pytest veilleur-de-test & echo $! > "$1/s2"; wait' _ "$vd" & r=$!
    sleep 30 & p=$!                                              # le lanceur : bien vivant
    for _ in $(seq 1 40); do [ -s "$vd/s2" ] && break; sleep 0.2; done
    sleep 1.5
    mkdir "$vd/v2" && echo "$r" > "$vd/v2/pid"
    ( REJEU_POULS_S=1; CI_ORPHELINS_MOTIF='veilleur-de-test'; ci_veilleur "$vd/v2" "$r" "$p" ) >/dev/null 2>&1 & w=$!
    sleep 1.5
    kill -9 "$r" 2>/dev/null                                     # le rejeu meurt, son verrou reste
    for _ in $(seq 1 40); do kill -0 "$w" 2>/dev/null || break; sleep 0.5; done
    sleep 1
    t "veilleur — rejeu tué à vif : le veilleur sort" "$(kill -0 "$w" 2>/dev/null && echo vivant)" ""
    t "veilleur — rejeu tué à vif : ses restes sont tués"       "$(ci_proc_table | awk -F'	' '$5 ~ /veilleur-de-test/ && $4 ~ /python/' | grep -c .)" "0"
    #  Mort, le rejeu n'a plus d'ancêtres : le veilleur y lit d'abord « lanceur disparu » ; l'un ou l'autre motif signe.
    t "veilleur — rejeu tué à vif : l'arrêt est signé" "$(ci_champ "$vd/v2/battement" motif | grep -c .)" "1"
    kill "$p" 2>/dev/null; rm -rf "$vd/v2"
  else
    echo "SKIP  veilleur — rejeu tué à vif : hors Windows init adopte les restes (cas couvert par la table relevée avant)"
  fi

  # ── Diagnostic ───────────────────────────────────────────────────────────
  t "diag — pas de verrou : libre"          "$(ci_rejeu_diagnostic '' non present '' 180)" "libre"
  t "diag — pid mort : périmé"              "$(ci_rejeu_diagnostic 9 non present 5 180)" "perime"
  t "diag — vivant, pouls frais : actif"    "$(ci_rejeu_diagnostic 9 oui present 5 180)" "actif"
  t "diag — non surveillé, frais : actif"   "$(ci_rejeu_diagnostic 9 oui non_surveille 5 180)" "actif"
  t "diag — lanceur parti, frais : arrêt"   "$(ci_rejeu_diagnostic 9 oui disparu 5 180)" "arret_en_cours"
  t "diag — lanceur parti ET figé : orphelin" "$(ci_rejeu_diagnostic 9 oui disparu 600 180)" "orphelin"
  t "diag — lanceur là, figé : figé"        "$(ci_rejeu_diagnostic 9 oui present 600 180)" "fige"
  t "diag — aucun pouls : jamais actif"     "$(ci_rejeu_diagnostic 9 oui present '' 180)" "sans_pouls"
  t "durée — secondes"  "$(ci_duree 42)" "42 s"
  t "durée — minutes"   "$(ci_duree 420)" "7 min"
  t "durée — heures"    "$(ci_duree 3900)" "1 h 05"
  t "durée — illisible" "$(ci_duree '')" "?"
  #  #2229 : un repère posé après la lecture de l'heure ne fait plus « il y a ? ».
  t "âge — ordinaire"                  "$(ci_age_s 100 160)" "60"
  t "âge — repère de la seconde même"  "$(ci_age_s 160 160)" "0"
  t "âge — repère après la lecture"    "$(ci_age_s 163 160)" "0"
  t "âge — repère illisible"           "$(ci_age_s '' 160)" ""
  t "noms de jobs — options écartées"  "$(ci_noms_de_jobs --venv test-scripts --tout lint-backend)" "test-scripts lint-backend"
  t "noms de jobs — aucun : vide"      "$(ci_noms_de_jobs --venv --tout)" ""

  # ── Décision de lancement ────────────────────────────────────────────────
  t "lancement — direct, tout libre"        "$(ci_lancement direct libre 0)" "prendre"
  t "lancement — direct, pid mort"          "$(ci_lancement direct orphelin 0)" "prendre"
  t "lancement — direct, occupé"            "$(ci_lancement direct occupe 0)" "refuser_occupe"
  t "lancement — direct, une file vivante"  "$(ci_lancement direct libre 2)" "refuser_file"
  t "lancement — attente, occupé"           "$(ci_lancement attendre occupe 0)" "attendre"
  t "lancement — attente, quelqu'un devant" "$(ci_lancement attendre libre 1)" "attendre"
  t "lancement — attente, son tour"         "$(ci_lancement attendre libre 0)" "prendre"

  # ── La file : ordre d'arrivée, rang, passer devant, retirer ──────────────
  t "ticket — vivant et frais"              "$(ci_ticket_vivant oui 5 180)" "oui"
  t "ticket — vivant mais figé"             "$(ci_ticket_vivant oui 600 180)" "non"
  t "ticket — pid mort"                     "$(ci_ticket_vivant non 5 180)" "non"
  t "file — tri par clé puis pid"           "$(printf '200.7\n100.9\n100.3\n' | ci_file_trier | tr '\n' ' ')" "100.3 100.9 200.7 "
  t "file — rang parmi les vivants"         "$(printf '100.1 mort 9\n200.5 oui 1\n300.7 oui 1\n' | ci_file_rang 7)" "2"
  t "file — absent : rang 0"                "$(printf '200.5 oui 1\n' | ci_file_rang 7)" "0"
  t "file — passer devant : clé − 1"        "$(printf '1792869503052486900.5\n' | ci_file_cle_devant)" "1792869503052486899"
  t "file — clé numérique"                  "$(ci_file_cle | grep -cE '^[0-9]{19}$')" "1"
  mkdir "$vd/c"
  sleep 30 & s=$!                                             # un autre rejeu qui attend, vivant
  ( exit 0 ) & r=$!; wait "$r"                                # un pid mort
  ci_file_inscrire "$vd/c/rejeu-ci.file" "$r" "pid=$r" >/dev/null
  t "file — un ticket mort n'est pas une file" "$(ci_file_lister "$vd/c/rejeu-ci.file" 180 | awk '{print $2}')" "non"
  (REJEU_DOSSIER_COMMUN="$vd/c"; ci_rejeu_acquerir "$vd/c/rejeu-ci.verrou" direct "" "pid=$$" >/dev/null)
  t "acquérir — direct, file morte : pris"  "$(cat "$vd/c/rejeu-ci.verrou/pid" 2>/dev/null)" "$$"
  ci_verrou_liberer "$vd/c/rejeu-ci.verrou" $$
  ci_file_inscrire "$vd/c/rejeu-ci.file" "$s" "pid=$s" >/dev/null
  t "acquérir — direct, file vivante : refusé (code 2)" \
    "$(ci_rejeu_acquerir "$vd/c/rejeu-ci.verrou" direct "" "pid=$$" >/dev/null; echo $?; [ -d "$vd/c/rejeu-ci.verrou" ] && echo pris)" "2"
  t "acquérir — attente dépassée : code 2, ticket retiré" \
    "$( (REJEU_ATTENTE_MAX_S=0 REJEU_POULS_S=0; ci_rejeu_acquerir "$vd/c/rejeu-ci.verrou" attendre "" "pid=$$" >/dev/null; echo $?); ci_file_ticket_de "$vd/c/rejeu-ci.file" $$ )" "2"
  ci_file_inscrire "$vd/c/rejeu-ci.file" $$ "pid=$$" >/dev/null
  t "passer devant — en tête"               "$(ci_file_passer_devant "$vd/c/rejeu-ci.file" $$; ci_file_noms "$vd/c/rejeu-ci.file" | grep -v "\.$r$" | head -1 | cut -d. -f2)" "$$"
  t "passer devant — ticket inconnu"        "$(ci_file_passer_devant "$vd/c/rejeu-ci.file" 1 || echo introuvable)" "introuvable"
  ci_file_retirer "$vd/c/rejeu-ci.file" $$
  t "acquérir — attente, son tour : pris, ticket retiré" \
    "$(ci_file_retirer "$vd/c/rejeu-ci.file" "$s"; (REJEU_POULS_S=0; ci_rejeu_acquerir "$vd/c/rejeu-ci.verrou" attendre "" "pid=$$" >/dev/null; echo $?); cat "$vd/c/rejeu-ci.verrou/pid"; ci_file_ticket_de "$vd/c/rejeu-ci.file" $$)" "0
$$"
  #  Reprise motivée : jamais un verrou actif, toujours un motif, toujours journalisée.
  date +%s > "$vd/c/rejeu-ci.verrou/pouls"
  t "reprise motivée — sans motif : refusée" \
    "$(ci_verrou_reprendre_motive "$vd/c/rejeu-ci.verrou" "court" >/dev/null || echo refus)" "refus"
  t "reprise motivée — verrou actif : refusée" \
    "$(ci_verrou_reprendre_motive "$vd/c/rejeu-ci.verrou" "motif assez long" >/dev/null || echo refus; cat "$vd/c/rejeu-ci.verrou/pid")" "refus
$$"
  echo "$r" > "$vd/c/rejeu-ci.verrou/pid"
  t "reprise motivée — pid mort : reprise, journalisée" \
    "$(ci_verrou_reprendre_motive "$vd/c/rejeu-ci.verrou" "motif assez long" >/dev/null && echo repris; grep -c 'motif=motif assez long' "$vd/c/rejeu-ci-file.log")" "repris
1"
  kill "$s" 2>/dev/null; wait "$s" 2>/dev/null
  rm -rf "$vd"

  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  return $st
}
