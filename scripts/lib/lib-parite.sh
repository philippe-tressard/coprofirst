#!/bin/bash
# =============================================================================
#  lib-parite.sh — Parité de CODE ≠ parité d'IMAGES (#511)
#
#  ## Le fait que ce module rend visible
#
#  Tous les contrôles du projet — le point 10 du pré-check, la série C de
#  check-reliability, la phase 0 de bascule.sh — comparent le `git rev-parse` des
#  deux nœuds. C'est la parité de **code**.
#
#  Or ce n'est pas le code qui sert : ce sont les **images Docker**. Entre les
#  deux il y a un `docker compose build`, et il peut échouer — saturation mémoire
#  pendant le build du front sur un RPi, c'est la cause fréquente.
#
#  🔴 L'état qui en résulte est le plus trompeur du système : parité git VERTE,
#  images périmées. Tous les contrôles disent OK, et un failover sert l'ancienne
#  version. C'est le risque nommé par #448 puis isolé par #511 :
#
#  > « Reste le cas où son build échoue : une alerte part, mais elle *prévient*
#  >   sans *empêcher*. »
#
#  ## Le remède : un fait, pas une déduction
#
#  `auto-deploy.sh` écrit `$REPO/.images-construites` avec le hash du commit
#  **pour lequel le build a réussi** — et ne l'écrit pas quand il échoue. Comparer
#  ce fichier au `git rev-parse HEAD` répond à la seule question qui compte :
#  *« les images que je m'apprête à démarrer correspondent-elles au code que je
#  crois servir ? »*
#
#  ⚠️ Un marqueur absent ne vaut pas « périmé » et ne vaut surtout pas « à
#  jour » : il vaut INCONNU. Un nœud dont le marqueur n'a jamais été écrit — une
#  installation antérieure à ce module — n'a rien prouvé, ni dans un sens ni dans
#  l'autre (`standards/04` §1).
#
#  Test : bash scripts/lib/lib-parite.sh --selftest
# =============================================================================

# ── Fonction PURE — aucun fichier, aucun docker, aucun réseau ────────────────
# Args : hash_git  hash_images
#   hash_git    : `git rev-parse HEAD` du dépôt local (vide si indéterminable)
#   hash_images : contenu de `.images-construites` (vide si absent)
# Échoit : "a-jour" | "images-perimees" | "inconnu"
verdict_parite_servie() {
    local git="${1:-}" images="${2:-}"
    #  Sans l'un OU l'autre, on ne peut RIEN conclure. Répondre « a-jour » ferait
    #  d'un contrôle aveugle un contrôle rassurant, ce qui est pire que pas de
    #  contrôle du tout.
    [ -z "$git" ] && { echo inconnu; return; }
    [ -z "$images" ] && { echo inconnu; return; }
    case "$(memes_hachages "$git" "$images")" in
        oui) echo "a-jour" ;;
        non) echo "images-perimees" ;;
        *)   echo inconnu ;;
    esac
}

# ── Deux hachages git désignent-ils le MÊME commit ? ─────────────────────────
# Args : hachage_a  hachage_b  → "oui" | "non" | "inconnu"
#
#  Comparaison sur le PRÉFIXE COMMUN : `git rev-parse HEAD` rend 40 caractères,
#  `--short` en rend 7 à 12 **selon la taille du dépôt**. Comparer les chaînes
#  entières rendrait « périmé » un nœud parfaitement à jour, et ce faux positif
#  ferait désarmer le contrôle en une semaine.
#
#  🔴 Cette règle était écrite ICI et nulle part ailleurs, alors que deux
#  fonctions comparent des hachages git pour la même raison (#854). Le point 10
#  du pré-check, resté sur un `=`, était en ÉCART **permanent** : les deux nœuds
#  rendaient `ee33a715` et `ee33a71`, le même commit abrégé sur 8 et 7. Son
#  détail excusait l'écart d'avance (« le standby s'aligne seul sous 5 min »), si
#  bien qu'un standby réellement en retard aurait affiché exactement la même
#  ligne. Un contrôle qui crie toujours ne dit plus rien.
#
#  Moins de 7 caractères communs : on ne conclut pas. Une abréviation aussi
#  courte n'identifie pas un commit, et deux préfixes de 4 qui coïncident ne
#  prouveraient rien.
memes_hachages() {
    local a="${1:-}" b="${2:-}"
    [ -z "$a" ] && { echo inconnu; return; }
    [ -z "$b" ] && { echo inconnu; return; }
    local n="${#b}"
    [ "$n" -gt "${#a}" ] && n="${#a}"
    [ "$n" -lt 7 ] && { echo inconnu; return; }
    [ "${a:0:$n}" = "${b:0:$n}" ] && echo oui || echo non
}

