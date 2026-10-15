#!/bin/bash
# =============================================================================
#  mise-a-jour.sh — La mise à jour nocturne d'une réplique CoproFirst,
#  réversible seule (#1756, 08/10/2026)
#
#  Lot DI-4 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
#  §4.10, règles 6, 7 et 12 ; D14, D15). Lancé chaque nuit par le cron de
#  l'installation (mode d'emploi : `deploiement/standard/LISEZMOI.md`).
#
#  ## Le déroulé — rien ne s'arrête tant que tout n'est pas prêt
#
#   1. la version à installer : celle de la branche `replica` du dépôt public ;
#   2. décider (fonction PURE `decider_cible`) : à jour, épinglée, trop tôt
#      (échelonnement), version illisible, ou mettre à jour ;
#   3. télécharger l'archive de déploiement de la version, tirer ses images,
#      vérifier leur signature — le service tourne toujours ;
#   4. arrêter l'API, SAUVEGARDER les volumes dans `COPROFIRST_SAUVEGARDES`
#      (fichiers, identité de l'installation) et la base PostgreSQL par un
#      EXPORT (`export_copropriete exporter`), réimporté dans une base jetable
#      pour être déclaré bon (`… verifier`) ;
#   5. poser les fichiers et la version, `up -d` (l'API migre en démarrant) ;
#   6. sonder `/api/health` ;
#   7. en échec : revenir aux fichiers et à l'image précédents (la base migrée
#      se sert sans migrer, `api/app/utils/revision_base.py`) ; si la santé
#      reste KO, RESTAURER la sauvegarde (fonction PURE `decider_issue`) — les
#      volumes, puis la base : schéma vidé, schéma initial de la version
#      précédente, import de l'export.
#   8. rendre compte : journal, et `POST /admin/maintenance/rapport` (tâche
#      `mise_a_jour`) — le contrôle de 06:00 en fait un courriel s'il a échoué.
#
#  🔴 Une réplique tient sur UN serveur (D15) : pas de standby, pas de bascule.
#  Le retour arrière et la sauvegarde hors de la machine sont tout son filet.
#
#  Réglages lus dans `.env` : COPROFIRST_VERSION (la version installée),
#  COPROFIRST_SAUVEGARDES (dossier OBLIGATOIRE, de préférence monté hors de
#  la machine), COPROFIRST_EPINGLEE=oui (ne pas suivre), COPROFIRST_DELAI_JOURS
#  (0 pour l'installation pilote, 1 par défaut), COPROFIRST_SIGNATURE
#  (`exigee` ou `si-possible`, défaut), MAINTENANCE_KEY (pour rendre compte).
#
#  ESSAI, jamais en service (lus dans l'ENVIRONNEMENT, pas dans `.env`) :
#  COPROFIRST_ESSAI_CIBLE=X.Y.Z installe cette version au lieu de celle de
#  `replica`, sans délai ; COPROFIRST_ESSAI_ARCHIVE=<fichier> prend l'archive de
#  déploiement sur le disque au lieu de la release. C'est ainsi que
#  `scripts/ci/essai-mise-a-jour.sh` éprouve tout le déroulé, de bout en bout,
#  sans rien promouvoir.
#
#  Test : bash deploiement/standard/mise-a-jour.sh --selftest
# =============================================================================
set -euo pipefail

DEPOT="philippe-tressard/coprofirst"
REGISTRE="ghcr.io/philippe-tressard"
SERVICES="api front caddy whatsapp-bridge"
SANTE_MAX_S=180

#  Les gestes communs d'une installation (`lib-installation.sh`, #1905) : à côté de
#  ce script dans le dépôt et dans l'archive ; depuis la copie de /tmp (plus bas),
#  dans le dossier de l'installation qu'elle reçoit en argument.
if [ -n "${MAJ_COPIE:-}" ]; then
    . "${1:?dossier manquant}/deploiement/standard/lib-installation.sh"
else
    . "$(dirname "$0")/lib-installation.sh"
fi

# ── Décisions PURES ───────────────────────────────────────────────────────────

#  $1 a ≤ $2 b, en versions X.Y.Z (comparaison numérique, pas alphabétique)
version_au_plus() {
    [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -1)" = "$1" ]
}

