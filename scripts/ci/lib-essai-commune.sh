#!/bin/bash
# =============================================================================
#  lib-essai-commune.sh — L'installation COMMUNE dans l'essai de mise à jour (#3007)
#
#  Module IMPORTÉ par `essai-mise-a-jour.sh` (mode `commune`), jamais exécuté par
#  un cron : pas de bit x, versionné en 100644.
#
#  Pourquoi (23/11/2026) — #3006 éprouvait une installation commune par morceaux :
#  la pile par bash, le `Caddyfile` sur un vrai Caddy, le refus de
#  `/auth/verifier-acces` par pytest. L'ASSEMBLAGE restait INCONNU : rien ne
#  constatait, sur des conteneurs réels, que la pile recréée par la mise à jour
#  porte la surcouche commune, que Caddy relaie `/uploads/*` à l'API, et que le
#  front sert l'hôte demandé.
#
#  Le déroulé, celui d'un hébergeur, sur l'installation de <de> :
#    1. `COPROPRIETES_FICHIER` dans `.env`, la pile recréée (surcouche comprise) ;
#    2. deux copropriétés, A et B, par `creer-copropriete.sh` de <de> ;
#    3. un fichier témoin chez A, dans un dossier que le code écrit (`fichiers/`) ;
#    4. le CONSTAT (`constater_commune`), avant ET après la mise à jour :
#       la surcouche sur les conteneurs, le fichier de A servi sous l'hôte de A et
#       refusé sous celui de B (le jeton de A), le front sous chaque hôte.
#
#  Les variables qu'il pose pour l'appelant : HOTE_A, HOTE_B, MDP_A (le témoin de
#  connexion, sous l'hôte de A). Il emploie COMPOSE, TRAVAIL, RACINE et `poser`.
#
#  Test : bash scripts/ci/lib-essai-commune.sh --selftest
# =============================================================================

#: Le fichier témoin, sous la racine de A : un dossier SERVI (claude-config#637).
TEMOIN_COMMUNE="fichiers/temoin-essai.txt"
CONTENU_A="fichier de la copropriete A"

