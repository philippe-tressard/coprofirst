#!/usr/bin/env bash
# =============================================================================
#  lib-images-base.sh — les images de base des Dockerfile, et leur re-tirage
#
#  Deux morceaux d'une notion, ensemble pour qu'un changement de l'un casse les
#  épreuves de l'autre :
#    images_de_base             les images que nomment les Dockerfile (PURE) ;
#    rafraichir_images_de_base  le re-tirage hebdomadaire de maintenance.sh
#                               (#1379), qui vivait dans le script, hors de
#                               portée de tout autotest.
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
images_de_base() {
    #  `sub(/\r$/…)` : deux Dockerfile du dépôt sont en CRLF, et l'awk des RPi
    #  garde le `\r` (celui de Git Bash le retire : sur le poste, rien ne se voit).
    awk '
        { sub(/\r$/, "") }
        FNR == 1 { delete etapes }
        toupper($1) == "FROM" {
            i = 2
            while ($i ~ /^--/) i++
            img = $i
            if (img != "" && img != "scratch" && !(img in etapes)) print img
            if (toupper($(i + 1)) == "AS") etapes[$(i + 2)] = 1
        }
    ' "$@" 2>/dev/null | sort -u
}

#  Délai avant la reprise d'un tirage refusé. Une variable pour que l'autotest
#  ne dorme pas : la valeur de production est celle-ci.
IMAGES_BASE_REPRISE_S=${IMAGES_BASE_REPRISE_S:-30}

# ── Les images de base : les correctifs publiés sous une étiquette (#1379) ────
#  `docker compose build` ne re-télécharge JAMAIS une image déjà présente, et
#  Dependabot ne change que l'étiquette : le 27/09/2026, `python:3.12-slim` avait
#  deux mois et `caddy:2` quatre. Les tirer le dimanche, sur les deux nœuds. Une
#  image renouvelée voit l'ancienne retirée quand plus rien ne s'en sert — sinon
#  chaque semaine en laisserait une ; une image ABSENTE est tirée et comptée
#  renouvelée (#1826).
#  Un échec n'est PAS silencieux : il met la maintenance en erreur, parce qu'un
#  nœud qui ne reçoit plus ses correctifs est l'écart même que #1377 a coûté.
rafraichir_images_de_base() { # $@ = les Dockerfile
    local img avant apres err tiree tirees=0 total=0 echecs=""
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
                [ -z "$avant" ] || docker image rm "$avant" >/dev/null 2>&1 || true
            fi
        else
            echecs="${echecs:+$echecs }$img"
        fi
    done
    log "  → $total image(s) de base, $tirees renouvelée(s)${echecs:+, ÉCHEC : $echecs}"
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

    echo "== rafraichir_images_de_base : un docker simulé, sous set -euo pipefail =="
    #  Le docker simulé lit son état dans $tmp/etat : une ligne « image id »
    #  par image présente ; `pull` pose l'identifiant de $tmp/registre, ou
    #  échoue si l'image y est absente. Exécuté dans un `bash` ENFANT sous
    #  `set -euo pipefail`, comme maintenance.sh : c'est la condition de #1826.
    cat > "$tmp/essai.sh" <<'ESSAI'
set -euo pipefail
. "$1"
ETAT=$2; REGISTRE=$3
log() { echo "LOG $*"; }
docker() {
    case "$1 $2" in
        "image inspect") awk -v i="$5" '$1 == i { print $2; t = 1 } END { exit !t }' "$ETAT" ;;
        "image rm")      echo "RM $3" >> "$ETAT.rm" ;;   # la fonction tait sa sortie
        "pull -q")       local id; id=$(awk -v i="$3" '$1 == i { print $2 }' "$REGISTRE")
                         [ -n "$id" ] || return 1
                         { grep -v "^$3 " "$ETAT" || true; echo "$3 $id"; } > "$ETAT.n"; mv "$ETAT.n" "$ETAT" ;;
    esac
}
GLOBAL_STATUT=succes GLOBAL_ERREUR="" IMAGES_BASE_REPRISE_S=0
rafraichir_images_de_base "${@:4}"
echo "FIN statut=$GLOBAL_STATUT bases=$HYG_BASES erreur=$GLOBAL_ERREUR"
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

    rm -rf "$tmp"
    [ "$st" -eq 0 ] && echo "lib-images-base : tous les cas passent."
    exit "$st"
fi
