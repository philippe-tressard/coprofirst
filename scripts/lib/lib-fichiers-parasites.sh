#!/bin/bash
# =============================================================================
#  lib-fichiers-parasites.sh — C33 et C34 : des copies laissées à côté de l'original
#
#  Deux angles morts de l'audit du 02/10/2026, même famille : des fichiers que
#  personne n'a créés par un script, que personne ne surveille, et qui portent
#  des données sensibles.
#
#  C33 (#1609) — des copies de `.env` à la racine du dépôt déployé.
#    `.env.avant-1109` (600), `.env.avant-120min-20260918` (660, donc lisible du
#    groupe) sur rpi1 ; `.env.avant-120min-20260918` sur rpi2. Des copies de
#    session, avec `SECRET_KEY` et SMTP d'avant deux changements. Git les voit
#    en `??` (`.gitignore` n'ignore que `.env` et `*.env`), et C29 (clés du
#    `.env`) ne lit que `.env` : rien ne les voyait. Liste blanche : `.env` et
#    `.env.example`. Un fichier de moins d'une minute est ignoré : `env_role_appliquer`
#    écrit `.env.tmp.<pid>` puis le renomme, et ce temporaire ne dure qu'un instant.
#
#  C34 (#1592) — des fichiers de base (`*.db*`) dans le volume de données.
#    La base de l'application vit dans PostgreSQL (volume `pg_data`) ; le volume
#    de données de l'API ne porte que l'identité de l'installation et des caches.
#    Tout fichier `*.db*` y est une copie de données personnelles hors de toute
#    règle de rétention, qu'une restauration manuelle pourrait prendre pour la
#    bonne.
#
#  C34 ne lit qu'un RÉPERTOIRE : un conteneur jetable, volume monté en LECTURE
#  SEULE, sans réseau, fait un `ls -1A`. Le volume doit exister avant (`docker
#  volume inspect`) : monter un volume absent le CRÉERAIT, vide, et une liste
#  vide dirait « rien de parasite » sur une mesure qui n'en est pas une.
#
#  WARN au pire, par nœud, qui le nomme. Aucun nettoyage ici : ce module MESURE.
#
#  SOURCÉ (mode 100644) par `lib-collecte.sh` (les fragments `collecte_env_copies`
#  et `collecte_db_volume`, repris dans COLLECT) ; `fichiers_parasites_verdicts` est appelé
#  par `lib-conformite.sh`. ⚠️ Il emploie `ok`, `warn`, `$SELF`, `$PEER`,
#  `$PEER_OK` et les champs S_*/P_* de son appelant.
#  Autotest : bash scripts/lib/lib-fichiers-parasites.sh --selftest
# =============================================================================

#: Les seuls fichiers `.env*` admis à la racine du dépôt déployé. UNE liste : la
#: collecte en tire ses `! -name`, la décision la relit.
ENV_ADMIS="${ENV_ADMIS:-.env .env.example}"
#: Le volume de données de l'API (`app_data` du compose, projet `5hostachy` :
#: l'autotest le vérifie) et l'image du conteneur jetable — l'image de base de
#: l'API (`FROM` de `api/Dockerfile`, l'autotest le vérifie), présente sur les
#: deux nœuds et re-tirée chaque semaine par la maintenance — `--pull=never` :
#: jamais de téléchargement ici.
VOLUME_DONNEES="${VOLUME_DONNEES:-5hostachy_app_data}"
IMAGE_LISTAGE="${IMAGE_LISTAGE:-python:3.12-slim}"
#: Un fichier plus récent que cela (minutes) n'est pas encore une « copie laissée ».
ENV_AGE_MIN_MIN=${ENV_AGE_MIN_MIN:-1}

