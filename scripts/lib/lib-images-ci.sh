#!/bin/bash
# =============================================================================
#  lib-images-ci.sh — Le nœud TIRE les images que la CI a construites pour son
#  commit, au lieu de les construire lui-même (#1758, 08/10/2026)
#
#  Module SOURCÉ par `lib-parite.sh` — donc par `auto-deploy.sh` et par la
#  synchronisation du pair dans `bascule.sh` : jamais exécuté par un cron. Pas
#  de bit x (`lib-*.sh` sont en 100644).
#
#  Lot DI-6 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
#  §4.10, règle 4, D12). Le workflow `images.yml` (#1753) publie, pour chaque
#  commit de `main`, les images des quatre services sous
#  `ghcr.io/philippe-tressard/coprofirst-<service>:sha-<commit>`. La référence —
#  les deux RPi — exécute alors EXACTEMENT les octets que les répliques
#  recevront à la promotion, et cesse de construire : plus de build concurrent,
#  plus d'image périmée à la bascule, plus de cache de build de 40 Go.
#
#  ## Ce qui ne change pas
#
#  Les images tirées sont ré-étiquetées sous les noms locaux de Compose
#  (`5hostachy-api:latest`…) : `docker compose up`, le marqueur
#  `.images-construites`, les points 12 et 18 du pré-check et C27 lisent ce
#  qu'ils lisaient. Le marqueur continue d'attester un FAIT — des images
#  prêtes pour ce commit —, qu'elles viennent du registre ou d'un build.
#
#  ## La décision (fonction PURE, --selftest)
#
#  | Images de la CI pour ce commit | Âge du commit      | Verdict      |
#  |--------------------------------|--------------------|--------------|
#  | tirées                         | —                  | `tirees`     |
#  | absentes                       | < DELAI_IMAGES_CI_S | `attendre`  |
#  | absentes                       | ≥ DELAI_IMAGES_CI_S | `construire` |
#  | absentes, sans attente demandée | —                 | `construire` |
#
#  « construire » est le SECOURS arbitré le 08/10/2026 (« build local +
#  alerte ») : la production ne dépend jamais de GitHub. Il coûte un second
#  chemin à entretenir, et il alerte à chaque emploi — un secours qui sert
#  sans le dire devient le chemin normal sans que personne l'ait décidé.
#  La bascule (`OBTENIR_SANS_ATTENTE=1`) n'attend pas : elle a besoin des
#  images maintenant.
#
#  Test : bash scripts/lib/lib-images-ci.sh --selftest
# =============================================================================

#: Où la CI publie (`.github/workflows/images.yml`, `env.REGISTRE`).
REGISTRE_IMAGES="ghcr.io/philippe-tressard"

#: Les services publiés — ceux que `docker-compose.yml` construit
#: (`test_images_publiees.py` tient la matrice de la CI, `test_images_ci.py` cette liste).
SERVICES_IMAGES="api front caddy whatsapp-bridge"

#: Au-delà, le nœud construit lui-même. La CI construit les quatre services
#: sur deux architectures en une quinzaine de minutes ; trente laissent passer
#: une file d'attente des runners sans geler un déploiement pour une panne.
DELAI_IMAGES_CI_S=1800

# ── La décision (PURE) ───────────────────────────────────────────────────────
#  $1 tirage (ok | absent) · $2 âge du commit en secondes · $3 délai
#  · $4 sans attente (1) → tirees | attendre | construire
decider_obtention() {
    local tirage="${1:-}" age="${2:-}" delai="${3:-0}" sans_attente="${4:-0}"
    if [ "$tirage" = ok ]; then echo tirees; return; fi
    if [ "$sans_attente" = 1 ]; then echo construire; return; fi
    #  Un âge illisible n'autorise pas à attendre indéfiniment : on construit.
    case "$age" in ''|*[!0-9]*) echo construire; return ;; esac
    if [ "$age" -lt "$delai" ]; then echo attendre; else echo construire; fi
}

# ── Le nom local qu'emploie Compose : `<projet>-<service>:latest` ───────────
#  Le projet est le nom du dossier (`/opt/5hostachy` → `5hostachy`), comme
#  Compose le déduit quand rien ne le fixe.
image_locale() {
    local projet="${COMPOSE_PROJECT_NAME:-$(basename "$PWD")}"
    printf '%s-%s:latest\n' "$(printf '%s' "$projet" | tr '[:upper:]' '[:lower:]')" "$1"
}

# ── Tirer les quatre images d'un commit, puis seulement les étiqueter ────────
#  $1 = commit complet. Tout ou rien : une image manquante → aucune étiquette
#  posée, les conteneurs en place gardent leurs images.
tirer_images() {
    local commit="${1:?commit}" s ref
    for s in $SERVICES_IMAGES; do
        docker pull --quiet "$REGISTRE_IMAGES/coprofirst-$s:sha-$commit" >/dev/null 2>&1 || return 1
    done
    for s in $SERVICES_IMAGES; do
        ref="$REGISTRE_IMAGES/coprofirst-$s:sha-$commit"
        docker tag "$ref" "$(image_locale "$s")" || return 1
        #  Retire l'étiquette du registre, garde le contenu (porté par l'étiquette
        #  locale) : sans cela, chaque commit laisserait quatre images référencées
        #  qu'aucune purge des images orphelines ne verrait.
        docker image rm "$ref" >/dev/null 2>&1 || true
    done
}