#  $1 courante · $2 cible · $3 épinglée (oui|…) · $4 âge de la promotion en
#  jours (vide : inconnu) · $5 délai d'échelonnement en jours
#  → a-jour | epinglee | inconnue | retrograde | attendre | mettre-a-jour
decider_cible() {
    local courante="$1" cible="$2" epinglee="$3" age="$4" delai="${5:-1}"
    local motif='^[0-9]+\.[0-9]+\.[0-9]+$'
    if ! [[ "$cible" =~ $motif ]]; then echo inconnue; return; fi
    if [ "$epinglee" = oui ]; then echo epinglee; return; fi
    if [ "$cible" = "$courante" ]; then echo a-jour; return; fi
    #  `replica` n'avance qu'en avant (#1754) : une cible plus ancienne est une
    #  anomalie, pas un ordre de retour arrière.
    if [[ "$courante" =~ $motif ]] && version_au_plus "$cible" "$courante"; then echo retrograde; return; fi
    case "$age" in ''|*[!0-9]*) age=0 ;; esac
    if [ "$age" -lt "$delai" ]; then echo attendre; return; fi
    echo mettre-a-jour
}

#  `moteur_de_url` vit dans `lib-installation.sh` (copie déclarée de la référence).

#  $1 santé après la mise à jour (ok|ko) · $2 santé après le retour à l'image
#  précédente (ok|ko|vide si non tenté) → reussie | revenir | revenue | restaurer
decider_issue() {
    if [ "$1" = ok ]; then echo reussie; return; fi
    case "${2:-}" in
        '') echo revenir ;;
        ok) echo revenue ;;
        *)  echo restaurer ;;
    esac
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    attendu() {  # $1 libellé · $2 attendu · $3 fonction · $4… arguments
        local lib="$1" voulu="$2" f="$3" got; shift 3
        got=$("$f" "$@")
        if [ "$got" = "$voulu" ]; then echo "PASS  $lib"; else echo "FAIL  $lib — « $got »"; fail=1; fi
    }
    echo "== self-test : quelle version installer =="
    attendu "même version → à jour"                     a-jour        decider_cible 2.120.0 2.120.0 non 5 1
    attendu "épinglée → ne suit pas"                    epinglee      decider_cible 2.120.0 2.121.0 oui 5 1
    attendu "cible illisible → inconnue"                inconnue      decider_cible 2.120.0 "404: Not" non 5 1
    attendu "cible plus ancienne → anomalie"            retrograde    decider_cible 2.121.0 2.120.0 non 5 1
    attendu "2.119.10 > 2.119.9 (numérique)"            mettre-a-jour decider_cible 2.119.9 2.119.10 non 5 1
    attendu "promue hier, délai 1 → mettre à jour"      mettre-a-jour decider_cible 2.120.0 2.121.0 non 1 1
    attendu "promue aujourd'hui, délai 1 → attendre"    attendre      decider_cible 2.120.0 2.121.0 non 0 1
    attendu "pilote (délai 0) → dès la promotion"       mettre-a-jour decider_cible 2.120.0 2.121.0 non 0 0
    attendu "âge illisible, délai 1 → attendre"         attendre      decider_cible 2.120.0 2.121.0 non "" 1
    attendu "première installation sans version"       mettre-a-jour decider_cible "" 2.121.0 non 3 1
    echo "== self-test : après la mise à jour =="
    attendu "santé OK → réussie"                        reussie   decider_issue ok ""
    attendu "santé KO → revenir à l'image précédente"   revenir   decider_issue ko ""
    attendu "revenue, santé OK → revenue"               revenue   decider_issue ko ok
    attendu "revenue, santé KO → restaurer"             restaurer decider_issue ko ko
    echo "== self-test : la base à sauvegarder =="
    attendu "PostgreSQL (psycopg)"                      postgresql moteur_de_url "postgresql+psycopg://u:p@postgres:5432/b"
    attendu "PostgreSQL sans pilote nommé"              postgresql moteur_de_url "postgresql://u:p@postgres/b"
    attendu "autre moteur → inconnu, donc refus"        inconnu    moteur_de_url "mysql://u:p@h/b"
    attendu "URL absente → inconnu, donc refus"         inconnu    moteur_de_url ""
    exit "$fail"
