#!/usr/bin/env bash
# =============================================================================
#  lib-sonde.sh — la sonde HTTP, écrite UNE fois.
#
#  Elle existait en TROIS exemplaires le 01/09/2026 — `health-watch.sh`,
#  `lib-verdicts.sh` (pour check-reliability) et `precheck-mep.sh` — et le
#  troisième avait déjà divergé : ni garde sur la sortie vide, ni timeout par
#  défaut. C'est la duplication ordinaire, celle qui ne se voit pas parce que la
#  fonction tient en trois lignes.
#
#  ⚠️ Et elle a déjà coûté. Le commentaire de `health-watch.sh` le dit :
#
#  > `curl -w '%{http_code}'` écrit DÉJÀ « 000 » quand la requête échoue ; le
#  > `|| echo 000` historique en ajoutait une seconde, d'où les « HTTP 000000 »
#  > des logs de la nuit du 30/07/2026. […] la même construction rendait un
#  > contrôle de check-reliability.sh faussement VERT (comparaison d'entiers sur
#  > « 0\n0 »).
#
#  Le correctif avait été porté dans deux copies sur trois. Une sonde ne rend
#  qu'UNE valeur, et il n'y a qu'un endroit où l'écrire.
#
#  Ce module ne dépend de rien : il est sourçable par un script d'exploitation
#  comme par un script de poste, avant tout le reste.
# =============================================================================

# ── Sonde HTTP — UNE valeur, toujours ────────────────────────────────────────
#  $3… = options de curl en plus (ex. `--doh-url`, ci-dessous).
http_code() {  # $1 = URL, $2 = timeout (défaut 10) → code HTTP ou 000
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time "${2:-10}" "${@:3}" "$1" 2>/dev/null)
  echo "${code:-000}"
}

# ── Quand c'est le RÉSOLVEUR du nœud qui se tait (21/10/2026) ───────────────
#  Le 20/10/2026 à 22:36, C1 a écrit « Site public KO (HTTP 000) » : ses deux
#  sondes avaient expiré à la RÉSOLUTION du nom (« Resolving timed out »), à la
#  même minute où l'autre nœud recevait un 200. Le site servait ; c'était le
#  chemin DNS du domicile aux heures chargées (`infra-rpi`, « La cause des 000 »).
#
#  Le nom se résout alors une fois par un AUTRE chemin — DNS sur HTTPS, à une
#  adresse IP, donc sans passer par `/etc/resolv.conf` — et la même requête est
#  rejouée. Pure : `echec_de_resolution` lit la sortie de `http_detail`.
RESOLVEUR_INDEPENDANT=${RESOLVEUR_INDEPENDANT:-https://1.1.1.1/dns-query}
echec_de_resolution() {  # $1 = sortie de http_detail → oui | non
  case "${1:-}" in
    "000 "*"Resolving timed out"*|"000 "*"Could not resolve host"*) echo oui ;;
    *) echo non ;;
  esac
}

# ── La même sonde, avec CE QUI A MANQUÉ (#2073) ──────────────────────────────
#  Un `000` ne dit pas où la requête s'est perdue : résolution, connexion, TLS
#  ou réponse. Le 17/10/2026, deux `000` ont fait promouvoir une base, et rien
#  dans le journal ne permettait de les situer. Même appel unique, mêmes
#  arguments : écrit « <code> dns=…s connexion=…s tls=…s total=…s ip=… <erreur> »
#  — le premier mot EST le code de `http_code`.
http_detail() {  # $1 = URL, $2 = timeout (défaut 10)
  local r
  r=$(curl -s -o /dev/null --max-time "${2:-10}" "$1" 2>/dev/null     -w '%{http_code} dns=%{time_namelookup}s connexion=%{time_connect}s tls=%{time_appconnect}s total=%{time_total}s ip=%{remote_ip} %{errormsg}')
  echo "${r:-000 (curl muet)}"
}

