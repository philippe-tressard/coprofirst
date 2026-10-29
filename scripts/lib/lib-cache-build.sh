#!/bin/bash
# =============================================================================
#  lib-cache-build.sh — Borner le cache de build Docker, et DIRE ce qu'on a
#  mesuré (#1524, 01/10/2026)
#
#  Module SOURCÉ par `auto-deploy.sh` (après chaque construction) et par
#  `maintenance.sh` (chaque dimanche) : la seule écriture de la purge, de son
#  plafond et de ses âges. Pas de bit x (`lib-*.sh` sont en 100644).
#
#  ## Ce qui ne marchait pas
#
#  Le 01/10/2026, rpi1 portait 40 Go de cache — et `auto-deploy` écrivait toutes
#  les cinq minutes « Cache de build ramené sous 10 Go. ». Une purge complète a
#  libéré 37 Go RÉELS (disque de 50 à 13 Go). Mesuré sur le nœud, Docker 29 avec
#  le stockage d'images containerd (`io.containerd.snapshotter.v1`) :
#
#  | Commande                                   | Ce qu'elle retire                    |
#  |--------------------------------------------|--------------------------------------|
#  | `prune --keep-storage` / `--max-used-space`| la seule part « récupérable »        |
#  | `prune --filter until=…` SANS `-a`         | idem                                 |
#  | `prune -a --filter until=…`                | aussi la part PARTAGÉE avec les images |
#
#  La part partagée — des instantanés communs au cache et aux images, que
#  `docker system df` ne compte pas comme récupérables — était de 30 Go sur 40.
#  Aucune des deux purges n'avait `-a` : elles n'y ont jamais touché, et le
#  plafond se calcule sur ce qu'elles voient, pas sur le disque.
#
#  ## Le remède
#
#  1. `-a` sur les deux passes. Par ÂGE d'abord : `until` porte sur la DERNIÈRE
#     UTILISATION d'une entrée, et le build qui vient de finir a touché tout ce
#     qu'il a réutilisé — après une construction, une fenêtre courte n'évince
#     donc que ce que plus rien n'emploie. Le prochain build reste rapide, et
#     `npm run build` n'est pas rejoué (risque d'OOM sur le RPi).
#  2. Le plafond ensuite, en garde-fou de la part récupérable.
#  3. La taille est MESURÉE avant et après, et c'est elle qu'on écrit. L'ancienne
#     ligne était posée sur le code de retour de docker : elle annonçait un
#     résultat qu'elle n'avait pas regardé (`standards/04`, observer la chose).
#
#  ⚠️ Le cache BuildKit est commun au daemon : rpi2 y porte aussi List-dons, et
#  `builder prune` n'a aucun filtre par projet. Ses couches inutilisées depuis
#  plus de `BUILD_CACHE_APRES_BUILD_H` partent avec les nôtres — son prochain
#  build est plus lent, jamais faux.
#
#  Test : bash scripts/lib/lib-cache-build.sh --selftest
# =============================================================================

#  `cache_go` (« 64.68GB » → 64) vit dans lib-verdicts.sh, qui le prête aussi à C16.
#  shellcheck source=lib-verdicts.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib-verdicts.sh"

#  Plafond de la part récupérable : les couches les plus récemment employées
#  sont gardées. Ne pas descendre trop bas — la bascule nocturne reconstruit
#  l'image du peer et compte sur ce cache.
BUILD_CACHE_KEEP=10737418240        # 10 Go
BUILD_CACHE_MAX_AGE_H=168           # dimanche : 7 j, périmé pour tous les projets
BUILD_CACHE_APRES_BUILD_H=24        # après un build : ce que celui-ci n'a pas réutilisé

# ── La mesure, telle que `docker system df` la rend : « 11.2GB|10.54GB » ──────
#  La taille, puis sa part récupérable. Vide si docker ne répond pas : le bilan
#  le dira INCONNU, jamais OK.
cache_build_mesure() {
    docker system df --format "{{.Type}}|{{.Size}}|{{.Reclaimable}}" 2>/dev/null \
        | grep -i "^Build Cache" | cut -d"|" -f2,3 | tr -d " " || true
}

