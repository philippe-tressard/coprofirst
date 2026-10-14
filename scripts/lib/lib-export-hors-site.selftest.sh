#!/bin/bash
# =============================================================================
#  lib-export-hors-site.selftest.sh — les CAS D'ESSAI de la copie hors site
#
#  🔴 Sorti de `export-hors-site.sh` le 12/09/2026 : le plafond de modularité
#  (rang 1) a refusé que le script grossisse en recevant le rattrapage borné à
#  la rétention. Il disait vrai — quatre-vingts lignes de cas d'essai n'ont rien
#  à faire dans le fichier qui orchestre le SSH, le disque et le rapport.
#
#  ⚠️ Ce fichier est SOURCÉ, jamais exécuté seul : il s'appuie sur les fonctions
#  que l'appelant a déjà chargées (`lib-export-hors-site.sh`). Le lancer
#  directement ne mesurerait rien — d'où l'absence de bit d'exécution, comme
#  tout module `lib-*.sh`.
#
#  Lancer : bash scripts/poste/export-hors-site.sh --selftest
#
#  Le motif est celui de `lib-analyse-styles.selftest.mjs` côté front : la
#  détection et ses cas d'essai ont deux rythmes différents, donc deux fichiers.
# =============================================================================
  st_fail=0
  check() { # description attendu obtenu
    if [ "$3" = "$2" ]; then echo "PASS  $1  → '$3'"
    else echo "FAIL  $1  attendu='$2' obtenu='$3'"; st_fail=1; fi
  }
  echo "== self-test export-hors-site =="

  check "rpi1 seul répond"          "rpi1"        "$(decider_source 200 000)"
  check "rpi2 seul répond"          "rpi2"        "$(decider_source 000 200)"
  check "les deux répondent"        "split-brain" "$(decider_source 200 200)"
  check "aucun ne répond"           "aucun"       "$(decider_source 000 000)"
  check "503 n'est pas un actif"    "rpi2"        "$(decider_source 503 200)"
  check "codes absents → aucun"     "aucun"       "$(decider_source)"

  # ── Continuité de la série (#775) ──
  # La veille et l'avant-veille présentes, sur une fenêtre de 2 jours : rien ne
  # manque. C'est le cas nominal, et il doit rendre une chaîne VIDE — un
  # contrôle qui crie sur une série complète est désarmé dans la semaine.
  SERIE_OK=$'hostachy_backup_20260904_020000.tar.gz\nhostachy_backup_20260903_020000.tar.gz'
  check "série complète → rien" "" "$(printf '%s' "$SERIE_OK" | jours_manquants 2 20260905)"
  # Un trou au milieu : c'est le seul cas qui compte, et c'est celui qu'une
  # simple présence d'archive ne voit pas.
  SERIE_TROU=$'hostachy_backup_20260904_020000.tar.gz'
  check "un jour manque"    "20260903" "$(printf '%s' "$SERIE_TROU" | jours_manquants 2 20260905)"
  # 🔴 LE CAS ZÉRO : aucune archive du tout. Une liste vide doit rendre TOUS les
  # jours, pas une chaîne vide — sinon « rien à signaler » et « je n'ai rien pu
  # lire » deviennent le même résultat (`standards/04` §1).
  check "liste vide → tous"  "20260904 20260903" "$(printf '' | jours_manquants 2 20260905)"
  # L'archive du jour même n'est pas exigée : elle n'existe qu'après 02:00.
  check "le jour même n'est pas exigé" "" "$(printf '%s' "$SERIE_OK" | jours_manquants 1 20260905)"
  # 🔴 Le faux « jour absent » du 29/09/2026 : export après 02:00, la rotation a
  # gardé J et J-1. Réclamer J-2 signalait chaque jour un trou qui n'en est pas un.
  SERIE_AVEC_JOUR=$'hostachy_backup_20260929_020000.tar.gz\nhostachy_backup_20260928_020000.tar.gz'
  check "le jour même présent → fenêtre J..J-1" "" "$(printf '%s' "$SERIE_AVEC_JOUR" | jours_manquants 2 20260929)"
  # …et un vrai trou dans cette fenêtre-là se voit toujours.
  check "jour présent, veille absente" "20260928" "$(printf '%s' 'hostachy_backup_20260929_020000.tar.gz' | jours_manquants 2 20260929)"

  # Le faux négatif du 04/08/2026 : `tar | grep -q` sous pipefail rendait
  # « absent » sur une archive contenant app.db. Le listing est désormais
  # analysé hors de tout tube, et ces cas verrouillent l'analyse.
  LISTING_OK=$'app.db\nuploads/\nuploads/doc.pdf'
  check "app.db en tête de listing"  "oui"        "$(listing_contient "$LISTING_OK" app.db)"
  check "app.db seul"                "oui"        "$(listing_contient 'app.db' app.db)"
  check "listing sans base"          "non"        "$(listing_contient $'uploads/\nuploads/doc.pdf' app.db)"
  check "listing vide"               "non"        "$(listing_contient '' app.db)"
  # Le piège de la sous-chaîne : un fichier nommé app.db DANS uploads n'est pas
  # la base. Une comparaison naïve l'accepterait.
  check "uploads/app.db ne compte pas" "non"      "$(listing_contient $'uploads/app.db\nuploads/x' app.db)"
  check "suffixe app.db2 ne compte pas" "non"     "$(listing_contient 'app.db2' app.db)"

  # ── Liste blanche du nom d'archive ─────────────────────────────────────────
  # Le nom vient du nœud distant et repart dans une commande exécutée là-bas.
  #  🔴 Jusqu'au 14/10/2026 (#1896), un échec ici posait `st=1` — une variable
  #  que le bilan ne lit pas : la liste blanche pouvait céder sous un « TOUS OK ».
  tn() { local r=refuse; nom_valide "$2" ${4:+"$4"} && r=ok
         [ "$r" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1 : attendu=$3 obtenu=$r"; st_fail=1; }; }
  tn "nom d'archive normal"      "hostachy_backup_2026-08-09_030000.tar.gz" ok
  tn "nom vide"                  ""                                          refuse
  tn "chemin absolu"             "/etc/shadow"                               refuse
  tn "remontée de répertoire"    "hostachy_backup_../../etc/shadow.tar.gz"   refuse
  tn "sous-répertoire"           "hostachy_backup_a/b.tar.gz"                refuse
  tn "la base elle-même"         "app.db"                                    refuse
  tn "substitution de commande"  'hostachy_backup_$(id).tar.gz'              refuse
  #  Le registre des installations (#1896) : son préfixe, et lui seul, dans sa série.
  tn "archive du registre"       "plateforme_backup_20261014_033000_paris.tar.gz" ok "$PREFIXE_PLATEFORME"
  tn "résidence prise pour le registre" "hostachy_backup_20261014_030000_paris.tar.gz" refuse "$PREFIXE_PLATEFORME"
  tn "registre pris pour la résidence"  "plateforme_backup_20261014_033000_paris.tar.gz" refuse
  tn "registre : remontée"       "plateforme_backup_../x.tar.gz"             refuse "$PREFIXE_PLATEFORME"
  tn "préfixe inconnu refusé"    "x_backup_1.tar.gz"                         refuse "x_backup_"
  tn "préfixe-motif refusé"      "a.tar.gz"                                  refuse ".*"

  check "archive saine"             "succes"      "$(verdict_archive 1024 oui oui ok | cut -d'|' -f1)"
  check "archive vide"              "erreur"      "$(verdict_archive 0 oui oui ok | cut -d'|' -f1)"
  check "empreinte différente"      "erreur"      "$(verdict_archive 1024 non oui ok | cut -d'|' -f1)"
  check "app.db absent"             "erreur"      "$(verdict_archive 1024 oui non ok | cut -d'|' -f1)"
  check "base corrompue"            "erreur"      "$(verdict_archive 1024 oui oui 'malformed' | cut -d'|' -f1)"
  # Le cas qui a coûté l'incident du 26/07 ailleurs : l'absence de contrôle
  # lue comme un succès. Ici, ne pas savoir vaut échec.
  check "intégrité non vérifiable"  "erreur"      "$(verdict_archive 1024 oui oui inconnue | cut -d'|' -f1)"
  #  Base serveur (PostgreSQL, DI-7b) : l'export vérifié remplace app.db.
  check "export présent, lignes justes" "succes"  "$(verdict_archive 1024 oui export ok | cut -d'|' -f1)"
  check "export aux lignes manquantes"  "erreur"  "$(verdict_archive 1024 oui export 'écarts : lot 3/4' | cut -d'|' -f1)"
  check "export non vérifié"            "erreur"  "$(verdict_archive 1024 oui export inconnue | cut -d'|' -f1)"
  check "export repéré dans le listing" "oui"     "$(listing_contient $'uploads/\nbase-export.tar.gz' "$NOM_EXPORT_BASE")"
  check "uploads/base-export… ne compte pas" "non" "$(listing_contient 'uploads/base-export.tar.gz' "$NOM_EXPORT_BASE")"
  check "résumé juste"                  "ok"      "$(verdict_export_base $'lot 4 4\nticket 12 12')"
  check "une table incomplète"          "écarts : lot 3/4" "$(verdict_export_base $'lot 3 4\nticket 12 12')"
  check "résumé vide → inconnue, jamais ok" "inconnue" "$(verdict_export_base '')"
  #  #1964 : Python sous Windows écrit en CRLF. Le `\r` collé à la dernière
  #  colonne rendait chaque table « en écart » — toute copie hors site échouait
  #  depuis le poste, depuis le passage à PostgreSQL.
  #  ⚠️ Le CR se fabrique À L'EXÉCUTION (`printf`) : sous Git Bash, un
  #  `$'…\r\n…'` écrit dans un "$(…)" perd son `\r`, et ce cas passait sans en
  #  contenir un seul. Le compte de CR ci-dessous est son cas zéro.
  #  Sans CRLF final : une substitution le retire sous Git Bash, pas sous Linux,
  #  et le compte différerait entre le poste et la CI.
  crlf_juste=$(printf 'lot 4 4\r\nticket 12 12')
  crlf_ecart=$(printf 'lot 3 4\r\nticket 12 12')
  check "le cas d'essai porte bien son CR" "1" "$(printf '%s' "$crlf_juste" | tr -cd '\r' | wc -c | tr -d ' ')"
  check "résumé CRLF (Python sous Windows)" "ok" "$(verdict_export_base "$crlf_juste")"
  check "CRLF n'efface pas un vrai écart" "écarts : lot 3/4" "$(verdict_export_base "$crlf_ecart")"

  LISTE=$'a\nb\nc\nd\ne'
  check "rotation garde 3"          $'a\nb'       "$(echo "$LISTE" | archives_a_supprimer 3)"
  check "rotation garde tout"       ""            "$(echo "$LISTE" | archives_a_supprimer 5)"
  check "rotation keep > total"     ""            "$(echo "$LISTE" | archives_a_supprimer 99)"
  # Garde-fou : une config aberrante ne doit pas vider la destination.
  check "keep=0 ne supprime rien"   ""            "$(echo "$LISTE" | archives_a_supprimer 0)"
  check "keep négatif ne fait rien" ""            "$(echo "$LISTE" | archives_a_supprimer -1)"
  check "liste vide"                ""            "$(printf '' | archives_a_supprimer 3)"

  # ── Le rattrapage se borne à la rétention (12/09/2026) ─────────────────────
  # Le cas réel : six archives anciennes sur l'autre nœud, deux conservées. On
  # ne tire QUE celles qui entreraient dans la rétention.
  DIST=$'hostachy_backup_20260908_020000.tar.gz\nhostachy_backup_20260909_020000.tar.gz\nhostachy_backup_20260910_020000.tar.gz'
  LOC=$'hostachy_backup_20260912_020000.tar.gz'
  check "rattrapage borné à 2" "hostachy_backup_20260910_020000.tar.gz" \
        "$(archives_a_rattraper 2 "$LOC" "$DIST")"
  # Rien à tirer quand le local porte déjà les plus récentes.
  check "rien à rattraper" "" \
        "$(archives_a_rattraper 2 $'hostachy_backup_20260911_020000.tar.gz\nhostachy_backup_20260912_020000.tar.gz' "$DIST")"
  # Le distant plus récent que tout le local : les deux partent.
  check "les deux plus récentes viennent du pair" \
        $'hostachy_backup_20260909_020000.tar.gz\nhostachy_backup_20260910_020000.tar.gz' \
        "$(archives_a_rattraper 2 'hostachy_backup_20260101_020000.tar.gz' "$DIST")"
  # Même garde que la rotation : une valeur aberrante ne tire rien.
  check "keep=0 ne tire rien"  "" "$(archives_a_rattraper 0 "$LOC" "$DIST")"
  check "pair vide"            "" "$(archives_a_rattraper 2 "$LOC" '')"

  # ── Archives nommées à l'heure de Paris (#1611) ───────────────────────────
  # `…_HHMMSS_paris` remplace `…_HHMMSS` (UTC) : le suffixe vient APRÈS les secondes,
  # donc le tri alphabétique reste chronologique et les lecteurs par JOUR lisent la
  # date de Paris. Anciennes et nouvelles archives coexistent pendant la rétention.
  P5=hostachy_backup_20261005_040000_paris.tar.gz
  P4=hostachy_backup_20261004_040000_paris.tar.gz
  P6=hostachy_backup_20261006_040000_paris.tar.gz
  U4=hostachy_backup_20261004_020000.tar.gz
  tn "nom à l'heure de Paris"    "$P5" ok
  check "série à l'heure de Paris, complète" "" \
        "$(printf '%s\n%s' "$P5" "$P4" | jours_manquants 2 20261006)"
  check "trou dans la série de Paris" "20261004" \
        "$(printf '%s' "$P5" | jours_manquants 2 20261006)"
  # Le défaut d'origine : prise à 00:30 à Paris, l'archive porte le jour de PARIS (le
  # nom UTC portait la veille, et le jour semblait manquer).
  check "00:30 à Paris compte pour son jour" "" \
        "$(printf '%s\n%s' hostachy_backup_20261005_003000_paris.tar.gz "$P4" | jours_manquants 2 20261006)"
  # Mélange à la bascule : l'ancienne (UTC) précède la nouvelle (Paris), l'ordre tient.
  check "rotation : la plus ancienne (UTC) part d'abord" "$U4" \
        "$(printf '%s\n%s\n%s\n' "$U4" "$P5" "$P6" | archives_a_supprimer 2)"
  check "rattrapage : anciennes et nouvelles mêlées" "$P6" \
        "$(archives_a_rattraper 2 "$P5" "$(printf '%s\n%s' "$U4" "$P6")")"

  [ $st_fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $st_fail
