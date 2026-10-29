#!/bin/bash
# =============================================================================
#  promotion.sh — Promouvoir une version de `main` sur la branche `replica`
#  (#1754, 08/10/2026)
#
#  Lot DI-2 du chantier multi-copropriétés (`specs/architecture/multi-coproprietes.md`
#  §4.10, règles 1 et 5, D11). Les répliques CoproFirst suivent `replica` ;
#  la référence suit `main`. Une version passe de l'un à l'autre par ce geste,
#  décidé par l'auteur et lancé à la main (workflow « Promotion »).
#
#  ## Les règles de l'auteur (#1934, 14/10/2026)
#
#  - une version normale se promeut à la main, au choix de l'auteur — pas
#    forcément la dernière —, quand elle tourne sur la référence depuis au
#    moins RODAGE_JOURS (7) ;
#  - un correctif urgent se promeut avec `URGENCE=1` : ni rodage ni blocage ;
#  - une issue OUVERTE portant le label `bloque-promotion` retient toute
#    promotion (sauf urgence) : c'est ainsi qu'un incident sur la référence se
#    déclare. Une liste illisible retient aussi — un contrôle qui ne s'exécute
#    pas ne vaut pas « aucun blocage » ;
#  - la nuit (déclenchement `schedule`), seule une version X.0.0 se promeut
#    seule, à J+7 (`choisir_majeure`). Retenue par un blocage, elle attend.
#
#  ## Ce que le geste décide (fonction PURE, testée par --selftest)
#
#  | Situation                                         | Verdict                 |
#  |---------------------------------------------------|-------------------------|
#  | version illisible                                 | `refus-version`         |
#  | aucun tag `vX.Y.Z`                                | `refus-sans-tag`        |
#  | le tag n'est pas sur `main`                       | `refus-hors-main`       |
#  | `replica` porte déjà ce commit                    | `deja`                  |
#  | le tag ne descend pas de `replica` (retour arrière, branche parallèle) | `refus-pas-en-avant` |
#  | (hors urgence) liste des blocages illisible       | `refus-blocage-illisible` |
#  | (hors urgence) une issue `bloque-promotion` ouverte | `refus-bloquee`       |
#  | (hors urgence) tag de moins de RODAGE_JOURS       | `refus-rodage`          |
#  | `replica` n'existe pas encore                     | `creer`                 |
#  | sinon                                             | `avancer`               |
#
#  🔴 `replica` est un POINTEUR, jamais une branche de travail : elle n'avance
#  qu'en avance rapide, vers un tag de `main`, et ne porte aucun commit propre.
#  Un correctif urgent passe par `main`, reçoit sa version, puis se promeut.
#  Le jour où un commit naîtrait sur `replica`, il y aurait deux produits.
#  Promouvoir UNE PR seule n'existe donc pas : une version emporte tout ce qui
#  la précède sur `main` (écarté le 14/10/2026 — code jamais exécuté par la
#  référence, chaîne Alembic divergente).
#
#  ## Ce que le geste AFFICHE
#
#  Les faits mesurables : âge du tag, blocages, état des contrôles du commit.
#  L'âge se compte depuis la fusion du commit sur `main` — la référence le sert
#  un quart d'heure plus tard (images de la CI).
#
#  Usage : VERSION=X.Y.Z [URGENCE=1] bash scripts/ci/promotion.sh   (clone aux tags lus)
#          GITHUB_EVENT_NAME=schedule bash scripts/ci/promotion.sh  (la majeure de la nuit)
#  Test  : bash scripts/ci/promotion.sh --selftest
# =============================================================================
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib-replica.sh"

#  Le rodage exigé avant une promotion qui n'est pas une urgence (spec §9,
#  question 8, tranchée le 14/10/2026).
RODAGE_JOURS=7

# ── La décision (PURE) ────────────────────────────────────────────────────────
#  $1 version · $2 commit du tag (vide : pas de tag) · $3 tag sur main (1 | 0)
#  · $4 commit de replica (vide : pas de branche) · $5 replica ancêtre du tag (1 | 0)
#  · $6 âge du tag en jours · $7 urgence (1 | 0)
#  · $8 blocages : vide (aucun), « inconnu » (liste illisible), ou « #12,#15 »
decider_promotion() {
    local version="$1" commit="$2" sur_main="$3" replica="$4" en_avant="$5"
    local age="${6:-0}" urgence="${7:-0}" blocages="${8:-}"
    if ! grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$' <<<"$version"; then echo refus-version; return; fi
    if [ -z "$commit" ]; then echo refus-sans-tag; return; fi
    if [ "$sur_main" != 1 ]; then echo refus-hors-main; return; fi
    if [ -n "$replica" ] && [ "$replica" = "$commit" ]; then echo deja; return; fi
    if [ -n "$replica" ] && [ "$en_avant" != 1 ]; then echo refus-pas-en-avant; return; fi
    if [ "$urgence" != 1 ]; then
        if [ "$blocages" = inconnu ]; then echo refus-blocage-illisible; return; fi
        if [ -n "$blocages" ]; then echo refus-bloquee; return; fi
        if [ "$age" -lt "$RODAGE_JOURS" ]; then echo refus-rodage; return; fi
    fi
    if [ -z "$replica" ]; then echo creer; return; fi
    echo avancer
}

