#!/usr/bin/env bash
# =============================================================================
#  lib-precheck-post.sh — le mode POST-MEP du pré-check : P1 et P3 (#1282)
#
#  🔴 POURQUOI (25/09/2026, post-check de la v2.49.2). Lancé APRÈS la MEP,
#  `precheck-mep.sh` concluait « ✗ MEP NON AUTORISÉE » alors que les vingt
#  points de production étaient verts : le verdict ne tenait qu'aux points
#  d'AVANT-push (0d, 0f, 0g, 16), qui échouent par construction une fois le lot
#  fusionné. La skill disait « lire les points 1 à 18 » — une consigne pour lire
#  AUTOUR d'un verdict faux. Un contrôle qui crie sur une MEP réussie finit
#  ignoré le jour où il a raison (`standards/04`).
#
#  `precheck-mep.sh --post-mep` n'exécute donc pas les points du LOT, et ajoute
#  les deux preuves que le post-check faisait À LA MAIN sur le RPi :
#    P1 — l'actif a DÉPLOYÉ le commit de `origin/main` (ligne `Déployé:`) ;
#    P3 — le site SERT la version de `origin/main` (bundle réellement reçu) ;
#    P3b — l'API la PUBLIE dans `GET /config` (`version_logicielle`, #2833).
#  Il n'écrit jamais la trace du pré-check : il n'autorise aucun push.
#
#  Sourcé par `precheck-mep.sh`, qui fournit `sur`, `rapporter`, `SITE`,
#  `ACTIF` et `RACINE_DEPOT`. Les verdicts, eux, sont PURS et s'éprouvent seuls :
#      bash scripts/lib/lib-precheck-post.sh --selftest
# =============================================================================

# shellcheck source=./lib-parite.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-parite.sh"   # memes_hachages
# shellcheck source=./lib-images-servies.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-images-servies.sh"   # le relevé du point 12

verdict_deploye() {         # $1 = sha de origin/main, $2 = dernier sha « Déployé: » de l'actif
                            # $3 = marqueur d'images de l'actif, $4 = conteneur API sur l'image étiquetée (oui/non/"")
  #  La ligne n'est écrite qu'APRÈS un build réussi (`auto-deploy.sh`) : la voir
  #  est la preuve ordinaire que l'image sert le commit. Le `git log` du nœud
  #  passe au vert avant le build (skill `mep-precheck`, piège 3).
  case "$(memes_hachages "$1" "$2")" in
    oui) echo OK; return ;;
    non) ;;
    *)   echo INCONNU; return ;;   # journal illisible, SSH muet : rien de prouvé
  esac
  #  🔴 Un nœud devenu actif par la BASCULE n'écrit pas `Déployé:` (#1474) : il
  #  a écrit `Aligné:` en standby, puis la bascule l'a démarré. Sa dernière ligne
  #  date alors de la dernière fois qu'il était actif. La preuve de rechange :
  #  ses images portent le commit (marqueur écrit après un build RÉUSSI), et le
  #  conteneur en service tourne sur le MANIFESTE de l'image étiquetée — sinon il
  #  tournerait encore sur les anciennes. C'est le fait du point 12 (#1675) ;
  #  P1 comparait deux DATES (création du conteneur, écriture du marqueur), un
  #  artefact qui rendait vert un conteneur recréé sur l'ancienne image (#1684).
  [ "$(memes_hachages "$1" "$3")" = oui ] || { echo FAIL; return; }
  case "${4:-}" in
    oui) echo OK ;;
    non) echo FAIL ;;
    *)   echo INCONNU ;;
  esac
}

conteneur_sur_image_etiquetee() {  # la ligne « api » du relevé, champ par champ
  #  PURE. Un écart MESURÉ dit « non » ; une mesure absente ne dit rien.
  case "$(verdict_image_service "${2:-}" "${3:-}" "${4:-}")" in
    OK)                 echo oui ;;
    NON_RECREE|PERIMEE) echo non ;;
    *)                  echo "" ;;
  esac
}

verdict_version_servie() {  # $1 = version de origin/main, $2 = sortie de check-version-servie.mjs
  #  L'extracteur rend la version, ou `INCONNU: <raison>` — jamais une sortie
  #  vide. Une sortie vide ici veut dire qu'il n'a pas tourné : INCONNU.
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$2" in
    "" | INCONNU*) echo INCONNU ;;
    "$1")          echo OK ;;
    *)             echo FAIL ;;   # une autre version servie : cache, déploiement incomplet
  esac
}

