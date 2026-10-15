#!/bin/bash
# =============================================================================
#  lib-servir.sh — SERVIR les images sur le nœud actif : l'API d'abord, le reste
#  ensuite, la base seulement démarrée — et le rôle RELU avant chaque geste
#  (module à sourcer ; extrait d'`auto-deploy.sh` le 15/10/2026, #1997 #1999)
#
#  Deux scripts servent des images neuves sur l'actif : `auto-deploy.sh` (la MEP)
#  et `MaJ-Hostachy.sh` (la reprise en main). Le second recréait TOUT par un
#  `up` sans liste — primaire PostgreSQL compris (#1999) — pendant que le
#  premier l'évitait depuis #1872. Le geste s'écrit donc ici, une fois.
#
#  ## L'API d'abord (#1662)
#  `up -d` recréait l'API et le front ensemble : le front repartait pendant que
#  l'API migrait et démarrait, et une lecture tombée dans cette fenêtre a rendu
#  503 à un résident (03/10/2026). On recrée l'API SEULE, on attend son 200 par
#  le chemin des résidents (Caddy → API), PUIS le reste. L'attente est BORNÉE
#  (`API_PRETE_MAX_S`) et ne bloque jamais : une API qui ne répond pas n'est pas
#  réparée en gardant l'ancien front.
#
#  ## La base n'est JAMAIS recréée (#1872)
#  `up -d` recrée un conteneur dont l'image étiquetée a changé, et la
#  maintenance du dimanche re-tire `postgres:<version>`. L'application est
#  recréée par sa liste ; la base n'est que DÉMARRÉE si
#  elle manque (`--no-recreate`). Sa nouvelle image est prise à la bascule.
#
#  ## Le rôle RELU avant chaque démarrage (#1997)
#  Le 15/10/2026, auto-deploy avait lu `.active` au DÉBUT de son passage ; un
#  failover l'a rétrogradé pendant qu'il tirait les images, et il a relancé
#  l'application ET le primaire sur un nœud qui n'était plus l'actif. L'appelant
#  fournit `SERVIR_GARDE`, une fonction appelée avant CHAQUE démarrage : si elle
#  échoue, rien de plus ne démarre et `servir_images` rend 1 — la base, la
#  dernière, ne démarre jamais derrière un rôle qui a changé.
#
#  L'appelant fournit `log` et `$REPO`.
#  Test : bash lib-servir.sh --selftest   (aucun effet de bord)
# =============================================================================

_LIB_SERVIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib-parite.sh
source "$_LIB_SERVIR/lib-parite.sh"         # demarrer_conteneurs — la seule porte du `up`
# shellcheck source=lib-sonde.sh
source "$_LIB_SERVIR/lib-sonde.sh"          # http_code, attendre_200
# shellcheck source=lib-applicatifs.sh
source "$_LIB_SERVIR/lib-applicatifs.sh"    # SERVICES_APPLICATIFS, SERVICE_BASE

API_PRETE_MAX_S=${API_PRETE_MAX_S:-120}