# ── La majeure de la nuit (PURE) ──────────────────────────────────────────────
#  $1 version portée par `replica` (vide : pas de branche — la création reste
#  un geste de l'auteur). Entrée : une ligne « X.Y.Z âge_en_jours » par tag.
#  Sortie : la plus haute X.0.0 rodée et en avant de `replica`, ou rien.
choisir_majeure() {
    local replica_version="$1" candidates
    [ -n "$replica_version" ] || { cat >/dev/null; return 0; }
    candidates=$(awk -v n="$RODAGE_JOURS" '$1 ~ /^[0-9]+\.0\.0$/ && $2 >= n { print $1 }')
    [ -n "$candidates" ] || return 0
    printf '%s\n%s\n' "$replica_version" "$candidates" | sort -uV \
        | awk -v r="$replica_version" 'f { dernier = $0 } $0 == r { f = 1 } END { print dernier }'
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    attendu() {  # $1 libellé · $2 verdict attendu · $3… arguments
        local lib="$1" voulu="$2" got; shift 2
        got=$(decider_promotion "$@")
        if [ "$got" = "$voulu" ]; then echo "PASS  $lib"; else echo "FAIL  $lib — « $got »"; fail=1; fi
    }
    echo "== self-test : promotion vers replica =="
    #                                                                              version   tag  main replica avant âge urg blocages
    attendu "première promotion → créer replica"         creer                   2.120.0   c2   1    ""      0     9   0   ""
    attendu "version suivante → avancer"                  avancer                 2.121.0   c3   1    c2      1     9   0   ""
    attendu "même version, relancée → déjà"               deja                    2.121.0   c3   1    c3      1     0   0   "#4"
    attendu "version ANTÉRIEURE → refus (pas de retour)"  refus-pas-en-avant      2.119.0   c1   1    c3      0     30  1   ""
    attendu "tag hors de main → refus"                    refus-hors-main         2.121.0   c9   0    c3      1     9   0   ""
    attendu "aucun tag → refus"                           refus-sans-tag          2.121.0   ""   1    c3      1     9   0   ""
    attendu "version illisible → refus"                   refus-version           "v2.1"    c3   1    c3      1     9   0   ""
    attendu "injection dans la version → refus"           refus-version           '1.2.3;rm' c3  1    c3      1     9   0   ""
    attendu "6 jours de rodage → refus"                   refus-rodage            2.121.0   c3   1    c2      1     6   0   ""
    attendu "7 jours de rodage → avancer"                 avancer                 2.121.0   c3   1    c2      1     7   0   ""
    attendu "0 jour mais urgence → avancer"               avancer                 2.121.1   c4   1    c2      1     0   1   ""
    attendu "issue bloque-promotion ouverte → refus"      refus-bloquee           2.121.0   c3   1    c2      1     9   0   "#12"
    attendu "blocage, mais urgence → avancer"             avancer                 2.121.1   c4   1    c2      1     0   1   "#12"
    attendu "blocages illisibles → refus, jamais OK"      refus-blocage-illisible 2.121.0   c3   1    c2      1     9   0   inconnu
    attendu "l'urgence ne permet pas de reculer"          refus-pas-en-avant      2.119.0   c1   1    c3      0     0   1   ""
    majeure() {  # $1 libellé · $2 attendu · $3 replica · $4 lignes « version âge »
        local got; got=$(printf '%s\n' "$4" | choisir_majeure "$3")
        if [ "$got" = "$2" ]; then echo "PASS  $1"; else echo "FAIL  $1 — « $got »"; fail=1; fi
    }
    majeure "majeure rodée, en avant → promue"          3.0.0  2.145.0 $'2.146.0 9\n3.0.0 7\n3.0.1 6'
    majeure "majeure de 6 jours → elle attend"          ""     2.145.0 $'3.0.0 6\n3.0.1 2'
    majeure "majeure déjà derrière replica → rien"      ""     3.2.0   $'3.0.0 40\n3.2.0 9'
    majeure "deux majeures rodées → la plus haute"      4.0.0  2.145.0 $'3.0.0 60\n4.0.0 8'
    majeure "aucune majeure → rien"                     ""     2.145.0 $'2.146.0 9\n2.147.0 8'
    majeure "pas de replica → rien (création manuelle)" ""     ""      $'3.0.0 9'
    majeure "10.0.0 se range après 9.0.0"               10.0.0 9.0.0   $'10.0.0 7\n9.0.0 90'
    exit "$fail"
fi

# ── Les faits, lus dans le dépôt et sur GitHub ────────────────────────────────
age_jours() {  # $1 commit → jours écoulés depuis sa fusion sur `main`
    echo $(( ( $(date +%s) - $(git log -1 --format=%ct "$1") ) / 86400 ))
}
#  Les issues ouvertes qui retiennent la promotion. Hors d'Actions, ou si GitHub
#  ne répond pas : « inconnu », qui retient aussi (jamais un « aucun » par défaut).
lire_blocages() {
    if [ -z "${GH_TOKEN:-}" ] || [ -z "${GITHUB_REPOSITORY:-}" ]; then echo inconnu; return; fi
    gh issue list --repo "${GITHUB_REPOSITORY:-}" --label bloque-promotion --state open \
        --json number --jq 'map("#\(.number)") | join(",")' 2>/dev/null || echo inconnu
}
ecrire_sorties() {  # paires clé=valeur pour les étapes suivantes du workflow
    printf '%s\n' "$@" >> "${GITHUB_OUTPUT:-/dev/null}"
}

resume="${GITHUB_STEP_SUMMARY:-/dev/null}"
nocturne=0
[ "${GITHUB_EVENT_NAME:-}" = schedule ] && nocturne=1
urgence=0
case "${URGENCE:-}" in true|1|oui) urgence=1 ;; esac
[ "$nocturne" = 1 ] && urgence=0   # la nuit ne promeut jamais en urgence