fi

# ── Le script lui-même est remplacé par l'archive : il se relance d'une copie ──
#  bash lit un script AU FIL de son exécution ; réécrire le fichier en cours de
#  route ferait exécuter un mélange des deux versions.
if [ -z "${MAJ_COPIE:-}" ]; then
    copie=$(mktemp /tmp/coprofirst-maj.XXXXXX)
    cp "$0" "$copie"
    MAJ_COPIE="$copie" exec bash "$copie" "$(cd "$(dirname "$0")/../.." && pwd)"
fi
trap 'rm -f "$MAJ_COPIE"' EXIT

DOSSIER="${1:?dossier manquant}"
cd "$DOSSIER"
exec 9>/tmp/coprofirst-maj.lock
flock -n 9 || { echo "$(date '+%F %T') Une mise à jour tourne déjà — rien à faire."; exit 0; }

COMPOSE=(docker compose -f docker-compose.yml -f deploiement/standard/compose.images.yml)
DEBUT=$(date +%s)
PROJET=$(printf '%s' "${COMPOSE_PROJECT_NAME:-$(basename "$DOSSIER")}" | tr '[:upper:]' '[:lower:]')

COURANTE=$(lire_env COPROFIRST_VERSION)
SAUVEGARDES=$(lire_env COPROFIRST_SAUVEGARDES)
SIGNATURE=$(lire_env COPROFIRST_SIGNATURE); SIGNATURE=${SIGNATURE:-si-possible}
DELAI=$(lire_env COPROFIRST_DELAI_JOURS); DELAI=${DELAI:-1}

rendre_compte() {  # $1 statut (succes|erreur) · $2 erreur (vide si succès) · $3 vers · $4 issue
    #  L'issue est un mot du contrat (`registre/contrat.ISSUES_MISE_A_JOUR`) : le
    #  rapport nocturne la transmet à la référence, qui alerte sur un retour (#1981).
    local details
    details=$(printf '{"de":"%s","vers":"%s","issue":"%s"}' "$COURANTE" "$3" "$4")
    rendre_compte_tache mise_a_jour "$1" "$2" "$details"
}

echouer() {  # $1 message — sortie SANS avoir touché au service
    journal "⚠ $1"
    rendre_compte erreur "$1" "${CIBLE:-}" "echouee"
    exit 1
}

# ── 1–2. La version à installer, et la décision ───────────────────────────────
AGE=""
if [ -n "${COPROFIRST_ESSAI_CIBLE:-}" ]; then
    CIBLE="${COPROFIRST_ESSAI_CIBLE:-}"; AGE=999
    journal "ESSAI : cible imposée $CIBLE (COPROFIRST_ESSAI_CIBLE), replica n'est pas lue."
else
    CIBLE=$(curl -fsSL -m 20 "https://raw.githubusercontent.com/$DEPOT/replica/front/package.json" 2>/dev/null \
        | sed -n 's/^[[:space:]]*"version": *"\([^"]*\)".*/\1/p' | head -1 || true)
    PUBLIEE=$(curl -fsSL -m 20 "https://api.github.com/repos/$DEPOT/releases/tags/v$CIBLE" 2>/dev/null \
        | sed -n 's/.*"published_at": *"\([^"]*\)".*/\1/p' | head -1 || true)
    [ -n "${PUBLIEE:-}" ] && AGE=$(( ( $(date +%s) - $(date -d "${PUBLIEE:-}" +%s) ) / 86400 ))
fi
DECISION=$(decider_cible "$COURANTE" "$CIBLE" "$(lire_env COPROFIRST_EPINGLEE)" "$AGE" "$DELAI")
case "$DECISION" in
    a-jour)    journal "À jour en $COURANTE."; exit 0 ;;
    epinglee)  journal "Version épinglée sur $COURANTE (COPROFIRST_EPINGLEE=oui) : $CIBLE n'est pas installée."; exit 0 ;;
    attendre)  journal "$CIBLE promue il y a ${AGE:-?} jour(s), délai $DELAI : installée une nuit prochaine."; exit 0 ;;
    inconnue)  echouer "version de replica illisible (« $CIBLE ») : dépôt injoignable ?" ;;
    retrograde) echouer "replica porte $CIBLE, plus ancienne que $COURANTE : anomalie, rien n'est fait." ;;
