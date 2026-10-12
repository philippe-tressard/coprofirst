#!/usr/bin/env bash
# =============================================================================
#  lib-images-base.sh — les images de base des Dockerfile et du compose, et leur re-tirage
#
#  Deux morceaux d'une notion, ensemble pour qu'un changement de l'un casse les
#  épreuves de l'autre :
#    images_de_base             les images que nomment les Dockerfile et les
#                               services NON construits du compose (PURE) ;
#    rafraichir_images_de_base  le re-tirage hebdomadaire de maintenance.sh
#                               (#1379), qui vivait dans le script, hors de
#                               portée de tout autotest.
#
#  🐘 Le compose depuis #1872 (12/10/2026) : `postgres:17.11` est déclaré par
#  `image:`, sans Dockerfile — il n'était re-tiré par rien, et les correctifs
#  Debian republiés sous son étiquette n'arrivaient jamais sur les nœuds.
#  🔴 Tirer n'est PAS redémarrer : le conteneur garde son image jusqu'à sa
#  prochaine recréation normale (la bascule de 02:00) ; la réplique du standby
#  continue de tourner. `auto-deploy.sh` ne recrée pas la base (`--no-recreate`).
#
#  🔴 Né de #1826 (11/10/2026). Le dimanche, sur rpi2 actif, `maintenance.sh`
#  s'est arrêté à « Rafraîchissement des images de base… » sans une ligne de
#  plus : `caddy:2.11` n'était pas sur le nœud, `docker image inspect` rendait 1
#  dans `avant=$(…)`, et `set -e` tuait le script. Depuis #1758 les nœuds TIRENT
#  les images de l'application au lieu de les construire : une image de base
#  absente en local est devenue le cas normal, et non une panne. Elle se tire
#  comme les autres. Le contrôle de 06:00 l'a dit « rapport perdu » — juste,
#  mais le script, lui, n'avait rien dit.
#
#  SOURCÉ (mode 100644) par `maintenance.sh`. `rafraichir_images_de_base` emploie
#  `log`, et écrit HYG_BASES, GLOBAL_STATUT et GLOBAL_ERREUR de son appelant.
#  Autotest : bash scripts/lib/lib-images-base.sh --selftest
# =============================================================================

#  Les images de base nommées par des Dockerfile, une par ligne, sans doublon.
#  Un `FROM` qui désigne une ÉTAPE du même fichier (`FROM builder`) n'est pas une
#  image à télécharger, ni `scratch`. Lues dans les fichiers, jamais recopiées :
#  une liste tenue à la main oublierait la prochaine image.
#  Un fichier `.yml`/`.yaml` est un compose : on y lit `images_de_compose`.
images_de_base() {
    local f dockerfiles=() composes=()
    for f in "$@"; do
        case "$f" in *.yml|*.yaml) composes+=("$f") ;; *) dockerfiles+=("$f") ;; esac
    done
    {
        #  `sub(/\r$/…)` : deux Dockerfile du dépôt sont en CRLF, et l'awk des RPi
        #  garde le `\r` (celui de Git Bash le retire : sur le poste, rien ne se voit).
        [ "${#dockerfiles[@]}" -eq 0 ] || awk '
            { sub(/\r$/, "") }
            FNR == 1 { delete etapes }
            toupper($1) == "FROM" {
                i = 2
                while ($i ~ /^--/) i++
                img = $i
                if (img != "" && img != "scratch" && !(img in etapes)) print img
                if (toupper($(i + 1)) == "AS") etapes[$(i + 2)] = 1
            }
        ' "${dockerfiles[@]}" 2>/dev/null
        [ "${#composes[@]}" -eq 0 ] || images_de_compose "${composes[@]}"
    } | sort -u
}