git fetch --quiet origin main 2>/dev/null || true
replica=$(git rev-parse --verify --quiet origin/replica 2>/dev/null || true)

version="${VERSION:-}"
if [ "$nocturne" = 1 ] && [ -z "$version" ]; then
    replica_version=""
    [ -n "$replica" ] && replica_version=$(version_du_commit "$replica")
    version=$(for t in $(git tag -l 'v[0-9]*.0.0' --merged origin/main); do
        echo "${t#v} $(age_jours "$(git rev-list -n 1 "$t")")"
    done | choisir_majeure "$replica_version")
    if [ -z "$version" ]; then
        echo "Aucune version X.0.0 rodée en avant de replica (${replica_version:-absente}) : rien à promouvoir cette nuit." | tee -a "$resume"
        ecrire_sorties "verdict=rien"
        exit 0
    fi
fi

tag="v$version"
commit=$(git rev-list -n 1 "refs/tags/$tag" 2>/dev/null || true)
sur_main=0
[ -n "$commit" ] && git merge-base --is-ancestor "$commit" origin/main 2>/dev/null && sur_main=1
en_avant=0
[ -n "$commit" ] && [ -n "$replica" ] && git merge-base --is-ancestor "$replica" "$commit" 2>/dev/null && en_avant=1
jours=0
[ -n "$commit" ] && jours=$(age_jours "$commit")
blocages=$(lire_blocages)
verdict=$(decider_promotion "$version" "$commit" "$sur_main" "$replica" "$en_avant" "$jours" "$urgence" "$blocages")

mode=""
[ "$urgence" = 1 ] && mode=urgence
[ "$nocturne" = 1 ] && mode=automatique

# ── Les faits, affichés pour l'auteur ─────────────────────────────────────────
{
    echo "## Promotion de $tag sur \`replica\`"
    echo
    echo "| Fait | Valeur |"
    echo "|---|---|"
    echo "| Verdict | \`$verdict\` |"
    echo "| Déclenchement | ${mode:-manuel} |"
    echo "| Commit du tag | \`${commit:-absent}\` |"
    echo "| \`replica\` avant | \`${replica:-absente}\` |"
    echo "| Rodage sur la référence | $jours jour(s) depuis la fusion — exigé : $RODAGE_JOURS, sauf urgence |"
    echo "| Issues \`bloque-promotion\` ouvertes | ${blocages:-aucune} |"
    if [ -n "$commit" ] && [ -n "${GH_TOKEN:-}" ] && [ -n "${GITHUB_REPOSITORY:-}" ]; then
        ci=$(gh api "repos/${GITHUB_REPOSITORY:-}/commits/$commit/check-runs" \
            --jq '[.check_runs[].conclusion] | group_by(.) | map("\(.[0] // "en cours") : \(length)") | join(", ")' 2>/dev/null || echo "illisible")
        echo "| Contrôles du commit | ${ci:-aucun} |"
    fi
} | tee -a "$resume"

case "$verdict" in
    creer|avancer)
        #  Avance rapide par construction : le verdict l'a vérifié. Un push
        #  sans `--force` le revérifie côté serveur, et la règle de la branche
        #  refuse tout le reste.
        git push origin "$commit:refs/heads/replica"
        echo "✓ replica → $tag ($commit)" | tee -a "$resume" ;;
    deja)
        echo "✓ replica porte déjà $tag : rien à faire." | tee -a "$resume" ;;
    refus-bloquee)
        if [ "$nocturne" = 1 ]; then
            #  Un incident déclaré retient la majeure : elle attend, la nuit
            #  n'échoue pas pour autant (sinon un courriel chaque nuit).
            echo "⏸ $tag retenue par $blocages : elle attend la fermeture." | tee -a "$resume"
            ecrire_sorties "verdict=retenue"
            exit 0
        fi
        echo "::error::promotion refusée : $verdict ($blocages) — fermer l'issue, ou promouvoir en urgence"
        exit 1 ;;
    *)
        echo "::error::promotion refusée : $verdict"
        exit 1 ;;
esac
ecrire_sorties "commit=$commit" "precedent=$replica" "verdict=$verdict" "version=$version" "mode=$mode"
exit 0
