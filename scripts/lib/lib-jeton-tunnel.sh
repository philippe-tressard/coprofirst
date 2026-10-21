#!/bin/bash
# =============================================================================
#  lib-jeton-tunnel.sh — Qu'est-ce qu'un jeton de tunnel Cloudflare (module à sourcer)
#
#  POURQUOI ce module existe (25/09/2026, #1318) :
#    Lors d'une rotation du jeton, l'IDENTIFIANT du tunnel (`91d1afa9-…`, affiché
#    en grand sur la page du tunnel) a été collé à la place du JETON (`eyJ…`,
#    caché dans la commande d'installation), sur les deux nœuds : site coupé,
#    deux failovers inutiles. Deux scripts reçoivent un jeton collé —
#    `changer-jeton-tunnel.sh` (rotation) et `install-cloudflared.sh`
#    (reconstruction d'un nœud) — et aucun ne regardait ce qu'on lui donnait.
#    La règle vit ici, une fois, pour les deux.
#
#  Un jeton est le base64 d'un JSON {"a":compte,"t":tunnel,"s":secret}.
#
#  ── Où vit le jeton (22/10/2026, #2115) ─────────────────────────────────────
#  Dans un FICHIER (`JETON_FICHIER`, root 600), jamais dans l'unité : `--token
#  <valeur>` dans `ExecStart` est lisible par tout compte local (`ps`,
#  `systemctl cat`/`show`) et se retrouve dans les journaux. Le jeton était en clair
#  sur les deux nœuds, parce que `cloudflared service install <jeton>` et le `sed`
#  de la rotation l'y écrivaient. L'unité ne porte plus que `--token-file <chemin>`.
#  C39 (`lib-jeton-tunnel-clair.sh`) échoue si l'ancienne forme revient.
#
#  Fonctions PURES : ni réseau, ni écriture, ni lecture de fichier. Elles rendent
#  toujours 0 (sauf `unite_vers_fichier`, qui refuse en 1) : sous `set -e`, un
#  `return 1` dans `X=$(…)` ferait avorter l'appelant avant son message.
#
#  Test : bash lib-jeton-tunnel.sh --selftest   (aucun effet de bord)
# =============================================================================

#: Le fichier du jeton — seule écriture du chemin (unité, scripts, C39 le lisent ici).
JETON_FICHIER="${JETON_FICHIER:-/etc/cloudflared/jeton}"

# ── Identifiant du tunnel porté par un jeton ─────────────────────────────────
# Rend l'identifiant `t`, ou rien si le texte n'est pas un jeton lisible.
jeton_tunnel_id() {
  local j="${1:-}" json
  [ -n "$j" ] || return 0
  j=$(printf '%s' "$j" | tr -- '-_' '+/')
  while [ $(( ${#j} % 4 )) -ne 0 ]; do j="$j="; done
  json=$(printf '%s' "$j" | base64 -d 2>/dev/null | tr -d '\0')
  printf '%s' "$json" | grep -q '"a":"' || return 0
  printf '%s' "$json" | grep -q '"s":"' || return 0
  printf '%s' "$json" | sed -n 's/.*"t":"\([^"]*\)".*/\1/p'
}

# ── Le tunnel installé : l'identifiant attendu ───────────────────────────────
# Depuis la valeur du jeton (celle du fichier, ou d'un `--token` hérité) : un jeton lisible donne son `t` ;
# un identifiant nu (l'erreur du 25/09) EST l'identifiant ; sinon rien à comparer.
tunnel_attendu() {
  local v="${1:-}" id
  id=$(jeton_tunnel_id "$v")
  if [ -n "$id" ]; then echo "$id"; return 0; fi
  if printf '%s' "$v" | grep -Eq '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
    echo "$v"
  fi
}

# ── Verdict sur la chaîne collée ─────────────────────────────────────────────
# Args : jeton  identifiant_attendu (vide = pas de comparaison)
# Rend : "ok" ou "refuse:<raison>" — la phrase à afficher : `motif_refus`.
verdict_jeton() {
  local j="${1:-}" attendu="${2:-}" id
  [ -n "$j" ] || { echo "refuse:vide"; return 0; }
  case "$j" in eyJ*) ;; *) echo "refuse:format"; return 0 ;; esac
  id=$(jeton_tunnel_id "$j")
  [ -n "$id" ] || { echo "refuse:illisible"; return 0; }
  if [ -n "$attendu" ] && [ "$id" != "$attendu" ]; then echo "refuse:autre-tunnel"; return 0; fi
  echo "ok"
}

motif_refus() {  # verdict → phrase pour la personne qui a collé
  case "${1#refuse:}" in
    format)       echo "Ce n'est pas le jeton. Le jeton commence par eyJ et fait plus de 150 caractères ; un code de la forme 91d1afa9-… est l'IDENTIFIANT du tunnel." ;;
    illisible)    echo "Cette chaîne commence par eyJ mais n'est pas un jeton de tunnel (copie tronquée ?)." ;;
    autre-tunnel) echo "Ce jeton appartient à un AUTRE tunnel que celui installé sur ce nœud." ;;
    vide)         echo "Rien n'a été collé." ;;
    *)            echo "Jeton refusé (${1:-})." ;;
  esac
}