# ── Le bilan d'une purge (PURE — testable) ───────────────────────────────────
#  $1 taille avant · $2 taille après · $3 part récupérable après · $4 âge (h)
#  · $5 passes refusées par docker (vide si aucune)
#  Une ligne, préfixée de « ⚠ » dès que la purge n'a pas prouvé son effet.
#
#  Le plafond se juge sur CHAQUE part, jamais sur le total. Le total mélange ce
#  que le plafond borne (la part récupérable) et ce que seule la purge par âge
#  atteint (la part partagée avec les images, #1524) : sur rpi2, le 01/10/2026,
#  11,2 Go dont 10,54 récupérables et 0,66 partagés, tout servi dans les 24 h —
#  comparé au total, le bilan criait au dépassement à chaque build.
#  - part récupérable au-dessus du plafond : le plafonnement n'a pas pris ;
#  - part partagée au-dessus du plafond : c'est le défaut de #1524 (30 Go).
cache_build_bilan() {
    local avant="$1" apres="$2" recup="$3" age="$4" refus="${5:-}" plafond_go go rgo
    #  `docker system df` parle en Go DÉCIMAUX, le plafond est en octets (10 Gio,
    #  soit 10,74 Go). `cache_go` tronque, d'où les comparaisons strictes.
    plafond_go=$(( BUILD_CACHE_KEEP / 1000000000 ))
    go=$(cache_go "$apres")
    rgo=$(cache_go "$recup")
    if [ "$go" -lt 0 ] || [ "$rgo" -lt 0 ]; then
        echo "⚠ Cache de build : mesure illisible après purge (${apres:-?}, récupérable ${recup:-?}) — effet INCONNU."
    elif [ -n "$refus" ]; then
        echo "⚠ Cache de build : purge $refus refusée par docker — ${avant:-?} → $apres."
    elif [ "$rgo" -gt "$plafond_go" ]; then
        echo "⚠ Cache de build : ${avant:-?} → $apres, dont $recup récupérables — au-dessus du plafond de ${plafond_go} Go."
    elif [ $(( go - rgo )) -gt "$plafond_go" ]; then
        echo "⚠ Cache de build : ${avant:-?} → $apres, dont $(( go - rgo )) Go partagés avec les images — la purge ne les atteint pas (#1524)."
    else
        echo "Cache de build : ${avant:-?} → $apres (inutilisé depuis plus de ${age} h retiré, plafond ${plafond_go} Go)."
    fi
}

# ── La purge : par âge, puis au plafond, toutes deux avec `-a` ───────────────
#  $1 = âge maximal en heures. Écrit le bilan mesuré sur la sortie standard.
cache_build_borner() {
    local age="$1" avant apres refus=""
    avant=$(cache_build_mesure)
    docker builder prune -af --filter "until=${age}h" >/dev/null 2>&1 \
        || refus="par âge"
    docker builder prune -af --max-used-space "$BUILD_CACHE_KEEP" >/dev/null 2>&1 \
        || refus="${refus:+$refus et }au plafond"
    apres=$(cache_build_mesure)
    cache_build_bilan "${avant%%|*}" "${apres%%|*}" "${apres#*|}" "$age" "$refus"
}

# ── Self-test ────────────────────────────────────────────────────────────────
#  Gardé par BASH_SOURCE : un script qui SOURCE ce module en ayant reçu
#  `--selftest` ne doit pas exécuter celui-ci (`lib-parite.sh`, #511).
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    fail=0
    attendu() {  # $1 libellé · $2 motif attendu · $3… arguments du bilan
        local lib="$1" motif="$2" got; shift 2
        got=$(cache_build_bilan "$@")
        if grep -qE "$motif" <<<"$got"; then
            echo "PASS  $lib"
        else
            echo "FAIL  $lib — « $got »"; fail=1
        fi
    }
    echo "== self-test : bilan de la purge du cache de build =="
    attendu "sous le plafond → bilan sans alerte"      '^Cache de build : 40.02GB → 1.2GB'  40.02GB 1.2GB 900MB 24 ""
    attendu "sous le gigaoctet → bilan sans alerte"   '^Cache de build : '                  2GB 980MB 500MB 24 ""
    #  rpi1, 01/10/2026 : la purge sans `-a` ne bouge rien, 30 Go partagés.
    #  L'ancienne ligne disait « ramené sous 10 Go » ; celle-ci doit le refuser.
    attendu "part partagée hors d'atteinte (#1524)"   '^⚠ .*30 Go partagés'                 40.02GB 40.02GB 10.62GB 24 ""
    #  rpi2, 01/10/2026 : 11,2 Go dont 10,54 récupérables, tout servi dans les
    #  24 h. Comparé au total, le bilan criait au dépassement à chaque build.
    attendu "rpi2 du 01/10 : chaque part sous le plafond" '^Cache de build : 11.44GB → 11.2GB' 11.44GB 11.2GB 10.54GB 24 ""
    attendu "part récupérable au-dessus → alerte"     '^⚠ .*récupérables — au-dessus'       14GB 13GB 12.5GB 24 ""
    attendu "taille illisible → INCONNU, jamais OK"   '^⚠ .*INCONNU'                        40GB "" "" 24 ""
    attendu "récupérable illisible → INCONNU"         '^⚠ .*INCONNU'                        40GB 2GB "" 24 ""
    attendu "passe refusée par docker → dite"         '^⚠ .*par âge refusée'                3GB 2GB 1GB 24 "par âge"
    attendu "avant illisible, après mesuré → ?"       '^Cache de build : \? → '             "" 1GB 500MB 168 ""

    echo "== self-test : la purge garde -a sur ses deux passes =="
    #  Sans `-a`, la part partagée avec les images n'est jamais retirée : c'est
    #  le défaut de #1524. On lit la fonction elle-même, pas une copie.
    corps=$(declare -f cache_build_borner)
    n_prune=$(printf '%s\n' "$corps" | grep -c 'builder prune' || true)
    n_tout=$(printf '%s\n' "$corps" | grep -cE 'builder prune -a|builder prune [^|]*--all' || true)
    if [ "$n_prune" -ge 2 ] && [ "$n_prune" -eq "$n_tout" ]; then
        echo "PASS  ${n_prune} passes, toutes avec -a"
    else
        echo "FAIL  ${n_tout} passe(s) avec -a sur ${n_prune}"; fail=1
    fi

    [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $fail
fi