esac
[ -n "$SAUVEGARDES" ] && [ -d "$SAUVEGARDES" ] && [ -w "$SAUVEGARDES" ] \
    || echouer "COPROFIRST_SAUVEGARDES absent ou non inscriptible : pas de mise à jour sans sauvegarde (D15)."
[ "$(moteur_de_url "$(lire_env DATABASE_URL)")" = postgresql ] \
    || echouer "DATABASE_URL de .env ne désigne pas une base PostgreSQL : on ne sauvegarde pas une base qu'on ne sait pas nommer."
journal "Mise à jour $COURANTE → $CIBLE."

# ── 3. Tout préparer pendant que le service tourne ────────────────────────────
TRAVAIL=$(mktemp -d)
if [ -n "${COPROFIRST_ESSAI_ARCHIVE:-}" ]; then
    cp "${COPROFIRST_ESSAI_ARCHIVE:-}" "$TRAVAIL/archive.tar.gz" || echouer "archive d'essai ${COPROFIRST_ESSAI_ARCHIVE:-} illisible."
else
    curl -fsSL -m 120 -o "$TRAVAIL/archive.tar.gz" \
        "https://github.com/$DEPOT/releases/download/v$CIBLE/coprofirst-deploiement-$CIBLE.tar.gz" \
        || echouer "archive de déploiement de $CIBLE introuvable."
fi
tar -xzf "$TRAVAIL/archive.tar.gz" -C "$TRAVAIL" || echouer "archive de $CIBLE illisible."
NOUVEAUX="$TRAVAIL/coprofirst-$CIBLE"
for s in $SERVICES; do
    if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
        gh attestation verify "oci://$REGISTRE/coprofirst-$s:$CIBLE" --owner "${DEPOT%%/*}" >/dev/null 2>&1 \
            || echouer "signature de coprofirst-$s:$CIBLE refusée."
    elif [ "$SIGNATURE" = exigee ]; then
        echouer "signature exigée, mais gh n'est pas installé ou pas connecté."
    else
        journal "⚠ Signature de coprofirst-$s:$CIBLE NON vérifiée (gh absent) — COPROFIRST_SIGNATURE=si-possible."
    fi
done
COPROFIRST_VERSION="$CIBLE" "${COMPOSE[@]}" pull --quiet || echouer "images de $CIBLE introuvables."

# ── 4. Sauvegarder, l'API arrêtée (aucun écrivain) ────────────────────────────
IMAGE_API="$REGISTRE/coprofirst-api:$COURANTE"
ARCHIVE="coprofirst_${COURANTE:-neuve}_vers_${CIBLE}_$(date +%Y%m%d_%H%M%S).tar.gz"
VOLUMES=(-v "${PROJET}_app_data:/donnees/app_data" -v "${PROJET}_uploads:/donnees/uploads" -v "$SAUVEGARDES:/sortie")
#  La base ne vit pas dans ces volumes : elle part dans un EXPORT à côté,
#  réimporté dans une base jetable pour être déclaré bon (P2-7).
BASE="${ARCHIVE%.tar.gz}-base.tar.gz"
PONCTUEL=("${COMPOSE[@]}" run --rm --no-deps -T -v "$SAUVEGARDES:/sortie" --entrypoint python api)
"${COMPOSE[@]}" stop api >/dev/null
sauvegarder() {
    docker run --rm "${VOLUMES[@]}" --entrypoint tar "$IMAGE_API" -czf "/sortie/$ARCHIVE" -C /donnees . || return 1
    "${PONCTUEL[@]}" -m app.utils.export_copropriete exporter env:DATABASE_URL "/sortie/$BASE" \
        && "${PONCTUEL[@]}" -m app.utils.export_copropriete verifier "/sortie/$BASE"
}
if ! sauvegarder; then
    "${COMPOSE[@]}" start api >/dev/null || true
    #  Le rapport part par l'API : l'envoyer avant qu'elle réponde rendait 502,
    #  et l'échec n'était connu que de ce journal (#1820).
    [ "$(sante)" = ok ] || journal "⚠ L'API ne répond pas après la sauvegarde refusée."
    echouer "sauvegarde avant mise à jour impossible ou invalide : rien n'est changé."
