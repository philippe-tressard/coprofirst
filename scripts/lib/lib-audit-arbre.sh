#!/bin/bash
# =============================================================================
#  lib-audit-arbre.sh — S1 : l'arbre déployé que ROOT exécute est-il celui du dépôt ?
#
#  Module SOURCÉ (mode 100644) par `audit-securite.sh` (audit de sécurité
#  nocturne). Jamais exécuté par un cron.
#  Autotest : bash scripts/lib/lib-audit-arbre.sh --selftest
#
#  ── POURQUOI ─────────────────────────────────────────────────────────────────
#
#  Les crons de root (`bascule.sh`, `maintenance.sh`, `check-reliability.sh`,
#  `health-watch.sh`) exécutent des scripts qui vivent dans `/opt/5hostachy`, un
#  arbre que POSSÈDE le compte de déploiement et que `auto-deploy.sh` réécrit
#  toutes les cinq minutes. C'est l'escalade décrite par `standards/03` §8 bis :
#  qui écrit dans cet arbre fait exécuter ce qu'il veut par root, la nuit même.
#  Le modèle de déploiement le veut ainsi (arbitrage du 09/08/2026) ; ce qui
#  manquait, c'est un contrôle qui DISE qu'un fichier de l'arbre n'est plus
#  celui du dépôt.
#
#  C7 compare le COMMIT de l'arbre à `origin/main` — un fichier modifié sur
#  place, ou ajouté à côté, laisse HEAD intact et C7 vert. Ce contrôle lit ce
#  que git sait de l'ARBRE DE TRAVAIL (`git status --porcelain`), sur les
#  seules zones que root exécute ou monte : scripts, points d'entrée, compose,
#  Caddyfile, Dockerfiles, hooks. Un fichier modifié, ajouté ou retiré dans ces
#  zones est un FAIL : rien, dans le fonctionnement normal, n'y écrit —
#  `auto-deploy.sh` fait un `git pull`, qui laisse l'arbre propre.
#
#  Ce qu'il ne voit pas, et qui est mesuré ailleurs : un commit poussé sur
#  `main` par un compte GitHub compromis (la protection de branche et la CI),
#  l'image d'un conteneur (S4 lit son étiquette de révision).
#
#  Fonctions PURES : un texte entre, un verdict sort —
#    CONFORME · ECART:<ce qui diffère> · INCONNU:<pourquoi>
# =============================================================================

#: Les zones de l'arbre déployé que ROOT exécute, monte ou source — chemins
#: relatifs à la racine du dépôt, tels que `git status -- <zones>` les prend.
#: `api/` et `front/` n'y sont pas : leur code entre dans l'image par la CI, pas
#: depuis cet arbre (#1758) — sauf leurs Dockerfile, que le secours construit.
ARBRE_ZONES_ROOT="${ARBRE_ZONES_ROOT:-scripts infra deploiement .githooks docker-compose.yml Caddyfile api/Dockerfile api/start.sh front/Dockerfile whatsapp-bridge/Dockerfile}"

#  $1 = sortie de `git status --porcelain=v1 --untracked-files=all -- <zones>`
#  $2 = code de retour de git (vide : non lancé)
#  → CONFORME | ECART:modifiés=[…] ajoutés=[…] retirés=[…] | INCONNU:…
arbre_verdict() {
    local statut=${1:-} rc=${2:-} ligne xy chemin modifies="" ajoutes="" retires=""
    [ -n "$rc" ] || { echo "INCONNU:git non lancé"; return 0; }
    [ "$rc" = 0 ] || { echo "INCONNU:git status rend $rc (dépôt illisible par root ?)"; return 0; }
    [ -n "$statut" ] || { echo CONFORME; return 0; }
    while IFS= read -r ligne; do
        [ -n "$ligne" ] || continue
        xy=${ligne:0:2}; chemin=${ligne:3}
        #  Un renommage s'écrit « R  ancien -> nouveau » : on garde la cible.
        chemin=${chemin##* -> }
        case "$xy" in
            '??')          ajoutes="$ajoutes${ajoutes:+,}$chemin" ;;
            *D*)           retires="$retires${retires:+,}$chemin" ;;
            *)             modifies="$modifies${modifies:+,}$chemin" ;;
        esac
    done <<< "$statut"
    printf 'ECART:'
    [ -z "$modifies" ] || printf 'modifiés=[%s] ' "$modifies"
    [ -z "$ajoutes" ]  || printf 'ajoutés=[%s] ' "$ajoutes"
    [ -z "$retires" ]  || printf 'retirés=[%s] ' "$retires"
    echo
}

