#!/bin/bash
# =============================================================================
#  lib-archive-deploiement.sh — L'archive du DÉPLOIEMENT STANDARD d'une version
#  (#1755) : ce qu'elle emporte, et comment elle se fabrique (module à sourcer)
#
#  Deux lecteurs : `notes-de-version.sh` la joint à la release d'une version
#  promue ; `essai-mise-a-jour.sh` en fabrique deux pour éprouver la mise à jour
#  nocturne sans rien promouvoir. Une seule liste, une seule fabrication.
# =============================================================================

# ── Ce que l'archive emporte (le mode d'emploi les cite tous) ─────────────────
#  🔒 test_deploiement_standard.py : chaque fichier du tableau de
#  `deploiement/standard/LISEZMOI.md` figure ici.
FICHIERS_DEPLOIEMENT=(
    docker-compose.yml
    deploiement/standard/compose.images.yml
    Caddyfile
    .env.example
    deploiement/standard/LISEZMOI.md
    deploiement/standard/mise-a-jour.sh
    deploiement/standard/lib-installation.sh
    deploiement/standard/lib-bases.sh
    deploiement/standard/correctifs-systeme.sh
    deploiement/standard/systeme/52coprofirst-correctifs
    deploiement/standard/systeme/apt-daily.timer.conf
    deploiement/standard/systeme/apt-daily-upgrade.timer.conf
    deploiement/standard/systeme/coprofirst-correctifs.service
    deploiement/standard/systeme/coprofirst-correctifs.timer
    #  La décision apt des nœuds de la référence (C30), que `correctifs-systeme.sh`
    #  source : une seule règle pour « ce serveur reçoit-il ses correctifs ? ».
    scripts/lib/lib-apt.sh
    deploiement/demo/reinitialiser.sh
    deploiement/demo/LISEZMOI.md
    deploiement/standard/postgresql/pg_hba.conf
    deploiement/standard/commune/LISEZMOI.md
    deploiement/standard/commune/coproprietes.exemple.json
    deploiement/standard/commune/garde-des-pages.caddy
    deploiement/standard/commune/fichiers.caddy
    deploiement/standard/commune/compose.commune.yml
    deploiement/standard/commune/creer-copropriete.sh
    LICENSE
)

#  $1 commit · $2 version · $3 dossier de sortie → chemin de l'archive
archiver_deploiement() {
    local sortie="$3/coprofirst-deploiement-$2.tar.gz" f
    #  `git archive` ne refuse pas un chemin absent du commit : il l'omet.
    for f in "${FICHIERS_DEPLOIEMENT[@]}"; do
        git cat-file -e "$1:$f" 2>/dev/null || { echo "::error::$f absent de $1" >&2; return 1; }
    done
    git archive --format=tar.gz --prefix="coprofirst-$2/" -o "$sortie" "$1" -- "${FICHIERS_DEPLOIEMENT[@]}"
    echo "$sortie"
}
