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
#    P3b — l'API la PUBLIE dans `GET /config` (`version_logicielle`, #2833) ;
#    P3c — chaque hôte sert les fichiers d'association des apps de SA version (#2860).
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

#  ── P3c — les fichiers d'association des apps, sur CHAQUE hôte (#2860) ─────────
#
#  🔴 POURQUOI (17/11/2026). `assetlinks.json` rendait 404 sur la démo pendant que
#  l'AASA y rendait 200, et la clôture de #2788 ne l'a pas vu : rien ne le sondait
#  après une MEP. Un fichier absent, mal typé ou redirigé ne fait aucune erreur : le
#  lien reste au navigateur (`test_liens_d_application.py`).
#
#  Chaque hôte se juge contre SA version : la démo monte seule à 04:30 et sert une
#  version plus ancienne que la production pendant des heures — la comparer à
#  `origin/main` crierait à chaque MEP. Sa version se lit dans `GET /config`
#  (`version_logicielle`, #2833) ; le fichier attendu, au tag `v<version>`. Une
#  version illisible (installation d'avant v3.114.0) rend INCONNU, jamais OK.

#: Les hôtes sondés : la production, et la démo publique (`api/app/demo/personnages.DOMAINE`).
HOTE_DEMO="https://demo.coprofirst.fr"
#: Les fichiers d'association, ceux du matcher `@liens_d_application` du `Caddyfile`.
FICHIERS_ASSOCIATION=(apple-app-site-association assetlinks.json)

verdict_association() {     # $1 = code HTTP, $2 = type servi, $3 = identique au fichier de sa version (oui/non/"")
  #  PURE. Les deux systèmes exigent 200, `application/json` et AUCUNE redirection :
  #  curl ne suit pas, donc une redirection est un 30x, refusé comme tel.
  case "${1:-}" in "" | 000) echo INCONNU; return ;; esac
  [ "$1" = 200 ] || { echo FAIL; return; }
  case "${2:-}" in application/json*) ;; *) echo FAIL; return ;; esac
  case "${3:-}" in
    oui) echo OK ;;
    non) echo FAIL ;;   # servi, mais pas celui de sa version : empreinte manquante, cache
    *)   echo INCONNU ;;
  esac
}

ref_de_version() {          # $1 = version publiée → le tag qui la porte, ou rien
  [ -n "${1:-}" ] || return 0
  git rev-parse -q --verify "refs/tags/v$1^{commit}" >/dev/null 2>&1 && { echo "v$1"; return; }
  #  Juste après la MEP, le tag peut ne pas être encore posé (`tag-version.sh`) :
  #  `origin/main` porte alors la version, et elle seule.
  [ "$(git show origin/main:front/package.json 2>/dev/null | grep -m1 '"version"' | cut -d'"' -f4)" = "$1" ] \
    && echo origin/main
}

sonder_association() {      # $1 = hôte, $2 = ref, $3 = fichier → « code|type|identique »
  local servi code type identique=""
  servi=$(mktemp)
  read -r code type < <(curl -s -o "$servi" -w '%{http_code} %{content_type}\n' --max-time 15 \
    "$1/.well-known/$3" 2>/dev/null)
  if [ -n "$2" ] && [ "${code:-}" = 200 ]; then
    identique=$(git show "$2:front/static/.well-known/$3" 2>/dev/null | python3 -c '
import json, sys
try:
    attendu = json.load(sys.stdin)
    print("oui" if json.load(open(sys.argv[1], encoding="utf-8")) == attendu else "non")
except Exception:
    print("")' "$servi" 2>/dev/null)
  fi
  rm -f "$servi"
  echo "${code:-}|${type:-}|${identique:-}"
}

precheck_associations() {
  local hote numero version ref nom code type identique
  for hote in "$SITE" "$HOTE_DEMO"; do
    [ "$hote" = "$SITE" ] && numero=P3c || numero=P3d
    version=$(curl -s --max-time 15 "$hote/api/config" 2>/dev/null | python3 -c \
      'import json,sys
try: print(json.load(sys.stdin).get("version_logicielle") or "")
except Exception: print("")' 2>/dev/null)
    ref=$(ref_de_version "$version")
    for nom in "${FICHIERS_ASSOCIATION[@]}"; do
      IFS='|' read -r code type identique <<< "$(sonder_association "$hote" "$ref" "$nom")"
      rapporter "$numero" "$(verdict_association "$code" "$type" "$identique")" \
                "Lien d'application : ${nom}" \
                "${hote#https://} version=${version:-illisible} code=${code:-?} type=${type:-?} identique=${identique:-?}"
    done
  done
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
  precheck_associations
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
  t "association servie, celle de sa version"    OK      verdict_association 200 "application/json" oui
  t "association servie mais périmée"            FAIL    verdict_association 200 "application/json" non
  #  🔴 Le 17/11/2026 (#2860) : la démo rendait 404 en `text/html`.
  t "association absente (404 du front)"         FAIL    verdict_association 404 "text/html; charset=utf-8" ""
  t "association redirigée"                      FAIL    verdict_association 301 "" ""
  t "association sans type JSON"                 FAIL    verdict_association 200 "text/plain" oui
  t "hôte injoignable"                           INCONNU verdict_association 000 "" ""
  t "version de l'hôte illisible"                INCONNU verdict_association 200 "application/json" ""
  if [ "$echecs" -eq 0 ]; then
    echo "✓ verdicts post-MEP : déployé, version servie, liens d'application, et les cas zéro rendent INCONNU."
    exit 0
  fi
  exit 1
fi