# ── Lire une PAGE, et la relire une fois avant de renoncer (20/10/2026) ──────
#  C25 lisait la page publique en UN appel : le 20/10/2026 à 15:51, une seule
#  résolution DNS expirée (« Resolving timed out », la panne du chemin du
#  domicile aux heures chargées, `infra-rpi`) a suffi à envoyer le digest
#  « non mesurable » — l'appel suivant, quinze minutes plus tard, était vert.
#  C1 et health-watch reprennent déjà leur sonde : un hoquet n'est pas une mesure.
#
#  `Accept: text/html` et un UA de navigateur : Cloudflare n'injecte ses scripts
#  que dans du HTML rendu à un navigateur (C25, #701).
#  $1 = URL, $2 = délai avant la reprise (s, défaut 10), $3 = fichier où écrire
#  ce qui a manqué (l'erreur de curl) → le HTML, ou rien après deux échecs.
page_html() {
  local url=$1 reprise=${2:-10} cause=${3:-/dev/null} page
  page=$(_page_html_une_fois "$url" 2>"$cause")
  if [ -z "$page" ]; then
    sleep "$reprise"
    page=$(_page_html_une_fois "$url" 2>"$cause")
  fi
  printf '%s' "$page"
}
_page_html_une_fois() {
  curl -sS --max-time 10 -H 'Accept: text/html' \
    -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36' \
    "$1"
}

# ── Attendre un 200, et JAMAIS sans fin (#1662) ──────────────────────────────
#
#  La boucle « sonder toutes les N s jusqu'au 200 » était écrite trois fois
#  (`maintenance.sh`, `MaJ-Hostachy.sh`, `bascule.sh`) quand `auto-deploy.sh` en
#  a eu besoin : elle s'écrit ici, et les deux premières y passent. `bascule.sh`
#  garde la sienne — elle sonde le pair par SSH, sous le piège de rollback.
#
#  Décision PURE : $1 = code obtenu, $2 = secondes écoulées, $3 = délai maximal
#  → prete | attendre | depassee. Un délai ou un écoulé illisible renonce : un
#  déploiement ne doit jamais rester suspendu à une sonde (le pire cas devient
#  « une mesure, puis on continue », jamais « on attend toujours »).
verdict_attente_200() {
  [ "${1:-}" = 200 ] && { echo prete; return; }
  case "${2:-}" in ''|*[!0-9]*) echo depassee; return ;; esac
  case "${3:-}" in ''|*[!0-9]*) echo depassee; return ;; esac
  [ "$2" -lt "$3" ] && echo attendre || echo depassee
}

#  $1 = délai maximal (s), $2 = pas entre deux mesures (s), $3… = la commande
#  qui écrit un code HTTP (ex. `http_code http://localhost/api/health 3`).
#  Écrit « prete|depassee <secondes> <dernier code> » ; rend 0 si prête, 1 sinon.
attendre_200() {
  local max=$1 pas=$2 debut=$SECONDS code v
  shift 2
  while :; do
    code=$("$@" 2>/dev/null) || true
    code=${code:-000}
    v=$(verdict_attente_200 "$code" "$((SECONDS - debut))" "$max")
    case "$v" in
      prete)    echo "prete $((SECONDS - debut)) $code"; return 0 ;;
      depassee) echo "depassee $((SECONDS - debut)) $code"; return 1 ;;
    esac
    sleep "$pas"
  done
}