# ── PURE : l'installation commune tient-elle ? ────────────────────────────────
#  $1 caddy monte les fragments communs (oui|non) · $2 le front lit l'hôte
#  demandé (oui|non) · $3 code du fichier de A sous l'hôte de A · $4 son contenu
#  est celui de A (oui|non) · $5 code du même fichier, jeton de A, sous l'hôte de B
#  · $6 code du front sous l'hôte de A · $7 sous l'hôte de B
#  → OK | ECHEC:<raisons>
verdict_commune() {
    local fautes=()
    [ "$1" = oui ] || fautes+=("Caddy ne monte pas les fragments communs (fichiers.caddy, garde-des-pages.caddy)")
    [ "$2" = oui ] || fautes+=("le front ne lit pas l'hôte demandé (HOST_HEADER)")
    [ "$3" = 200 ] || fautes+=("le fichier de A, sous l'hôte de A, rend ${3:-rien} au lieu de 200")
    [ "$4" = oui ] || fautes+=("le fichier servi sous l'hôte de A n'est pas celui de A")
    case "$5" in 401|403|404) ;; *) fautes+=("le jeton de A ouvre le fichier sous l'hôte de B (${5:-rien})") ;; esac
    case "$6" in 2??|3??) ;; *) fautes+=("le front ne répond pas sous l'hôte de A (${6:-rien})") ;; esac
    case "$7" in 2??|3??) ;; *) fautes+=("le front ne répond pas sous l'hôte de B (${7:-rien})") ;; esac
    if [ ${#fautes[@]} -eq 0 ]; then echo OK; else local IFS=';'; echo "ECHEC:${fautes[*]}"; fi
}

#  PURE. Le verdict de l'essai et celui de l'installation commune, en un seul.
#  $1 et $2 : OK | ECHEC:<raisons> → OK | ECHEC:<raisons des deux>
joindre_verdicts() {
    local fautes=()
    [ "$1" = OK ] || fautes+=("${1#ECHEC:}")
    [ "$2" = OK ] || fautes+=("installation commune : ${2#ECHEC:}")
    if [ ${#fautes[@]} -eq 0 ]; then echo OK; else local IFS=';'; echo "ECHEC:${fautes[*]}"; fi
}

#  L'hôte d'une adresse (`http://75011-essai-a.localhost/` → `75011-essai-a.localhost`).
hote_de() { printf '%s\n' "$1" | sed -E 's#^[a-z]+://##; s#[/:].*$##'; }

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$(verdict_commune "${@:3}"); r=${r%%:*}
          [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }
    t "tout tient"                              OK     oui oui 200 oui 401 200 200
    t "redirection du front admise"             OK     oui oui 200 oui 401 302 307
    t "sans la surcouche dans Caddy"            ECHEC  non oui 200 oui 401 200 200
    t "front sans l'hôte demandé"               ECHEC  oui non 200 oui 401 200 200
    t "le fichier de A n'est pas servi"         ECHEC  oui oui 404 non 401 200 200
    t "un autre contenu sous l'hôte de A"       ECHEC  oui oui 200 non 401 200 200
    t "le jeton de A ouvre B"                   ECHEC  oui oui 200 oui 200 200 200
    t "le front de B rend 421"                  ECHEC  oui oui 200 oui 401 200 421
    t "une mesure absente"                      ECHEC  oui oui ""  oui 401 200 200
    j() { local r; r=$(joindre_verdicts "$3" "$4")
          [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }
    j "les deux tiennent"         OK                                        OK          OK
    j "l'essai seul échoue"       "ECHEC:pas d'export"                      "ECHEC:pas d'export" OK
    j "la commune seule échoue"   "ECHEC:installation commune : front B"    OK          "ECHEC:front B"
    j "les deux échouent"         "ECHEC:x;installation commune : y"        "ECHEC:x"   "ECHEC:y"
    h=$(hote_de "http://75011-essai-a.localhost/")
    [ "$h" = 75011-essai-a.localhost ] && echo "PASS  hôte d'une adresse → $h" || { echo "FAIL  hôte d'une adresse : $h"; st=1; }
    [ "$st" -eq 0 ] && echo "lib-essai-commune : tous les cas passent."
    exit "$st"
fi

# ── Les gestes (sur l'installation de l'essai) ────────────────────────────────

#  Code HTTP d'une requête vers l'installation, sous un hôte. $1 hôte · $2 chemin
#  · $3 fichier du corps (facultatif) · reste : options de curl.
code_sous() {
    local hote="$1" chemin="$2" corps="${3:-/dev/null}"; shift 3 || shift $#
    curl -s -m 10 -o "$corps" -w '%{http_code}' -H "Host: $hote" "$@" "http://localhost$chemin" || true
}

#  Deux copropriétés, A et B, sur l'installation de <de>. Pose HOTE_A, HOTE_B, MDP_A.
installer_commune() {
    local c log adresse racine
    poser COPROPRIETES_FICHIER /app/data/coproprietes.json
    mapfile -t COMPOSE < <(. "$RACINE/deploiement/standard/lib-installation.sh"; definir_compose; printf '%s\n' "${COMPOSE[@]}")
    "${COMPOSE[@]}" up -d --quiet-pull
    attendre_sante || { echo "::error::l'installation ne répond plus une fois déclarée commune"; return 1; }
    for c in a b; do
        log="$TRAVAIL/creer-$c.log"
        bash deploiement/standard/commune/creer-copropriete.sh "essai-$c" \
            --code-postal 7501"$([ $c = a ] && echo 1 || echo 2)" --nom "Essai $c" \
            --expediteur "contact@exemple.test" 2>&1 | tee "$log" \
            || { echo "::error::creer-copropriete.sh a échoué pour essai-$c"; return 1; }
        adresse=$(sed -n 's/.*Copropriété essai-'"$c"' déclarée : *//p' "$log" | tail -1 | tr -d '\r ')
        [ -n "$adresse" ] || { echo "::error::adresse de essai-$c introuvable dans la sortie"; return 1; }
        if [ $c = a ]; then
            HOTE_A=$(hote_de "$adresse")
            MDP_A=$(sed -n 's/.*Mot de passe temporaire : *//p' "$log" | tail -1 | tr -d '\r ')
            [ -n "$MDP_A" ] || { echo "::error::mot de passe initial de essai-a introuvable"; return 1; }
        else
            HOTE_B=$(hote_de "$adresse")
        fi
    done
    racine=$("${COMPOSE[@]}" exec -T api cat /app/data/coproprietes.json \
        | python3 -c 'import json,sys; print(next(c["racine_fichiers"] for c in json.load(sys.stdin)["coproprietes"] if c["identifiant"] == "essai-a"))')
    "${COMPOSE[@]}" exec -T -u app api sh -c "mkdir -p '$racine/$(dirname "$TEMOIN_COMMUNE")' && printf '%s' '$CONTENU_A' > '$racine/$TEMOIN_COMMUNE'"
    echo "Copropriétés : A sous $HOTE_A, B sous $HOTE_B ; témoin $TEMOIN_COMMUNE chez A."
}

#  Le constat, sur les conteneurs en service. $1 libellé (« avant », « après »).
constater_commune() {
    local jarre="$TRAVAIL/jeton-a.txt" corps="$TRAVAIL/temoin.txt" montages env_front
    local caddy front code_a contenu code_b front_a front_b
    #  Les conteneurs EN SERVICE, pas la commande : c'est la pile recréée qu'on juge.
    #  Lus dans une variable, puis jugés : jamais un tube vers `grep -q` sous pipefail.
    montages=$(docker inspect "$("${COMPOSE[@]}" ps -q caddy)" --format '{{range .Mounts}}{{println .Destination}}{{end}}' 2>/dev/null || true)
    env_front=$(docker inspect "$("${COMPOSE[@]}" ps -q front)" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null || true)
    caddy=non; front=non
    if grep -qx '/etc/caddy/commune/fichiers.caddy' <<<"$montages" \
        && grep -qx '/etc/caddy/commune/garde-des-pages.caddy' <<<"$montages"; then caddy=oui; fi
    if grep -qx 'HOST_HEADER=host' <<<"$env_front"; then front=oui; fi
    rm -f "$jarre"
    code_sous "$HOTE_A" /api/auth/login /dev/null -c "$jarre" -X POST -H 'Content-Type: application/json' \
        -d "{\"email\":\"admin@localhost\",\"password\":\"$MDP_A\"}" >/dev/null
    code_a=$(code_sous "$HOTE_A" "/uploads/$TEMOIN_COMMUNE" "$corps" -b "$jarre")
    contenu=$([ "$(cat "$corps" 2>/dev/null)" = "$CONTENU_A" ] && echo oui || echo non)
    code_b=$(code_sous "$HOTE_B" "/uploads/$TEMOIN_COMMUNE" /dev/null -b "$jarre")
    front_a=$(code_sous "$HOTE_A" / /dev/null)
    front_b=$(code_sous "$HOTE_B" / /dev/null)
    echo "Constat commun ($1) : caddy=$caddy front=$front A/A=$code_a ($contenu) A/B=$code_b front A=$front_a B=$front_b"
    verdict_commune "$caddy" "$front" "$code_a" "$contenu" "$code_b" "$front_a" "$front_b"
}