# ── Les collectes, exécutées sur CHAQUE nœud (reprises par COLLECT) ──────────
#  Même contrainte que `lib-collecte.sh` : chaînes entre guillemets SIMPLES, donc
#  AUCUNE apostrophe dans les fragments, même en commentaire.
#   - env_copies : « ok: » puis « nom:mode » des `.env*` hors liste blanche (le
#     mode en octal, `%m`), séparés par des virgules ; VIDE si le répertoire
#     manque. Le marqueur « ok: » distingue « aucune copie » de « mesure
#     impossible » — cas zéro ;
#   - db_volume : « ok: » puis les noms contenant « .db » du volume ; VIDE si
#     docker manque, si le volume n existe pas ou si le conteneur échoue (délai
#     de 20 s).
collecte_env_copies() { # $1 = la racine du dépôt déployé
    local n excl=''
    for n in $ENV_ADMIS; do excl="$excl ! -name $n"; done
    printf '\nif [ -d %s ]; then\necho "env_copies=ok:$(find %s -maxdepth 1 -type f -name \".env*\" -mmin +%s%s -printf \"%%f:%%m\\n\" 2>/dev/null | LC_ALL=C sort | paste -sd, -)"
else\necho "env_copies="\nfi\n' \
        "$1" "$1" "$ENV_AGE_MIN_MIN" "$excl"
}

collecte_db_volume() {
    printf '%s' '
if command -v docker >/dev/null 2>&1 && docker volume inspect '"$VOLUME_DONNEES"' >/dev/null 2>&1 && _l=$(timeout 20 docker run --rm --network none --pull=never -v '"$VOLUME_DONNEES"':/data:ro '"$IMAGE_LISTAGE"' ls -1A /data 2>/dev/null); then
echo "db_volume=ok:$(printf "%s\n" "$_l" | grep -F .db | paste -sd, -)"
else
echo "db_volume="
fi
'
}

# ── Décisions PURES (aucun effet de bord) ────────────────────────────────────

#  $1 « ok:a:600,b:660 » → « a:600,b:660 » (vide si aucune) ; échoue sans le marqueur.
fp_valeur() { case "${1:-}" in ok:*) printf '%s' "${1#ok:}" ;; *) return 1 ;; esac; }

#  $1 le relevé C33 · → les « nom:mode » qui ne sont pas dans ENV_ADMIS (la
#  décision relit la liste que la collecte a déjà appliquée : un relevé forgé ou
#  une collecte plus ancienne ne fait pas un faux positif sur `.env.example`).
env_copies_utiles() {
    local v e out=''
    v=$(fp_valeur "${1:-}") || return 1
    local IFS=,
    for e in $v; do
        case " $ENV_ADMIS " in *" ${e%:*} "*) continue ;; esac
        out="$out${out:+,}$e"
    done
    printf '%s' "$out"
}

#  → OK | COPIES | INCONNU
verdict_env_copies() {
    local u
    u=$(env_copies_utiles "${1:-}") || { echo INCONNU; return; }
    [ -n "$u" ] && echo COPIES || echo OK
}

#  $1 un mode octal (« 660 ») → « oui » si le groupe ou les autres y accèdent.
mode_ouvert() {
    case "${1:-}" in ''|*[!0-7]*) echo inconnu; return ;; esac
    [ "${#1}" -ge 2 ] || { echo inconnu; return; }
    [ "${1: -2}" = 00 ] && echo non || echo oui
}