# ── La porte : obtenir les images du commit courant ──────────────────────────
#  Les arguments passent au build de secours (`--quiet`…). Retour : 0 images
#  prêtes · 3 en attente de la CI (rien n'a changé) · autre = échec du build.
#  `IMAGES_OBTENUES` dit comment : tirees | attente | construites.
obtenir_images() {
    IMAGES_OBTENUES=inconnues
    exporter_git_hash || return 1
    local commit date_commit age
    commit=$(git rev-parse HEAD) || return 1
    date_commit=$(git log -1 --format=%ct HEAD 2>/dev/null)
    age=$(( $(date +%s) - ${date_commit:-0} ))
    if tirer_images "$commit"; then
        IMAGES_OBTENUES=tirees
        return 0
    fi
    case "$(decider_obtention absent "$age" "$DELAI_IMAGES_CI_S" "${OBTENIR_SANS_ATTENTE:-0}")" in
        attendre)
            IMAGES_OBTENUES=attente
            return 3 ;;
        *)
            IMAGES_OBTENUES=construites
            construire_images "$@" ;;
    esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    fail=0
    attendu() {  # $1 libellé · $2 verdict attendu · $3… arguments
        local lib="$1" voulu="$2" got; shift 2
        got=$(decider_obtention "$@")
        if [ "$got" = "$voulu" ]; then echo "PASS  $lib"; else echo "FAIL  $lib — « $got »"; fail=1; fi
    }
    echo "== self-test : obtenir les images d'un commit =="
    attendu "images de la CI tirées → tirees"               tirees     ok     99999 1800 0
    attendu "absentes, commit récent → attendre"             attendre   absent 300   1800 0
    attendu "absentes, délai dépassé → construire (secours)" construire absent 1800  1800 0
    attendu "absentes, bascule sans attente → construire"    construire absent 10    1800 1
    attendu "tirées pendant une bascule → tirees"            tirees     ok     10    1800 1
    attendu "âge illisible → construire, jamais attendre"    construire absent ""    1800 0
    attendu "âge négatif (horloge) → construire"             construire absent -5    1800 0

    echo "== self-test : nom local des images =="
    vu=$(cd / && COMPOSE_PROJECT_NAME=5Hostachy image_locale api)
    if [ "$vu" = "5hostachy-api:latest" ]; then echo "PASS  projet fixé, en minuscules → $vu"
    else echo "FAIL  attendu 5hostachy-api:latest, obtenu « $vu »"; fail=1; fi
    ICI_DOSSIER=$(mktemp -d)/5hostachy
    mkdir -p "$ICI_DOSSIER"
    vu=$(cd "$ICI_DOSSIER" && unset COMPOSE_PROJECT_NAME && image_locale whatsapp-bridge)
    if [ "$vu" = "5hostachy-whatsapp-bridge:latest" ]; then echo "PASS  projet déduit du dossier → $vu"
    else echo "FAIL  attendu 5hostachy-whatsapp-bridge:latest, obtenu « $vu »"; fail=1; fi
    rm -rf "$(dirname "$ICI_DOSSIER")"

    echo "== self-test : tout ou rien =="
    #  Docker simulé : le front n'est pas publié. Aucune étiquette ne doit être posée.
    vu=$(bash -c "source '${BASH_SOURCE[0]}'
        docker() { case \"\$1 \$*\" in *coprofirst-front*) [ \"\$1\" = pull ] && return 1 ;; esac; echo \"\$1\"; }
        cd / ; COMPOSE_PROJECT_NAME=5hostachy tirer_images abc && echo tire || echo refuse" | tr '\n' ' ')
    case "$vu" in
        *tag*) echo "FAIL  une étiquette a été posée alors qu'une image manquait — « $vu »"; fail=1 ;;
        *refuse*) echo "PASS  une image manquante → aucune étiquette posée" ;;
        *) echo "FAIL  sortie inattendue « $vu »"; fail=1 ;;
    esac
    vu=$(bash -c "source '${BASH_SOURCE[0]}'
        docker() { echo \"\$1 \${@: -1}\"; }
        cd / ; COMPOSE_PROJECT_NAME=5hostachy tirer_images abc" | grep '^tag' | tr '\n' '|')
    if [ "$vu" = "tag 5hostachy-api:latest|tag 5hostachy-front:latest|tag 5hostachy-caddy:latest|tag 5hostachy-whatsapp-bridge:latest|" ]; then
        echo "PASS  les quatre images sont étiquetées sous leur nom de Compose"
    else echo "FAIL  étiquettes posées : « $vu »"; fail=1; fi

    [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $fail
fi
