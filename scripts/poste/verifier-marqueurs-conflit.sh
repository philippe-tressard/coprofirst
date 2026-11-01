#!/usr/bin/env bash
# =============================================================================
#  Refuse un commit dont l'index porte des marqueurs de conflit (#1616).
#
#  POURQUOI (02/10/2026). En reportant un lot par `cherry-pick`, un conflit sur
#  un fichier en CRLF a été « résolu » par un script dont l'expression attendait
#  des fins de ligne LF : elle n'a rien remplacé, `git add` a suivi, et le
#  commit créé portait `<<<<<<< HEAD` / `=======` / `>>>>>>>` en tête d'un
#  module. RIEN ne l'a refusé : `.githooks/pre-commit` ne contrôlait que le
#  retard sur l'amont. Rattrapé parce que des tests lancés juste après ont
#  échoué à l'import — c'est-à-dire par chance, pas par un contrôle.
#
#  CE QU'IL MESURE. `git diff --cached --check` reconnaît nativement les
#  marqueurs (« leftover conflict marker »), CRLF compris. Il signale AUSSI les
#  espaces en fin de ligne : on ne retient que les marqueurs — un contrôle qui
#  crie sur une ligne de commentaire à espace final est désarmé dans la semaine
#  (`standards/05`). Mesuré avant de câbler : zéro occurrence dans les fichiers
#  versionnés au 02/10/2026, donc rien à rattraper.
#  ⚠️ `LC_ALL=C` : le message est TRADUIT par git selon la locale, et un poste en
#  français ne dirait plus « leftover conflict marker » — le contrôle se
#  tairait en silence. Le cas zéro du self-test le prouve avec le vrai git.
#
#  VERDICTS (code de sortie) :
#    0  aucun marqueur dans l'index
#    1  marqueur(s) trouvé(s) — le commit doit être refusé
#    3  INCONNU : git n'a pas pu mesurer (jamais OK, `standards/04`)
#
#  Dérogation (fichier de test qui contient légitimement un marqueur) :
#  ALLOW_MARQUEURS=1 git commit ...   — lue par le hook, pas par ce script.
#  ⚠️ ALLOW_STALE=1 ne dispense PAS de ce contrôle : il répond à une autre
#  question (le retard sur l'amont), et un marqueur n'est pas « périmé ».
#
#  Usage : bash scripts/poste/verifier-marqueurs-conflit.sh
#          bash scripts/poste/verifier-marqueurs-conflit.sh --selftest
# =============================================================================
set -uo pipefail
# shellcheck source=../lib/lib-poste-gnu.sh
. "$(dirname "$0")/../lib/lib-poste-gnu.sh"
poste_gnu_poser "$@"   # macOS : les outils GNU en tête du PATH, comme Git Bash et la CI (#2419)

RACINE_DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"

# ── Fonction de décision PURE : quelles lignes du rapport sont des marqueurs ─
#  Entrée : la sortie de `git diff --check` sur stdin. Sortie : les seules lignes
#  qui parlent d'un marqueur de conflit (vide si aucune).
trouver_marqueurs() { grep -i 'leftover conflict marker' || true; }

# ── Mesure : l'index du dépôt `$1` (défaut : le répertoire courant) ──────────
#  Rend 0 / 1 / 3 (voir l'en-tête) ; le détail des lignes fautives sur stderr.
verifier_index() {
  local dir="${1:-.}" sortie st trouves
  sortie=$(LC_ALL=C LANGUAGE=C git -C "$dir" diff --cached --check 2>&1)
  st=$?
  trouves=$(printf '%s\n' "$sortie" | trouver_marqueurs)
  if [ -n "$trouves" ]; then
    {
      echo
      echo "✗ Commit refusé : l'index contient des marqueurs de conflit."
      echo
      printf '%s\n' "$trouves" | sed 's/^/    /'
      echo
      echo "  Un conflit résolu à moitié a été ajouté (git add) sans que les lignes"
      echo "  <<<<<<< ======= >>>>>>> aient disparu. Ouvre le fichier, tranche, puis :"
      echo "      git add <fichier>"
      echo "  Le même contrôle se rejoue seul : bash scripts/poste/verifier-marqueurs-conflit.sh"
      echo "  Fichier de test qui porte un marqueur À DESSEIN : ALLOW_MARQUEURS=1 git commit ..."
      echo
    } >&2
    return 1
  fi
  #  0 : git a lu l'index et rien trouvé. 1 et 2 : « des problèmes d'espaces ont
  #  été trouvés » — sans intérêt ici. Tout le reste (128 : pas un dépôt, index
  #  illisible…) est INCONNU : se taire vaudrait un vert.
  case "$st" in
    0|1|2) return 0 ;;
    *) echo "INCONNU : git diff --cached --check a échoué (code $st) — marqueurs de conflit non mesurés." >&2
       return 3 ;;
  esac
}

