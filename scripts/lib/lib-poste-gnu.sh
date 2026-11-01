#!/bin/bash
# =============================================================================
#  lib-poste-gnu.sh — les outils GNU d'un poste macOS, par UNE porte (#2419)
#
#  Module SOURCÉ (mode 100644) en tête de chaque script de `scripts/poste/`.
#
#  ## Le défaut
#
#  Le poste passe d'un PC Windows à un Mac (01/11/2026). Les scripts du poste et
#  les autotests que le rejeu joue écrivent `date -d`, `stat -c`, `find -printf`,
#  `sed -E … t;`, `nproc`, `timeout` : la syntaxe GNU, celle de la CI (Ubuntu) et
#  celle que Git Bash fournissait sous Windows. Le Mac n'a que leurs homonymes BSD,
#  qui refusent ou lisent autrement : onze autotests de la CI tombaient sur le Mac.
#
#  ## La règle
#
#  Arbitrée le 01/11/2026 : sur macOS, les outils GNU de Homebrew passent EN TÊTE
#  du PATH (`poste_gnu_poser`) — on ne réécrit pas quarante appels en BSD, dont la
#  moitié s'exécute sur les nœuds. Le PATH se transmet : les étapes du rejeu et les
#  autotests qu'il lance voient les mêmes outils. Ailleurs, la porte ne fait rien.
#  Un outil absent ne se remplace pas en silence par son homonyme BSD : le pré-vol
#  et le pré-check le disent (`poste_gnu_etat`), avec la commande qui répare.
#
#  🔒 L'autotest exige que chaque script de `scripts/poste/` source cette porte.
#
#  Self-test : bash scripts/lib/lib-poste-gnu.sh --selftest (job `test-scripts`).
# =============================================================================

#  Les formules de Homebrew dont le `libexec/gnubin` porte les noms GNU nus.
POSTE_GNU_FORMULES="coreutils findutils gnu-sed grep"
#  Une commande par formule : celle dont on vérifie qu'elle répond en GNU.
POSTE_GNU_TEMOINS="date find sed grep"
#  …et le `bash` que les scripts relancent : celui d'Apple est un 3.2, sans `${x,,}`
#  ni tableau associatif. Celui de Homebrew vit dans `<préfixe>/bin`, posé avec les autres.

# poste_systeme [UNAME] — windows | darwin | linux (tout autre Unix compte comme linux).
poste_systeme() {
  case "${1:-$(uname -s 2>/dev/null)}" in
    MINGW*|MSYS*|CYGWIN*) echo windows ;;
    Darwin) echo darwin ;;
    *) echo linux ;;
  esac
}

# poste_gnu_chemins PREFIXE — les `gnubin` des formules puis `<préfixe>/bin` (bash), par `:`.
poste_gnu_chemins() {
  local f c=""
  for f in $POSTE_GNU_FORMULES; do c="$c${c:+:}$1/opt/$f/libexec/gnubin"; done
  echo "$c:$1/bin"
}

# poste_gnu_prefixer CHEMINS PATH — CHEMINS devant PATH, chacun une seule fois. Pure.
poste_gnu_prefixer() {
  local reste=":$2:" d IFS=:
  for d in $1; do reste=${reste//:$d:/:}; done
  reste=${reste#:}; reste=${reste%:}
  echo "$1${reste:+:$reste}"
}

# poste_gnu_poser — sur macOS, les outils GNU de Homebrew en tête du PATH. Idempotent.
poste_gnu_poser() {
  [ "$(poste_systeme)" = darwin ] || return 0
  local prefixe="${HOMEBREW_PREFIX:-/opt/homebrew}"
  [ -d "$prefixe" ] || prefixe=/usr/local
  PATH=$(poste_gnu_prefixer "$(poste_gnu_chemins "$prefixe")" "$PATH")
  export PATH
  #  Le PATH ne change pas l'interpréteur DÉJÀ lancé : un script parti sous le bash 3.2
  #  d'Apple y resterait, et tomberait plus loin sur une erreur de syntaxe sans rapport.
  if [ "${BASH_VERSINFO[0]:-0}" -lt 4 ]; then
    echo "✗ $(basename "$0") tourne sous bash ${BASH_VERSION:-?} (celui d'Apple) : relancer avec" \
         "$prefixe/bin/bash $0 — ou ouvrir un terminal qui lit ~/.zprofile (#2419)" >&2
    exit 2
  fi
}

# poste_gnu_etat SYSTEME "OUTIL:oui|non …" — vide si le poste a ses outils GNU, sinon
# « REFUS … · réparer : … ». Pure : la sonde est `poste_gnu_sonder`.
poste_gnu_etat() {
  [ "$1" = darwin ] || return 0
  local t manquants=""
  for t in $2; do
    case "$t" in *:oui) ;; *) manquants="$manquants ${t%%:*}" ;; esac
  done
  [ -z "$manquants" ] && [ -n "$2" ] && return 0
  [ -n "$2" ] || manquants=" (aucune sonde)"
  echo "REFUS outils GNU absents sur macOS :${manquants} — leur homonyme BSD lit autrement" \
       "(date -d, stat -c, sed t;) · réparer : brew install $POSTE_GNU_FORMULES bash"
}

