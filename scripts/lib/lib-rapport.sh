#!/bin/bash
# =============================================================================
#  lib-rapport.sh — Rapport d'exécution d'une tâche planifiée (module à sourcer)
#
#  POURQUOI ce module existe (04/08/2026) :
#    `maintenance.sh` savait rendre compte à l'application ; `bascule.sh`, non.
#    Résultat : la ligne « Bascule actif/standby » de l'écran Admin → Maintenance
#    était rouge « Jamais exécutée » EN PERMANENCE, alors que la bascule tournait
#    parfaitement chaque nuit. Un rouge permanent n'apprend rien et, pire, ne
#    peut plus rien signaler : si la bascule s'arrêtait vraiment, l'écran serait
#    identique. C'est le « battement manquant » de standards/04 §4, doublé d'une
#    alerte qu'on apprend à ignorer (standards/07 §5).
#
#    Plutôt que de recopier `envoyer_rapport()` dans un second script — ce que la
#    règle de non-duplication interdit, et ce qui aurait figé deux formats de
#    charge utile destinés à diverger — la fonction est extraite ici.
#
#  CE QU'IL CORRIGE AU PASSAGE : l'échappement JSON. L'implémentation d'origine
#    ne protégeait que les guillemets (`sed 's/"/\\"/g'`). Un message d'erreur
#    contenant une barre oblique inverse ou un SAUT DE LIGNE — ce que produit
#    n'importe quelle sortie de commande capturée — fabriquait un JSON invalide :
#    l'API répondait 422, le rapport était perdu, et le script se contentait de
#    journaliser « rapport non enregistré ». Une panne rendue muette par le
#    message d'erreur qui devait la décrire.
#
#  Usage :
#    source /opt/5hostachy/scripts/lib/lib-rapport.sh
#    cle=$(rapport_cle /opt/5hostachy) || exit 0
#    charge=$(rapport_payload bascule rpi1 applicative succes 42 '{"vers":"rpi2"}' '' "$debut" "$fin")
#    rapport_envoyer "http://192.168.1.223" "$cle" "$charge" "bascule"
#
#  Les fonctions de CONSTRUCTION sont pures (aucune E/S) et couvertes par
#  `bash lib-rapport.sh --selftest`, lancé en intégration continue.
#  ⚠ L'autotest couvre la construction, jamais l'envoi : cf. standards/04 §11.
#
#  Ce module est SOURCÉ, jamais exécuté par cron → mode 100644 (le job CI
#  `test-scripts` le vérifie ; un bit d'exécution ici serait trompeur).
# =============================================================================

# ── Échappement d'une chaîne pour insertion dans un littéral JSON ────────────
# Ordre imposé : la barre oblique inverse d'ABORD, sinon on échapperait les
# séquences que l'on vient soi-même d'introduire.
rapport_echapper() { # $1=texte brut → texte sûr pour un "…" JSON
    printf '%s' "${1:-}" \
        | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/ /g' \
        | tr '\n\r' '  ' \
        | sed -e 's/  *$//'
}

# ── Construction de la charge utile ──────────────────────────────────────────
# Pure : ne lit aucun fichier, n'ouvre aucune connexion. `details` est un
# fragment JSON déjà formé (chaque tâche a ses propres chiffres, une colonne par
# chiffre serait ingérable — cf. le commentaire de HistoriqueMaintenance).
rapport_payload() { # tache noeud portee statut duree details erreur debut fin [tokens] [taille_db]
    local tache="${1:-}" noeud="${2:-}" portee="${3:-applicative}" statut="${4:-succes}"
    local duree="${5:-null}" details="${6:-null}" erreur="${7:-}" debut="${8:-}" fin="${9:-}"
    local tokens="${10:-0}" taille="${11:-null}"
    #  🔴 Une date VIDE s'écrit `null`, jamais `""` (#1367, 27/09/2026). Le
    #  battement de début (`maintenance.sh`, #488) n'a pas de fin : `""` était
    #  refusé par le schéma (« input is too short »), 422 chaque dimanche depuis
    #  le 23/08, sur les deux nœuds, sans que rien ne le dise hors du journal.
    local cree="null" terminee="null"
    [ -n "$debut" ] && cree="\"$debut\""
    [ -n "$fin" ] && terminee="\"$fin\""
    printf '{"tache":"%s","noeud":"%s","portee":"%s","statut":"%s","tokens_supprimes":%s,"taille_db_octets":%s,"duree_secondes":%s,"details":%s,"erreur":"%s","cree_le":%s,"terminee_le":%s}' \
        "$tache" "$noeud" "$portee" "$statut" "$tokens" "$taille" "$duree" \
        "${details:-null}" "$(rapport_echapper "$erreur")" "$cree" "$terminee"
}