# ── Self-test : cas fautifs prouvés, cas propres, cas zéro ──────────────────
#  Index fabriqués dans un dépôt TEMPORAIRE, isolé de la configuration de
#  l'utilisateur (ni hooks globaux, ni autocrlf) ; le dépôt réel n'est jamais
#  touché. Le dernier groupe fait tourner le VRAI `.githooks/pre-commit` dans un
#  de ces dépôts : sans lui, on prouverait la fonction mais pas qu'elle est
#  branchée — le défaut même de #561.
verifier_marqueurs_selftest() {
  local ok=0 ko=0 tmp msg
  _ok()   { echo "  OK    $1"; ok=$((ok+1)); }
  _ko()   { echo "  ÉCHEC $1"; ko=$((ko+1)); }
  _attend() {  # _attend <libellé> <attendu> <obtenu>
    if [ "$2" = "$3" ]; then _ok "$1"; else _ko "$1 (attendu $2, obtenu $3)"; fi
  }

  tmp=$(mktemp -d 2>/dev/null) || { echo "INCONNU : mktemp indisponible — self-test non exécuté." >&2; return 3; }
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" RETURN
  export HOME="$tmp/home" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null
  mkdir -p "$HOME"

  _g() { git -C "$1" -c user.name=essai -c user.email=essai@example.org \
              -c core.autocrlf=false -c core.hooksPath=/dev/null "${@:2}"; }
  _depot() {  # _depot <nom> → crée un dépôt vide, affiche son chemin
    mkdir -p "$tmp/$1" && git -C "$tmp/$1" init -q && echo "$tmp/$1"
  }
  _mesure() { verifier_index "$1" >/dev/null 2>&1; echo $?; }

  echo "== Fonction pure =="
  _attend "un rapport qui nomme un marqueur est retenu" "1" \
    "$(printf 'a.txt:1: leftover conflict marker\n' | trouver_marqueurs | wc -l | tr -d ' ')"
  _attend "les espaces en fin de ligne ne sont PAS un marqueur" "0" \
    "$(printf 'a.txt:3: trailing whitespace.\n+x  \n' | trouver_marqueurs | wc -l | tr -d ' ')"
  _attend "cas zéro : un rapport vide ne contient rien" "0" \
    "$(printf '' | trouver_marqueurs | wc -l | tr -d ' ')"

  echo "== Index réel (git en anglais forcé, un dépôt jetable) =="
  local d
  d=$(_depot propre)
  _attend "cas zéro : un index vide est accepté" "0" "$(_mesure "$d")"

  d=$(_depot lf)
  printf 'debut\n<<<<<<< HEAD\nnous\n=======\neux\n>>>>>>> autre\nfin\n' > "$d/a.txt"
  _g "$d" add a.txt
  _attend "marqueurs en LF : refusé" "1" "$(_mesure "$d")"
  msg=$(verifier_index "$d" 2>&1 >/dev/null)   # pas de `grep -q` en tube : SIGPIPE sous pipefail
  case "$msg" in
    *a.txt*) _ok "le message nomme le fichier fautif" ;;
    *) _ko "le message ne nomme pas le fichier fautif ($msg)" ;;
  esac

  d=$(_depot crlf)
  printf 'debut\r\n<<<<<<< HEAD\r\nnous\r\n=======\r\neux\r\n>>>>>>> autre\r\nfin\r\n' > "$d/b.py"
  _g "$d" add b.py
  _attend "marqueurs en CRLF (le cas de #1616) : refusé" "1" "$(_mesure "$d")"

  d=$(_depot seul)
  printf 'x\n=======\ny\n' > "$d/c.txt"
  _g "$d" add c.txt
  _attend "un « ======= » seul (milieu de conflit) : refusé" "1" "$(_mesure "$d")"

  d=$(_depot espaces)
  printf 'une ligne avec espaces   \nune autre\t\n' > "$d/d.txt"
  _g "$d" add d.txt
  _attend "espaces en fin de ligne seuls : accepté" "0" "$(_mesure "$d")"

  d=$(_depot retrait)
  printf '<<<<<<< HEAD\nnous\n=======\neux\n>>>>>>> autre\n' > "$d/e.txt"
  _g "$d" add e.txt && _g "$d" commit -q -m "marqueurs déjà committés"
  printf 'resolu\n' > "$d/e.txt"
  _g "$d" add e.txt
  _attend "un commit qui RETIRE les marqueurs : accepté" "0" "$(_mesure "$d")"

  mkdir -p "$tmp/hors" "$tmp/hors/sous"
  _attend "hors de tout dépôt : INCONNU, jamais OK" "3" \
    "$(GIT_CEILING_DIRECTORIES="$tmp/hors" verifier_index "$tmp/hors/sous" >/dev/null 2>&1; echo $?)"

  echo "== Le hook pre-commit RÉEL, branché =="
  local h="$RACINE_DEPOT/.githooks/pre-commit" sortie st
  if [ ! -f "$h" ]; then
    _ko "le hook $h n'existe pas"
  else
    d=$(_depot hook)
    mkdir -p "$d/scripts/poste"
    cp "$RACINE_DEPOT/scripts/poste/verifier-marqueurs-conflit.sh" \
       "$RACINE_DEPOT/scripts/poste/verifier-fins-de-ligne.py" \
       "$RACINE_DEPOT/scripts/poste/lib_console.py" "$d/scripts/poste/"
    _commit() { _g "$d" -c core.hooksPath="$RACINE_DEPOT/.githooks" commit -q -m "$1" 2>&1; }

    printf 'a\n<<<<<<< HEAD\nb\n=======\nc\n>>>>>>> x\n' > "$d/f.txt"
    _g "$d" add f.txt
    sortie=$(_commit "avec marqueurs"); st=$?
    [ "$st" -ne 0 ] && _ok "hook : un commit à marqueurs est refusé" || _ko "hook : un commit à marqueurs PASSE"
    case "$sortie" in *"marqueurs de conflit"*) _ok "hook : le refus dit pourquoi" ;; *) _ko "hook : refus muet ($sortie)" ;; esac

    sortie=$(ALLOW_STALE=1 _commit "avec marqueurs, ALLOW_STALE"); st=$?
    if [ "$st" -ne 0 ] && case "$sortie" in *"marqueurs de conflit"*) true ;; *) false ;; esac; then
      _ok "hook : ALLOW_STALE=1 ne dispense PAS du contrôle"
    else
      _ko "hook : ALLOW_STALE=1 laisse passer un marqueur, ou refuse pour une autre raison ($sortie)"
    fi

    sortie=$(ALLOW_MARQUEURS=1 _commit "dérogation voulue"); st=$?
    [ "$st" -eq 0 ] && _ok "hook : ALLOW_MARQUEURS=1 déroge" || _ko "hook : ALLOW_MARQUEURS=1 ne déroge pas ($sortie)"

    printf 'propre\n' > "$d/f.txt"
    _g "$d" add f.txt
    sortie=$(_commit "propre"); st=$?
    [ "$st" -eq 0 ] && _ok "hook : un index propre est accepté" || _ko "hook : un index propre est refusé ($sortie)"
  fi

  echo
  if [ "$ko" -eq 0 ]; then
    echo "== TOUS OK ($ok contrôles) =="
    return 0
  fi
  echo "== $ko ÉCHEC(S) sur $((ok+ko)) =="
  return 1
}

if [ "${1:-}" = "--selftest" ]; then verifier_marqueurs_selftest; exit $?; fi
if [ "$#" -gt 0 ]; then
  echo "Usage : $0 [--selftest]" >&2
  exit 2
fi

verifier_index "."
exit $?