#  $@ : options de `up` pour l'APPLICATION (MaJ-Hostachy : --force-recreate) —
#  jamais pour la base. Rend 0 si tout est servi, 1 si la garde a refusé, 2 si
#  un démarrage a échoué. ⚠️ Appelée derrière `||`, elle ne bénéficie plus de
#  `set -e` : chaque démarrage dit donc son échec lui-même.
servir_images() {
    local garde=${SERVIR_GARDE:-true} r
    "$garde" || return 1
    demarrer_conteneurs "$@" api || return 2
    if r=$(attendre_200 "$API_PRETE_MAX_S" 2 http_code http://localhost/api/health 3); then
        log "API prête en $(echo "$r" | cut -d' ' -f2) s — recréation du reste."
    else
        log "⚠ API sans réponse 200 après $(echo "$r" | cut -d' ' -f2) s (dernier code $(echo "$r" | cut -d' ' -f3), délai ${API_PRETE_MAX_S} s) — le reste est recréé quand même."
    fi
    "$garde" || return 1
    # shellcheck disable=SC2086  # une liste de services, découpée exprès
    demarrer_conteneurs "$@" $SERVICES_APPLICATIFS || return 2
    "$garde" || return 1
    demarrer_conteneurs --no-recreate "$SERVICE_BASE" || return 2
}

# ── Autotest (job CI `test-scripts`) ──────────────────────────────────────────
#  `servir_images` jouée sur un docker, et une sonde SIMULÉS : la trace
#  dit dans quel ordre les gestes ont eu lieu, et lesquels n'ont pas eu lieu.
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    fail=0
    ICI="$_LIB_SERVIR/$(basename "${BASH_SOURCE[0]}")"
    #  $1 libellé · $2 trace attendue · $3 code HTTP de la sonde
    #  $4 la garde (corps de fonction) · $5 options de servir_images
    s() {
        local d r; d=$(mktemp -d)
        r=$(cd "$d" && TR="$d/trace" REPO="$d" bash -c "source '$ICI'
              docker() { echo \"docker \$*\" >> \"\$TR\"; }
              http_code() { echo sonde >> \"\$TR\"; echo $3; }
              log() { echo \"log \$*\" >> \"\$TR\"; }
              sleep() { :; }
              garde() { $4; }
              SERVIR_GARDE=garde API_PRETE_MAX_S=1 servir_images $5 >/dev/null; echo \"rendu \$?\" >> \"\$TR\"
              grep -oE '^(docker compose [u]p -d.*|sonde|log (⛔|⚠ )?API|rendu [0-9])' \"\$TR\" | sed 's/^docker compose [u]p -d/UP/' | uniq | paste -sd'>' -")
        rm -rf "$d"
        if [ "$r" = "$2" ]; then echo "PASS  $1"
        else echo "FAIL  $1"; echo "      attendu=$2"; echo "      obtenu =${r:-rien}"; fail=1; fi
    }
    #  « UP » abrège `docker compose up -d` dans les traces attendues.
    app="UP $SERVICES_APPLICATIFS"
    base="UP --no-recreate $SERVICE_BASE"
    s "API prête : le reste n'est recréé qu'après son 200, la base seulement démarrée" \
      "UP api>sonde>log API>$app>$base>rendu 0" 200 true
    #  🔴 Une API qui ne répond jamais ne bloque pas le déploiement.
    s "API muette : attente bornée, dite, puis le reste" \
      "UP api>sonde>log ⚠ API>$app>$base>rendu 0" 000 true
    #  MaJ-Hostachy --nocache : l'option va à l'application, jamais à la base.
    s "--force-recreate : l'application seulement" \
      "UP --force-recreate api>sonde>log API>UP --force-recreate $SERVICES_APPLICATIFS>$base>rendu 0" \
      200 true --force-recreate
    #  🔴 #1997 : le rôle a changé AVANT le passage — rien ne démarre.
    s "rôle perdu avant de servir : RIEN ne démarre" \
      "rendu 1" 200 false
    #  🔴 #1997 : le failover rétrograde le nœud PENDANT que l'API redémarre —
    #  ni le reste de l'application, ni surtout la base ne repartent derrière.
    s "rôle perdu après l'API : ni le reste, ni la BASE" \
      "UP api>sonde>log API>rendu 1" 200 \
      '! grep -qs "up -d api" "$TR"'
    #  …et perdu juste avant la base : elle ne démarre pas.
    s "rôle perdu avant la base : la base ne démarre pas" \
      "UP api>sonde>log API>$app>rendu 1" 200 \
      '! grep -qs "up -d $SERVICES_APPLICATIFS" "$TR"'
    #  Un démarrage en échec se DIT (2), il ne passe pas pour un rôle perdu (1).
    d=$(mktemp -d)
    r=$(cd "$d" && REPO="$d" bash -c "source '$ICI'
          docker() { [ \"\$4\" = api ] && return 1; return 0; }
          http_code() { echo 200; }; log() { :; }; sleep() { :; }
          servir_images; echo \$?")
    rm -rf "$d"
    if [ "$r" = 2 ]; then echo "PASS  l'API ne démarre pas → 2, et rien d'autre ne démarre"
    else echo "FAIL  démarrage en échec : rendu $r, attendu 2"; fail=1; fi
    #  Aucun `docker compose up` écrit ici : tout passe par `demarrer_conteneurs`.
    n=$(grep -vE '^[[:space:]]*#' "$ICI" | grep -cE '^[[:space:]]*docker compose [u]p' || true)
    if [ "$n" -eq 0 ]; then echo "PASS  aucun up écrit ici : tout passe par la porte de lib-parite"
    else echo "FAIL  $n up écrits directement dans lib-servir.sh"; fail=1; fi
    [ $fail -eq 0 ] && echo "== lib-servir : TOUS OK ==" || echo "== lib-servir : ÉCHECS =="
    exit $fail
fi