#  Le nombre de chemins qu'un verdict ECART nomme (pour la ligne de constat).
arbre_compte() { # $1 = verdict
    case "${1:-}" in
        ECART:*) printf '%s' "${1#ECART:}" | grep -o '\[[^]]*\]' | tr -d '[]' | tr ',' '\n' | grep -c . ;;
        *)       echo 0 ;;
    esac
}

# ── La lecture (effet de bord : git, en lecture seule) ───────────────────────
#  $1 = le dépôt. Écrit la sortie de git, rend son code — INCONNU si l'arbre
#  n'est pas un dépôt. `-c safe.directory` : root lit un arbre qui ne lui
#  appartient pas (C5, « dubious ownership »).
# shellcheck disable=SC2086  # ARBRE_ZONES_ROOT est une liste, coupée exprès
arbre_lire() {
    git -C "${1:-/opt/5hostachy}" -c safe.directory='*' status --porcelain=v1 --untracked-files=all \
        -- $ARBRE_ZONES_ROOT 2>/dev/null
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
audit_arbre_selftest() {
    local st=0
    t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; }; }
    echo "== self-test lib-audit-arbre (S1) =="
    t "arbre propre" CONFORME "$(arbre_verdict "" 0)"
    t "un script modifié sur place" "ECART:modifiés=[scripts/exploitation/bascule.sh] " \
      "$(arbre_verdict " M scripts/exploitation/bascule.sh" 0)"
    t "un fichier ajouté à côté" "ECART:ajoutés=[scripts/lib/lib-x.sh] " \
      "$(arbre_verdict "?? scripts/lib/lib-x.sh" 0)"
    t "un point d'entrée retiré" "ECART:retirés=[infra/points-entree/cron-root.crontab] " \
      "$(arbre_verdict " D infra/points-entree/cron-root.crontab" 0)"
    t "les trois à la fois, dans l'ordre" \
      "ECART:modifiés=[Caddyfile,docker-compose.yml] ajoutés=[scripts/x.sh] retirés=[.githooks/pre-push] " \
      "$(arbre_verdict $' M Caddyfile\n?? scripts/x.sh\n D .githooks/pre-push\nMM docker-compose.yml' 0)"
    t "un renommage nomme la cible" "ECART:modifiés=[scripts/b.sh] " \
      "$(arbre_verdict "R  scripts/a.sh -> scripts/b.sh" 0)"
    t "compte des chemins" 4 "$(arbre_compte "ECART:modifiés=[a,b] ajoutés=[c] retirés=[d] ")"
    t "compte d'un CONFORME" 0 "$(arbre_compte CONFORME)"
    #  LE CAS ZÉRO : git muet ou en échec n'est jamais « propre ».
    t "git non lancé" "INCONNU:git non lancé" "$(arbre_verdict "" "")"
    t "git en échec (dépôt illisible)" INCONNU "$(arbre_verdict "" 128 | cut -d: -f1)"
    #  La lecture réelle, sur un dépôt jetable : un fichier modifié est vu.
    local d; d=$(mktemp -d)
    ( cd "$d" && git init -q . && git config user.email a@b && git config user.name a \
      && mkdir -p scripts infra && echo a > scripts/x.sh && echo b > infra/y && echo c > autre \
      && git add -A && git commit -qm init && echo z >> scripts/x.sh && echo n > infra/neuf && echo m >> autre )
    local s; s=$(arbre_lire "$d"); local rc=$?
    t "lecture réelle : modifié + ajouté dans les zones, « autre » ignoré" \
      "ECART:modifiés=[scripts/x.sh] ajoutés=[infra/neuf] " "$(arbre_verdict "$s" "$rc")"
    local d2; d2=$(mktemp -d)
    t "lecture réelle : arbre qui n'est pas un dépôt → INCONNU" INCONNU \
      "$(s=$(arbre_lire "$d2"); arbre_verdict "$s" "$?" | cut -d: -f1)"
    rm -rf "$d" "$d2"
    [ "$st" -eq 0 ] && echo "lib-audit-arbre : tous les cas passent."
    return "$st"
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    audit_arbre_selftest; exit $?
fi