# ── Auto-test (aucun réseau : la sonde est simulée) ──────────────────────────
#  `source lib-sonde.sh` depuis un script lancé avec `--selftest` verrait ses
#  propres arguments : la garde sur BASH_SOURCE l'empêche (`lib-parite.sh`, #511).
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  st=0
  #  Une sonde simulée qui rend, à chaque appel, le code suivant de $CODES
  #  (le dernier se répète) — l'état vit dans un fichier, la sonde étant
  #  appelée dans une sous-coque.
  _F=$(mktemp); trap 'rm -f "$_F"' EXIT
  sonde_simulee() {
    local n; n=$(cat "$_F" 2>/dev/null || echo 0); echo $((n + 1)) > "$_F"
    local -a c; read -r -a c <<< "$CODES"
    [ "$n" -ge "${#c[@]}" ] && n=$(( ${#c[@]} - 1 ))
    echo "${c[$n]}"
  }
  t() { local libelle=$1 attendu=$2 r; CODES=$3; echo 0 > "$_F"; shift 3
        r=$(timeout 15 bash -c "$(declare -f attendre_200 verdict_attente_200 sonde_simulee); _F=$_F CODES='$CODES' attendre_200 $*" 2>/dev/null | cut -d' ' -f1)
        if [ "$r" = "$attendu" ]; then echo "PASS  $libelle → $r"
        else echo "FAIL  $libelle  attendu=$attendu obtenu=${r:-rien}"; st=1; fi; }
  #  Décision pure : un 200 prête, l'échéance dépassée renonce, sinon on attend.
  v() { local libelle=$1 attendu=$2 r; shift 2; r=$(verdict_attente_200 "$@")
        if [ "$r" = "$attendu" ]; then echo "PASS  $libelle → $r"
        else echo "FAIL  $libelle  attendu=$attendu obtenu=${r:-rien}"; st=1; fi; }
  v "200 : prête"                              prete    200 0 120
  v "200 à l'échéance : prête quand même"      prete    200 130 120
  v "503 dans le délai : on attend"            attendre 503 10 120
  v "000 au-delà du délai : on renonce"        depassee 000 121 120
  #  🔴 Un délai illisible ne doit JAMAIS faire attendre sans fin (#1662) :
  #  il vaut zéro — une seule mesure, puis on renonce.
  v "délai vide : on renonce"                  depassee 000 0 ""
  v "délai illisible : on renonce"             depassee 503 0 "x"
  v "écoulé illisible : on renonce"            depassee 503 "?" 120
  #  La boucle, sur une sonde simulée (pas de 0 s : le test ne dort pas).
  t "prête au premier appel"                   prete    "200"             120 0 sonde_simulee
  t "redémarrage : 000, 502, 503 puis 200"     prete    "000 502 503 200" 120 0 sonde_simulee
  t "jamais prête : bornée, elle renonce"      depassee "000"             1   0 sonde_simulee
  t "délai illisible : bornée quand même"      depassee "503"             x   0 sonde_simulee
  #  `echec_de_resolution` : seule la RÉSOLUTION du nœud ouvre la reprise par
  #  un autre résolveur — un lien coupé ou un site en erreur n'y ont pas droit.
  r() { local libelle=$1 attendu=$2 got; got=$(echec_de_resolution "$3")
        if [ "$got" = "$attendu" ]; then echo "PASS  $libelle → $got"
        else echo "FAIL  $libelle  attendu=$attendu obtenu=$got"; st=1; fi; }
  r "résolution expirée (20/10/2026)"          oui "000 dns=0s connexion=0s tls=0s total=10s ip= Resolving timed out after 10001 milliseconds"
  r "nom introuvable"                          oui "000 dns=0s connexion=0s tls=0s total=0s ip= Could not resolve host: 5hostachy.fr"
  r "connexion expirée : le lien, pas le DNS"  non "000 dns=0.02s connexion=0s tls=0s total=10s ip= Connection timed out after 10001 milliseconds"
  r "site en erreur"                           non "503 dns=0.02s connexion=0.03s tls=0.05s total=0.1s ip=::1 "
  r "sortie vide"                              non ""
  #  `http_detail` : son premier mot EST le code (#2073) ; curl muet → 000.
  d() { local libelle=$1 attendu=$2 r; r=$(bash -c "curl() { $3; }; $(declare -f http_detail); http_detail https://x 1" | cut -d' ' -f1)
        if [ "$r" = "$attendu" ]; then echo "PASS  $libelle → $r"
        else echo "FAIL  $libelle  attendu=$attendu obtenu=${r:-rien}"; st=1; fi; }
  d "détail d'un 200"                          200 "printf '200 dns=0.01s connexion=0.02s tls=0.04s total=0.1s ip=::1 '"
  d "détail d'une résolution expirée"          000 "printf '000 dns=0s connexion=0s tls=0s total=10s ip= Resolving timed out after 10000 milliseconds'"
  d "curl muet : 000, jamais vide"             000 "return 6"
  #  `page_html` : un échec puis une page → la page ; deux échecs → rien, et
  #  la cause de curl dans le fichier. `curl` simulé, compteur dans $_F.
  p() { local libelle=$1 attendu=$2 sorties=$3 r cause; echo 0 > "$_F"; cause=$(mktemp)
        r=$(bash -c "sleep() { :; }
          curl() { local n; n=\$(cat $_F); echo \$((n + 1)) > $_F; local -a s=($sorties)
                   [ \"\${s[\$n]}\" = vide ] && { echo 'curl: (28) Resolving timed out after 10000 milliseconds' >&2; return 28; }
                   echo \"\${s[\$n]}\"; }
          $(declare -f page_html _page_html_une_fois); page_html https://x 10 $cause")
        [ "$attendu" = vide ] && { [ -z "$r" ] && grep -q "Resolving timed out" "$cause" && r=vide; }
        rm -f "$cause"
        if [ "$r" = "$attendu" ]; then echo "PASS  $libelle → $r"
        else echo "FAIL  $libelle  attendu=$attendu obtenu=${r:-rien}"; st=1; fi; }
  p "page reçue du premier coup"               "<html>"  "'<html>'"
  p "DNS expiré une fois, puis la page"        "<html>"  "vide '<html>'"
  p "deux échecs : rien, et la cause est dite" vide      "vide vide"
  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $st
fi
