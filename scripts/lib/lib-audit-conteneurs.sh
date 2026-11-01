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
#  Et le DURCISSEMENT (#2368) : un conteneur que le compose durcit
#  (`<<: *conteneur_durci`) doit tourner sans autre capacité que celles qu'il
#  déclare, avec `no-new-privileges` et une racine en lecture seule. S4 est un
#  contrôle de CONFORMITÉ : il lit `CapDrop`, `CapAdd`, `SecurityOpt` et
#  `ReadonlyRootfs`, et les confronte à `CONTENEURS_DURCIS` — que l'autotest
#  confronte lui-même au compose, dans les deux sens.
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
#: sécurité, montages liés (séparés par `;`), capacités retirées, racine en
#: lecture seule, révision de l'image (toujours la DERNIÈRE : `conteneur_provenance`).
CONTENEURS_FORMAT='{{.Name}}|{{.HostConfig.Privileged}}|{{join .HostConfig.CapAdd ","}}|{{.HostConfig.NetworkMode}}|{{.HostConfig.PidMode}}|{{join .HostConfig.SecurityOpt ","}}|{{range .HostConfig.Binds}}{{.}};{{end}}|{{join .HostConfig.CapDrop ","}}|{{.HostConfig.ReadonlyRootfs}}|{{index .Config.Labels "org.opencontainers.image.revision"}}'

#: Les conteneurs DURCIS (#2368) — `<<: *conteneur_durci` dans docker-compose.yml —
#: et les capacités que chacun reçoit, avec la MÊME raison que le compose :
#:   hostachy_caddy     NET_BIND_SERVICE — écouter sur :80, un port privilégié ;
#:   hostachy_front     aucune — le compte `app` est posé par l'image ;
#:   hostachy_api       CHOWN, DAC_READ_SEARCH, SETUID, SETGID — `start.sh` rend
#:                      ses volumes à `app` puis descend par `setpriv` : uvicorn
#:                      n'en garde aucune ;
#:   hostachy_whatsapp  les mêmes — `privileges.js` rend auth_state à `node`,
#:                      puis descend : Baileys n'en garde aucune.
#: S4 refuse un conteneur de cette liste qui n'a pas exactement ces capacités,
#: les autres retirées, `no-new-privileges` et une racine en lecture seule.
CONTENEURS_DURCIS="${CONTENEURS_DURCIS:-hostachy_caddy=NET_BIND_SERVICE hostachy_front= hostachy_api=CHOWN,DAC_READ_SEARCH,SETGID,SETUID hostachy_whatsapp=CHOWN,DAC_READ_SEARCH,SETGID,SETUID}"
#: Ceux qui ne le sont PAS encore, chacun avec son ticket — jugés sur la règle
#: d'avant : aucune capacité ajoutée. L'autotest échoue si l'un d'eux devient
#: durci dans le compose sans quitter cette liste, et pour un service du compose
#: qui ne figure dans aucune des deux.
#:   hostachy_postgres  #2429 — sa configuration ne s'applique qu'à la recréation
#:                      de la base, à la bascule de nuit : elle s'éprouve à part.
CONTENEURS_NON_DURCIS="${CONTENEURS_NON_DURCIS:-hostachy_postgres}"

#: Les montages LIÉS que `docker-compose.yml` demande (chemin sur l'hôte), tous
#: en lecture seule. L'autotest les confronte au fichier du dépôt : un montage
#: ajouté au compose sans être déclaré ici fait échouer la CI, et l'inverse aussi.
CONTENEURS_BINDS_ADMIS="${CONTENEURS_BINDS_ADMIS:-/etc/localtime /opt/5hostachy/Caddyfile /opt/5hostachy/infra/postgresql/pg_hba.conf /opt/5hostachy/infra/postgresql/initdb}"
#: Le projet Compose dont on juge les conteneurs (le daemon de rpi2 est partagé).
CONTENEURS_PROJET="${CONTENEURS_PROJET:-5hostachy}"

# ── Décisions PURES ──────────────────────────────────────────────────────────

#  Une liste de capacités sous une forme comparable : majuscules, sans le
#  préfixe `CAP_` (Docker l'ajoute ou non selon sa version), triée, `,`.
caps_normaliser() {
    printf '%s' "${1:-}" | tr 'a-z,' 'A-Z\n' | sed -e 's/[[:space:]]//g' -e 's/^CAP_//' \
        | grep -v '^$' | sort -u | paste -sd, -
}