fi
journal "Sauvegarde vérifiée : $SAUVEGARDES/$ARCHIVE + $BASE."

# ── 5–6. Poser la version, démarrer, sonder ──────────────────────────────────
PRECEDENT="$DOSSIER/.precedent"
rm -rf "$PRECEDENT" && mkdir -p "$PRECEDENT"
(cd "$NOUVEAUX" && find . -type f) | while read -r f; do
    mkdir -p "$PRECEDENT/$(dirname "$f")" "$DOSSIER/$(dirname "$f")"
    [ -f "$DOSSIER/$f" ] && cp -p "$DOSSIER/$f" "$PRECEDENT/$f"
    cp "$NOUVEAUX/$f" "$DOSSIER/$f"
done
cp -p .env "$PRECEDENT/.env"
sed -i "s/^COPROFIRST_VERSION=.*/COPROFIRST_VERSION=$CIBLE/" .env
grep -q "^COPROFIRST_VERSION=" .env || echo "COPROFIRST_VERSION=$CIBLE" >> .env
"${COMPOSE[@]}" up -d --remove-orphans >/dev/null 2>&1 || true
NEUVE=$(sante)

# ── 7. L'issue ────────────────────────────────────────────────────────────────
RETOUR=""
if [ "$(decider_issue "$NEUVE" "")" = revenir ]; then
    journal "⚠ Santé KO après la mise à jour vers $CIBLE — retour à $COURANTE."
    (cd "$PRECEDENT" && find . -type f) | while read -r f; do cp -p "$PRECEDENT/$f" "$DOSSIER/$f"; done
    "${COMPOSE[@]}" up -d --remove-orphans >/dev/null 2>&1 || true
    RETOUR=$(sante)
fi
case "$(decider_issue "$NEUVE" "$RETOUR")" in
    reussie)
        journal "Mise à jour réussie : $CIBLE (en $(( $(date +%s) - DEBUT )) s)."
        rendre_compte succes "" "$CIBLE" "reussie" ;;
    revenue)
        journal "⚠ Revenue en $COURANTE : la base garde les migrations de $CIBLE, compatibles."
        rendre_compte erreur "santé KO après la mise à jour vers $CIBLE — revenue en $COURANTE" "$CIBLE" "revenue"
        exit 1 ;;
    restaurer)
        journal "🔴 Santé KO aussi en $COURANTE — restauration de $ARCHIVE."
        "${COMPOSE[@]}" stop api >/dev/null || true
        docker run --rm "${VOLUMES[@]}" --entrypoint sh "$IMAGE_API" -c \
            "rm -rf /donnees/app_data/* /donnees/uploads/* && tar -xzf /sortie/$ARCHIVE -C /donnees"
        #  La base de la version PRÉCÉDENTE (fichiers et .env déjà revenus) :
        #  schéma vidé, schéma initial de cette version, puis l'export d'avant.
        "${COMPOSE[@]}" exec -T postgres psql -U coprofirst -d coprofirst -q \
            -c "DROP SCHEMA public CASCADE" -c "CREATE SCHEMA public" \
            && "${PONCTUEL[@]}" -m app.utils.schema_initial \
            && "${PONCTUEL[@]}" -m app.utils.export_copropriete importer "/sortie/$BASE" env:DATABASE_URL \
            || journal "🔴 Restauration de la base ÉCHOUÉE — l'export d'avant la mise à jour est $SAUVEGARDES/$BASE."
        "${COMPOSE[@]}" up -d >/dev/null 2>&1 || true
        journal "Restauration terminée — santé : $(sante)."
        rendre_compte erreur "santé KO en $CIBLE puis en $COURANTE — sauvegarde $ARCHIVE restaurée" "$CIBLE" "restauree"
        exit 1 ;;
esac
rm -rf "$TRAVAIL"
