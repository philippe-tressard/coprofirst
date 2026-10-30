#!/bin/bash
# =============================================================================
#  veille-securite.sh — la VEILLE nocturne des vulnérabilités (workflow
#  `veille-securite.yml`) : ce que chaque étape a rendu, et à qui le dire
#
#  ── POURQUOI ─────────────────────────────────────────────────────────────────
#
#  La CI audite les dépendances (pip-audit, `npm run lint:audit`) À CHAQUE PR —
#  c'est-à-dire quand le code change. Un avis publié ENTRE deux PR n'est vu par
#  personne : une semaine sans lot, c'est une semaine où une faille connue de
#  tous tourne en production sans qu'un seul contrôle ait pu la voir. Depuis
#  2026, les exploitations automatisées suivent les avis publics en heures.
#  Ce workflow rejoue donc chaque nuit, SUR `main` TEL QU'IL TOURNE :
#    1. l'audit Python (le même script que la CI, mêmes exceptions nominatives) ;
#    2. l'audit Node du front (le même `lint:audit`, mêmes exceptions) ;
#    3. l'analyse des QUATRE images publiées pour ce commit (Trivy : paquets du
#       système et des langages, CRITICAL et HIGH corrigeables) — ce que
#       pip-audit et npm ne voient pas : Debian, OpenSSL, Caddy, Node lui-même ;
#    4. la vérification de leur attestation de provenance (Sigstore,
#       `images.yml`) : l'image que les nœuds tirent est bien celle que la CI
#       a construite depuis ce dépôt.
#
#  ── À QUI ────────────────────────────────────────────────────────────────────
#
#  Un workflow rouge que personne ne regarde est un contrôle sans destinataire
#  (`standards/07` §1). Le résultat va dans UNE issue du dépôt, « Veille sécurité
#  nocturne », étiquette `securite` : ouverte au premier rouge, commentée chaque
#  nuit tant qu'il dure, fermée quand tout est revenu au vert — jamais une
#  issue par nuit, jamais un rouge silencieux. Les décisions sont pures et
#  auto-testées ; `gh` ne sert qu'à la fin.
#
#  Usage (dans le workflow) :
#    bash scripts/ci/veille-securite.sh etape <dossier> <nom> <code> <sortie>
#    bash scripts/ci/veille-securite.sh rapport <dossier>
#    bash scripts/ci/veille-securite.sh --selftest
# =============================================================================
set -uo pipefail

VEILLE_TITRE="Veille sécurité nocturne"
VEILLE_ETIQUETTE="securite"
#: Les étapes attendues, dans l'ordre du rapport. Une étape ABSENTE du dossier
#: (jamais lancée, workflow interrompu) est un rouge : INCONNU n'est pas vert.
VEILLE_ETAPES="python node trivy-api trivy-front trivy-caddy trivy-whatsapp-bridge attestation"
#: Combien de lignes de la sortie d'une étape rouge entrent dans l'issue.
VEILLE_LIGNES=40

# ── Décisions PURES ──────────────────────────────────────────────────────────

#  $1 = le dossier des résultats (<nom>.rc, <nom>.txt) → le nombre d'étapes
#  rouges ou absentes, et leurs noms sur stdout (« python trivy-api »).
veille_rouges() {
    local dossier=${1:-} e rc rouges=""
    for e in $VEILLE_ETAPES; do
        rc=$(cat "$dossier/$e.rc" 2>/dev/null)
        [ "$rc" = 0 ] || rouges="$rouges${rouges:+ }$e"
    done
    printf '%s' "$rouges"
}

#  $1 = le dossier · $2 = le commit audité → le corps Markdown de l'issue ou du commentaire
veille_corps() {
    local dossier=${1:-} sha=${2:-?} e rc etat
    printf '## Veille du %s — `main` à %s\n\n' "$(date -u +%Y-%m-%d)" "${sha:0:12}"
    printf '| Étape | Résultat |\n|---|---|\n'
    for e in $VEILLE_ETAPES; do
        rc=$(cat "$dossier/$e.rc" 2>/dev/null)
        case "$rc" in
            0)  etat="✅ vert" ;;
            '') etat="⚠️ non lancée (INCONNU, jamais vert)" ;;
            *)  etat="❌ rouge (code $rc)" ;;
        esac
        printf '| %s | %s |\n' "$e" "$etat"
    done
    for e in $VEILLE_ETAPES; do
        rc=$(cat "$dossier/$e.rc" 2>/dev/null)
        [ -n "$rc" ] && [ "$rc" != 0 ] || continue
        printf '\n<details><summary>%s — fin de la sortie</summary>\n\n```\n' "$e"
        tail -n "$VEILLE_LIGNES" "$dossier/$e.txt" 2>/dev/null | sed 's/`/'"'"'/g'
        printf '```\n</details>\n'
    done
    printf '\nRègle : `scripts/ci/veille-securite.sh` ; exceptions nominatives : `api/scripts/check_audit_python.py`, `front/audit-exceptions.json`.\n'
}

#  $1 = les rouges (vide : tout vert) · $2 = le numéro de l'issue ouverte (vide : aucune)
#  → ouvrir | commenter | fermer | rien
veille_decision() {
    local rouges=${1:-} issue=${2:-}
    if [ -n "$rouges" ]; then
        [ -n "$issue" ] && echo commenter || echo ouvrir
    else
        [ -n "$issue" ] && echo fermer || echo rien
    fi
}

# ── Les effets de bord (gh), isolés ──────────────────────────────────────────
veille_issue_ouverte() {
    gh issue list --state open --label "$VEILLE_ETIQUETTE" --search "in:title \"$VEILLE_TITRE\"" \
        --json number --jq '.[0].number // empty' 2>/dev/null
}