#  $1 = un nom de conteneur → ses capacités déclarées (statut 0) s'il est
#  DURCI ; statut 1 sinon.
conteneur_capacites_declarees() {
    local e
    for e in $CONTENEURS_DURCIS; do
        [ "${e%%=*}" = "$1" ] && { printf '%s' "${e#*=}"; return 0; }
    done
    return 1
}

#  $1 = une ligne au format CONTENEURS_FORMAT → CONFORME | ECART:… | INCONNU:…
conteneur_verdict() {
    local ligne=${1:-} nom priv caps net pid secopt binds capdrop ro rev ecarts="" b hote mode voulues
    [ -n "$ligne" ] || { echo "INCONNU:ligne vide"; return 0; }
    IFS='|' read -r nom priv caps net pid secopt binds capdrop ro rev <<< "$ligne"
    nom=${nom#/}
    [ -n "$nom" ] && [ -n "$priv" ] || { echo "INCONNU:ligne incomplète"; return 0; }
    [ "$priv" = false ] || ecarts="$ecarts privilégié;"
    if voulues=$(conteneur_capacites_declarees "$nom"); then
        case "$ro" in true|false) ;; *) echo "INCONNU:ligne incomplète (racine en lecture seule non lue)"; return 0 ;; esac
        [ "$(caps_normaliser "$caps")" = "$(caps_normaliser "$voulues")" ] \
            || ecarts="$ecarts capacités=[$caps] (déclarées : [$voulues]);"
        case ",$(caps_normaliser "$capdrop")," in *,ALL,*) ;; *) ecarts="$ecarts capacités-non-retirées=[$capdrop];" ;; esac
        case ",$secopt," in
            *,no-new-privileges,*|*,no-new-privileges:true,*|*,no-new-privileges=true,*) ;;
            *) ecarts="$ecarts gain-de-privilège-permis;" ;;
        esac
        [ "$ro" = true ] || ecarts="$ecarts racine-en-écriture;"
    else
        [ -z "$caps" ] || ecarts="$ecarts capacités=[$caps];"
    fi
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
#  Seuls les éléments d'une clé `volumes:` comptent : un `tmpfs` (`- /tmp:size=…`)
#  a la même forme, et n'est pas un chemin de l'hôte (#2368).
#  🔴 Le `\r` est retiré d'abord : `docker-compose.yml` est versionné en CRLF, et
#  le `sed` de Linux garde le `\r` en fin de ligne — `:ro$` ne correspondait plus
#  sur le runner de la CI, alors que celui de MSYS l'avale (rouge de #2374).
compose_montages_lies() {
    printf '%s\n' "${1:-}" | tr -d '\r' \
        | awk '/^    [a-z_]+:/ { cle = $1 } /^      - / && cle == "volumes:"' \
        | sed -n 's/^[[:space:]]*-[[:space:]]*"\{0,1\}\(\.\{0,1\}\/[^:"]*\):[^:"]*\(:[a-z,]*\)\{0,1\}"\{0,1\}[[:space:]]*$/\1 \2/p' \
        | sed -e 's|^\./|/opt/5hostachy/|' -e 's/ :\(.*\)$/ \1/' -e 's/ $/ rw/' \
        | sed 's/ \([a-z]*,\)*ro\(,[a-z]*\)*$/ ro/; t; s/ [a-z,]*$/ rw/'
}

