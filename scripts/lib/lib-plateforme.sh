#!/bin/bash
# =============================================================================
#  lib-plateforme.sh — la base `plateforme` du registre : ses DÉCISIONS et ses
#  GESTES de création (module à sourcer, #1877, #1972)
#
#  POURQUOI ce module existe (15/10/2026, #1972) : la base du registre se crée à
#  DEUX moments — à l'allumage du registre (`creer-base-plateforme.sh`) et quand
#  la référence renaît de la copie hors site (`restaurer-copie-hors-site.sh`, et
#  son banc). Le second ne peut pas appeler le premier : celui-ci redémarre l'API,
#  qui inscrit aussitôt la référence — et la base n'est plus neuve pour l'import.
#  Les gestes vivent donc ici, une fois : la règle de nommage, la lecture de
#  l'URL, la création du rôle et de la base fermée aux autres.
#
#  Éprouvé par les self-tests de ses deux appelants (même raison que
#  `lib-export-hors-site.sh` : un self-test vide ici rendrait 0 sans rien mesurer).
# =============================================================================

# ── PURE : que faire ? ────────────────────────────────────────────────────────
#  $1 actif (oui|non) · $2 PostgreSQL primaire (oui|non) · $3 utilisateur de l'URL
#  · $4 base de l'URL · $5 mot de passe présent (oui|non) · $6 rôle existe (oui|non)
#  · $7 base existe (oui|non)  →  CREER | DEJA_FAIT | REFUS:<raison>
decider_creation() {
    [ "$1" = oui ] || { echo "REFUS:ce nœud n'est pas l'actif"; return; }
    [ "$2" = oui ] || { echo "REFUS:le PostgreSQL de ce nœud n'est pas le primaire"; return; }
    [ -n "$3" ] && [ -n "$4" ] || { echo "REFUS:PLATEFORME_DATABASE_URL absente ou illisible dans .env"; return; }
    case "$3$4" in *[!a-z0-9_]*) echo "REFUS:utilisateur ou base hors de [a-z0-9_]"; return ;; esac
    [ "$3" != coprofirst ] && [ "$4" != coprofirst ] \
        || { echo "REFUS:la plateforme ne partage ni le rôle ni la base de la résidence"; return; }
    [ "$5" = oui ] || { echo "REFUS:mot de passe absent de PLATEFORME_DATABASE_URL"; return; }
    [ "$6" = oui ] && [ "$7" = oui ] && { echo DEJA_FAIT; return; }
    echo CREER
}

# ── PURE : la copie hors site emporte-t-elle le registre ? (#1972) ────────────
#  $1 le `.env` déclare le registre (oui|non) · $2 une archive du registre est
#  fournie (oui|non)  →  AVEC | SANS | REFUS:<raison>
#  🔴 Registre déclaré SANS son archive : refus. L'API démarrerait, migrerait une
#  base vide et y inscrirait la seule référence — le registre renaîtrait VIDE, en
#  silence, et les installations inscrites seraient perdues.
decider_registre() {
    case "$1$2" in
        ouioui)   echo AVEC ;;
        nonnon)   echo SANS ;;
        ouinon)   echo "REFUS:le .env déclare le registre (PLATEFORME_DATABASE_URL) : fournir son archive par --registre, sinon il renaîtrait vide" ;;
        nonoui)   echo "REFUS:archive du registre fournie, mais PLATEFORME_DATABASE_URL est absente du .env" ;;
        *)        echo "REFUS:arguments non compris" ;;
    esac
}

# ── Lire une partie de l'URL de la base — le mot de passe ne s'affiche jamais ─
#  $1 URL · $2 u (utilisateur) | b (base) | m (mot de passe, décodé) → sur stdout
plateforme_url_partie() {
    python3 -c 'import sys,urllib.parse as u; p=u.urlsplit(sys.argv[1]); print({"u":p.username or "","b":p.path.lstrip("/"),"m":u.unquote(p.password or "")}[sys.argv[2]])' "$1" "$2" 2>/dev/null
}

# ── psql sur le PostgreSQL de la PRODUCTION (en root, sur le nœud qui sert) ───
plateforme_psql_ref() { docker exec -i hostachy_postgres psql -v ON_ERROR_STOP=1 -U coprofirst -d coprofirst "$@"; }

# ── Le rôle et la base existent-ils déjà ? ────────────────────────────────────
#  $1 commande de requête (`pgq` : une ligne, sans en-tête) · $2 utilisateur · $3 base
#  → « oui|non oui|non ». Un nom hors de [a-z0-9_] n'est jamais interpolé dans la
#  requête : il rend « non non », et `decider_creation` le refuse ensuite.
plateforme_existants() {
    local q="$1" util="$2" base="$3" r=non b=non
    case "$util$base" in *[!a-z0-9_]*|'') echo "non non"; return ;; esac
    [ "$("$q" "SELECT 1 FROM pg_roles WHERE rolname='$util'")" = 1 ] && r=oui
    [ "$("$q" "SELECT 1 FROM pg_database WHERE datname='$base'")" = 1 ] && b=oui
    echo "$r $b"
}

# ── Créer le rôle et la base, fermée aux autres rôles ─────────────────────────
#  $1 commande psql (une fonction de l'appelant, qui vise le bon serveur)
#  · $2 utilisateur · $3 base · $4 mot de passe · $5 rôle existe · $6 base existe
#  Les noms ont été validés par `decider_creation` ([a-z0-9_]) ; le mot de passe
#  passe par une variable psql, jamais par la ligne de commande.
#  → 0, ou 1 avec la raison sur la sortie standard.
plateforme_creer() {
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
