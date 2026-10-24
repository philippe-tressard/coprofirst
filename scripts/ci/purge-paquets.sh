#!/bin/bash
# =============================================================================
#  purge-paquets.sh — Retirer les releases et les images GHCR que plus aucune
#  vague ne peut servir (#2210, 24/10/2026)
#
#  Chaque commit de `main` publie ses images (`sha-<commit>`), chaque version
#  taguée son étiquette `X.Y.Z` et sa release (workflow « Images ») : sans purge,
#  tout s'accumule. Ce qui se GARDE est ce que la référence peut encore proposer
#  ou servir à une installation — la règle de `api/app/registre/versions.py`,
#  exécutée ici telle quelle, jamais recopiée :
#  - la liste proposée (les 5 dernières mineures, chacune à son dernier correctif) ;
#  - la cible de chaque vague du canal Urgence (Urgence, Pilote, Standard) ;
#  - toute version, et toute image, plus jeune que la fenêtre de garde (8 jours) :
#    les cibles de demain, et les images `sha-<commit>` que tire la référence.
#
#  Une image GARDÉE garde ce qu'elle désigne : ses manifestes par architecture et
#  ses attestations (manifestes sans étiquette, ou étiquetés `sha256-<empreinte>`).
#  Le tag git `vX.Y.Z` ne se supprime jamais (règle du dépôt) : seule sa release part.
#
#  ## La décision (fonction PURE, testée par --selftest)
#
#  | Une version du paquet…                                  | Verdict     |
#  |---------------------------------------------------------|-------------|
#  | plus jeune que la fenêtre de garde                      | `garder`    |
#  | étiquetée d'une version à garder                        | `garder`    |
#  | désignée par une image gardée (architecture, attestation) | `garder`  |
#  | étiquetée `sha256-<e>` où `e` est une image gardée       | `garder`    |
#  | sinon                                                   | `supprimer` |
#
#  Sans `SUPPRIMER=oui`, rien ne part : la liste s'affiche (constat). Au plus
#  `PLAFOND` suppressions par passage — le quota de l'API, et une borne si la
#  règle se trompait ; le passage suivant reprend. Une lecture qui échoue arrête
#  tout : ne rien savoir garder purgerait tout (`standards/04`).
#
#  Entrées (environnement) : GH_TOKEN, SUPPRIMER (`oui` pour supprimer), PLAFOND.
#  Test : bash scripts/ci/purge-paquets.sh --selftest
# =============================================================================
set -euo pipefail

PROPRIETAIRE="philippe-tressard"
DEPOT="$PROPRIETAIRE/coprofirst"
REGISTRE="ghcr.io/$PROPRIETAIRE"
SERVICES="api front caddy whatsapp-bridge"
VERSIONS_PY="$(dirname "${BASH_SOURCE[0]}")/../../api/app/registre/versions.py"

# ── La décision (PURE) ────────────────────────────────────────────────────────
#  $1 étiquettes (séparées par des espaces) · $2 âge en jours · $3 fenêtre de
#  garde en jours · $4 versions à garder · $5 empreinte de la version du paquet
#  · $6 empreintes désignées par une image gardée
decider_paquet() {
    local etiquettes="$1" age="$2" fenetre="$3" gardees="$4" empreinte="$5" designees="$6" e
    if [ "$age" -lt "$fenetre" ]; then echo garder; return; fi
    for e in $etiquettes; do
        case " $gardees " in *" $e "*) echo garder; return ;; esac
        case "$e" in
            sha256-*) case " $designees " in *" sha256:${e#sha256-} "*) echo garder; return ;; esac ;;
        esac
    done
    if [ -n "$empreinte" ]; then
        case " $designees " in *" $empreinte "*) echo garder; return ;; esac
    fi
    echo supprimer
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    attendu() {  # $1 libellé · $2 verdict attendu · $3… arguments
        local lib="$1" voulu="$2" got; shift 2
        got=$(decider_paquet "$@")
        if [ "$got" = "$voulu" ]; then echo "PASS  $lib"; else echo "FAIL  $lib — « $got »"; fail=1; fi
    }
    G="3.12.0 3.13.9 3.14.3"; D="sha256:aaa sha256:bbb"
    echo "== self-test : garder ou supprimer une version d'un paquet =="
    attendu "jeune, sans étiquette → garder"            garder    ""                 2  8 "$G" sha256:zzz "$D"
    attendu "jeune, sha-<commit> → garder"              garder    "sha-abc"          7  8 "$G" sha256:zzz "$D"
    attendu "étiquette gardée → garder"                 garder    "sha-abc 3.13.9"   40 8 "$G" sha256:zzz "$D"
    attendu "manifeste d'architecture désigné → garder" garder    ""                 40 8 "$G" sha256:aaa "$D"
    attendu "attestation sha256-<gardée> → garder"      garder    "sha256-bbb"       40 8 "$G" sha256:zzz "$D"
    attendu "ancienne version périmée → supprimer"      supprimer "sha-abc 3.11.7"   40 8 "$G" sha256:zzz "$D"
    attendu "vieux sha-<commit> → supprimer"            supprimer "sha-def"          9  8 "$G" sha256:zzz "$D"
    attendu "orphelin sans étiquette → supprimer"       supprimer ""                 30 8 "$G" sha256:zzz "$D"
    attendu "attestation d'une périmée → supprimer"     supprimer "sha256-ccc"       30 8 "$G" sha256:ccc "$D"
    attendu "une version préfixe d'une gardée → supprimer" supprimer "3.12"          30 8 "$G" sha256:zzz "$D"
    attendu "release périmée, sans empreinte → supprimer" supprimer "3.11.7"         30 8 "$G" ""         ""
    exit "$fail"
