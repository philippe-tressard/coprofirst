#!/bin/bash
# =============================================================================
#  lib-audit-conteneurs.sh — S4 : les conteneurs qui tournent sont-ils ceux du
#  dépôt, sans privilège qu'il ne leur donne ?
#
#  Module SOURCÉ (mode 100644) par `audit-securite.sh` (audit de sécurité
#  nocturne). Jamais exécuté par un cron.
#  Autotest : bash scripts/lib/lib-audit-conteneurs.sh --selftest
#
#  ── POURQUOI ─────────────────────────────────────────────────────────────────
#
#  Un conteneur est la frontière entre l'application exposée au public et le
#  nœud. Elle ne tient que si le conteneur n'est pas privilégié, ne partage ni
#  le réseau ni les processus de l'hôte, ne monte ni la prise Docker ni un
#  chemin du système en écriture, et n'a pas désactivé seccomp ou AppArmor.
#  `docker-compose.yml` ne demande rien de tout cela — mais c'est ce qui TOURNE
#  qu'il faut lire, pas le fichier : un `docker run` à la main, un compose
#  modifié sur place (S1 le dirait) ou une image qui s'attend à plus laissent
#  le fichier intact.
#
#  Et l'IMAGE : la CI publie chaque image avec l'étiquette
#  `org.opencontainers.image.revision=<commit>` (`images.yml`), et le nœud
#  tire celle de son commit (#1758). Une image dont la révision n'est pas le
#  HEAD de l'arbre déployé est soit un SECOURS (construite ici, sans étiquette
#  — le chemin arbitré le 08/10/2026, qui alerte déjà), soit une image
#  périmée, soit une image qui ne vient pas de la CI. WARN, qui le nomme.
#
#  Deux mesures par conteneur de l'application, une pour la prise Docker.
#  Lecture seule : `docker inspect`, `stat`. Un conteneur hors liste n'est pas
#  jugé ici — C2 compte ceux de l'application, C35 la pile de bureau.
#
#  Fonctions PURES : une ligne de `docker inspect` entre, un verdict sort —
#    CONFORME · ECART:<ce qui diffère> · INCONNU:<pourquoi>
# =============================================================================

#: Le format passé à `docker inspect`, UNE ligne par conteneur, champs séparés
#: par `|` : nom, privilégié, capacités ajoutées, réseau, pid, options de
#: sécurité, montages liés (séparés par `;`), révision de l'image.
CONTENEURS_FORMAT='{{.Name}}|{{.HostConfig.Privileged}}|{{join .HostConfig.CapAdd ","}}|{{.HostConfig.NetworkMode}}|{{.HostConfig.PidMode}}|{{join .HostConfig.SecurityOpt ","}}|{{range .HostConfig.Binds}}{{.}};{{end}}|{{index .Config.Labels "org.opencontainers.image.revision"}}'

#: Les montages LIÉS que `docker-compose.yml` demande (chemin sur l'hôte), tous
#: en lecture seule. L'autotest les confronte au fichier du dépôt : un montage
#: ajouté au compose sans être déclaré ici fait échouer la CI, et l'inverse aussi.
CONTENEURS_BINDS_ADMIS="${CONTENEURS_BINDS_ADMIS:-/etc/localtime /opt/5hostachy/Caddyfile /opt/5hostachy/infra/postgresql/pg_hba.conf /opt/5hostachy/infra/postgresql/initdb}"
#: Le projet Compose dont on juge les conteneurs (le daemon de rpi2 est partagé).
CONTENEURS_PROJET="${CONTENEURS_PROJET:-5hostachy}"

# ── Décisions PURES ──────────────────────────────────────────────────────────

