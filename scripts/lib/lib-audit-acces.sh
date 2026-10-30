#!/bin/bash
# =============================================================================
#  lib-audit-acces.sh — S6 : que disent les journaux de la NUIT des attaques —
#  sondes de scanners, forçage de comptes, gestes sensibles ?
#
#  Module SOURCÉ (mode 100644) par `audit-securite.sh` (audit de sécurité
#  nocturne), sur le nœud ACTIF seulement : le standby ne sert rien.
#  Autotest : bash scripts/lib/lib-audit-acces.sh --selftest
#
#  ── POURQUOI ─────────────────────────────────────────────────────────────────
#
#  Les attaques automatisées — et depuis 2026 pilotées par des agents — ne
#  ressemblent pas à une panne : le site répond, aucun 500, rien dans C36. Elles
#  se lisent dans ce que les journaux ÉCRIVENT DÉJÀ et que personne ne relisait :
#
#   1. le journal d'accès de Caddy (anonyme : ni adresse ni agent, #1588) dit le
#      CHEMIN et le STATUT. Un scanner demande `/.env`, `/.git/config`,
#      `/wp-login.php`, `/phpmyadmin`… Qu'il reçoive 404 est le bruit de fond
#      d'Internet ; qu'il reçoive 2xx est une BRÈCHE — un secret servi. FAIL.
#      Les refus sur `/api/auth/login` (401) comptés sur 24 h disent un forçage
#      de comptes au-delà d'un seuil ; les 429 disent que la limite de débit a
#      travaillé — un chiffre à lire, pas un défaut ;
#   2. le journal de SÉCURITÉ de l'API (`utils/journal_securite`, #1040) nomme
#      les gestes sensibles — connexion refusée, jeton de rafraîchissement
#      rejoué (vol probable), rôle ajouté, compte supprimé, adresse changée —
#      et il n'a aucun destinataire : « WARNING n'est pas une alerte ». Ce
#      contrôle est son lecteur de la nuit : les gestes qui doivent se RELIRE
#      remontent au digest, avec leurs comptes.
#
#  Rien ici n'identifie une personne : des chemins, des statuts, des codes
#  d'évènement et des comptes. Lecture seule, jamais la base.
#
#  Fonctions PURES : un relevé entre, un verdict sort.
# =============================================================================

#: Les chemins qu'aucun client légitime ne demande — la signature d'un scanner.
#: Motif awk, en minuscules (le chemin est abaissé avant comparaison).
ACCES_CHEMINS_SONDES='\.env|\.git/|\.git$|wp-login|wp-admin|wp-content|xmlrpc\.php|phpmyadmin|\.aws/|actuator|cgi-bin|\.php($|\?)|\.\./|%2e%2e|/etc/passwd|\.ssh/|\.htpasswd|\.bak$|\.sql$|id_rsa'
#: La route de connexion de l'API (`routers/auth.py`, préfixe /auth, `POST /login`).
ACCES_ROUTE_CONNEXION="${ACCES_ROUTE_CONNEXION:-/api/auth/login}"
#: Au-delà de ce nombre de connexions REFUSÉES en 24 h, on parle de forçage.
#: Une résidence de ~150 comptes fait quelques dizaines de fautes de frappe par
#: jour ; des centaines viennent d'une liste de mots de passe.
ACCES_SEUIL_REFUS="${ACCES_SEUIL_REFUS:-100}"
#: Les évènements du journal de sécurité qui se RELISENT (un WARN qui les compte)
#: et ceux qui se COMPTENT seulement (dans la ligne OK). La liste des codes fait
#: foi dans `api/app/utils/journal_securite.py` (`_NIVEAUX`) ; l'autotest du
#: dépôt vérifie que chaque code cité ici y existe.
ACCES_EVENEMENTS_A_RELIRE="jeton_rejoue role_ajoute compte_supprime adresse_changee rattachement_hors_proposition bail_hors_de_ses_lots compte_purge_epargne"
ACCES_EVENEMENTS_COMPTES="connexion_refusee mot_de_passe_reinitialise adresse_changement_demande role_retire compte_desactive"