# ── Faut-il (re)construire les images ? ──────────────────────────────────────
#
# 🔴 LE TROU DU 22/09/2026 (#1131). `auto-deploy.sh` décidait sur le CODE :
# « mon HEAD vaut celui d'origin, donc rien à faire ». Après la bascule de
# 02:00, le standby avait le bon code et des images d'une version antérieure —
# et il l'a répété toutes les cinq minutes pendant quatre heures :
#
#     [06:13:01] Aucun changement (ed26d1d) — rien à déployer (aligner).
#
# Ce sont les IMAGES qu'un failover démarre. La question n'est donc pas « ai-je
# le bon code ? » mais « mes images sont-elles bâties sur le code que j'ai ? ».
# Les deux valeurs étaient déjà écrites côte à côte ; personne ne les comparait.
#
# ⚠️ Et SANS réintroduire le battement (`project_battement_auto_deploy`) : un
# build qui échoue laisse le marqueur en arrière, donc on retenterait toutes
# les cinq minutes. D'où le troisième argument — le sha pour lequel une
# tentative a DÉJÀ échoué. On ne réessaie pas le même, on attend le suivant.
#
# $1 = HEAD local · $2 = marqueur des images · $3 = sha d'un échec déjà connu
# → reconstruire | tirer | rien
#
# `tirer` (#3033, 24/11/2026) : un échec connu sur CE code interdit de le
# reconstruire, jamais de TIRER les images de la CI, qui ne coûte rien et peut
# réussir — le 23/11, elles ont été publiées 9 min après l'abandon de l'attente,
# et le nœud est resté bloqué jusqu'à un geste à la main.
verdict_reconstruction() {
    local git="${1:-}" images="${2:-}" echoue="${3:-}"
    #  Sans HEAD, on ne sait rien : ne rien faire vaut mieux qu'un build à
    #  l'aveugle, et le point 18 du pré-check le dira de toute façon.
    #  🔴 Des `if`, PAS des `[ … ] && { … }` : sous le `set -e` de
    #  `auto-deploy.sh`, une condition fausse en dernière commande fait sortir
    #  le script — il est mort en silence sur les DEUX nœuds le 22/09/2026,
    #  plus aucun déploiement automatique pendant une demi-heure.
    #
    #  ⚠️ La leçon était déjà écrite à dix lignes d'ici, dans `auto-deploy.sh` :
    #  « Pas de `LOCK=non; [ -f … ] && LOCK=oui` : sous `set -e`, un test faux
    #  fait sortir ». Je l'ai refaite le jour même où je la lisais.
    if [ -z "$git" ]; then
        #  Sans HEAD, on ne sait rien : ne rien faire vaut mieux qu'un build à
        #  l'aveugle, et le point 18 du pré-check le dira de toute façon.
        echo rien
        return
    fi
    #  Une tentative a déjà échoué sur CE code : le refaire toutes les cinq
    #  minutes ne le fera pas réussir, et la trace est dans le journal. Les
    #  images de la CI, elles, se tirent encore — sauf si elles valent déjà le code.
    if [ -n "$echoue" ] && [ "$(memes_hachages "$git" "$echoue")" = oui ]; then
        if [ "$(verdict_parite_servie "$git" "$images")" = a-jour ]; then
            echo rien
        else
            echo tirer
        fi
        return
    fi
    case "$(verdict_parite_servie "$git" "$images")" in
        a-jour) echo rien ;;
        #  `inconnu` — marqueur absent — vaut reconstruire : c'est l'état d'un
        #  nœud dont on ne peut PAS affirmer que ses images valent son code.
        *)      echo reconstruire ;;
    esac
}

# ── Lecture du marqueur (effet de bord : lit un fichier) ─────────────────────
# $1 = racine du dépôt → le hash pour lequel les images ont été construites, ou ""
hash_images_construites() {
    local f="${1:-}/.images-construites"
    [ -r "$f" ] || { echo ""; return; }
    tr -d ' \t\r\n' < "$f"
}