#  PURE. $1 = le texte d'un docker-compose.yml → une ligne par service :
#  « <container_name> durci <cap_add> », « <container_name> non », ou
#  « <container_name> <ce qui empêche de le juger> ». Un service qui redéfinit
#  une clé de l'ancre (read_only, cap_drop, security_opt) n'est pas durci, quoi
#  qu'il hérite : il sort en `surcharge-de-l-ancre`. `cap_add` se lit `[A, B]`.
compose_durcissement() {
    printf '%s\n' "${1:-}" | tr -d '\r' | awk '
        function sortir() { if (svc != "") print nom, etat, caps; svc = "" }
        /^[^ #]/ { sortir(); dans = ($0 ~ /^services:/); next }
        !dans { next }
        /^  [A-Za-z0-9_-]+:[[:space:]]*$/ { sortir(); svc = $1; sub(/:$/, "", svc); nom = svc; etat = "non"; caps = ""; next }
        /^    container_name:/ { nom = $2; next }
        /^    <<:[[:space:]]*\*conteneur_durci/ { if (etat == "non") etat = "durci"; next }
        /^    (read_only|cap_drop|security_opt):/ { etat = "surcharge-de-l-ancre"; next }
        /^    cap_add:[[:space:]]*\[/ { c = $0; sub(/^[^[]*\[/, "", c); sub(/\].*$/, "", c); gsub(/[[:space:]]/, "", c); caps = c; next }
        /^    cap_add:/ { etat = "cap_add-illisible(forme-[A,B]-attendue)"; next }
        END { sortir() }'
}

#  PURE. $1 = le texte d'un docker-compose.yml → les clés de l'ancre
#  `conteneur_durci` qui MANQUENT, une par ligne (rien : l'ancre est entière).
compose_ancre_manquante() {
    local ancre
    ancre=$(printf '%s\n' "${1:-}" | tr -d '\r' \
        | awk '/^x-conteneur-durci: &conteneur_durci/ { dans = 1; next } /^[^ #]/ { dans = 0 } dans')
    [ -n "$ancre" ] || { echo "ancre-absente"; return 0; }
    grep -q '^  cap_drop: \[ALL\]' <<< "$ancre" || echo "cap_drop"
    grep -q '^  security_opt: \[no-new-privileges:true\]' <<< "$ancre" || echo "no-new-privileges"
    grep -q '^  read_only: true' <<< "$ancre" || echo "read_only"
}

#  PURE. $1 = le texte d'un docker-compose.yml → les écarts entre le compose et
#  les deux listes déclarées ici, un par ligne ; rien quand tout concorde.
durcissement_ecarts() {
    local lus nom etat caps decl e m
    lus=$(compose_durcissement "${1:-}")
    [ -n "$lus" ] || { echo "aucun service lu dans le compose"; return 0; }
    for m in $(compose_ancre_manquante "${1:-}"); do echo "ancre conteneur_durci : $m manque"; done
    while read -r nom etat caps; do
        case "$etat" in
            durci)
                if decl=$(conteneur_capacites_declarees "$nom"); then
                    [ "$(caps_normaliser "$caps")" = "$(caps_normaliser "$decl")" ] \
                        || echo "$nom : cap_add du compose [$caps], CONTENEURS_DURCIS [$decl]"
                else
                    echo "$nom : durci par le compose, absent de CONTENEURS_DURCIS"
                fi
                case " $CONTENEURS_NON_DURCIS " in
                    *" $nom "*) echo "$nom : durci par le compose, encore dans CONTENEURS_NON_DURCIS" ;;
                esac ;;
            non)
                case " $CONTENEURS_NON_DURCIS " in
                    *" $nom "*) ;;
                    *) echo "$nom : ni durci par le compose, ni dans CONTENEURS_NON_DURCIS" ;;
                esac
                if conteneur_capacites_declarees "$nom" >/dev/null; then
                    echo "$nom : dans CONTENEURS_DURCIS, le compose ne le durcit pas"
                fi ;;
            *)  echo "$nom : $etat" ;;
        esac
    done <<< "$lus"
    for e in $CONTENEURS_DURCIS $CONTENEURS_NON_DURCIS; do
        grep -q "^${e%%=*} " <<< "$lus" || echo "${e%%=*} : déclaré ici, absent du compose"
    done
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
    local DURCI="|ALL|true"
    local API="/hostachy_api|false|CAP_CHOWN,CAP_DAC_READ_SEARCH,CAP_SETGID,CAP_SETUID|5hostachy_default||no-new-privileges:true|/etc/localtime:/etc/localtime:ro;${DURCI}|${H}000"
    local CADDY="/hostachy_caddy|false|NET_BIND_SERVICE|5hostachy_default||no-new-privileges:true|/etc/localtime:/etc/localtime:ro;/opt/5hostachy/Caddyfile:/etc/caddy/Caddyfile:ro;${DURCI}|${H}000"
    t "l'API telle que compose la lance" CONFORME "$(conteneur_verdict "$API")"
    #  Le DURCISSEMENT (#2368) : chaque propriété de l'ancre, retirée une à une.
    t "durci : les capacités dans un autre ordre, sans CAP_" CONFORME \
      "$(conteneur_verdict "${API/CAP_CHOWN,CAP_DAC_READ_SEARCH,CAP_SETGID,CAP_SETUID/setuid,SETGID,DAC_READ_SEARCH,chown}")"
    t "durci : une capacité de plus que déclaré" \
      "ECART:capacités=[NET_BIND_SERVICE,SYS_ADMIN] (déclarées : [NET_BIND_SERVICE]);" \
      "$(conteneur_verdict "${CADDY/|NET_BIND_SERVICE|/|NET_BIND_SERVICE,SYS_ADMIN|}")"
    t "durci : une capacité de moins (le front n'en a aucune)" CONFORME \
      "$(conteneur_verdict "/hostachy_front|false||n||no-new-privileges:true|${DURCI}|r")"
    t "durci : la capacité déclarée manque" "ECART:capacités=[] (déclarées : [NET_BIND_SERVICE]);" \
      "$(conteneur_verdict "${CADDY/|NET_BIND_SERVICE|/||}")"
    t "durci : les capacités par défaut gardées" "ECART:capacités-non-retirées=[];" \
      "$(conteneur_verdict "${CADDY/|ALL|true/||true}")"
    t "durci : no-new-privileges absent" "ECART:gain-de-privilège-permis;" \
      "$(conteneur_verdict "${CADDY/no-new-privileges:true/}")"
    t "durci : no-new-privileges:false" "ECART:gain-de-privilège-permis;" \
      "$(conteneur_verdict "${CADDY/no-new-privileges:true/no-new-privileges:false}")"
    t "durci : racine en écriture" "ECART:racine-en-écriture;" \
      "$(conteneur_verdict "${CADDY/|ALL|true/|ALL|false}")"
    #  Les lignes RÉELLES des conteneurs durcis, relevées sur le banc du standby
    #  (01/11/2026, noms ramenés à ceux de la production) : Docker 29 préfixe
    #  `CAP_`, et range les capacités à sa façon.
    t "ligne réelle : l'API durcie (banc, 01/11)" CONFORME \
      "$(conteneur_verdict "/hostachy_api|false|CAP_CHOWN,CAP_DAC_READ_SEARCH,CAP_SETGID,CAP_SETUID|5hostachy_hostachy||no-new-privileges:true|5hostachy_backups:/backups:rw;5hostachy_app_data:/app/data:rw;5hostachy_uploads:/app/uploads:rw;|ALL|true|0745031b851dab52a3d313f97876575431a79e13")"
    t "ligne réelle : le front durci (banc, 01/11)" CONFORME \
      "$(conteneur_verdict "/hostachy_front|false||5hostachy_hostachy||no-new-privileges:true||ALL|true|ca22e76c4d4569d36834e679c4a4ecef130aa16a")"
    t "ligne réelle : le bridge durci (banc, 01/11)" CONFORME \
      "$(conteneur_verdict "/hostachy_whatsapp|false|CAP_CHOWN,CAP_DAC_READ_SEARCH,CAP_SETGID,CAP_SETUID|5hostachy_hostachy||no-new-privileges:true|/etc/localtime:/etc/localtime:ro;5hostachy_whatsapp_auth:/app/auth_state:rw;|ALL|true|")"
    t "ligne réelle : Caddy durci (banc, 01/11)" CONFORME \
      "$(conteneur_verdict "/hostachy_caddy|false|CAP_NET_BIND_SERVICE|5hostachy_hostachy||no-new-privileges:true|/etc/localtime:/etc/localtime:ro;/opt/5hostachy/Caddyfile:/etc/caddy/Caddyfile:ro;5hostachy_caddy_data:/data:rw;5hostachy_caddy_config:/config:rw;5hostachy_caddy_logs:/var/log/caddy:rw;5hostachy_uploads:/srv/uploads:ro;|ALL|true|ca22e76c4d4569d36834e679c4a4ecef130aa16a")"
    t "durci : une ligne d'avant #2368 (sans CapDrop ni racine) n'est pas lue conforme" INCONNU \
      "$(conteneur_verdict "/hostachy_api|false|||n||||r" | cut -d: -f1)"
    t "non durci déclaré (PostgreSQL, #2429) : la règle d'avant" CONFORME \
      "$(conteneur_verdict "/hostachy_postgres|false||n|||5hostachy_pg_data:/var/lib/postgresql/data:rw;||false|r")"
    t "non durci : une capacité ajoutée reste un écart" "ECART:capacités=[SYS_ADMIN];" \
      "$(conteneur_verdict "/hostachy_postgres|false|SYS_ADMIN|n|||||false|r")"
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
    #  Les montages de hostachy_api au premier audit (30/10/2026) : ses volumes
    #  nommés ne sont pas des montages de l'hôte.
    t "volumes nommés de l'API (production, 30/10)" CONFORME \
      "$(conteneur_verdict "/x|false|||5hostachy_default||5hostachy_app_data:/app/data:rw;5hostachy_uploads:/app/uploads:rw;5hostachy_backups:/backups:rw;/etc/localtime:/etc/localtime:ro;|r")"
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
    t "lecture : un tmpfs n'est pas un montage de l'hôte" "/etc/localtime ro" \
      "$(compose_montages_lies $'services:\r\n  a:\r\n    tmpfs:\r\n      - /tmp:size=16m\r\n    volumes:\r\n      - /etc/localtime:/etc/localtime:ro\r\n')"
    #  La lecture du DURCISSEMENT dans un compose (#2368), sur les formes fautives.
    local D=$'x-conteneur-durci: &conteneur_durci\r\n  cap_drop: [ALL]\r\n  security_opt: [no-new-privileges:true]\r\n  read_only: true\r\nservices:\r\n  a:\r\n    container_name: c_a\r\n    <<: *conteneur_durci\r\n    cap_add: [SETUID, CHOWN] # raison\r\n  b:\r\n    image: x\r\n  c:\r\n    <<: *conteneur_durci # sans container_name\r\n    read_only: false\r\n  d:\r\n    <<: *conteneur_durci\r\n    cap_add:\r\n      - CHOWN\r\nvolumes:\r\n  donnees:\r\n'
    t "lecture du durcissement : durci, non, surcharge, cap_add en liste" \
      "c_a durci SETUID,CHOWN|b non |c surcharge-de-l-ancre |d cap_add-illisible(forme-[A,B]-attendue) " \
      "$(compose_durcissement "$D" | paste -sd'|' -)"
    t "ancre entière" "" "$(compose_ancre_manquante "$D")"
    t "ancre amputée de read_only" read_only "$(compose_ancre_manquante "${D/read_only: true/read_only: false}")"
    t "ancre absente" ancre-absente "$(compose_ancre_manquante "services:")"
    t "écarts : chaque forme fautive nommée, dans les deux sens" \
      "c_a : durci par le compose, absent de CONTENEURS_DURCIS|b : ni durci par le compose, ni dans CONTENEURS_NON_DURCIS|c : surcharge-de-l-ancre|d : cap_add-illisible(forme-[A,B]-attendue)|z : déclaré ici, absent du compose" \
      "$(CONTENEURS_DURCIS="z=" CONTENEURS_NON_DURCIS="" durcissement_ecarts "$D" | paste -sd'|' -)"
    t "écarts : capacités qui diffèrent, non durci encore déclaré" \
      "c_a : cap_add du compose [SETUID,CHOWN], CONTENEURS_DURCIS [CHOWN]|c_a : durci par le compose, encore dans CONTENEURS_NON_DURCIS" \
      "$(CONTENEURS_DURCIS="c_a=CHOWN" CONTENEURS_NON_DURCIS="c_a" durcissement_ecarts "${D%%  b:*}" | paste -sd'|' -)"
    t "écarts : rien quand tout concorde" "" \
      "$(CONTENEURS_DURCIS="c_a=CHOWN,SETUID" CONTENEURS_NON_DURCIS="" durcissement_ecarts "${D%%  b:*}")"
    t "écarts : compose illisible" "aucun service lu dans le compose" "$(durcissement_ecarts "")"
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
        #  Le DURCISSEMENT du compose EST celui déclaré ici (#2368), dans les deux
        #  sens ; le cas zéro d'abord — aucun service durci lu, c'est la lecture
        #  qui est cassée, pas un compose conforme.
        local c; c=$(cat "$compose")
        if ! grep -q ' durci ' <<< "$(compose_durcissement "$c")"; then
            echo "FAIL  aucun service durci lu dans $compose — la lecture est cassée, contrôle INCONNU"; st=1
        else
            t "le durcissement du compose est celui de CONTENEURS_DURCIS et CONTENEURS_NON_DURCIS" "" \
              "$(durcissement_ecarts "$c")"
            t "faute injectée : une capacité de plus au compose est vue" "hostachy_caddy : cap_add du compose [NET_BIND_SERVICE,SYS_ADMIN], CONTENEURS_DURCIS [NET_BIND_SERVICE]" \
              "$(durcissement_ecarts "${c/"cap_add: [NET_BIND_SERVICE]"/cap_add: [NET_BIND_SERVICE,SYS_ADMIN]}")"
        fi
    fi
    [ "$st" -eq 0 ] && echo "lib-audit-conteneurs : tous les cas passent."
    return "$st"
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    audit_conteneurs_selftest; exit $?
fi