#  $1 = une ligne au format CONTENEURS_FORMAT → CONFORME | ECART:… | INCONNU:…
conteneur_verdict() {
    local ligne=${1:-} nom priv caps net pid secopt binds rev ecarts="" b hote mode
    [ -n "$ligne" ] || { echo "INCONNU:ligne vide"; return 0; }
    IFS='|' read -r nom priv caps net pid secopt binds rev <<< "$ligne"
    nom=${nom#/}
    [ -n "$nom" ] && [ -n "$priv" ] || { echo "INCONNU:ligne incomplète"; return 0; }
    [ "$priv" = false ] || ecarts="$ecarts privilégié;"
    [ -z "$caps" ] || ecarts="$ecarts capacités=[$caps];"
    [ "$net" != host ] || ecarts="$ecarts réseau-de-l-hôte;"
    [ "$pid" != host ] || ecarts="$ecarts processus-de-l-hôte;"
    case "$secopt" in *unconfined*) ecarts="$ecarts sécurité-désactivée=[$secopt];" ;; esac
    local IFS=';'
    for b in $binds; do
        [ -n "$b" ] || continue
        hote=${b%%:*}
        mode=${b##*:}
        #  Un volume NOMMÉ (`5hostachy_pg_data:/var/lib/…`) figure aussi dans
        #  `HostConfig.Binds` : ce n'est pas un chemin de l'hôte, et le compose
        #  les déclare. Seul un chemin absolu est un montage lié — le premier
        #  audit en production les comptait tous en FAIL (30/10/2026).
        case "$hote" in /*) ;; *) continue ;; esac
        case "$hote" in
            *docker.sock*) ecarts="$ecarts prise-docker=[$b];"; continue ;;
        esac
        case " $CONTENEURS_BINDS_ADMIS " in
            *" $hote "*) [ "$mode" = ro ] || ecarts="$ecarts montage-en-écriture=[$b];" ;;
            *) ecarts="$ecarts montage-non-déclaré=[$b];" ;;
        esac
    done
    unset IFS
    if [ -n "$ecarts" ]; then echo "ECART:${ecarts# }"; else echo CONFORME; fi
}

#  $1 = la ligne · $2 = le HEAD de l'arbre déployé (sha complet ou court)
#  → CI (l'image de ce commit) | SECOURS (sans révision : construite ici)
#    | AUTRE:<révision> (une autre révision) | INCONNU
conteneur_provenance() {
    local rev=${1##*|} head=${2:-}
    [ -n "${1:-}" ] && [ -n "$head" ] || { echo INCONNU; return 0; }
    if [ -z "$rev" ]; then echo SECOURS
    elif [ "${rev:0:${#head}}" = "$head" ] || [ "${head:0:${#rev}}" = "$rev" ]; then echo CI
    else echo "AUTRE:${rev:0:12}"; fi
}

#  Le nom d'un conteneur, lu sur sa ligne.
conteneur_nom() { local n=${1%%|*}; printf '%s' "${n#/}"; }

#  $1 = `stat -c '%U:%G:%a' /var/run/docker.sock` → CONFORME | ECART:… | INCONNU
prise_docker_verdict() {
    local s=${1:-} u g m
    [ -n "$s" ] || { echo "INCONNU:prise Docker illisible"; return 0; }
    IFS=: read -r u g m <<< "$s"
    [ "$u" = root ] || { echo "ECART:propriétaire $u (voulu root)"; return 0; }
    case "$m" in
        660|600|640) [ "$g" = docker ] || [ "$g" = root ] || { echo "ECART:groupe $g (voulu docker)"; return 0; } ;;
        *) echo "ECART:mode $m (voulu 660 root:docker — un mode plus ouvert rend root à tout compte local)"; return 0 ;;
    esac
    echo CONFORME
}

#  PURE. $1 = le texte d'un docker-compose.yml → « <chemin hôte> <mode> » par
#  montage LIÉ (source commençant par `/` ou `./`, chemin relatif résolu sous
#  /opt/5hostachy), mode `ro` ou `rw` — un montage sans mode est en écriture.
#  🔴 Le `\r` est retiré d'abord : `docker-compose.yml` est versionné en CRLF, et
#  le `sed` de Linux garde le `\r` en fin de ligne — `:ro$` ne correspondait plus
#  sur le runner de la CI, alors que celui de MSYS l'avale (rouge de #2374).
compose_montages_lies() {
    printf '%s\n' "${1:-}" | tr -d '\r' \
        | sed -n 's/^[[:space:]]*-[[:space:]]*"\{0,1\}\(\.\{0,1\}\/[^:"]*\):[^:"]*\(:[a-z,]*\)\{0,1\}"\{0,1\}[[:space:]]*$/\1 \2/p' \
        | sed -e 's|^\./|/opt/5hostachy/|' -e 's/ :\(.*\)$/ \1/' -e 's/ $/ rw/' \
        | sed 's/ \([a-z]*,\)*ro\(,[a-z]*\)*$/ ro/; t; s/ [a-z,]*$/ rw/'
}

# ── Les lectures (effets de bord : docker et stat, en lecture seule) ─────────
conteneurs_lire() {
    local ids
    ids=$(docker ps -q --filter "label=com.docker.compose.project=$CONTENEURS_PROJET" 2>/dev/null) || return 0
    [ -n "$ids" ] || return 0
    # shellcheck disable=SC2086  # liste d'identifiants, coupée exprès
    docker inspect --format "$CONTENEURS_FORMAT" $ids 2>/dev/null
}
prise_docker_lire() { stat -c '%U:%G:%a' /var/run/docker.sock 2>/dev/null; }

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
audit_conteneurs_selftest() {
    local st=0
    t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; }; }
    echo "== self-test lib-audit-conteneurs (S4) =="
    local H=abc123def456
    local API="/hostachy_api|false|||5hostachy_default||/etc/localtime:/etc/localtime:ro;|${H}000"
    local CADDY="/hostachy_caddy|false|||5hostachy_default||/etc/localtime:/etc/localtime:ro;/opt/5hostachy/Caddyfile:/etc/caddy/Caddyfile:ro;|${H}000"
    t "l'API telle que compose la lance" CONFORME "$(conteneur_verdict "$API")"
    t "Caddy et son Caddyfile en lecture seule" CONFORME "$(conteneur_verdict "$CADDY")"
    t "privilégié" "ECART:privilégié;" "$(conteneur_verdict "${API/|false|/|true|}")"
    t "capacité ajoutée" "ECART:capacités=[SYS_ADMIN];" "$(conteneur_verdict "/x|false|SYS_ADMIN||default||;|r")"
    t "réseau de l'hôte" "ECART:réseau-de-l-hôte;" "$(conteneur_verdict "/x|false||host|||;|r")"
    t "processus de l'hôte" "ECART:processus-de-l-hôte;" "$(conteneur_verdict "/x|false|||host||;|r")"
    t "seccomp désactivé" "ECART:sécurité-désactivée=[seccomp=unconfined];" \
      "$(conteneur_verdict "/x|false||||seccomp=unconfined|;|r")"
    t "la prise Docker montée" "ECART:prise-docker=[/var/run/docker.sock:/var/run/docker.sock:rw];" \
      "$(conteneur_verdict "/x|false|||||/var/run/docker.sock:/var/run/docker.sock:rw;|r")"
    t "un montage déclaré, mais en écriture" "ECART:montage-en-écriture=[/opt/5hostachy/Caddyfile:/etc/caddy/Caddyfile:rw];" \
      "$(conteneur_verdict "${CADDY/Caddyfile:ro/Caddyfile:rw}")"
    t "un montage non déclaré (/etc en lecture)" "ECART:montage-non-déclaré=[/etc:/hote/etc:ro];" \
      "$(conteneur_verdict "/x|false|||||/etc:/hote/etc:ro;|r")"
    t "deux écarts, dans l'ordre" "ECART:privilégié; réseau-de-l-hôte;" "$(conteneur_verdict "/x|true||host|||;|r")"
    #  La ligne RÉELLE de hostachy_api au premier audit (30/10/2026) : ses volumes
    #  nommés ne sont pas des montages de l'hôte.
    t "volumes nommés de l'API (production, 30/10)" CONFORME \
      "$(conteneur_verdict "/hostachy_api|false|||5hostachy_default||5hostachy_app_data:/app/data:rw;5hostachy_uploads:/app/uploads:rw;5hostachy_backups:/backups:rw;/etc/localtime:/etc/localtime:ro;|r")"
    t "un volume nommé n'excuse pas la prise Docker à côté" "ECART:prise-docker=[/var/run/docker.sock:/s:rw];" \
      "$(conteneur_verdict "/x|false|||||5hostachy_pg_data:/var/lib/postgresql/data:rw;/var/run/docker.sock:/s:rw;|r")"
    t "nom du conteneur" hostachy_api "$(conteneur_nom "$API")"
    t "provenance : l'image de ce commit" CI "$(conteneur_provenance "$API" "$H")"
    t "provenance : HEAD court contre révision longue" CI "$(conteneur_provenance "$API" "${H:0:7}")"
    t "provenance : construite ici (secours)" SECOURS "$(conteneur_provenance "${API%|*}|" "$H")"
    t "provenance : une autre révision" "AUTRE:fedcba987654" "$(conteneur_provenance "${API%|*}|fedcba9876543210" "$H")"
    #  LE CAS ZÉRO.
    t "ligne vide" INCONNU "$(conteneur_verdict "" | cut -d: -f1)"
    t "ligne tronquée" INCONNU "$(conteneur_verdict "/x" | cut -d: -f1)"
    t "provenance sans HEAD" INCONNU "$(conteneur_provenance "$API" "")"
    t "prise Docker : root:docker 660" CONFORME "$(prise_docker_verdict root:docker:660)"
    t "prise Docker : 666" ECART "$(prise_docker_verdict root:docker:666 | cut -d: -f1)"
    t "prise Docker : à un autre compte" ECART "$(prise_docker_verdict ptressard:docker:660 | cut -d: -f1)"
    t "prise Docker : illisible" INCONNU "$(prise_docker_verdict "" | cut -d: -f1)"
    #  La liste des montages admis EST celle du compose : lue dans le fichier du
    #  dépôt, chemins relatifs résolus sous /opt/5hostachy. Dans les deux sens.
    #  La lecture, éprouvée sur les formes que le compose peut prendre — CRLF
    #  compris, la forme du fichier versionné.
    local E=$'services:\r\n  a:\r\n    volumes:\r\n      - /etc/localtime:/etc/localtime:ro\r\n      - ./Caddyfile:/etc/caddy/Caddyfile:ro\r\n      - "./x:/y"\r\n      - ./z:/w:rw\r\n      - ./q:/q:z,ro\r\n      - donnees:/data\r\n'
    t "lecture : CRLF, guillemets, sans mode (= rw), :rw, options, volume nommé ignoré" \
      "/etc/localtime ro|/opt/5hostachy/Caddyfile ro|/opt/5hostachy/x rw|/opt/5hostachy/z rw|/opt/5hostachy/q ro" \
      "$(compose_montages_lies "$E" | paste -sd'|' -)"
    t "lecture : texte vide → rien" "" "$(compose_montages_lies "")"
    #  La liste des montages admis EST celle du compose : lue dans le fichier du
    #  dépôt (chemin relatif à ce module, aucun outil hors coreutils), dans les
    #  deux sens. 🔴 Une lecture vide n'est pas « rien à déclarer » : le cas zéro
    #  le dit en clair, au lieu d'un `[]` à deviner (rouge de #2374).
    local compose="$(dirname "${BASH_SOURCE[0]}")/../../docker-compose.yml" lus
    if [ ! -r "$compose" ]; then
        echo "FAIL  docker-compose.yml illisible ($compose) — contrôle des montages INCONNU"; st=1
    else
        lus=$(compose_montages_lies "$(cat "$compose")")
        if [ -z "$lus" ]; then
            echo "FAIL  aucun montage lié lu dans $compose — la lecture est cassée, contrôle INCONNU"; st=1
        else
            t "les montages liés du compose sont tous déclarés ici" \
              "$(printf '%s\n' $CONTENEURS_BINDS_ADMIS | sort -u | paste -sd' ' -)" \
              "$(cut -d' ' -f1 <<< "$lus" | sort -u | paste -sd' ' -)"
            t "aucun montage lié en écriture dans le compose" "" "$(grep ' rw$' <<< "$lus" || true)"
        fi
    fi
    [ "$st" -eq 0 ] && echo "lib-audit-conteneurs : tous les cas passent."
    return "$st"
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    audit_conteneurs_selftest; exit $?
fi
