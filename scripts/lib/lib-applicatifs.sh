#!/bin/bash
# =============================================================================
#  lib-applicatifs.sh — Les conteneurs de L'APPLICATION, la base mise à part
#  (module à sourcer, DI-7b, #1781)
#
#  POURQUOI ce module existe :
#    « Le standby ne fait tourner aucun conteneur » était écrit neuf fois, par
#    `docker ps -q --filter name=hostachy | wc -l` : le split-brain des contrôles,
#    l'actif que le pré-check déduit, la garde au démarrage, la bascule, et les
#    scripts qui refusent de tourner ailleurs que sur le standby. Sous PostgreSQL
#    (DI-7, D16), une RÉPLIQUE de la base tourne en permanence sur le standby :
#    ces neuf comptes y verraient un conteneur, donc un split-brain sans fin, et
#    chaque `docker compose stop` sans liste arrêterait la réplique.
#
#    Ce qui ne tourne QUE sur l'actif, c'est l'application. Elle se nomme ici,
#    une fois ; la base (`hostachy_postgres`) n'en est pas.
#
#  Ce module ne contient que des DÉCLARATIONS et une fonction pure de filtrage :
#  ni SSH, ni écriture. `compter_applicatifs` lit `docker ps`, rien d'autre.
#
#  Usage :
#    source "$REPO/scripts/lib/lib-applicatifs.sh"
#    n=$(compter_applicatifs)                               # en local
#    n=$($SSH_CMD "$PAIR" "$COMPTER_APPLICATIFS")           # chez le pair
#    docker compose stop $SERVICES_APPLICATIFS              # sans la base
#
#  🔒 `api/tests/test_applicatifs_source_unique.py` : ces listes suivent
#  `docker-compose.yml`, et aucun script ne recompte « tout hostachy ».
#
#  Test : bash lib-applicatifs.sh --selftest   (aucun effet de bord)
# =============================================================================

#: Les services Compose de l'application — pour `docker compose stop|up`.
SERVICES_APPLICATIFS="api front caddy whatsapp-bridge"

#: Leurs conteneurs, au même rang (`container_name` de docker-compose.yml).
CONTENEURS_APPLICATIFS="hostachy_api hostachy_front hostachy_caddy hostachy_whatsapp"

#: La base : le seul service qui n'est pas de l'application (profil `postgresql`).
SERVICE_BASE="postgres"

# ── PURE : les services que CE nœud fait tourner quand il sert ────────────────
#  $1 = oui si la base PostgreSQL est gérée ici (`base_postgresql_activee`).
#  🔴 Un `docker compose up|stop` s'écrit TOUJOURS avec sa liste (#1997, #1999) :
#  sans elle, la base est démarrée ou arrêtée par un geste qui ne la nommait pas
#  — c'est ainsi qu'un déploiement a relancé un primaire sur un nœud rétrogradé.
#  Nommer la base quand son profil est éteint l'allumerait (Compose active le
#  profil d'un service visé) : d'où l'argument, jamais un `postgres` en dur.
services_du_noeud() {
    if [ "${1:-}" = oui ]; then echo "$SERVICES_APPLICATIFS $SERVICE_BASE"
    else echo "$SERVICES_APPLICATIFS"; fi
}

#: Le motif d'un nom de conteneur applicatif — ligne entière (`grep -x`).
MOTIF_APPLICATIFS="$(printf '%s' "$CONTENEURS_APPLICATIFS" | tr ' ' '|')"

#: La commande qui compte les conteneurs applicatifs EN MARCHE, telle quelle :
#: exécutable en local (`eval`) comme chez le pair par SSH. Rend toujours un
#: nombre et le code 0 (`grep -c` rend 1 sur zéro ligne).
COMPTER_APPLICATIFS="docker ps --format '{{.Names}}' 2>/dev/null | grep -cxE '$MOTIF_APPLICATIFS' || true"

# ── PURE : des noms de conteneurs (un par ligne, sur l'entrée) → leur nombre ──
compter_applicatifs_dans() {
    grep -cxE "$MOTIF_APPLICATIFS" || true
}

compter_applicatifs() {
    docker ps --format '{{.Names}}' 2>/dev/null | compter_applicatifs_dans
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    cas() {  # $1 libellé, $2 noms (\n), $3 attendu
        local got
        got=$(printf '%b' "$2" | compter_applicatifs_dans)
        if [ "$got" = "$3" ]; then echo "PASS  $1 → $got"; else echo "FAIL  $1 → $got (attendu $3)"; st=1; fi
    }
    cas "aucun conteneur"                       ""                                                              0
    cas "les quatre de l'application"           "hostachy_api\nhostachy_front\nhostachy_caddy\nhostachy_whatsapp" 4
    cas "la réplique seule (standby, DI-7)"     "hostachy_postgres"                                             0
    cas "l'actif et sa base"                    "hostachy_api\nhostachy_postgres\nhostachy_caddy"               2
    cas "un voisin de la machine (List-dons)"   "listdons_app\nhostachy_api"                                    1
    cas "un nom qui ne fait que commencer pareil" "hostachy_api_essai\nhostachy_apiv2"                          0
    got=$(services_du_noeud oui)
    if [ "$got" = "$SERVICES_APPLICATIFS $SERVICE_BASE" ]; then echo "PASS  base gérée ici → l'application et la base"; else echo "FAIL  services_du_noeud oui → $got"; st=1; fi
    got=$(services_du_noeud non)
    if [ "$got" = "$SERVICES_APPLICATIFS" ]; then echo "PASS  base non gérée → l'application seule"; else echo "FAIL  services_du_noeud non → $got"; st=1; fi
    got=$(services_du_noeud "")
    if [ "$got" = "$SERVICES_APPLICATIFS" ]; then echo "PASS  rien lu → jamais la base"; else echo "FAIL  services_du_noeud '' → $got"; st=1; fi
    #  La commande envoyée au pair compte comme la fonction : on l'EXÉCUTE, avec
    #  un `docker` simulé — lire son texte ne dirait pas ce qu'elle rend.
    docker() { printf 'hostachy_api
hostachy_postgres
listdons_app
hostachy_caddy
'; }
    got=$(eval "$COMPTER_APPLICATIFS")
    if [ "$got" = 2 ]; then echo "PASS  COMPTER_APPLICATIFS exécutée → 2"; else echo "FAIL  COMPTER_APPLICATIFS exécutée → $got (attendu 2)"; st=1; fi
    docker() { :; }
    got=$(eval "$COMPTER_APPLICATIFS"); code=$?
    if [ "$got" = 0 ] && [ "$code" = 0 ]; then echo "PASS  rien ne tourne → 0, code 0"; else echo "FAIL  rien ne tourne → '$got' code $code"; st=1; fi
    unset -f docker
    [ "$st" -eq 0 ] && echo "lib-applicatifs : tous les cas passent."
    exit "$st"
fi