# ── Masquer tout jeton dans un texte (filtre stdin → stdout) ─────────────────
# Pour citer un journal de cloudflared dans une alerte ou à l'écran sans y
# recopier le secret.
masquer_jeton() { sed -E 's/eyJ[A-Za-z0-9+\/=_-]*/<jeton masqué>/g'; }

# ── Le jeton lu dans une unité HÉRITÉE (`--token <valeur>`) ──────────────────
# Rend la valeur, ou rien si l'unité n'en porte pas (déjà migrée, ou illisible).
jeton_dans_unite() {
  printf '%s
' "${1:-}" | grep -o -- '--token [^ ]*' | head -n 1 | cut -d' ' -f2
}

# ── L'unité systemd qui lit le jeton dans JETON_FICHIER ──────────────────────
# Rend le texte de l'unité où `--token <valeur>` est remplacé par `--token-file
# <JETON_FICHIER>` (déjà migrée : le chemin est seulement ramené à JETON_FICHIER),
# ou échoue (code 1) si elle ne porte pas exactement UNE de ces deux formes :
# deviner où l'écrire, c'est ce qui casse. Aucun jeton n'entre ni ne sort ici.
unite_vers_fichier() {
  local texte="$1" n_clair n_fichier
  n_clair=$(printf '%s
' "$texte" | grep -o -- '--token [^ ]*' | wc -l)
  n_fichier=$(printf '%s
' "$texte" | grep -o -- '--token-file [^ ]*' | wc -l)
  [ $(( n_clair + n_fichier )) -eq 1 ] || return 1
  # Délimiteur `|` : absent d'un chemin sérieux.
  printf '%s
' "$texte" | sed -E "s|--token(-file)? [^ ]*|--token-file $JETON_FICHIER|"
}

# ── L'unité d'un nœud NEUF (install-cloudflared.sh) ──────────────────────────
# Celle que `cloudflared service install` écrivait, sauf le jeton : elle lit
# JETON_FICHIER. Écrite ici, une fois ; `unite_vers_fichier` la laisse intacte.
unite_modele() {
  cat <<UNITE
[Unit]
Description=cloudflared
After=network-online.target
Wants=network-online.target

[Service]
TimeoutStartSec=15
Type=notify
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run --token-file $JETON_FICHIER
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
UNITE
}

# ── Self-test ────────────────────────────────────────────────────────────────
# Garde `BASH_SOURCE = $0` : sourcé depuis un script lancé avec `--selftest`,
# ce bloc ne doit pas s'exécuter à sa place (cf. lib-role.sh).
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  fail=0
  eq() { if [ "$2" = "$3" ]; then echo "PASS  $1"; else echo "FAIL  $1  attendu=[$3] obtenu=[$2]"; fail=1; fi; }
  ID=11111111-2222-3333-4444-555555555555
  BON=$(printf '{"a":"compte","t":"%s","s":"c2VjcmV0"}' "$ID" | base64 | tr -d '\n=')
  AUTRE=$(printf '{"a":"compte","t":"99999999-2222-3333-4444-555555555555","s":"eA=="}' | base64 | tr -d '\n')
  echo "== self-test lib-jeton-tunnel =="
  eq "jeton lisible → identifiant (sans remplissage =)" "$(jeton_tunnel_id "$BON")" "$ID"
  eq "jeton_tunnel_id sur un identifiant nu → rien"     "$(jeton_tunnel_id "$ID")"  ""
  eq "tunnel attendu : jeton installé"                  "$(tunnel_attendu "$BON")"  "$ID"
  eq "tunnel attendu : identifiant installé (25/09)"    "$(tunnel_attendu "$ID")"   "$ID"
  eq "tunnel attendu : valeur quelconque → rien"        "$(tunnel_attendu "abc")"   ""
  eq "verdict : bon jeton, bon tunnel"                  "$(verdict_jeton "$BON" "$ID")"     "ok"
  eq "verdict : bon jeton, rien à comparer"             "$(verdict_jeton "$BON" "")"        "ok"
  eq "verdict : l'identifiant collé (25/09)"            "$(verdict_jeton "$ID" "$ID")"      "refuse:format"
  eq "verdict : rien collé"                             "$(verdict_jeton "" "$ID")"         "refuse:vide"
  eq "verdict : eyJ tronqué"                            "$(verdict_jeton "eyJhIjoi" "$ID")" "refuse:illisible"
  eq "verdict : jeton d'un autre tunnel"                "$(verdict_jeton "$AUTRE" "$ID")"   "refuse:autre-tunnel"
  eq "masquage : le jeton disparaît" "$(printf 'x --token %s y' "$BON" | masquer_jeton)" "x --token <jeton masqué> y"
  eq "motif : l'identifiant est nommé" "$(motif_refus refuse:format | grep -c IDENTIFIANT)" "1"
  UNITE="[Service]
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run --token $BON
Restart=on-failure"
  eq "unité héritée : le jeton en est lu"              "$(jeton_dans_unite "$UNITE")" "$BON"
  eq "unité migrée : aucun jeton à lire"               "$(jeton_dans_unite "$(unite_vers_fichier "$UNITE")")" ""
  eq "unité : --token devient --token-file"      "$(unite_vers_fichier "$UNITE" | grep ExecStart)"      "ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run --token-file $JETON_FICHIER"
  #  LE POINT DE #2115 : rien de secret ne subsiste dans l'unité produite.
  eq "unité : plus aucun eyJ après la migration"       "$(unite_vers_fichier "$UNITE" | grep -c eyJ)" "0"
  eq "unité : le reste est intact"                     "$(unite_vers_fichier "$UNITE" | grep -c Restart=on-failure)" "1"
  eq "unité déjà migrée : inchangée (idempotent)"      "$(unite_vers_fichier "$(unite_vers_fichier "$UNITE")")" "$(unite_vers_fichier "$UNITE")"
  eq "unité migrée vers un autre chemin : ramenée à JETON_FICHIER"      "$(unite_vers_fichier "ExecStart=/x tunnel run --token-file /tmp/ailleurs" | grep -c "token-file $JETON_FICHIER\$")" "1"
  eq "unité d'un nœud neuf : lit le fichier, sans aucun jeton"      "$(unite_modele | grep -c "tunnel run --token-file $JETON_FICHIER\$")|$(unite_modele | grep -c eyJ)" "1|0"
  eq "unité d'un nœud neuf : unite_vers_fichier la laisse telle quelle"      "$(unite_vers_fichier "$(unite_modele)")" "$(unite_modele)"
  unite_vers_fichier "[Service]
ExecStart=/usr/bin/cloudflared tunnel run" >/dev/null; eq "unité sans jeton ni fichier → refus" "$?" "1"
  unite_vers_fichier "$UNITE
ExecStartPost=/bin/true --token x" >/dev/null; eq "unité à deux --token → refus" "$?" "1"
  [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $fail
fi