# ── Un entier pour la charge utile, ou `null` (PURE) ─────────────────────────
# Écrit `taille_db_octets` : la réponse de `psql` (`pg_database_size`) quand elle
# est un entier, `null` (valeur JSON) sinon — réponse vide, message d'erreur,
# retour chariot. Un zéro inventé passerait pour une mesure.
# Code de retour toujours 0 : l'appelant tourne sous `set -e`.
rapport_entier_ou_null() { # $1=valeur brute → entier, ou `null`, sur stdout
    local v="${1:-}"
    v=${v%$'\r'}
    case "$v" in
        ''|*[!0-9]*) printf 'null' ;;
        *)           printf '%s' "$v" ;;
    esac
    return 0
}

# ── Lecture de la clé partagée ───────────────────────────────────────────────
# Codes octaux \042 (guillemet) et \047 (apostrophe) : écrire ces caractères
# littéralement dans un `tr` finit toujours par casser au premier niveau
# d'imbrication supplémentaire.
rapport_cle() { # $1=repo → clé sur stdout, code 1 si absente
    local repo="${1:-/opt/5hostachy}" ligne
    ligne=$(grep -m1 '^MAINTENANCE_KEY=' "$repo/.env" 2>/dev/null) || return 1
    ligne=$(printf '%s' "${ligne#MAINTENANCE_KEY=}" | tr -d '\042\047\r')
    [ -n "$ligne" ] || return 1
    printf '%s' "$ligne"
}

