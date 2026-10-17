#!/bin/bash
# =============================================================================
#  lib-bases.sh — les gestes communs à TOUTE base PostgreSQL d'une installation
#  (module à sourcer, #2053)
#
#  Une base et un rôle par copropriété (spec multi-copropriétés §4.3), et la base
#  `plateforme` du registre (§4.11) : chacune se crée de la même façon — un rôle
#  qui ne se connecte qu'à SA base, une base fermée aux autres rôles. Ces gestes
#  vivaient dans `scripts/lib/lib-plateforme.sh`, qui ne part pas avec une
#  installation ; ils vivent ici, dans ce que l'archive de déploiement emporte, et
#  `lib-plateforme.sh` les source.
#
#  Lecteurs : `scripts/lib/lib-plateforme.sh` (registre), et par lui
#  `creer-base-plateforme.sh` et `lib-restauration.sh` ;
#  `deploiement/standard/commune/creer-copropriete.sh` (copropriété).
#  Éprouvés par les self-tests de leurs appelants.
# =============================================================================

# ── Lire une partie de l'URL de la base — le mot de passe ne s'affiche jamais ─
#  $1 URL · $2 u (utilisateur) | b (base) | m (mot de passe, décodé) → sur stdout
base_url_partie() {
    python3 -c 'import sys,urllib.parse as u; p=u.urlsplit(sys.argv[1]); print({"u":p.username or "","b":p.path.lstrip("/"),"m":u.unquote(p.password or "")}[sys.argv[2]])' "$1" "$2" 2>/dev/null
}

# ── Le rôle et la base existent-ils déjà ? ────────────────────────────────────
#  $1 commande de requête (`pgq` : une ligne, sans en-tête) · $2 utilisateur · $3 base
#  → « oui|non oui|non ». Un nom hors de [a-z0-9_] n'est jamais interpolé dans la
#  requête : il rend « non non », et l'appelant le refuse ensuite.
base_existants() {
    local q="$1" util="$2" base="$3" r=non b=non
    case "$util$base" in *[!a-z0-9_]*|'') echo "non non"; return ;; esac
    [ "$("$q" "SELECT 1 FROM pg_roles WHERE rolname='$util'")" = 1 ] && r=oui
    [ "$("$q" "SELECT 1 FROM pg_database WHERE datname='$base'")" = 1 ] && b=oui
    echo "$r $b"
}

# ── Créer le rôle et la base, fermée aux autres rôles ─────────────────────────
#  $1 commande psql (une fonction de l'appelant, qui vise le bon serveur)
#  · $2 utilisateur · $3 base · $4 mot de passe · $5 rôle existe · $6 base existe
#  Les noms ont été validés par l'appelant ([a-z0-9_]) ; le mot de passe
#  passe par une variable psql, jamais par la ligne de commande.
#  → 0, ou 1 avec la raison sur la sortie standard.
base_creer() {
    local psql="$1" util="$2" base="$3" mdp="$4"
    if [ "$5" = non ]; then
        printf '%s\n' "CREATE ROLE $util WITH LOGIN PASSWORD :'mdp';" | "$psql" -v mdp="$mdp" >/dev/null \
            || { echo "rôle non créé"; return 1; }
    fi
    if [ "$6" = non ]; then
        "$psql" -c "CREATE DATABASE $base OWNER $util;" >/dev/null || { echo "base non créée"; return 1; }
        "$psql" -c "REVOKE CONNECT ON DATABASE $base FROM PUBLIC;" >/dev/null
    fi
    return 0
}