precheck_points_post() {
  git fetch origin --quiet 2>/dev/null
  local attendu deploye version ligne
  attendu=$(git rev-parse origin/main 2>/dev/null)
  deploye=$(sur "$ACTIF" "grep -o 'Déployé: [0-9a-f]*' /var/log/hostachy-deploy.log 2>/dev/null | tail -1")
  deploye=${deploye#Déployé: }
  local marqueur recree api
  marqueur=$(sur "$ACTIF" "tr -d ' \t\r\n' < /opt/5hostachy/.images-construites 2>/dev/null")
  #  Le conteneur API tourne-t-il sur l'image étiquetée ? Le relevé du point 12,
  #  ligne « api » : « oui », « non », ou rien si une mesure manque.
  api=$(sur "$ACTIF" "$(collecte_images_servies)" | grep '^api ')
  # shellcheck disable=SC2086  # les champs du relevé, découpés exprès
  recree=$(conteneur_sur_image_etiquetee $api)
  rapporter P1 "$(verdict_deploye "$attendu" "$deploye" "$marqueur" "$recree")" "Déploiement terminé sur l'actif" \
            "origin/main=${attendu:0:8} dernier « Déployé: »=${deploye:-absent} images=${marqueur:-absent} conteneur sur l'image=${recree:-?}"

  version=$(git show origin/main:front/package.json 2>/dev/null | grep -m1 '"version"' | cut -d'"' -f4)
  if command -v node >/dev/null 2>&1; then
    ligne=$(node "$RACINE_DEPOT/front/scripts/check-version-servie.mjs" --site "$SITE" 2>/dev/null | tail -1)
  else
    ligne="INCONNU: node absent du poste"
  fi
  VERSION_SERVIE="$ligne"   # lue par la conclusion (`lib-precheck-infra.sh`)
  rapporter P3 "$(verdict_version_servie "$version" "$ligne")" "Version servie par le site" \
            "attendue=${version:-?} servie=${ligne:-?}"

  #  P3b — la release que l'API PUBLIE (`GET /config`, `version_logicielle`, #2833) : celle
  #  que les apps lisent pour juger « au moins vX.Y.Z ». Même verdict que P3 : une
  #  mesure impossible rend INCONNU, jamais OK.
  local publiee
  publiee=$(curl -s --max-time 15 "$SITE/api/config" 2>/dev/null | python3 -c \
    'import json,sys
try: print(json.load(sys.stdin).get("version_logicielle") or "INCONNU: clé absente")
except Exception as e: print(f"INCONNU: {type(e).__name__}")' 2>/dev/null)
  rapporter P3b "$(verdict_version_servie "$version" "${publiee:-INCONNU: python3 absent}")" \
            "Version publiée par l'API (GET /config)" "attendue=${version:-?} publiée=${publiee:-?}"
}

#  ── Auto-test : les décisions se vérifient sans réseau ni RPi ──────────────
if [ "${1:-}" = "--selftest" ]; then
  echecs=0
  t() {
    local libelle="$1" att="$2"; shift 2
    local obtenu; obtenu=$("$@")
    if [ "$obtenu" = "$att" ]; then echo "PASS  $libelle"
    else echo "FAIL  $libelle — attendu $att, obtenu $obtenu"; echecs=$((echecs + 1)); fi
  }
  t "déployé = origin/main (abréviation courte)" OK      verdict_deploye 6ff171ea1ae1090e 6ff171e
  t "l'actif sert encore l'ancien commit"        FAIL    verdict_deploye 6ff171ea1ae1090e d038e72
  #  🔴 Le cas zéro : aucune ligne `Déployé:` lue ne doit PAS rendre OK.
  t "journal illisible ou SSH muet"              INCONNU verdict_deploye 6ff171ea1ae1090e ""
  t "origin/main introuvable"                    INCONNU verdict_deploye "" 6ff171e
  #  🔴 Le 30/09/2026 (#1474) : MEP à 01:58, bascule à 02:05. L'actif est devenu
  #  actif par la BASCULE — sa dernière ligne `Déployé:` date de la veille, mais
  #  ses images portent le commit et son conteneur tourne sur leur manifeste.
  t "actif par la bascule, images et conteneur à jour" OK  verdict_deploye 33f58335849 b6a0f63e 33f58335 oui
  t "images à jour, conteneur sur une autre image" FAIL    verdict_deploye 33f58335849 b6a0f63e 33f58335 non
  t "images d'un autre commit"                     FAIL    verdict_deploye 33f58335849 b6a0f63e b6a0f63e oui
  #  La seconde preuve illisible ne vaut ni OK ni FAIL : on n'a rien vu.
  t "images à jour, manifeste illisible"           INCONNU verdict_deploye 33f58335849 b6a0f63e 33f58335 ""
  #  🔴 #1684 : un conteneur RECRÉÉ après le build, mais sur l'ancienne image —
  #  les dates disaient « oui », le manifeste dit « non ».
  t "conteneur sur l'image étiquetée"              oui     conteneur_sur_image_etiquetee api oui sha256:aa sha256:aa 33f5833 33f5833
  t "conteneur recréé sur une autre image"         non     conteneur_sur_image_etiquetee api oui sha256:bb sha256:aa 33f5833 33f5833
  t "images sans le commit de l'API"               non     conteneur_sur_image_etiquetee api non sha256:aa sha256:aa 33f5833 b6a0f63
  t "manifeste du conteneur absent"                ""      conteneur_sur_image_etiquetee api oui - sha256:aa 33f5833 33f5833
  t "ligne « api » absente du relevé"              ""      conteneur_sur_image_etiquetee
  t "version servie = origin/main"               OK      verdict_version_servie 2.49.2 2.49.2
  t "une autre version servie"                   FAIL    verdict_version_servie 2.49.2 2.49.1
  #  Le 25/09/2026 : la 403 du proxy cloud. Nommée par l'extracteur (#1283),
  #  elle reste un INCONNU ici — un refus n'est pas une version.
  t "extracteur en INCONNU"                      INCONNU verdict_version_servie 2.49.2 "INCONNU: https://5hostachy.fr/ a répondu HTTP 403"
  t "extracteur muet"                            INCONNU verdict_version_servie 2.49.2 ""
  t "version attendue illisible"                 INCONNU verdict_version_servie "" 2.49.2
  if [ "$echecs" -eq 0 ]; then
    echo "✓ verdicts post-MEP : déployé, version servie, et les cas zéro rendent INCONNU."
    exit 0
  fi
  exit 1
fi