#  $1 le relevé → « .env.avant-1109 (600), .env.avant-120min-20260918 (660, lisible hors propriétaire) »
env_copies_decrire() {
    local e out='' note
    local IFS=,
    for e in $(env_copies_utiles "${1:-}"); do
        note="mode ${e##*:}"
        [ "$(mode_ouvert "${e##*:}")" = oui ] && note="$note, lisible hors propriétaire"
        out="$out${out:+, }${e%:*} ($note)"
    done
    printf '%s' "$out"
}

#  $1 le relevé C34 → les fichiers « *.db* » du volume, « a,b » (tous parasites)
db_parasites() { fp_valeur "${1:-}"; }

#  → OK | PARASITES | INCONNU
verdict_db_volume() {
    local u
    u=$(db_parasites "${1:-}") || { echo INCONNU; return; }
    [ -n "$u" ] && echo PARASITES || echo OK
}

# ── C33 et C34, par nœud ─────────────────────────────────────────────────────
fichiers_parasites_verdicts() {
    local n p renv rdb l
    for n in "$SELF" "$PEER"; do
        if [ "$n" = "$SELF" ]; then p=S; else [ "$PEER_OK" -eq 0 ] || continue; p=P; fi
        eval "renv=\${${p}_env_copies:-} rdb=\${${p}_db_volume:-}"
        # ── C33 (#1609) ──
        case "$(verdict_env_copies "$renv")" in
            OK)     ok   "Aucune copie de .env à côté de l'original sur $n (seuls ${ENV_ADMIS// /, } à la racine)" ;;
            COPIES) warn "Copie(s) de .env laissée(s) à la racine du dépôt déployé de $n : $(env_copies_decrire "$renv") — des copies de session portent SECRET_KEY et SMTP d'avant un changement ; git les voit en « ?? » et C29 ne lit que .env : les supprimer après vérification (#1609)" ;;
            *)      warn "Copies de .env sur $n INCONNUES (répertoire illisible : '${renv:-vide}') — ni vert ni rouge" ;;
        esac
        # ── C34 (#1592) ──
        case "$(verdict_db_volume "$rdb")" in
            OK)         ok   "Volume de données de $n : aucun fichier de base" ;;
            PARASITES)  l=$(db_parasites "$rdb")
                        warn "Fichier(s) de base dans le volume de données de $n : ${l//,/, } — des copies de données personnelles, hors de toute rétention, qu'une restauration manuelle pourrait prendre pour la bonne : les retirer après vérification (aucun service ne les ouvre, #1592)" ;;
            *)          warn "Fichiers de base du volume de données de $n INCONNUS (docker, volume ou listage indisponible : '${rdb:-vide}') — ni vert ni rouge" ;;
        esac
    done
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → ${r:-(rien)}" || { echo "FAIL  $1  attendu=${2:-(rien)} obtenu=${r:-(rien)}"; st=1; }; }
    ICI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

    echo "== C33 : la décision =="
    t "rpi1 le 02/10 : trois copies"        COPIES  verdict_env_copies "ok:.env.avant-1109:600,.env.avant-120min-20260918:660"
    t "rpi2 le 02/10 : une copie"           COPIES  verdict_env_copies "ok:.env.avant-120min-20260918:600"
    t "rien à côté de .env (mesuré)"        OK      verdict_env_copies "ok:"
    t ".env.example est admis"              OK      verdict_env_copies "ok:.env.example:644"
    t "relevé vide (répertoire illisible) → INCONNU" INCONNU verdict_env_copies ""
    t "sans marqueur « ok: » → INCONNU, jamais OK"   INCONNU verdict_env_copies ".env.bak:600"
    t ".env.exemple (faute de frappe) n'est PAS admis" COPIES verdict_env_copies "ok:.env.exemple:644"
    t "la liste utile garde les modes"      ".env.a:600,.env.b:660" env_copies_utiles "ok:.env.a:600,.env.example:644,.env.b:660"
    t "description : 600 fermé, 660 lisible du groupe" ".env.avant-1109 (mode 600), .env.avant-120min-20260918 (mode 660, lisible hors propriétaire)" \
      env_copies_decrire "ok:.env.avant-1109:600,.env.avant-120min-20260918:660"
    t "mode 600"  non     mode_ouvert 600
    t "mode 640"  oui     mode_ouvert 640
    t "mode 604"  oui     mode_ouvert 604
    t "mode 400"  non     mode_ouvert 400
    t "mode 644"  oui     mode_ouvert 644
    t "mode illisible" inconnu mode_ouvert "rw-"

    echo "== C33 : la collecte, exécutée pour de bon sur un répertoire témoin =="
    tmp=$(mktemp -d); mkdir "$tmp/depot"
    touch "$tmp/depot/.env"; touch "$tmp/depot/.env.example"; touch "$tmp/depot/README"
    touch "$tmp/depot/.env.avant-1109"; chmod 600 "$tmp/depot/.env.avant-1109"
    touch "$tmp/depot/.env.avant-120min-20260918"; chmod 660 "$tmp/depot/.env.avant-120min-20260918"
    mkdir "$tmp/depot/.env.d"
    for f in .env .env.example README .env.d .env.avant-1109 .env.avant-120min-20260918; do touch -d "10 minutes ago" "$tmp/depot/$f"; done
    touch "$tmp/depot/.env.tmp.4242"          # le temporaire d'env_role_appliquer : trop récent
    env_champ() { bash -c "$(collecte_env_copies "$1")" | sed -n 's/^env_copies=//p'; }
    #  Le mode attendu est RELU par `stat` : sur un disque sans droits unix (poste
    #  Windows), `chmod` ne change rien, et un « 660 » écrit en dur échouerait à tort.
    m1=$(stat -c %a "$tmp/depot/.env.avant-1109"); m2=$(stat -c %a "$tmp/depot/.env.avant-120min-20260918")
    t "collecte : les deux copies, avec leur mode, et rien d'autre" "ok:.env.avant-1109:$m1,.env.avant-120min-20260918:$m2" env_champ "$tmp/depot"
    if [ "$m1:$m2" = "600:660" ]; then echo "PASS  collecte : les modes du ticket (600 et 660) sont rendus tels quels"
    else echo "SKIP  collecte : (chmod sans effet sur ce disque : modes $m1/$m2 relus par stat, pas ceux du ticket)"; fi
    t "collecte : .env, .env.example, un dossier .env.d et le temporaire récent sont ignorés" 0 \
      eval 'env_champ "$tmp/depot" | grep -cE "\.env:|\.env\.example|\.env\.d|tmp"'
    rm "$tmp/depot/.env.avant-1109" "$tmp/depot/.env.avant-120min-20260918"
    t "collecte : plus aucune copie → « ok: » vide (mesuré)" "ok:" env_champ "$tmp/depot"
    t "collecte : répertoire absent → VIDE (INCONNU), jamais « ok: »" "" env_champ "$tmp/absent"
    t "collecte : le fragment est du shell valide" oui eval 'bash -n <<<"$(collecte_env_copies /opt/x)" && echo oui'
    t "collecte : aucune apostrophe dans le fragment" 0 eval 'collecte_env_copies /opt/x | grep -c "$(printf "\047")"'
    t "collecte : un « ! -name » par fichier admis" 2 eval 'collecte_env_copies /opt/x | grep -o "! -name" | wc -l | tr -d " "'
    rm -rf "$tmp"

    echo "== C34 : la décision =="
    t "des copies d'incident"                           PARASITES verdict_db_volume "ok:copie.db,copie.db.corrupt,recuperee.db"
    t "la liste nomme chaque fichier, dans l'ordre" "copie.db.corrupt,recuperee.db,data.db" \
      db_parasites "ok:copie.db.corrupt,recuperee.db,data.db"
    t "un seul fichier de base suffit"                  PARASITES verdict_db_volume "ok:ancienne.db"
    t "aucun fichier de base (mesuré) → OK"             OK       verdict_db_volume "ok:"
    t "relevé vide (docker, volume ou listage) → INCONNU" INCONNU verdict_db_volume ""
    t "sans marqueur « ok: » → INCONNU, jamais OK"      INCONNU  verdict_db_volume "copie.db"

    echo "== C34 : la collecte, exécutée sur un docker simulé =="
    docker() { case "$1" in
        volume) [ "$2" = inspect ] && [ "${VOL_OK:-oui}" = oui ] ;;
        run)    echo "docker run $*" >> "$TRACE"; [ "${RUN_OK:-oui}" = oui ] && printf '%s\n' installation copie.db copie.db.corrupt data.db cache-manuel-pdf ;;
    esac; }
    timeout() { shift; "$@"; }
    TRACE=$(mktemp)
    db_champ() { bash -c "$(declare -f docker timeout); TRACE=$TRACE VOL_OK=${VOL_OK:-oui} RUN_OK=${RUN_OK:-oui}; export TRACE VOL_OK RUN_OK; $(collecte_db_volume)" | sed -n 's/^db_volume=//p'; }
    t "collecte : seuls les noms en « .db » sont relevés" "ok:copie.db,copie.db.corrupt,data.db" db_champ
    t "collecte : le geste est UN listage, sans réseau, en lecture seule, sans téléchargement" 1 \
      eval 'grep -c -- "--network none --pull=never -v 5hostachy_app_data:/data:ro python:3.12-slim ls -1A /data" "$TRACE"'
    t "collecte : aucun fichier ouvert, un listage seulement" 0 eval 'grep -cE "cat |head |/data/[^ ]" "$TRACE"'
    : > "$TRACE"; VOL_OK=non
    t "collecte : volume absent → VIDE, et AUCUN conteneur lancé (il créerait le volume)" "|0" \
      eval 'echo "$(db_champ)|$(grep -c "docker run" "$TRACE")"'
    VOL_OK=oui RUN_OK=non
    t "collecte : le conteneur échoue → VIDE (INCONNU)" "" db_champ
    unset VOL_OK RUN_OK
    docker() { case "$1" in volume) return 0 ;; run) printf '%s\n' installation cache-manuel-pdf ;; esac; }
    t "collecte : volume sans fichier de base → « ok: » vide (mesuré)" "ok:" db_champ
    unset -f docker timeout
    t "collecte : sans docker → VIDE" "db_volume=" eval 'PATH=/nonexistent "$BASH" -c "$(collecte_db_volume)"'
    t "collecte : le fragment est du shell valide" oui eval 'bash -n <<<"$(collecte_db_volume)" && echo oui'
    t "collecte : aucune apostrophe dans le fragment" 0 eval 'collecte_db_volume | grep -c "$(printf "\047")"'
    t "le volume désigné est celui de l'API dans le compose" 1 eval 'grep -cE "^ +- ${VOLUME_DONNEES#5hostachy_}:/app/data$" "$ICI/../../docker-compose.yml"'
    t "l'image du listage est l'image de base de l'API" 1 eval 'grep -cx "FROM $IMAGE_LISTAGE" "$ICI/../../api/Dockerfile"'
    rm -f "$TRACE"

    echo "== les constats, sur les DEUX nœuds =="
    ok()   { echo "OK $*"; }
    warn() { echo "WARN $*"; }
    SELF=rpi1 PEER=rpi2 PEER_OK=0
    S_env_copies="ok:" P_env_copies="ok:" S_db_volume="ok:" P_db_volume="ok:"
    sortie=$(fichiers_parasites_verdicts)
    t "deux nœuds sains → quatre OK, aucun WARN" "4|0" eval 'echo "$(grep -c "^OK" <<< "$sortie")|$(grep -c "^WARN" <<< "$sortie")"'
    #  Les faits du 02/10/2026.
    S_env_copies="ok:.env.avant-1109:600,.env.avant-120min-20260918:660" P_env_copies="ok:.env.avant-120min-20260918:600"
    S_db_volume="ok:copie.db.corrupt,recuperee.db,data.db"
    sortie=$(fichiers_parasites_verdicts)
    t "faute du ticket #1609 : WARN sur rpi1 qui nomme ses deux copies et le mode ouvert" 1 \
      eval 'grep -c "^WARN Copie(s) de .env laissée(s) à la racine du dépôt déployé de rpi1 : .env.avant-1109 (mode 600), .env.avant-120min-20260918 (mode 660, lisible hors propriétaire)" <<< "$sortie"'
    t "…et un WARN distinct sur rpi2" 1 eval 'grep -c "^WARN Copie(s) de .env .* de rpi2 : .env.avant-120min-20260918 (mode 600)" <<< "$sortie"'
    t "faute du ticket #1592 : WARN sur rpi1 qui nomme les trois fichiers" 1 \
      eval 'grep -c "^WARN Fichier(s) de base dans le volume de données de rpi1 : copie.db.corrupt, recuperee.db, data.db" <<< "$sortie"'
    t "…et rpi2, dont le volume est propre, n'a aucun WARN de volume" 0 eval 'grep -c "^WARN .*volume de données de rpi2" <<< "$sortie"'
    S_env_copies="" S_db_volume=""
    sortie=$(fichiers_parasites_verdicts)
    t "rien mesuré sur rpi1 → deux WARN INCONNU, jamais OK" "2|0" \
      eval 'echo "$(grep "^WARN" <<< "$sortie" | grep -c "rpi1.*INCONNU")|$(grep -c "^OK .*rpi1" <<< "$sortie")"'
    PEER_OK=255
    t "pair injoignable : rien sur rpi2" 0 eval 'fichiers_parasites_verdicts | grep -c "rpi2"'
    unset -f ok warn

    [ "$st" -eq 0 ] && echo "lib-fichiers-parasites : tous les cas passent."
    exit "$st"
fi