# ── Les lectures (effets de bord : docker, lecture seule) ────────────────────
#  Caddy : « ok:<requêtes>:<sondes>:<sondes servies 2xx>:<refus de connexion>:<429> »
#  sur les 24 dernières heures ; VIDE si Caddy ne tourne pas ou si le fichier
#  n'a aucune ligne datée — cas zéro, comme C36.
acces_lire_caddy() {
    [ -n "$(docker ps -q -f name=hostachy_caddy 2>/dev/null)" ] || return 0
    docker exec hostachy_caddy tail -n 50000 /var/log/caddy/access.log 2>/dev/null \
        | acces_compter_caddy "$(date +%s)"
}
#  PURE : le journal sur l'entrée standard, l'instant en $1.
#  Le motif passe par l'ENVIRONNEMENT, pas par `-v` : awk réécrit les séquences
#  d'échappement d'une valeur `-v` (`\.` devient `.`), et le motif cessait
#  d'être une expression régulière valide.
acces_compter_caddy() {
    SONDES="$ACCES_CHEMINS_SONDES" awk -v m="${1:-0}" -v login="$ACCES_ROUTE_CONNEXION" '
    BEGIN { n=0; s=0; s2=0; r=0; l=0; t=0; sondes=ENVIRON["SONDES"] }
    {
        if (!match($0, /"ts":[0-9]+/)) next
        ts = substr($0, RSTART+5, RLENGTH-5) + 0
        if (ts > t) t = ts
        if (ts < m - 86400) next
        n++
        st = 0; if (match($0, /"status":[0-9]+/)) st = substr($0, RSTART+9, RLENGTH-9) + 0
        uri = ""; if (match($0, /"uri":"[^"]*"/)) uri = tolower(substr($0, RSTART+7, RLENGTH-8))
        if (uri ~ sondes) { s++; if (st >= 200 && st < 300) s2++ }
        if (index(uri, login) == 1 && st == 401) r++
        if (st == 429) l++
    }
    END { if (t == 0) print ""; else print "ok:" n ":" s ":" s2 ":" r ":" l }'
}
#  L'API : « <code> <nombre> » par ligne, pour les évènements du journal de
#  sécurité des 24 dernières heures ; VIDE si le conteneur ne tourne pas.
acces_lire_securite() {
    [ -n "$(docker ps -q -f name=hostachy_api 2>/dev/null)" ] || return 0
    docker logs --since 24h hostachy_api 2>&1 | acces_compter_securite
}
#  PURE : les lignes « … WARNING securite — securite <code> acteur=… » sur stdin.
acces_compter_securite() {
    sed -n 's/^.* securite — securite \([a-z_]*\) .*$/\1/p' | sort | uniq -c \
        | awk '{ print $2 " " $1 }'
}

# ── Décisions PURES ──────────────────────────────────────────────────────────

#  $1 = relevé Caddy → INCONNU | BRECHE:<n> | FORCAGE:<refus> | OK
acces_verdict_caddy() {
    local v n s s2 r l
    case "${1:-}" in ok:*) v=${1#ok:} ;; *) echo INCONNU; return 0 ;; esac
    IFS=: read -r n s s2 r l <<< "$v"
    for x in "$n" "$s" "$s2" "$r" "$l"; do case "$x" in ''|*[!0-9]*) echo INCONNU; return 0 ;; esac; done
    if   [ "$s2" -gt 0 ]; then echo "BRECHE:$s2"
    elif [ "$r" -gt "${2:-$ACCES_SEUIL_REFUS}" ]; then echo "FORCAGE:$r"
    else echo OK; fi
}
#  Les cinq champs d'un relevé, pour la ligne de constat (vide si illisible).
acces_champs_caddy() { case "${1:-}" in ok:*) printf '%s' "${1#ok:}" | tr ':' ' ' ;; esac; }