#  Les images des services d'un compose qui ne se CONSTRUISENT pas (`image:` sans
#  `build:`) — celles d'un service construit arrivent par son Dockerfile. Une
#  étiquette interpolée (`${…}`) ne se tire pas telle quelle : écartée, et
#  `test_images_compose_suivies.py` refuse alors l'image, faute d'être suivie.
#  Indentation du dépôt : services à 2 espaces, leurs clés à 4 — un compose
#  indenté autrement ne rendrait rien, ce que le même test verrait (cas zéro).
images_de_compose() {
    awk '
        function emettre() {
            if (svc && img != "" && !construit && img !~ /\$/) print img
            svc = 0; img = ""; construit = 0
        }
        { sub(/\r$/, "") }
        FNR == 1 { emettre(); dans = 0 }
        /^[^[:space:]#]/ { emettre(); dans = ($0 ~ /^services:[[:space:]]*$/); next }
        dans && /^  [^[:space:]#][^:]*:[[:space:]]*(#.*)?$/ { emettre(); svc = 1; next }
        dans && svc && /^    image:/ { img = $2; gsub(/["\047]/, "", img) }
        dans && svc && /^    build:/ { construit = 1 }
        END { emettre() }
    ' "$@" 2>/dev/null
}

#  Délai avant la reprise d'un tirage refusé. Une variable pour que l'autotest
#  ne dorme pas : la valeur de production est celle-ci.
IMAGES_BASE_REPRISE_S=${IMAGES_BASE_REPRISE_S:-30}

#  Les anciennes images qu'un conteneur emploie encore (postgres, qui tourne sur
#  l'image tirée et non sur une image construite) : `docker image rm` les refuse
#  tant qu'il n'est pas recréé. Notées ici, retirées au passage suivant — sans
#  quoi chaque correctif laisserait ~400 Mo sur la carte SD : `docker image prune`
#  ne voit que les images du projet (étiquette compose), pas l'image officielle.
#  Hors du dépôt, comme `noyau-tente`.
IMAGES_BASE_A_RETIRER="${IMAGES_BASE_A_RETIRER:-/var/lib/hostachy/images-base-a-retirer}"

#  $1 = identifiant d'une ancienne image. Retirée, ou notée si un conteneur s'en
#  sert encore. Jamais une image étiquetée : celle-là sert encore à quelqu'un.
retirer_ancienne_image() {
    local etiquettes
    etiquettes=$(docker image inspect -f '{{len .RepoTags}}' "$1" 2>/dev/null) || return 0  # partie
    [ "$etiquettes" = 0 ] || return 0
    docker image rm "$1" >/dev/null 2>&1 && return 0
    mkdir -p "$(dirname "$IMAGES_BASE_A_RETIRER")" 2>/dev/null || true
    grep -qxF "$1" "$IMAGES_BASE_A_RETIRER" 2>/dev/null \
        || echo "$1" >> "$IMAGES_BASE_A_RETIRER" 2>/dev/null || true
}

#  Rejoue les retraits notés ; garde ceux qu'un conteneur emploie toujours.
retirer_images_en_attente() {
    [ -s "$IMAGES_BASE_A_RETIRER" ] || return 0
    local id notees
    notees=$(cat "$IMAGES_BASE_A_RETIRER" 2>/dev/null) || return 0
    : > "$IMAGES_BASE_A_RETIRER" 2>/dev/null || return 0
    for id in $notees; do retirer_ancienne_image "$id"; done
}

#  Combien d'anciennes images attendent encore leur retrait.
images_en_attente() {
    grep -c . "$IMAGES_BASE_A_RETIRER" 2>/dev/null || true
}

# ── Les images de base : les correctifs publiés sous une étiquette (#1379) ────
#  `docker compose build` ne re-télécharge JAMAIS une image déjà présente, et
#  Dependabot ne change que l'étiquette : le 27/09/2026, `python:3.12-slim` avait
#  deux mois et `caddy:2` quatre. Les tirer le dimanche, sur les deux nœuds. Une
#  image renouvelée voit l'ancienne retirée quand plus rien ne s'en sert — sinon
#  chaque semaine en laisserait une (un conteneur qui l'emploie encore la fait
#  attendre le passage suivant, #1872) ; une image ABSENTE est tirée et comptée
#  renouvelée (#1826).
#  Un échec n'est PAS silencieux : il met la maintenance en erreur, parce qu'un
#  nœud qui ne reçoit plus ses correctifs est l'écart même que #1377 a coûté.
rafraichir_images_de_base() { # $@ = les Dockerfile et le compose
    local img avant apres err tiree tirees=0 total=0 echecs="" attente
    retirer_images_en_attente
    for img in $(images_de_base "$@"); do
        total=$(( total + 1 ))
        #  `|| true` : absente du nœud, l'image n'a pas d'identifiant — c'est
        #  vide, pas une erreur (#1826 : sans lui, `set -e` tuait le script).
        avant=$(docker image inspect -f '{{.Id}}' "$img" 2>/dev/null) || avant=""
        #  Une reprise après 30 s : le 27/09/2026, sur le banc, deux tirages sur
        #  quatre ont échoué puis réussi à la main une minute plus tard.
        #  Transitoire n'est pas absent — mais une erreur rouge chaque dimanche
        #  pour un hoquet du registre apprendrait à ignorer la vraie.
        tiree=oui
        if ! docker pull -q "$img" >/dev/null 2>&1; then
            sleep "$IMAGES_BASE_REPRISE_S"
            err=$(docker pull -q "$img" 2>&1 >/dev/null) \
                || { tiree=non; log "  ⚠ $img : ${err:-tirage refusé}"; }
        fi
        if [ "$tiree" = oui ]; then
            apres=$(docker image inspect -f '{{.Id}}' "$img" 2>/dev/null) || apres=""
            if [ -n "$apres" ] && [ "$avant" != "$apres" ]; then
                tirees=$(( tirees + 1 ))
                [ -z "$avant" ] || retirer_ancienne_image "$avant"
            fi
        else
            echecs="${echecs:+$echecs }$img"
        fi
    done
    attente=$(images_en_attente); [ "${attente:-0}" != 0 ] || attente=""
    log "  → $total image(s) de base, $tirees renouvelée(s)${attente:+, $attente ancienne(s) gardée(s) tant que leur conteneur tourne}${echecs:+, ÉCHEC : $echecs}"
    HYG_BASES="$tirees/$total renouvelée(s)${echecs:+ — échec : $echecs}"
    if [ -n "$echecs" ]; then
        GLOBAL_STATUT="erreur"
        GLOBAL_ERREUR="${GLOBAL_ERREUR:+$GLOBAL_ERREUR | }images de base non tirées : $echecs"
    fi
    return 0
}

# ── Autotest (job CI `test-scripts`) ──────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { if [ "$3" = "$2" ]; then echo "PASS  $1 → ${3:-(rien)}"
          else echo "FAIL  $1  attendu=${2:-(rien)} obtenu=${3:-(rien)}"; st=1; fi; }
    ICI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    tmp=$(mktemp -d)

    echo "== images_de_base : ce que nomment les Dockerfile =="
    printf 'FROM node:22-alpine AS builder\nRUN x\nFROM node:22-alpine AS runner\nCOPY --from=builder /a /b\n' > "$tmp/front"
    printf 'FROM python:3.12-slim\n' > "$tmp/api"
    printf 'FROM --platform=linux/arm64 caddy:2 AS base\nFROM base\nFROM scratch\n' > "$tmp/caddy"
    t "étapes, doublons, --platform et scratch écartés" \
      "caddy:2 node:22-alpine python:3.12-slim" \
      "$(images_de_base "$tmp/front" "$tmp/api" "$tmp/caddy" | paste -sd' ' -)"
    #  Une étape d'un fichier ne masque pas une image du même nom dans un autre.
    printf 'FROM alpine AS python\n' > "$tmp/a"; printf 'FROM python\n' > "$tmp/b"
    t "une étape ne déborde pas sur le fichier suivant" "alpine python" \
      "$(images_de_base "$tmp/a" "$tmp/b" | paste -sd' ' -)"
    t "aucun fichier → rien" "" "$(images_de_base "$tmp/absent")"
    #  🔴 Vécu sur le banc du 27/09/2026 : deux Dockerfile du dépôt sont en CRLF,
    #  le `\r` restait collé au nom, et `docker pull` répondait « invalid
    #  reference format » — deux images sur quatre jamais tirées.
    printf 'FROM python:3.12-slim\r\nRUN x\r\n' > "$tmp/crlf"
    t "Dockerfile en CRLF : nom sans retour chariot (\\r rendu en #)" "python:3.12-slim" \
      "$(images_de_base "$tmp/crlf" | tr '\r' '#')"

    echo "== images_de_base : les services NON construits du compose (#1872) =="
    #  Un service construit (même s'il nomme son image) vient par son Dockerfile ;
    #  une étiquette interpolée ne se tire pas ; une clé d'une autre section que
    #  `services:` n'est pas un service.
    cat > "$tmp/compose.yml" <<'COMPOSE'
services:
  caddy:
    build:
      context: .
    depends_on:
      - api
  api:
    build: ./api
    image: coprofirst-api:local
  postgres:
    image: postgres:17.11
    profiles: ["postgresql"]
  cache:   # un commentaire
    image: 'redis:7.4'  # épinglée
  publie:
    image: "ghcr.io/x/y:${V:-1}"
  sans_image:
    restart: always

volumes:
  pg_data:
    image: piege:1
COMPOSE
    t "compose : image: sans build:, guillemets ôtés, interpolée et hors services écartées" \
      "postgres:17.11 redis:7.4" "$(images_de_base "$tmp/compose.yml" | paste -sd' ' -)"
    t "Dockerfile et compose ensemble, comme maintenance.sh" \
      "postgres:17.11 python:3.12-slim redis:7.4" \
      "$(images_de_base "$tmp/api" "$tmp/compose.yml" | paste -sd' ' -)"
    sed 's/$/\r/' "$tmp/compose.yml" > "$tmp/crlf.yml"
    t "compose en CRLF : même relevé" "postgres:17.11 redis:7.4" \
      "$(images_de_base "$tmp/crlf.yml" | tr '\r' '#' | paste -sd' ' -)"

    echo "== rafraichir_images_de_base : un docker simulé, sous set -euo pipefail =="
    #  Le docker simulé lit son état dans $tmp/etat : une ligne « image id » par
    #  image étiquetée, « - id » pour une ancienne qui a perdu son étiquette ;
    #  $tmp/etat.utilise nomme les identifiants qu'un conteneur emploie (`rm`
    #  les refuse, comme docker). `pull` pose l'identifiant de $tmp/registre et
    #  dés-étiquette l'ancien, ou échoue si l'image y est absente. Exécuté dans
    #  un `bash` ENFANT sous `set -euo pipefail`, comme maintenance.sh : c'est la
    #  condition de #1826.
    cat > "$tmp/essai.sh" <<'ESSAI'
set -euo pipefail
. "$1"
ETAT=$2; REGISTRE=$3; IMAGES_BASE_A_RETIRER=$ETAT.attente
log() { echo "LOG $*"; }
docker() {
    case "$1 $2" in
        "image inspect") awk -v f="$4" -v i="$5" '$1 == i || $2 == i {
                             print (f ~ /RepoTags/ ? ($1 == "-" ? 0 : 1) : $2); t = 1; exit }
                             END { exit !t }' "$ETAT" ;;
        "image rm")      ! grep -qxF "$3" "$ETAT.utilise" 2>/dev/null || return 1
                         { awk -v i="$3" '$2 != i' "$ETAT"; } > "$ETAT.n"; mv "$ETAT.n" "$ETAT"
                         echo "RM $3" >> "$ETAT.rm" ;;   # la fonction tait sa sortie
        "pull -q")       local id; id=$(awk -v i="$3" '$1 == i { print $2 }' "$REGISTRE")
                         [ -n "$id" ] || return 1
                         awk -v i="$3" -v n="$id" '$1 == i && $2 != n { $1 = "-" } $1 != i' "$ETAT" > "$ETAT.n"
                         echo "$3 $id" >> "$ETAT.n"; mv "$ETAT.n" "$ETAT" ;;
    esac
}
GLOBAL_STATUT=succes GLOBAL_ERREUR="" IMAGES_BASE_REPRISE_S=0
rafraichir_images_de_base "${@:4}"
echo "FIN statut=$GLOBAL_STATUT bases=$HYG_BASES erreur=$GLOBAL_ERREUR"
echo "ATTENTE $(paste -sd' ' - < "$ETAT.attente" 2>/dev/null || true)"
cat "$ETAT.rm" 2>/dev/null || true; rm -f "$ETAT.rm"
ESSAI
    printf 'FROM caddy:2.11\n' > "$tmp/df-caddy"
    printf 'FROM python:3.12-slim\n' > "$tmp/df-api"
    printf 'caddy:2.11 sha:c2\npython:3.12-slim sha:p2\n' > "$tmp/registre"
    essai() { bash "$tmp/essai.sh" "$ICI/lib-images-base.sh" "$tmp/etat" "$tmp/registre" "$tmp/df-caddy" "$tmp/df-api" 2>&1; }

    #  Le cas du 11/10/2026 sur rpi2 : caddy absent, python présent et à jour.
    printf 'python:3.12-slim sha:p2\n' > "$tmp/etat"
    sortie=$(essai)
    t "faute du 11/10 : image ABSENTE → le passage va au bout" 1 "$(grep -c '^FIN statut=succes' <<< "$sortie")"
    t "…l'image absente est tirée et comptée renouvelée" 1 "$(grep -c 'bases=1/2 renouvelée(s)' <<< "$sortie")"
    t "…et rien n'est retiré (il n'y avait pas d'ancienne)" 0 "$(grep -c '^RM' <<< "$sortie")"
    #  §46 : sans le `|| avant=""`, la même situation tue le script — c'est donc
    #  bien lui que le cas précédent éprouve.
    sed 's/2>\/dev\/null) || avant=""/2>\/dev\/null)/' "$ICI/lib-images-base.sh" > "$tmp/fautive.sh"
    printf 'python:3.12-slim sha:p2\n' > "$tmp/etat"
    sortie=$(bash "$tmp/essai.sh" "$tmp/fautive.sh" "$tmp/etat" "$tmp/registre" "$tmp/df-caddy" "$tmp/df-api" 2>&1)
    t "faute injectée : inspect nu sous set -e → le script meurt sans FIN" 0 "$(grep -c '^FIN' <<< "$sortie")"

    printf 'caddy:2.11 sha:c1\npython:3.12-slim sha:p2\n' > "$tmp/etat"
    sortie=$(essai)
    t "image renouvelée : comptée, l'ancienne retirée" "1|1" \
      "$(grep -c 'bases=1/2' <<< "$sortie")|$(grep -c '^RM sha:c1' <<< "$sortie")"
    printf 'caddy:2.11 sha:c2\npython:3.12-slim sha:p2\n' > "$tmp/etat"
    t "tout à jour : 0 renouvelée, succès" 1 "$(essai | grep -c 'FIN statut=succes bases=0/2')"
    printf 'python:3.12-slim sha:p2\n' > "$tmp/registre"; printf 'python:3.12-slim sha:p2\n' > "$tmp/etat"
    sortie=$(essai)
    t "tirage refusé : la maintenance passe en erreur, en le nommant" 1 \
      "$(grep -c 'FIN statut=erreur .*images de base non tirées : caddy:2.11' <<< "$sortie")"

    echo "== postgres : une image qu'un conteneur emploie (#1872) =="
    printf 'services:\n  postgres:\n    image: postgres:17.11\n' > "$tmp/df-compose.yml"
    printf 'caddy:2.11 sha:c2\npython:3.12-slim sha:p2\npostgres:17.11 sha:g2\n' > "$tmp/registre"
    printf 'caddy:2.11 sha:c2\npython:3.12-slim sha:p2\npostgres:17.11 sha:g1\n' > "$tmp/etat"
    echo sha:g1 > "$tmp/etat.utilise"; rm -f "$tmp/etat.attente"
    essai_pg() { bash "$tmp/essai.sh" "$ICI/lib-images-base.sh" "$tmp/etat" "$tmp/registre" \
                   "$tmp/df-caddy" "$tmp/df-api" "$tmp/df-compose.yml" 2>&1; }
    sortie=$(essai_pg)
    #  🔴 Le tirage ne touche pas au conteneur : l'ancienne image, qu'il emploie,
    #  reste — notée, et dite au journal.
    t "correctif postgres tiré : compté, l'ancienne gardée et notée" "1|0|ATTENTE sha:g1|1" \
      "$(grep -c 'FIN statut=succes bases=1/3' <<< "$sortie")|$(grep -c '^RM' <<< "$sortie")|$(grep '^ATTENTE' <<< "$sortie")|$(grep -c '1 ancienne(s) gardée(s)' <<< "$sortie")"
    sortie=$(essai_pg)
    t "conteneur pas encore recréé : toujours gardée, notée une fois" "0|ATTENTE sha:g1" \
      "$(grep -c '^RM' <<< "$sortie")|$(grep '^ATTENTE' <<< "$sortie")"
    echo sha:g2 > "$tmp/etat.utilise"      # la bascule a recréé le conteneur
    sortie=$(essai_pg)
    t "conteneur recréé : l'ancienne retirée au passage suivant" "1|ATTENTE |0" \
      "$(grep -c '^RM sha:g1' <<< "$sortie")|$(grep '^ATTENTE' <<< "$sortie")|$(grep -c 'gardée' <<< "$sortie")"
    #  Une notée qui a disparu entre-temps est oubliée ; une notée qui porte de
    #  nouveau une étiquette n'est JAMAIS retirée.
    printf 'sha:zz\nsha:p2\n' > "$tmp/etat.attente"
    sortie=$(essai_pg)
    t "notées disparue ou ré-étiquetée : oubliées, rien retiré" "0|ATTENTE " \
      "$(grep -c '^RM' <<< "$sortie")|$(grep '^ATTENTE' <<< "$sortie")"

    rm -rf "$tmp"
    [ "$st" -eq 0 ] && echo "lib-images-base : tous les cas passent."
    exit "$st"
fi
