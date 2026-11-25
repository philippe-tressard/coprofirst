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
#    2. deux copropriétés : A, celle de l'installation, déclarée à la main ; B, par
#       `creer-copropriete.sh` de <de> ;
#    3. un fichier témoin chez A, dans un dossier que le code écrit (`fichiers/`) ;
#    4. le CONSTAT (`constater_commune`), avant ET après la mise à jour :
#       la surcouche sur les conteneurs, le fichier de A servi sous l'hôte de A et
#       refusé sous celui de B (le jeton de A), le front sous chaque hôte.
#
#  Les variables qu'il pose pour l'appelant : HOTE_A, HOTE_B, MDP_A (le témoin de
#  connexion, sous l'hôte de A). Il emploie COMPOSE, TRAVAIL, RACINE, `poser` et
#  `attendre_sante`.
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


# ── Les gestes (sur l'installation de l'essai) ────────────────────────────────

#  Code HTTP d'une requête vers l'installation, sous un hôte. $1 hôte · $2 chemin
#  · $3 fichier du corps (facultatif) · reste : options de curl.
code_sous() {
    local hote="$1" chemin="$2" corps="${3:-/dev/null}"; shift 3 || shift $#
    curl -s -m 10 -o "$corps" -w '%{http_code}' -H "Host: $hote" "$@" "http://localhost$chemin" || true
}

#: L'hôte commun de l'essai : un nom RÉSERVÉ (`.test`), jamais un vrai domaine
#: (`standards/03` §8 quater) ; une déclaration exige un nom de domaine, pas `localhost`.
HOTE_COMMUN_ESSAI="essai.test"