#  $1 = relevé de l'API (« code n » par ligne) → « code=n » pour les évènements à
#  RELIRE présents (séparés par des espaces) ; vide s'il n'y en a aucun.
acces_a_relire() {
    local ligne code n out=""
    while read -r code n; do
        [ -n "$code" ] || continue
        case " $ACCES_EVENEMENTS_A_RELIRE " in *" $code "*) out="$out${out:+ }$code=$n" ;; esac
    done <<< "${1:-}"
    printf '%s' "$out"
}
#  Idem pour les évènements qui se COMPTENT seulement.
acces_comptes() {
    local code n out=""
    while read -r code n; do
        [ -n "$code" ] || continue
        case " $ACCES_EVENEMENTS_COMPTES " in *" $code "*) out="$out${out:+ }$code=$n" ;; esac
    done <<< "${1:-}"
    printf '%s' "$out"
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
audit_acces_selftest() {
    local st=0
    t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; st=1; }; }
    echo "== self-test lib-audit-acces (S6) =="
    #  Le journal de Caddy aux formes RÉELLES (2.11) : now = 1791300000.
    local J; J=$(cat <<'X'
{"level":"info","ts":1791200000.1,"request":{"method":"GET","host":"h","uri":"/.env"},"status":200}
{"level":"info","ts":1791250000.5,"request":{"method":"GET","host":"h","uri":"/wp-login.php"},"status":404}
{"level":"info","ts":1791280000.9,"request":{"method":"GET","host":"h","uri":"/.git/config"},"status":404}
{"level":"info","ts":1791290000.2,"request":{"method":"POST","host":"h","uri":"/api/auth/login"},"status":401}
{"level":"info","ts":1791290001.2,"request":{"method":"POST","host":"h","uri":"/api/auth/login"},"status":401}
{"level":"info","ts":1791290002.2,"request":{"method":"POST","host":"h","uri":"/api/auth/login"},"status":200}
{"level":"info","ts":1791290003.2,"request":{"method":"POST","host":"h","uri":"/api/auth/login"},"status":429}
{"level":"info","ts":1791299000.0,"request":{"method":"GET","host":"h","uri":"/api/health"},"status":200}
{"level":"info","ts":1791299900.7,"request":{"method":"GET","host":"h","uri":"/Admin/../../etc/passwd"},"status":404}
{"level":"info","ts":1791299901.7,"request":{"method":"GET","host":"h","uri":"/tableau-de-bord?x=1"},"status":200}
X
)
    #  Le `/.env` servi en 200 est HORS fenêtre (1791200000) : 9 requêtes, 3 sondes, 0 servie.
    t "compte : requêtes, sondes, servies, refus, 429" "ok:9:3:0:2:1" "$(acces_compter_caddy 1791300000 <<< "$J")"
    t "verdict : la nuit ordinaire" OK "$(acces_verdict_caddy "ok:9:3:0:2:1")"
    t "verdict : une sonde SERVIE (le /.env à 200 dans la fenêtre)" "BRECHE:1" \
      "$(acces_verdict_caddy "$(acces_compter_caddy 1791250000 <<< "$J")")"
    t "verdict : forçage au-delà du seuil" "FORCAGE:101" "$(acces_verdict_caddy "ok:500:0:0:101:3" 100)"
    t "verdict : au seuil, pas de forçage" OK "$(acces_verdict_caddy "ok:500:0:0:100:3" 100)"
    t "verdict : la brèche prime sur le forçage" "BRECHE:2" "$(acces_verdict_caddy "ok:500:4:2:300:3" 100)"
    t "la casse ne cache pas une sonde" 1 "$(acces_compter_caddy 1791300000 <<< '{"ts":1791299999,"request":{"uri":"/WP-ADMIN/"},"status":404}' | cut -d: -f3)"
    t "un chemin légitime n'est pas une sonde" "ok:1:0:0:0:0" \
      "$(acces_compter_caddy 1791300000 <<< '{"ts":1791299999,"request":{"uri":"/api/documents/12/telecharger"},"status":200}')"
    t "champs pour la ligne" "9 3 0 2 1" "$(acces_champs_caddy "ok:9:3:0:2:1")"
    #  LE CAS ZÉRO.
    t "journal sans ligne datée → vide" "" "$(acces_compter_caddy 1791300000 <<< 'pas du json')"
    t "relevé vide → INCONNU" INCONNU "$(acces_verdict_caddy "")"
    t "relevé sans marqueur → INCONNU" INCONNU "$(acces_verdict_caddy "9:3:0:2:1")"
    t "champ non entier → INCONNU" INCONNU "$(acces_verdict_caddy "ok:9:x:0:2:1")"
    docker() { case "$1" in ps) : ;; esac; }
    t "Caddy arrêté → relevé vide, jamais « ok: »" "" "$(acces_lire_caddy)"
    t "API arrêtée → relevé vide" "" "$(acces_lire_securite)"
    unset -f docker

    #  Le journal de sécurité, aux formes RÉELLES de `journaliser_securite`.
    local L; L=$(cat <<'X'
2026-10-30 02:11:03,120 WARNING securite — securite connexion_refusee acteur=- cible=12
2026-10-30 02:11:09,004 WARNING securite — securite connexion_refusee acteur=- cible=-
2026-10-30 03:40:00,000 WARNING securite — securite jeton_rejoue acteur=7 cible=7
2026-10-30 09:12:00,000 WARNING securite — securite role_ajoute acteur=1 cible=33 conseil_syndical
2026-10-30 09:13:00,000 INFO securite — securite mot_de_passe_change acteur=33 cible=33
2026-10-30 10:00:00,000 INFO app.main — démarrage
X
)
    local C; C=$(acces_compter_securite <<< "$L")
    t "comptes par code" $'connexion_refusee 2\njeton_rejoue 1\nmot_de_passe_change 1\nrole_ajoute 1' "$C"
    t "à relire : jeton rejoué et rôle ajouté" "jeton_rejoue=1 role_ajoute=1" "$(acces_a_relire "$C")"
    t "comptés : les refus" "connexion_refusee=2" "$(acces_comptes "$C")"
    t "rien à relire sur une nuit calme" "" "$(acces_a_relire "connexion_refusee 3")"
    t "journal vide → rien" "|" "$(acces_a_relire "")|$(acces_comptes "")"
    #  Chaque code cité ici existe dans `_NIVEAUX` de l'API : une liste recopiée
    #  diverge au premier renommage, et le contrôle se tairait sur un code mort.
    local niveaux="$(dirname "${BASH_SOURCE[0]}")/../../api/app/utils/journal_securite.py" c manquants=""
    for c in $ACCES_EVENEMENTS_A_RELIRE $ACCES_EVENEMENTS_COMPTES; do
        grep -q "^    \"$c\":" "$niveaux" || manquants="$manquants $c"
    done
    t "chaque code cité existe dans journal_securite._NIVEAUX" "" "$manquants"
    t "la route de connexion est celle de l'API" 1 \
      "$(grep -c 'prefix="/auth"' "$(dirname "${BASH_SOURCE[0]}")/../../api/app/routers/auth.py")$( grep -q '@router.post("/login")' "$(dirname "${BASH_SOURCE[0]}")/../../api/app/routers/auth.py" || echo " (POST /login absent)")"
    [ "$st" -eq 0 ] && echo "lib-audit-acces : tous les cas passent."
    return "$st"
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    audit_acces_selftest; exit $?
fi