# ── Lecture du sha d'un build ÉCHOUÉ ─────────────────────────────────────────
#
# 🔴 Symétrique de `hash_images_construites`, et pour la même raison : un
# `$(cat fichier-absent | tr …)` sous `set -o pipefail` prend le code d'échec de
# `cat`, et `set -e` tue le script appelant. C'est ce qui a arrêté `auto-deploy`
# sur les DEUX nœuds le 22/09/2026 — une demi-heure sans déploiement, sans une
# ligne de journal, parce que le fichier d'échec n'existait pas encore.
#
# ⚠️ Le test `-r` d'abord : il ne lit que ce qui est lisible, et rend le vide
# sinon. Aucun pipe, donc rien à faire échouer.
hash_echec_build() {
    local f="${1:-}/.images-echec"
    [ -r "$f" ] || { echo ""; return; }
    tr -d ' 	
' < "$f"
}

# ── Écriture du sha d'un build échoué ────────────────────────────────────────
# $1 = racine du dépôt, $2 = hash dont le build vient d'échouer
marquer_echec_build() {
    printf '%s
' "${2:-}" > "${1:-}/.images-echec" 2>/dev/null || true
}

# ── Écriture du marqueur — appelée UNIQUEMENT après un build réussi ──────────
# $1 = racine du dépôt, $2 = hash construit
marquer_images_construites() {
    printf '%s\n' "${2:-}" > "${1:-}/.images-construites" 2>/dev/null || true
}

# ── Construire les images : UNE porte, et elle porte le commit (#1684) ───────
#
# 🔴 Le front grave `GIT_HASH` dans son bundle (`front/Dockerfile`, défaut
# `dev`) : un build lancé sans l'exporter sert un front qui se dit « dev ».
# Quatre builds l'écrivaient chacun : le déploiement et l'alignement
# d'`auto-deploy` l'exportaient, son RATTRAPAGE (#1131) et la synchronisation
# du pair par `bascule.sh` (phase 0) ne l'exportaient pas. Le commit se lit ici,
# dans le dépôt courant, au moment du build — jamais transmis par l'appelant.
# Les arguments passent à `docker compose build` (`--quiet`, `--no-cache`,
# services). 🔒 api/tests/test_construction_images_porte_unique.py
#
# La release (`front/package.json`) part avec : l'API la publie dans `GET /config`
# (#2833). Illisible, elle reste vide — le build n'en dépend jamais.
# 🔒 api/tests/test_version_logicielle_servie.py
exporter_git_hash() {
    GIT_HASH=$(git rev-parse --short HEAD) || return 1
    export GIT_HASH
    VERSION_IMAGE=$(sed -nE 's/^[[:space:]]*"version":[[:space:]]*"([^"]+)".*/\1/p' front/package.json 2>/dev/null | head -1)
    export VERSION_IMAGE
}
construire_images() {
    exporter_git_hash || return 1
    docker compose build "$@"
}

# ── Obtenir les images : les TIRER de la CI, construire en secours (#1758) ──
# `obtenir_images` est la porte d'auto-deploy et de la bascule ; elle appelle
# `construire_images` quand les images de la CI manquent. Elle vit dans son
# module, avec sa décision et son self-test.
# shellcheck source=lib-images-ci.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib-images-ci.sh"

# ── Démarrer les conteneurs : UNE porte, elle aussi (#1697) ──────────────────
#
# 🔴 `docker-compose.yml` pose l'étiquette `git.hash=${GIT_HASH:-dev}` du front
# AU `up`, pas au build : un `up -d` lancé sans `GIT_HASH` étiquette le front
# « dev » — bascule (phase 5 et rollback), failover, garde de démarrage,
# relance de l'API par la maintenance. `MaJ-Hostachy.sh` lit cette étiquette
# pour choisir ce qu'il reconstruit, et le `up` suivant qui l'exporte recrée le
# front pour une étiquette seulement.
#
# ⚠️ Chemin de PRODUCTION critique : la porte ne bloque JAMAIS le démarrage. Un
# commit illisible rend le front « dev » comme avant, il n'empêche pas le site de
# revenir. Les arguments passent à `docker compose up -d` (un service, par ex.).
# 🔒 api/tests/test_construction_images_porte_unique.py
demarrer_conteneurs() {
    exporter_git_hash 2>/dev/null || true
    docker compose up -d "$@"
}