#  Deux copropriétés sur l'installation de <de>, par le chemin de l'hébergeur
#  (`deploiement/standard/commune/LISEZMOI.md`) :
#  - A : la copropriété DE L'INSTALLATION, déclarée à la main (« Déclarer les
#    copropriétés ») — sa base et son secret restent `DATABASE_URL` et `SECRET_KEY`.
#    C'est le passage d'une installation propre à une installation commune ; une
#    déclaration vide est refusée (« Aucune copropriété déclarée »), d'où une
#    première copropriété écrite, jamais créée par l'outil ;
#  - B : ajoutée par `creer-copropriete.sh`, sa base et son secret neufs.
#  Pose HOTE_A, HOTE_B, MDP_A : le mot de passe de l'administrateur initial de
#  l'installation, devenu celui de A ($1), une fois changé (il est temporaire).
installer_commune() {
    local log adresse
    #  Pas d'apostrophe dans le message de `:?` : bash l'y lit comme un début de
    #  chaîne, et tout le reste du fichier disparaissait (constater_commune jamais
    #  définie — l'essai du 25/11/2026, run 45511494349).
    MDP_A="${1:?mot de passe attendu : administrateur initial}"
    poser ORIGIN "http://$HOTE_COMMUN_ESSAI"
    poser COPROPRIETES_FICHIER /app/data/coproprietes.json
    "${COMPOSE[@]}" exec -T -u app api sh -c 'cat > /app/data/coproprietes.json' <<JSON
{"coproprietes": [{"identifiant": "essai-a", "code_postal": "75011", "nom": "Essai a",
  "anciens_alias": [], "hotes": [], "suspendue": false,
  "base": "DATABASE_URL", "secret": "SECRET_KEY", "racine_fichiers": "/app/uploads/essai-a",
  "expediteur": "contact@exemple.test", "nom_expediteur": "Essai a"}]}
JSON
    mapfile -t COMPOSE < <(. "$RACINE/deploiement/standard/lib-installation.sh"; definir_compose; printf '%s\n' "${COMPOSE[@]}")
    "${COMPOSE[@]}" up -d --quiet-pull
    attendre_sante || { echo "::error::l'installation ne répond plus une fois déclarée commune"; return 1; }
    HOTE_A="75011-essai-a.$HOTE_COMMUN_ESSAI"
    log="$TRAVAIL/creer-b.log"
    bash deploiement/standard/commune/creer-copropriete.sh essai-b --code-postal 75012 \
        --nom "Essai b" --expediteur contact@exemple.test 2>&1 | tee "$log" \
        || { echo "::error::creer-copropriete.sh a échoué pour essai-b"; return 1; }
    adresse=$(sed -n 's/.*Copropriété essai-b déclarée : *//p' "$log" | tail -1 | tr -d '\r ')
    [ -n "$adresse" ] || { echo "::error::adresse de essai-b introuvable dans la sortie"; return 1; }
    HOTE_B=$(hote_de "$adresse")
    #  Le mot de passe initial est TEMPORAIRE (#3019) : tant qu'il tient, toute route
    #  rend 403 sauf son changement. L'hébergeur le change d'abord ; l'essai aussi.
    local jarre="$TRAVAIL/jeton-initial.txt" neuf code
    neuf="Essai-$(openssl rand -hex 12)"
    code_sous "$HOTE_A" /api/auth/login /dev/null -c "$jarre" -X POST -H 'Content-Type: application/json' \
        -d "{\"email\":\"admin@localhost\",\"password\":\"$MDP_A\"}" >/dev/null
    code=$(code_sous "$HOTE_A" /api/auth/change-password "$TRAVAIL/changement.json" -b "$jarre" -X POST \
        -H 'Content-Type: application/json' \
        -d "{\"mot_de_passe_actuel\":\"$MDP_A\",\"nouveau_mot_de_passe\":\"$neuf\"}")
    [ "$code" = 204 ] || { echo "::error::mot de passe initial de A non changé : HTTP $code ($(head -c 200 "$TRAVAIL/changement.json" 2>/dev/null))"; return 1; }
    MDP_A="$neuf"
    #  Le runner résout les noms de l'essai, comme un navigateur : la sonde de version
    #  lit le site par son adresse. Une machine jetable seulement (CI).
    if [ "${GITHUB_ACTIONS:-}" = true ]; then
        printf '127.0.0.1 %s %s %s\n' "$HOTE_COMMUN_ESSAI" "$HOTE_A" "$HOTE_B" | sudo tee -a /etc/hosts >/dev/null
    fi
    "${COMPOSE[@]}" exec -T -u app api sh -c "mkdir -p '/app/uploads/essai-a/$(dirname "$TEMOIN_COMMUNE")' && printf '%s' '$CONTENU_A' > '/app/uploads/essai-a/$TEMOIN_COMMUNE'"
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

# ── Les exports de base d'une sauvegarde avant mise à jour ────────────────────
#  Un export par base (`mise-a-jour.sh`, `export_de`) : `<archive>-base.tar.gz` sur
#  une installation propre ; sur une commune, `<archive>-base-<identifiant>.tar.gz`
#  par copropriété. L'essai ne cherchait que le premier : sur une commune, la
#  sauvegarde complète était lue « pas d'export » (run 45561020043, 25/11/2026).
EXPORT_DE_BASE='-base(-[a-z0-9-]+)?\.tar\.gz$'
#  A et B : une base chacune.
BASES_ESSAI_COMMUNE=2
#  $@ noms de fichiers → le nombre d'exports de base parmi eux.
compter_exports_base() { printf '%s\n' "$@" | grep -cE -- "$EXPORT_DE_BASE" || true; }

# ── Autotest : en DERNIER, une fois toutes les fonctions définies ─────────────
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
    e() { local r; r=$(compter_exports_base "${@:3}")
          [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }
    v=coprofirst_3.125.7_vers_3.125.8_20261125_063110
    e "installation propre"               1  "$v.tar.gz" "$v-base.tar.gz"
    e "commune : une par copropriété"     2  "$v.tar.gz" "$v-base-essai-a.tar.gz" "$v-base-essai-b.tar.gz"
    e "l'archive des volumes seule"       0  "$v.tar.gz"
    e "un nom qui finit en -base ailleurs" 0 "$v-base.tar.gz.part" "notes-base.txt"
    h=$(hote_de "http://75011-essai-a.localhost/")
    [ "$h" = 75011-essai-a.localhost ] && echo "PASS  hôte d'une adresse → $h" || { echo "FAIL  hôte d'une adresse : $h"; st=1; }
    #  Le module entier s'est chargé : chaque fonction dont l'essai a besoin existe.
    for f in verdict_commune joindre_verdicts compter_exports_base hote_de code_sous installer_commune constater_commune; do
        [ "$(type -t "$f")" = function ] && echo "PASS  $f définie" || { echo "FAIL  $f absente après chargement"; st=1; }
    done
    [ "$st" -eq 0 ] && echo "lib-essai-commune : tous les cas passent."
    exit "$st"
fi