# poste_gnu_sonder — « OUTIL:oui|non » pour chaque témoin, tel que le PATH courant le résout.
poste_gnu_sonder() {
  local t out=""
  for t in $POSTE_GNU_TEMOINS; do
    #  « (GNU coreutils) », « (GNU sed) »… — le grep d'Apple se dit « BSD grep, GNU compatible ».
    if "$t" --version 2>/dev/null | head -1 | grep -qF '(GNU '; then out="$out $t:oui"
    else out="$out $t:non"; fi
  done
  if [ "$(bash -c 'echo "${BASH_VERSINFO[0]}"' 2>/dev/null)" -ge 4 ] 2>/dev/null; then out="$out bash:oui"
  else out="$out bash:non"; fi
  echo "${out# }"
}

_poste_gnu_selftest() {
  local echecs=0 racine
  racine="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  _cas() {  # description attendu obtenu
    if [ "$2" = "$3" ]; then echo "PASS  $1"
    else echo "FAIL  $1  attendu=[$2] obtenu=[$3]"; echecs=$((echecs + 1)); fi
  }
  _cas "système : Git Bash"  windows "$(poste_systeme MINGW64_NT-10.0)"
  _cas "système : macOS"     darwin  "$(poste_systeme Darwin)"
  _cas "système : Ubuntu"    linux   "$(poste_systeme Linux)"
  _cas "chemins : un gnubin par formule" \
    "/b/opt/coreutils/libexec/gnubin:/b/opt/findutils/libexec/gnubin:/b/opt/gnu-sed/libexec/gnubin:/b/opt/grep/libexec/gnubin:/b/bin" \
    "$(poste_gnu_chemins /b)"
  _cas "préfixe : devant le PATH"            "/g1:/g2:/usr/bin:/bin" "$(poste_gnu_prefixer /g1:/g2 /usr/bin:/bin)"
  _cas "préfixe : idempotent, sans doublon"  "/g1:/g2:/usr/bin:/bin" "$(poste_gnu_prefixer /g1:/g2 /g2:/usr/bin:/g1:/bin)"
  _cas "préfixe : PATH vide"                 "/g1"                   "$(poste_gnu_prefixer /g1 "")"
  _cas "état : hors macOS, rien à dire"      ""                      "$(poste_gnu_etat linux "date:non")"
  _cas "état : Windows, rien à dire"         ""                      "$(poste_gnu_etat windows "")"
  _cas "état : macOS outillé"                ""                      "$(poste_gnu_etat darwin "date:oui find:oui sed:oui grep:oui bash:oui")"
  _cas "état : macOS, sed BSD et bash 3.2 → nommés" \
    "REFUS outils GNU absents sur macOS : sed bash — leur homonyme BSD lit autrement (date -d, stat -c, sed t;) · réparer : brew install $POSTE_GNU_FORMULES bash" \
    "$(poste_gnu_etat darwin "date:oui find:oui sed:non grep:oui bash:non")"
  #  CAS ZÉRO : sans sonde, rien n'est prouvé — jamais un vert.
  local sans_sonde; sans_sonde=$(poste_gnu_etat darwin "")
  _cas "état : macOS sans sonde → refus" oui \
    "$([[ "$sans_sonde" == REFUS*"(aucune sonde)"* ]] && echo oui || echo non)"
  #  La porte posée, les témoins répondent en GNU — éprouvé sur le poste qui la joue.
  if [ "$(poste_systeme)" = darwin ]; then
    ( echecs=0; poste_gnu_poser; _cas "macOS : la porte posée, les témoins répondent en GNU" "" \
        "$(poste_gnu_etat darwin "$(poste_gnu_sonder)")"; exit "$echecs" ) || echecs=$((echecs + 1))
    if [ -x /bin/bash ] && [ "$(/bin/bash -c 'echo "${BASH_VERSINFO[0]}"')" -lt 4 ]; then
      local sous32 rc32
      sous32=$(/bin/bash -c '. "$1"; poste_gnu_poser; echo PASSE' _ "${BASH_SOURCE[0]}" 2>&1); rc32=$?
      _cas "macOS : sous le bash 3.2 d'Apple, la porte arrête le script (code 2, nommé)" "2 oui" \
        "$rc32 $([[ "$sous32" == *"bash 3."*"relancer avec"* && "$sous32" != *PASSE* ]] && echo oui || echo non)"
    fi
  else
    local avant="$PATH"; poste_gnu_poser
    _cas "hors macOS : la porte ne touche pas au PATH" "$avant" "$PATH"
  fi
  #  🔒 Chaque script du poste passe par la porte, avant son premier geste.
  local f manquants=""
  for f in "$racine"/scripts/poste/*.sh; do
    grep -qE '^[[:space:]]*poste_gnu_poser([[:space:]]|$)' "$f" || manquants="$manquants $(basename "$f")"
  done
  _cas "chaque script de scripts/poste/ appelle poste_gnu_poser" "" "${manquants# }"

  if [ "$echecs" -eq 0 ]; then echo "✓ lib-poste-gnu : tous les cas passent."; return 0; fi
  echo "✗ lib-poste-gnu : $echecs cas en échec."
  return 1
}

#  Garde « exécuté, pas sourcé ».
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  _poste_gnu_selftest
  exit $?
fi
