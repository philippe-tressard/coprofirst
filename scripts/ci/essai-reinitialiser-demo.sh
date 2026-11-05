#!/bin/bash
# =============================================================================
#  essai-reinitialiser-demo.sh — La remise à zéro de la démo, jouée EN ENTIER
#  contre un `docker` et un `curl` factices (#2546)
#
#  `reinitialiser.sh --selftest` éprouve ses décisions pures ; il ne voyait pas ce
#  qui a mis la démo hors service le 05/11/2026 : une commande qui échoue APRÈS
#  l'arrêt de l'API, `set -e` qui sort, et l'API qui ne repart jamais. Ici, le
#  script réel tourne dans un dossier jetable, avec sa bibliothèque réelle ; seuls
#  `docker`, `curl`, `flock` et `sleep` sont remplacés, et chaque appel est noté.
#
#  Chaque scénario vérifie le FAIT :
#    - l'API est servie à la fin, quoi qu'il ait échoué ;
#    - le rapport part, et part quand l'API est servie (il passe par elle) ;
#    - chaque commande ponctuelle tourne sous `-u app` ;
#    - un chargement échoué revide la base : jamais une démo à moitié chargée.
#
#  Test : bash scripts/ci/essai-reinitialiser-demo.sh --selftest
# =============================================================================
set -euo pipefail

RACINE="$(cd "$(dirname "$0")/../.." && pwd)"
[ "${1:-}" = "--selftest" ] || { echo "usage : $0 --selftest" >&2; exit 2; }

JETABLE=$(mktemp -d)
trap 'rm -rf "$JETABLE"' EXIT

#  $1 scénario : ok | fichiers | chargement | sante | pas-demo
#  → un dossier de travail : `trace` (appels à docker), `rapports`, `etat`, `code`, `sortie`.
jouer() {
    local d="$JETABLE/$1" faux
    faux="$d/faux"
    mkdir -p "$d/deploiement/demo" "$d/deploiement/standard" "$faux"
    cp "$RACINE/deploiement/demo/reinitialiser.sh" "$d/deploiement/demo/"
    cp "$RACINE/deploiement/standard/lib-installation.sh" "$d/deploiement/standard/"
    printf 'MODE_DEMO=%s\nDATABASE_URL=postgresql+psycopg://demo@postgres/demo\nMAINTENANCE_KEY=cle-essai\n' \
        "$([ "$1" = pas-demo ] && echo non || echo oui)" > "$d/.env"
    echo servie > "$d/etat"
    : > "$d/trace"; : > "$d/rapports"

    cat > "$faux/docker" <<'FAUX'
#!/bin/bash
echo "$*" >> "$ESSAI/trace"
case "$*" in
    *" stop api"*)              echo arretee > "$ESSAI/etat" ;;
    *" up -d"*)                 [ "$SCENARIO" = sante ] || echo servie > "$ESSAI/etat" ;;
    *"find "*)                  [ "$SCENARIO" != fichiers ] || { echo "find: Permission denied" >&2; exit 1; } ;;
    *"app.demo.charger"*)       [ "$SCENARIO" != chargement ] || exit 1 ;;
esac
exit 0
FAUX
    cat > "$faux/curl" <<'FAUX'
#!/bin/bash
case "$*" in
    *maintenance/rapport*) { cat; echo " etat=$(cat "$ESSAI/etat")"; } >> "$ESSAI/rapports" ;;
    *api/health*)          [ "$(cat "$ESSAI/etat")" = servie ] && printf 200 || printf 502 ;;
esac
exit 0
FAUX
    printf '#!/bin/bash\nexit 0\n' > "$faux/flock"
    printf '#!/bin/bash\nexit 0\n' > "$faux/sleep"
    chmod +x "$faux"/*

    local code=0
    (cd "$d" && ESSAI="$d" SCENARIO="$1" SANTE_MAX_S=2 COPROFIRST_ESSAI_VERROU="$d/verrou" \
        PATH="$faux:$PATH" bash deploiement/demo/reinitialiser.sh) > "$d/sortie" 2>&1 || code=$?
    echo "$code" > "$d/code"
    echo "$d"
}

ECHECS=0
verifier() {  # $1 libellé · $2 commande de test (évaluée)
    if eval "$2"; then echo "PASS  $1"; else echo "FAIL  $1"; ECHECS=$((ECHECS + 1)); fi
}
#  Toutes les commandes ponctuelles (`run`) portent `-u app`, et il y en a.
runs_sous_app() {
    local runs
    runs=$(grep -c ' run ' "$1/trace" || true)
    [ "$runs" -gt 0 ] && [ "$(grep ' run ' "$1/trace" | grep -c -- ' -u app ' || true)" = "$runs" ]
}
vidages() { grep -c 'DROP SCHEMA public' "$1/trace" || true; }

echo "== scénario : tout réussit =="
d=$(jouer ok)
verifier "sort à 0"                                   '[ "$(cat "$d/code")" = 0 ]'
verifier "l'API est servie à la fin"                  '[ "$(cat "$d/etat")" = servie ]'
verifier "chaque run sous -u app"                     'runs_sous_app "$d"'
verifier "rapport « succes », API servie"            'grep -q "\"statut\":\"succes\".* etat=servie" "$d/rapports"'
verifier "un seul vidage de la base"                  '[ "$(vidages "$d")" = 1 ]'

echo "== scénario : le vidage des fichiers échoue (l'incident du 05/11/2026) =="
d=$(jouer fichiers)
verifier "sort en échec"                              '[ "$(cat "$d/code")" != 0 ]'
verifier "l'API est RELANCÉE"                         '[ "$(cat "$d/etat")" = servie ]'
verifier "le chargement n'est pas tenté"              '! grep -q "app.demo.charger" "$d/trace"'
verifier "rapport « erreur » qui nomme l'étape, API servie" \
    'grep -q "\"statut\":\"erreur\".*vidage des fichiers.* etat=servie" "$d/rapports"'

echo "== scénario : le chargement échoue =="
d=$(jouer chargement)
verifier "sort en échec"                              '[ "$(cat "$d/code")" = 1 ]'
verifier "l'API est RELANCÉE"                         '[ "$(cat "$d/etat")" = servie ]'
verifier "la base est vidée une SECONDE fois"         '[ "$(vidages "$d")" = 2 ]'
verifier "le second vidage précède la relance"        \
    '[ "$(grep -n "DROP SCHEMA" "$d/trace" | tail -1 | cut -d: -f1)" -lt "$(grep -n "up -d api" "$d/trace" | tail -1 | cut -d: -f1)" ]'
verifier "rapport « erreur » : démo servie vide"      'grep -q "\"statut\":\"erreur\".*servie vide.* etat=servie" "$d/rapports"'
verifier "un seul rapport (le piège ne double pas)"   '[ "$(grep -c tache "$d/rapports")" = 1 ]'

echo "== scénario : l'API ne répond pas après le rechargement =="
d=$(jouer sante)
verifier "sort en échec"                              '[ "$(cat "$d/code")" = 1 ]'
verifier "rapport « santé KO »"                       'grep -q "santé KO" "$d/rapports"'

echo "== scénario : ce n'est pas la démo =="
d=$(jouer pas-demo)
verifier "sort à 0"                                   '[ "$(cat "$d/code")" = 0 ]'
verifier "aucun appel à docker"                       '[ ! -s "$d/trace" ]'

if [ "$ECHECS" -gt 0 ]; then
    echo "$ECHECS vérification(s) en échec."
    exit 1
fi
echo "essai-reinitialiser-demo : tous les scénarios passent."