fi

SUPPRIMER="${SUPPRIMER:-non}"
PLAFOND="${PLAFOND:-300}"
TRAVAIL=$(mktemp -d)
trap 'rm -rf "$TRAVAIL"' EXIT
echo "Purge des paquets — mode : $([ "$SUPPRIMER" = oui ] && echo SUPPRESSION || echo constat), plafond $PLAFOND."

# ── Ce qui se garde : la règle de l'API, sur les releases publiées ────────────
gh api --paginate "repos/$DEPOT/releases?per_page=100" | jq -s 'add // []' > "$TRAVAIL/releases.json" \
    || { echo "::error::releases illisibles : rien n'est purgé"; exit 1; }
jq '[.[] | select(.draft | not) | {version: (.tag_name | ltrimstr("v")), publiee_le: .created_at}]' \
    "$TRAVAIL/releases.json" > "$TRAVAIL/versions.json"
GARDEES=$(python3 -I "$VERSIONS_PY" garder < "$TRAVAIL/versions.json" | tr '\n' ' ') \
    || { echo "::error::aucune version à garder : rien n'est purgé"; exit 1; }
FENETRE=$(python3 -I "$VERSIONS_PY" fenetre)
echo "À garder ($(wc -w <<< "$GARDEES") versions, et tout ce qui a moins de $FENETRE jours) : $GARDEES"

supprimees=0
supprimer() {  # $1 libellé · $2… commande
    local lib="$1"; shift
    if [ "$supprimees" -ge "$PLAFOND" ]; then return 0; fi
    supprimees=$((supprimees + 1))
    if [ "$SUPPRIMER" = oui ]; then
        "$@" >/dev/null && echo "supprimé : $lib" || echo "::warning::non supprimé : $lib"
    else
        echo "à supprimer : $lib"
    fi
}

# ── Les releases périmées (le tag reste) ──────────────────────────────────────
while IFS=$'\t' read -r version age; do
    if [ "$(decider_paquet "$version" "$age" "$FENETRE" "$GARDEES" "" "")" = supprimer ]; then
        supprimer "release v$version" gh release delete "v$version" --repo "$DEPOT" --yes
    fi
done < <(jq -r '.[] | select(.version | test("^[0-9]+\\.[0-9]+\\.[0-9]+$"))
    | [.version, ((now - (.publiee_le | fromdateiso8601)) / 86400 | floor)] | @tsv' "$TRAVAIL/versions.json")

# ── Les images de chaque service ──────────────────────────────────────────────
for s in $SERVICES; do
    paquet="coprofirst-$s"
    gh api --paginate "users/$PROPRIETAIRE/packages/container/$paquet/versions?per_page=100" \
        | jq -s 'add // []' > "$TRAVAIL/$s.json" \
        || { echo "::error::versions de $paquet illisibles : rien n'est purgé"; exit 1; }
    jq -r '.[] | [.id, .name, ((now - (.created_at | fromdateiso8601)) / 86400 | floor),
        (.metadata.container.tags | join(" "))] | @tsv' "$TRAVAIL/$s.json" > "$TRAVAIL/$s.tsv"
    #  Ce que désignent les images gardées par leur étiquette : architectures et
    #  attestations. Un manifeste illisible arrête tout — on ne saurait plus quoi garder.
    designees=""
    while IFS=$'\t' read -r _id empreinte age etiquettes; do
        if [ "$age" -lt "$FENETRE" ]; then continue; fi
        if [ "$(decider_paquet "$etiquettes" "$age" "$FENETRE" "$GARDEES" "" "")" != garder ]; then
            continue
        fi
        enfants=$(docker buildx imagetools inspect --raw "$REGISTRE/$paquet@$empreinte" \
            | jq -r '.manifests[]?.digest' | tr '\n' ' ') \
            || { echo "::error::manifeste de $paquet@$empreinte illisible : rien n'est purgé"; exit 1; }
        designees="$designees $empreinte $enfants"
    done < "$TRAVAIL/$s.tsv"
    n=0
    while IFS=$'\t' read -r id empreinte age etiquettes; do
        if [ "$(decider_paquet "$etiquettes" "$age" "$FENETRE" "$GARDEES" "$empreinte" "$designees")" = supprimer ]; then
            n=$((n + 1))
            supprimer "$paquet ${etiquettes:-sans étiquette} ($empreinte, $age j)" \
                gh api -X DELETE "users/$PROPRIETAIRE/packages/container/$paquet/versions/$id"
        fi
    done < "$TRAVAIL/$s.tsv"
    echo "$paquet : $(wc -l < "$TRAVAIL/$s.tsv") versions, $n périmées."
done
if [ "$supprimees" -ge "$PLAFOND" ]; then
    echo "Plafond de $PLAFOND atteint : le passage suivant reprendra."
fi
echo "Purge terminée : $supprimees $([ "$SUPPRIMER" = oui ] && echo traitées || echo à supprimer)."