# ── Self-test (aucun effet de bord) ──────────────────────────────────────────
#
# 🔴 `${BASH_SOURCE[0]}` = `$0` : le bloc ne s'exécute QUE si ce fichier est
# lancé, jamais s'il est sourcé. Sans cette garde, un script qui fait
# `source lib-parite.sh` en ayant reçu `--selftest` verrait ses propres
# positionnels hérités ici, exécuterait CE self-test et sortirait — sa propre
# batterie ne tournerait jamais, et la CI serait verte en mesurant autre chose.
#
# Constaté en écrivant #511 : `health-watch.sh --selftest` s'est mis à afficher
# les huit cas de la parité au lieu de ses cinq cas de `decide_failover`. C'est
# aussi pourquoi `lib-role.sh` est sourcé APRÈS le bloc de self-test de ses
# appelants — un contournement, là où la garde est le remède.
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    fail=0
    check() { # description attendu git images
        local desc="$1" exp="$2"; shift 2
        local got; got=$(verdict_parite_servie "$@")
        if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
        else echo "FAIL  $desc  attendu=$exp obtenu=$got"; fail=1; fi
    }
    LONG=a1b2c3d4e5f60718293a4b5c6d7e8f9012345678
    AUTRE=9876543210fedcba9876543210fedcba98765432

    echo "== self-test lib-parite.verdict_parite_servie =="
    check "images construites sur le commit courant"     "a-jour"          "$LONG" "$LONG"
    check "marqueur court (git --short) mais concordant" "a-jour"          "$LONG" "a1b2c3d"
    check "build échoué : images restées en arrière"     "images-perimees" "$LONG" "$AUTRE"
    check "marqueur court divergent"                     "images-perimees" "$LONG" "9876543"
    # 🔴 Les trois cas qui doivent rendre INCONNU, jamais OK.
    check "marqueur absent (nœud jamais construit)"      "inconnu"         "$LONG" ""
    check "git indéterminable (dépôt illisible)"         "inconnu"         ""      "$LONG"
    check "les deux indéterminables"                     "inconnu"         ""      ""
    #  Un marqueur tronqué ne prouve rien : deux commits partagent facilement
    #  quatre caractères. En dessous de sept, on refuse de conclure plutôt que de
    #  déclarer une parité sur une coïncidence.
    check "marqueur trop court pour trancher"            "inconnu"         "$LONG" "a1b2"

    # ── verdict_reconstruction (#1131) ───────────────────────────────────────
    #
    # 🔴 Le premier cas est CELUI DU 22/09/2026 : le standby avait le bon code
    # et des images d'avant, et `auto-deploy` concluait « rien à déployer ».
    checkr() {
        local desc="$1" exp="$2"; shift 2
        local got; got=$(verdict_reconstruction "$@")
        if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
        else echo "FAIL  $desc  attendu=$exp obtenu=$got"; fail=1; fi
    }
    echo "== self-test lib-parite.verdict_reconstruction =="
    checkr "images d'une version antérieure (le cas du 22/09)" "reconstruire" "$LONG" "$AUTRE" ""
    checkr "marqueur absent : on ne peut PAS affirmer la parité" "reconstruire" "$LONG" "" ""
    checkr "images bâties sur le code courant : ne rien faire"   "rien"        "$LONG" "$LONG" ""
    checkr "marqueur court concordant : ne rien faire"           "rien"        "$LONG" "a1b2c3d" ""
    #  ⚠️ Le battement : une tentative a échoué sur CE code, on ne la refait pas
    #  toutes les cinq minutes (`project_battement_auto_deploy`).
    checkr "échec déjà connu sur ce sha : tirer seulement (#3033)" "tirer"     "$LONG" "$AUTRE" "$LONG"
    checkr "échec connu sur un AUTRE sha : on reconstruit"       "reconstruire" "$LONG" "$AUTRE" "$AUTRE"
    checkr "échec connu, images déjà au code : rien"             "rien"        "$LONG" "$LONG" "$LONG"
    checkr "sans HEAD, aucun build à l'aveugle"                  "rien"        ""      "$AUTRE" ""

    # ── 🔴 SOUS `set -e`, et c'est le cas qui manquait (22/09/2026) ──────────
    #
    # Ces fonctions sont appelées par `auto-deploy.sh`, qui tourne en
    # `set -euo pipefail`. Le self-test, lui, les appelait dans un `$( )` sans
    # `set -e` : une sortie prématurée y était INVISIBLE.
    #
    # Une écriture en `[ … ] && { … }` a donc passé tous les cas ci-dessus et
    # tué le script sur les deux nœuds en production — plus aucun déploiement
    # automatique pendant une demi-heure, sans une ligne de journal.
    #
    # ⚠️ Le sous-shell relit CE fichier : il éprouve donc le code tel qu'il
    # sera sourcé, pas une copie.
    #  🔴 LA LECTURE d'un fichier ABSENT, sous `pipefail` (22/09/2026).
    #
    #  `VAR=$(cat fichier-absent | tr …)` prend le code d'échec de `cat`, et
    #  `set -e` tue le script appelant. `auto-deploy` est mort là-dessus sur les
    #  deux nœuds — le fichier `.images-echec` n'existait simplement pas encore.
    #
    #  ⚠️ Aucun des cas ci-dessus ne pouvait le voir : ils passent des CHAÎNES,
    #  et le défaut était dans la lecture du fichier. Un contrôle ne mord que
    #  sur ce qu'il exerce.
    VIDE=$(mktemp -d)
    for lecture in hash_images_construites hash_echec_build; do
        if bash -euo pipefail -c "source '${BASH_SOURCE[0]}'; $lecture '$VIDE' >/dev/null" 2>/dev/null; then
            echo "PASS  $lecture sur un dépôt sans marqueur ne fait pas sortir"
        else
            echo "FAIL  $lecture SORT sous set -e quand le fichier est absent"
            fail=1
        fi
    done
    rmdir "$VIDE" 2>/dev/null || true

    echo "== self-test : survie sous set -euo pipefail =="
    for cas in "$LONG $LONG" "$LONG $AUTRE" "$LONG ''" "'' ''"; do
        if bash -euo pipefail -c "source '${BASH_SOURCE[0]}'; verdict_reconstruction $cas >/dev/null; echo survecu" >/dev/null 2>&1; then
            echo "PASS  verdict_reconstruction($cas) ne fait pas sortir"
        else
            echo "FAIL  verdict_reconstruction($cas) SORT sous set -e — le script appelant meurt"
            fail=1
        fi
    done

    # ── construire_images exporte le commit au build (#1684) ─────────────────
    #  Docker simulé : il rend la valeur de GIT_HASH qu'il VOIT dans son
    #  environnement — ce que `docker compose build` transmet au Dockerfile.
    echo "== self-test lib-parite.construire_images =="
    DEPOT=$(mktemp -d)
    git -C "$DEPOT" init -q && git -C "$DEPOT" -c user.name=t -c user.email=t@example.org \
        commit -q --allow-empty -m t
    ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
    vu=$(cd "$DEPOT" && unset GIT_HASH && bash -c "source '$ICI'
        docker() { echo \"\$* GIT_HASH=\$(printenv GIT_HASH)\"; }
        construire_images --quiet")
    attendu="compose build --quiet GIT_HASH=$(git -C "$DEPOT" rev-parse --short HEAD)"
    if [ "$vu" = "$attendu" ]; then echo "PASS  le build voit le commit du dépôt  → $vu"
    else echo "FAIL  attendu « $attendu », obtenu « $vu »"; fail=1; fi

    # ── demarrer_conteneurs porte le commit, et ne bloque jamais (#1697) ─────
    echo "== self-test lib-parite.demarrer_conteneurs =="
    vu=$(cd "$DEPOT" && unset GIT_HASH && bash -c "source '$ICI'
        docker() { echo \"\$* GIT_HASH=\$(printenv GIT_HASH)\"; }
        demarrer_conteneurs api")
    attendu="compose up -d api GIT_HASH=$(git -C "$DEPOT" rev-parse --short HEAD)"
    if [ "$vu" = "$attendu" ]; then echo "PASS  le up voit le commit du dépôt  → $vu"
    else echo "FAIL  attendu « $attendu », obtenu « $vu »"; fail=1; fi
    #  Hors dépôt git : le commit est illisible, le démarrage a lieu quand même.
    HORS=$(mktemp -d)
    vu=$(cd "$HORS" && unset GIT_HASH && bash -euo pipefail -c "source '$ICI'
        docker() { echo \"\$*\"; }
        demarrer_conteneurs; echo survecu" 2>/dev/null | paste -sd'|')
    if [ "$vu" = "compose up -d|survecu" ]; then echo "PASS  commit illisible : le up part quand même"
    else echo "FAIL  commit illisible : attendu « compose up -d|survecu », obtenu « $vu »"; fail=1; fi
    rmdir "$HORS" 2>/dev/null || true
    rm -rf "$DEPOT"

    [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $fail
fi