veille_rapport() { # $1 = dossier
    local dossier=${1:-} sha rouges issue corps decision
    sha=$(git rev-parse HEAD 2>/dev/null)
    rouges=$(veille_rouges "$dossier")
    issue=$(veille_issue_ouverte)
    corps=$(veille_corps "$dossier" "$sha")
    decision=$(veille_decision "$rouges" "$issue")
    echo "rouges : ${rouges:-aucune} · issue ouverte : ${issue:-aucune} → $decision"
    case "$decision" in
        ouvrir)
            gh label create "$VEILLE_ETIQUETTE" --color B60205 --description "Sécurité : vulnérabilité, durcissement, veille" --force >/dev/null 2>&1 || true
            gh issue create --title "$VEILLE_TITRE : $rouges" --label "$VEILLE_ETIQUETTE" --body "$corps" ;;
        commenter)
            gh issue comment "$issue" --body "$corps" ;;
        fermer)
            gh issue comment "$issue" --body "$corps"$'\n\n'"Tout est revenu au vert : fermée par la veille."
            gh issue close "$issue" --reason completed ;;
        rien) ;;
    esac
    [ -z "$rouges" ]
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; }; }
    d=$(mktemp -d)
    for e in $VEILLE_ETAPES; do echo 0 > "$d/$e.rc"; echo "ok" > "$d/$e.txt"; done
    t "tout vert → aucun rouge" "" "$(veille_rouges "$d")"
    t "tout vert, pas d'issue → rien" rien "$(veille_decision "" "")"
    t "tout vert, issue ouverte → fermer" fermer "$(veille_decision "" 42)"
    echo 1 > "$d/python.rc"; printf 'ligne1\nPYSEC-2026-1 cryptography\n' > "$d/python.txt"
    rm -f "$d/trivy-caddy.rc"
    t "un rouge et une étape absente → les deux, dans l'ordre" "python trivy-caddy" "$(veille_rouges "$d")"
    t "des rouges, pas d'issue → ouvrir" ouvrir "$(veille_decision "python" "")"
    t "des rouges, issue ouverte → commenter" commenter "$(veille_decision "python" 42)"
    corps=$(veille_corps "$d" 0123456789abcdef)
    t "corps : le commit, court" 1 "$(grep -c '`main` à 0123456789ab$' <<< "$corps")"
    t "corps : une ligne par étape" 7 "$(grep -c '^| [a-z-]* | ' <<< "$corps")"
    t "corps : le rouge et son code" 1 "$(grep -c '^| python | ❌ rouge (code 1) |$' <<< "$corps")"
    t "corps : l'étape absente n'est pas verte" 1 "$(grep -c '^| trivy-caddy | ⚠️ non lancée' <<< "$corps")"
    t "corps : la sortie du rouge, repliée" 1 "$(grep -c '^PYSEC-2026-1 cryptography$' <<< "$corps")"
    t "corps : rien de la sortie d'une étape verte" 0 "$(grep -c '^ok$' <<< "$corps")"
    #  L'étape, telle que le workflow l'écrit.
    bash "$0" etape "$d" node 2 "npm audit : 1 high" >/dev/null
    t "etape : code et sortie écrits" "2|npm audit : 1 high" "$(cat "$d/node.rc")|$(cat "$d/node.txt")"
    #  Le rapport, gh remplacé par un témoin : ouvrir, commenter, fermer.
    #  Le témoin ne rend que les quatre premiers mots : le titre entier est un seul mot.
    gh() { case "${2:-}" in list) : ;; *) echo "gh $1 $2 ${3:-} ${4:-}" ;; esac; }
    git() { echo abcdef0123456789; }
    t "rapport : rouges sans issue → une issue créée, étiquetée" 1 \
      "$(veille_rapport "$d" | grep -c "^gh issue create --title $VEILLE_TITRE : python node trivy-caddy"'$')"
    gh() { case "$1" in issue) case "$2" in list) echo 42 ;; *) echo "gh $1 $2 ${3:-}" ;; esac ;; esac; }
    t "rapport : rouges et issue 42 → commentée, pas fermée" "1|0" \
      "$(s=$(veille_rapport "$d"); echo "$(grep -c '^gh issue comment 42' <<< "$s")|$(grep -c 'close' <<< "$s")")"
    for e in $VEILLE_ETAPES; do echo 0 > "$d/$e.rc"; done
    t "rapport : tout vert et issue 42 → commentée puis fermée" "1|1" \
      "$(s=$(veille_rapport "$d"); echo "$(grep -c '^gh issue comment 42' <<< "$s")|$(grep -c '^gh issue close 42' <<< "$s")")"
    t "rapport : le code de sortie dit les rouges" "0" "$(veille_rapport "$d" >/dev/null; echo $?)"
    echo 1 > "$d/attestation.rc"
    t "rapport : un rouge → code 1" "1" "$(veille_rapport "$d" >/dev/null; echo $?)"
    unset -f gh git
    rm -rf "$d"
    [ "$st" -eq 0 ] && echo "veille-securite : tous les cas passent."
    exit "$st"
fi

case "${1:-}" in
    etape)
        #  $2 dossier · $3 nom · $4 code · $5 sortie (texte)
        mkdir -p "$2" && printf '%s\n' "$4" > "$2/$3.rc" && printf '%s\n' "$5" > "$2/$3.txt" ;;
    rapport)
        veille_rapport "$2" ;;
    *)
        echo "usage : $0 etape <dossier> <nom> <code> <sortie> | rapport <dossier> | --selftest" >&2; exit 2 ;;
esac