# ── Envoi ────────────────────────────────────────────────────────────────────
# Ne fait JAMAIS échouer l'appelant : quand cette fonction s'exécute, le travail
# a déjà eu lieu. Perdre le rapport ne doit pas transformer un succès en échec.
rapport_envoyer() { # $1=url_base $2=clé $3=charge $4=libellé
    local base="${1:-}" cle="${2:-}" charge="${3:-}" libelle="${4:-rapport}" http
    if [ -z "$base" ] || [ -z "$cle" ]; then
        log "  ⚠ $libelle non enregistré (cible ou clé manquante)"
        return 0
    fi
    #  Valider AVANT d'envoyer, et dire POURQUOI (16/08/2026).
    #  `rapport_payload` n'échappe que le champ `erreur` ; le fragment `details`
    #  est fourni tout construit par l'appelant, et rien ne le vérifiait. La
    #  maintenance hebdomadaire y injectait la sortie de `docker buildx prune`
    #  — « Total:<TAB>5.122GB » — or JSON interdit les caractères de contrôle
    #  non échappés dans une chaîne. Charge invalide → 422, et le journal ne
    #  disait que « HTTP 422 » : impossible de distinguer un rejet de schéma
    #  d'un JSON malformé, donc l'écran d'administration est resté figé sur un
    #  rapport vieux de cinq jours pendant que la tâche tournait très bien.
    #  Cf. `standards/07` §5 — ce qui échoue en silence ne se découvre jamais.
    if command -v python3 >/dev/null 2>&1; then
        local motif
        if ! motif=$(printf '%s' "$charge" \
                | python3 -c 'import json,sys
try:
    json.load(sys.stdin); print("")
except Exception as e:
    print(e)' 2>/dev/null); then
            motif="validateur indisponible"
        fi
        if [ -n "$motif" ]; then
            log "  ⚠ $libelle NON ENVOYÉ — charge utile JSON invalide : $motif"
            log "     (le travail, lui, a bien eu lieu — seul le compte rendu est perdu)"
            return 0
        fi
    fi
    #  🔴 La charge passe par l'ENTRÉE STANDARD, jamais en argument (#1964) : sous
    #  Windows, le curl de Git Bash réencode ses arguments dans la page de code du
    #  système — « é » devient 0xE9, l'API refuse le corps en 400. Le rapport
    #  perdu ainsi, le 14/10/2026, était celui d'une copie hors site en ÉCHEC.
    #  🔒 test_curl_corps_par_stdin.py.
    http=$(printf '%s' "$charge" | curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
        -X POST "$base/api/admin/maintenance/rapport" \
        -H "Content-Type: application/json" \
        -H "x-maintenance-key: $cle" \
        --data-binary @- 2>/dev/null) || http="000"
    #  Le code reste LISIBLE par l'appelant qui en a besoin (`rapporter_verdicts`
    #  ne mémorise un envoi que s'il a abouti). Pas par le code de retour : cette
    #  fonction rend 0 exprès, et `maintenance.sh` tourne sous `set -e`.
    RAPPORT_HTTP="$http"
    if [ "$http" = "201" ]; then
        log "  → $libelle enregistré sur $base (HTTP $http)"
    else
        log "  ⚠ $libelle non enregistré sur $base (HTTP $http)"
    fi
    return 0
}

# ── Purges hebdomadaires, DANS l'API (#1232) ────────────────────────────────
# `maintenance.sh` purgeait cinq tables par `docker exec hostachy_api python`,
# API en marche : un process tiers sur la base. Il les DEMANDE désormais à l'API,
# qui les fait dans son process et rend les comptes.
#  PURE. La charge du battement. Avec `details` (fragment JSON déjà formé), elle
#  porte aussi `erreur`, VIDE compris : l'API remplace alors les deux, et un
#  `erreur` absent laisserait affiché un échec résolu (#1805).
#  Avec une durée (`$5`, en secondes), elle porte celle du passage (#2199) : la
#  ligne prolongée montrait sinon celle du premier relevé.
battement_payload() { # $1=tâche $2=nœud [$3=details $4=erreur $5=durée]
    local base
    base=$(printf '"tache":"%s","noeud":"%s"' "$(rapport_echapper "${1:-}")" "$(rapport_echapper "${2:-}")")
    [ -n "${5:-}" ] && base=$(printf '%s,"duree_secondes":%s' "$base" "$(rapport_entier_ou_null "$5")")
    if [ -n "${3:-}" ]; then
        printf '{%s,"details":%s,"erreur":"%s"}' "$base" "$3" "$(rapport_echapper "${4:-}")"
    else
        printf '{%s}' "$base"
    fi
}

#  « J'ai tourné, et rien n'a changé » : prolonge le dernier rapport du nœud sans
#  créer de ligne (#1396), et rafraîchit ses constats s'ils sont fournis — leurs
#  chiffres ont pu bouger (#1805). Le code HTTP reste lisible dans RAPPORT_HTTP —
#  un 404 dit qu'il n'y a rien à prolonger, et l'appelant renverra un rapport complet.
rapport_battement() { # $1=url_base $2=clé $3=tâche $4=nœud [$5=details $6=erreur $7=durée]
    #  La charge par l'entrée standard, comme `rapport_envoyer` (#1964).
    RAPPORT_HTTP=$(battement_payload "${3:-}" "${4:-}" "${5:-}" "${6:-}" "${7:-}" \
        | curl -s -o /dev/null -w '%{http_code}' --max-time 15 \
        -X POST "${1:-}/api/admin/maintenance/battement" \
        -H "Content-Type: application/json" \
        -H "x-maintenance-key: ${2:-}" \
        --data-binary @- 2>/dev/null) || RAPPORT_HTTP="000"
    [ "$RAPPORT_HTTP" = "200" ] || log "  ⚠ Battement ${3:-} non enregistré sur ${1:-} (HTTP $RAPPORT_HTTP)"
    return 0
}

rapport_purges() { # $1=url_base $2=clé → corps JSON sur stdout, code 1 si ≠ 200
    local base="${1:-}" cle="${2:-}" corps http
    [ -n "$base" ] && [ -n "$cle" ] || return 1
    corps=$(curl -s --max-time 120 -w '\n%{http_code}' \
        -X POST "$base/api/admin/maintenance/purges" \
        -H "x-maintenance-key: $cle" 2>/dev/null) || return 1
    http="${corps##*$'\n'}"
    [ "$http" = "200" ] || { printf 'HTTP %s' "$http"; return 1; }
    printf '%s' "${corps%$'\n'*}"
}

# Fonction PURE : lit la réponse des purges. $1=json $2=clé de `comptes`, ou
# « erreurs » → la liste jointe par « | ». Un compte absent vaut 0 ET le dit
# sur stderr : une clé renommée côté API ne doit pas devenir un zéro muet.
purges_lire() {
    printf '%s' "${1:-}" | PYTHONIOENCODING=utf-8 python3 -c '
import json, sys
cle = sys.argv[1]
try:
    d = json.load(sys.stdin)
except Exception as e:
    print(f"réponse illisible : {e}", file=sys.stderr); print(0 if cle != "erreurs" else "réponse illisible"); sys.exit(1)
if cle == "erreurs":
    print(" | ".join(d.get("erreurs") or []))
else:
    c = (d.get("comptes") or {})
    if cle not in c:
        print(f"compte « {cle} » absent de la réponse", file=sys.stderr)
    print(int(c.get(cle, 0)))
' "${2:-}"
}

# Journalisation : réutilise le log() de l'appelant s'il en définit un.
if ! declare -f log >/dev/null 2>&1; then
    log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fi

# ── Self-test ────────────────────────────────────────────────────────────────
# ── Le rapport d'une bascule réussie (`bascule.sh`) ───────────────────────────
# POURQUOI (04/08/2026) : jusqu'ici la bascule ne rendait compte à personne. La
# ligne « Bascule actif/standby » de l'écran Admin → Maintenance affichait donc
# « Jamais exécutée » EN PERMANENCE, alors qu'elle réussissait chaque nuit — et,
# plus grave, l'écran serait resté IDENTIQUE si elle s'était arrêtée pour de bon.
# Un rouge permanent ne signale rien : c'est le battement manquant de
# standards/04 §4. Elle alerte quand elle échoue (send_alert_email) ET rend
# compte quand elle réussit — une alerte ne prouve jamais que la tâche tourne.
#
# La cible est le PEER : les flags viennent d'être inversés, c'est lui qui porte
# maintenant l'API. Poster sur soi-même échouerait — même erreur que celle
# corrigée le 02/08 pour l'hygiène locale du standby. `noeud` = QUI a agi (comme
# dans maintenance.sh) : l'ancien actif ; le nœud devenu actif est dans `vers`.
# Sorti de bascule.sh, qui atteignait le plafond de 500 lignes (DI-7b, #1781).
rapporter_bascule() { # $1 dépôt · $2 self · $3 peer · $4 IP du peer · $5 commit · $6 début
    local cle fin details
    cle=$(rapport_cle "$1") || { log "  ⚠ MAINTENANCE_KEY illisible — rapport de bascule non enregistré"; return 0; }
    fin=$(date -u +%Y-%m-%dT%H:%M:%S)
    details=$(printf '{"depuis":"%s","vers":"%s","commit":"%s"}' "$2" "$3" "${5:0:7}")
    rapport_envoyer "http://$4" "$cle" \
      "$(rapport_payload bascule "$2" applicative succes "$SECONDS" "$details" '' "$6" "$fin")" \
      "Rapport bascule"
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st_fail=0
    check() { if [ "$3" = "$2" ]; then echo "PASS  $1"
              else echo "FAIL  $1"; echo "        attendu = $2"; echo "        obtenu  = $3"; st_fail=1; fi }
    echo "== self-test lib-rapport =="

    check "texte simple inchangé"    'tout va bien'      "$(rapport_echapper 'tout va bien')"
    check "guillemet échappé"        'il a dit \"non\"'  "$(rapport_echapper 'il a dit "non"')"
    # Le cas qui cassait le JSON en silence : une sortie de commande capturée.
    check "saut de ligne aplati"     'ligne1 ligne2'     "$(rapport_echapper 'ligne1
ligne2')"
    check "barre oblique échappée"   'C:\\\\chemin'      "$(rapport_echapper 'C:\\chemin')"
    check "chaîne vide"              ''                  "$(rapport_echapper '')"

    attendu='{"tache":"bascule","noeud":"rpi1","portee":"applicative","statut":"succes","tokens_supprimes":0,"taille_db_octets":null,"duree_secondes":42,"details":{"vers":"rpi2"},"erreur":"","cree_le":"D","terminee_le":"F"}'
    check "charge utile nominale" "$attendu" \
        "$(rapport_payload bascule rpi1 applicative succes 42 '{"vers":"rpi2"}' '' D F)"

    check "details omis → null" \
        '{"tache":"t","noeud":"","portee":"applicative","statut":"succes","tokens_supprimes":0,"taille_db_octets":null,"duree_secondes":null,"details":null,"erreur":"","cree_le":null,"terminee_le":null}' \
        "$(rapport_payload t)"

    #  #1805 — le battement des contrôles porte leurs constats et leur erreur.
    check "battement sans constats : la tâche et le nœud seuls"         '{"tache":"reliability","noeud":"rpi1"}' "$(battement_payload reliability rpi1)"
    check "battement avec constats : details tel quel, erreur échappée"         '{"tache":"reliability","noeud":"rpi1","details":{"warn":1},"erreur":"KO \"503\""}'         "$(battement_payload reliability rpi1 '{"warn":1}' 'KO "503"')"
    check "battement avec constats sans échec : erreur vide, pas absente"         '{"tache":"reliability","noeud":"rpi1","details":{"warn":1},"erreur":""}'         "$(battement_payload reliability rpi1 '{"warn":1}' '')"
    check "battement avec durée : celle du passage, en entier"         '{"tache":"reliability","noeud":"rpi1","duree_secondes":23,"details":{"warn":1},"erreur":""}'         "$(battement_payload reliability rpi1 '{"warn":1}' '' 23)"
    check "battement : une durée illisible part en null, jamais en zéro"         '{"tache":"reliability","noeud":"rpi1","duree_secondes":null,"details":{"warn":1},"erreur":""}'         "$(battement_payload reliability rpi1 '{"warn":1}' '' x)"

    #  Le battement de début (#1367) : une fin vide part en null.
    check "battement : fin vide → null" \
        '{"tache":"maintenance","noeud":"rpi1","portee":"hygiene_locale","statut":"en_cours","tokens_supprimes":0,"taille_db_octets":null,"duree_secondes":null,"details":null,"erreur":"","cree_le":"D","terminee_le":null}' \
        "$(rapport_payload maintenance rpi1 hygiene_locale en_cours null null '' D '')"

    # Le JSON produit doit être *analysable*, pas seulement ressemblant : c'est
    # la seule vérification qui aurait attrapé le défaut d'échappement d'origine.
    if command -v python3 >/dev/null 2>&1; then
        for cas in 'erreur simple' 'guillemet " dedans' 'multi
ligne' 'anti\slash'; do
            if printf '%s' "$(rapport_payload t n applicative erreur 1 null "$cas" D F)" \
                 | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
                echo "PASS  JSON analysable — cas « $(printf '%s' "$cas" | tr '\n' ' ') »"
            else
                echo "FAIL  JSON invalide — cas « $(printf '%s' "$cas" | tr '\n' ' ') »"; st_fail=1
            fi
        done
        #  Le champ `details` est fourni TOUT CONSTRUIT par l'appelant : c'est
        #  le seul endroit de la charge utile que `rapport_payload` n'échappe
        #  pas, et donc le seul que les cas ci-dessus ne couvraient pas. La
        #  maintenance hebdomadaire y a injecté cinq mois durant la sortie de
        #  `docker buildx prune` — « Total:<TAB>5.122GB » — sans qu'aucun test
        #  ne regarde : le 422 n'est apparu qu'en production, le 16/08/2026.
        #  On vérifie ici les deux sens : le détail brut DOIT casser, et le
        #  même détail échappé DOIT passer. Sans le premier, le test ne
        #  prouverait pas qu'il sait détecter quoi que ce soit (§2 « cas zéro »).
        brut=$(printf '{"cache":"Total:\t5.122GB"}')
        if printf '%s' "$(rapport_payload t n applicative succes 1 "$brut" '' D F)" \
             | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
            echo "FAIL  details avec TABULATION accepté — le test ne détecte rien"; st_fail=1
        else
            echo "PASS  details avec tabulation → JSON invalide (cas zéro vérifié)"
        fi
        propre=$(printf '{"cache":"%s"}' "$(rapport_echapper "$(printf 'Total:\t5.122GB')")")
        if printf '%s' "$(rapport_payload t n applicative succes 1 "$propre" '' D F)" \
             | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
            echo "PASS  details échappé → JSON valide"
        else
            echo "FAIL  details échappé refusé — rapport_echapper insuffisant"; st_fail=1
        fi
        #  #1805 — le battement, avec une erreur multiligne à guillemets.
        if printf '%s' "$(battement_payload reliability rpi1 "$propre" 'KO "503"
puis \502')" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["details"]["cache"]' 2>/dev/null; then
            echo "PASS  battement avec constats → JSON valide"
        else
            echo "FAIL  battement avec constats → JSON INVALIDE"; st_fail=1
        fi
    else
        # standards/04 §1 : un contrôle qui ne peut pas s'exécuter rend INCONNU.
        echo "FAIL  python3 absent — validité JSON NON vérifiée (INCONNU, pas OK)"; st_fail=1
    fi

    # purges_lire — la lecture de la réponse de l'API (#1232).
    REP='{"comptes":{"tokens":2,"prt":0,"emails":5},"erreurs":[]}'
    check "purges : compte lu"            '2' "$(purges_lire "$REP" tokens 2>/dev/null)"
    check "purges : zéro réel"            '0' "$(purges_lire "$REP" prt 2>/dev/null)"
    check "purges : aucune erreur"        ''  "$(purges_lire "$REP" erreurs 2>/dev/null)"
    check "purges : erreurs jointes"      'a | b' \
        "$(purges_lire '{"comptes":{},"erreurs":["a","b"]}' erreurs 2>/dev/null)"
    check "purges : clé absente DITE"     'compte « notifications » absent de la réponse' \
        "$(purges_lire "$REP" notifications 2>&1 >/dev/null)"

    # rapport_entier_ou_null — la taille de la base, telle que psql la rend.
    check "taille : un entier"               '8421376' "$(rapport_entier_ou_null 8421376)"
    check "taille : zéro réel"               '0'    "$(rapport_entier_ou_null 0)"
    check "taille : retour chariot retiré"   '10'   "$(rapport_entier_ou_null $'10\r')"
    check "taille : réponse vide → null"     'null' "$(rapport_entier_ou_null '')"
    check "taille : sans argument → null"    'null' "$(rapport_entier_ou_null)"
    check "taille : message d'erreur → null" 'null' "$(rapport_entier_ou_null 'Error response from daemon')"
    check "taille : négatif → null"          'null' "$(rapport_entier_ou_null -1)"
    #  Insérée telle quelle dans la charge utile, elle laisse un JSON valide.
    check "taille : insérée dans la charge utile" \
        '{"tache":"t","noeud":"","portee":"applicative","statut":"succes","tokens_supprimes":0,"taille_db_octets":10,"duree_secondes":0,"details":null,"erreur":"","cree_le":null,"terminee_le":null}' \
        "$(rapport_payload t '' applicative succes 0 null '' '' '' 0 "$(rapport_entier_ou_null 10)")"

    [ $st_fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $st_fail
fi
