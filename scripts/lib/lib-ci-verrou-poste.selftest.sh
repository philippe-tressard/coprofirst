#!/bin/bash
# =============================================================================
#  lib-ci-verrou-poste.selftest.sh — Les cas de `lib-ci-verrou-poste.sh --selftest` (#2765)
#
#  Sourcé par `lib-ci-verrou-poste.sh --selftest` seulement (job `test-scripts`).
#  Le COMPORTEMENT sur de vrais rejeux : `rejouer-ci.sh` copié dans des dépôts
#  jetables, sur un `ci.yml` d'une seule étape témoin, sous un DOUBLE du verrou du
#  poste. Le verrou réel n'est jamais pris : VERROU_POSTE_PY nomme le double, et
#  VERROU_POSTE_DIR un dossier jetable — que le vrai lirait aussi, si l'on se trompait
#  de chemin. Ce que le double imite : le contrat de `verrou_poste.py` — `prendre
#  --libelle L [--depot D] [--session S] -- <commande>`, qui DEVIENT la commande sous un
#  flock, et `etat` ; il est confronté au vrai quand le poste l'a (dernier cas).
# =============================================================================

ci_verrou_poste_selftest() {
  local st=0 vd ici journal x r1 r2 c1 c2 code reel aide
  t() { [ "$2" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1  attendu=[$3] obtenu=[$2]"; st=1; }; }
  #  Une attente se borne par une CONDITION, jamais par un délai (#2298) : 20 s au plus.
  _attendre() { local _i; for _i in $(seq 1 100); do "$@" && return 0; sleep 0.2; done; return 1; }
  ici=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
  vd=$(mktemp -d); journal="$vd/journal"

  cat > "$vd/verrou_poste.py" <<'PY'
import fcntl, os, pathlib, sys
d = pathlib.Path(os.environ["VERROU_POSTE_DIR"]); d.mkdir(parents=True, exist_ok=True)
a = sys.argv[1:]
verrou = open(d / "verrou", "a+")
if a == ["etat"]:
    try:
        fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("Libre")
    except BlockingIOError:
        print("Tenu par : « %s »" % (d / "tenu").read_text(encoding="utf-8"))
    sys.exit(0)
if a[:1] != ["prendre"] or "--" not in a:
    sys.exit("double : prendre --libelle L [--depot D] [--session S] -- <commande>")
i = a.index("--"); opts, cmd = a[1:i], a[i + 1:]
cles = opts[0::2]
if not cmd or len(opts) % 2 or "--libelle" not in cles or set(cles) - {"--libelle", "--depot", "--session"}:
    sys.exit("double : options refusées " + repr(opts))
fcntl.flock(verrou, fcntl.LOCK_EX)
(d / "tenu").write_text(opts[2 * cles.index("--libelle") + 1], encoding="utf-8")
with open(d / "appels", "a", encoding="utf-8") as f:
    f.write(repr(opts) + "\n")
os.set_inheritable(verrou.fileno(), True)
os.execvp(cmd[0], cmd)
PY

  _depot() {               # $1 = nom → un dépôt jetable : les scripts du lot, une étape témoin
    local d="$vd/$1"
    mkdir -p "$d/.github/workflows" && cp -R "$ici/scripts" "$d/"
    cat > "$d/.github/workflows/ci.yml" <<'YML'
name: essai
on: push
jobs:
  temoin:
    runs-on: ubuntu-latest
    steps:
      - name: Témoin
        run: echo "debut $TEMOIN" >> "$JOURNAL"; sleep 2; echo "fin $TEMOIN" >> "$JOURNAL"
YML
    git -C "$d" -c init.defaultBranch=essai init -q && git -C "$d" add -A \
      && git -C "$d" -c user.name=essai -c user.email=essai@exemple.test -c core.hooksPath=/dev/null \
           -c commit.gpgsign=false commit -qm essai
  }
  _rejeu() {               # $1 = dépôt · $2 = témoin · $3 = verrou_poste.py → code du rejeu
    ( cd "$vd/$1" && env -u REJEU_SOUS_VERROU_POSTE -u REJEU_DOSSIER_COMMUN -u MARQUEUR_CI -u CI_FICHIER \
        VERROU_POSTE_PY="$3" VERROU_POSTE_DIR="$vd/poste" TEMOIN="$2" JOURNAL="$journal" \
        bash scripts/poste/rejouer-ci.sh > "$vd/$2.sortie" 2>&1 )
  }
  _apparie() {             # $1 = journal → oui si chaque début est suivi de SA fin, deux tâches
    awk 'NR % 2 == 1 { if ($1 != "debut") m = 1; w = $2 }
         NR % 2 == 0 { if ($1 != "fin" || $2 != w) m = 1 }
         END { print (NR == 4 && !m) ? "oui" : "non" }' "$1"
  }
  _attend_le_poste() { grep -q "attente du verrou du poste" "$vd/a/.git/rejeu-ci.verrou/battement" 2>/dev/null; }
  _r_parti() { _attend_le_poste || grep -q "debut r" "$journal"; }
  _poste() { VERROU_POSTE_PY="$vd/verrou_poste.py" VERROU_POSTE_DIR="$vd/poste" ci_verrou_poste_dire; }

  # ── La décision d'entrée (PURE) ──────────────────────────────────────────
  t "entrée — sans marqueur : première"           "$(ci_verrou_poste_entree "" 42 "")" "premiere"
  t "entrée — marqueur d'un autre pid : première"  "$(ci_verrou_poste_entree 41 42 42)" "premiere"
  t "entrée — sous le poste, verrou à soi"         "$(ci_verrou_poste_entree 42 42 42)" "reentree"
  t "entrée — sous le poste, verrou d'un autre"    "$(ci_verrou_poste_entree 42 42 43)" "perdu"
  t "entrée — sous le poste, verrou disparu"       "$(ci_verrou_poste_entree 42 42 "")" "perdu"
  t "chemin — défaut sous \$HOME, jamais en dur"   "$(HOME=/h VERROU_POSTE_PY='' ci_verrou_poste_chemin)" "/h/.claude/bin/verrou_poste.py"
  t "absent — dit INCONNU, avec le chemin"         "$(VERROU_POSTE_PY="$vd/nulle-part.py" ci_verrou_poste_dire)" "INCONNU — $vd/nulle-part.py introuvable"

  _depot a && _depot b && _depot c || { echo "FAIL  dépôts jetables non construits"; rm -rf "$vd"; return 1; }

  # ── Un rejeu et une tâche lourde d'un autre dépôt (le xcodebuild) ────────
  #  X tient le poste jusqu'au signal ; le rejeu, lancé pendant, doit l'attendre.
  : > "$journal"
  VERROU_POSTE_DIR="$vd/poste" python3 "$vd/verrou_poste.py" prendre --libelle xcodebuild -- \
    sh -c 'echo "debut x" >> "$1"; while [ ! -f "$2" ]; do sleep 0.1; done; echo "fin x" >> "$1"' _ "$journal" "$vd/go" &
  x=$!
  _attendre grep -q "debut x" "$journal"
  t "état — le tenant du poste est nommé"          "$(_poste)" "Tenu par : « xcodebuild »"
  _rejeu a r "$vd/verrou_poste.py" & r1=$!
  _attendre _r_parti
  t "ordre — verrou du rejeu pris, PUIS le poste attendu" "$(_attend_le_poste && echo oui || echo non)" "oui"
  t "rejeu — n'a pas commencé tant que le poste est tenu" "$(grep -c 'debut r' "$journal")" "0"
  t "etat-rejeu.sh — dit l'attente et qui tient le poste" \
    "$(cd "$vd/a" && VERROU_POSTE_PY="$vd/verrou_poste.py" VERROU_POSTE_DIR="$vd/poste" bash scripts/poste/etat-rejeu.sh \
       | grep -cE 'attente du verrou du poste|Tenu par : « xcodebuild »')" "2"
  touch "$vd/go"; wait "$x"; wait "$r1"; code=$?
  t "rejeu et tâche lourde — l'un après l'autre"    "$(tr '\n' ' ' < "$journal")" "debut x fin x debut r fin r "
  t "rejeu — vert, son code traverse le verrou"     "$code" "0"
  t "rejeu — appel au contrat (libellé, dépôt)"     "$(grep -c "'--libelle', 'rejeu de la CI'.*'--depot'" "$vd/poste/appels")" "1"

  # ── Deux rejeux lancés ensemble, de deux clones : seul le poste les départage ──
  : > "$journal"
  _rejeu b p "$vd/verrou_poste.py" & r1=$!
  _rejeu c q "$vd/verrou_poste.py" & r2=$!
  wait "$r1"; c1=$?; wait "$r2"; c2=$?
  t "deux rejeux simultanés — tous deux verts"     "$c1 $c2" "0 0"
  t "deux rejeux simultanés — l'un après l'autre"  "$(_apparie "$journal")" "oui"
  t "après — le poste est libre"                   "$(_poste)" "Libre"
  t "après — le verrou du rejeu est rendu"         "$([ -d "$vd/b/.git/rejeu-ci.verrou" ] && echo tenu || echo rendu)" "rendu"
  t "après — etat-rejeu.sh dit le poste libre" \
    "$(cd "$vd/b" && VERROU_POSTE_PY="$vd/verrou_poste.py" VERROU_POSTE_DIR="$vd/poste" bash scripts/poste/etat-rejeu.sh | grep -c 'Libre$')" "1"

  # ── Verrou du poste ABSENT (CI, autre machine) : le rejeu passe et le dit ──
  : > "$journal"
  _rejeu a z "$vd/absent/verrou_poste.py"; code=$?
  t "absent — le rejeu reste possible (vert)"      "$code" "0"
  t "absent — il le dit INCONNU, jamais OK"        "$(grep -c 'Verrou du poste INCONNU' "$vd/z.sortie")" "1"
  t "absent — son étape a tourné"                  "$(tr '\n' ' ' < "$journal")" "debut z fin z "

  # ── Le double contre le vrai, quand le poste l'a ─────────────────────────
  #  `prendre --help` sort à l'analyse des arguments : ni file, ni verrou touchés.
  reel="${HOME:-}/.claude/bin/verrou_poste.py"
  if [ -f "$reel" ]; then
    aide=$(python3 "$reel" prendre --help 2>&1)
    t "contrat — le vrai verrou_poste.py prend --libelle et --depot" \
      "$([[ $aide == *--libelle* && $aide == *--depot* ]] && echo oui || echo non)" "oui"
  else
    echo "INFO  contrat du vrai verrou_poste.py : INCONNU ici ($reel absent) — seul le double est éprouvé"
  fi

  #  En sortie, plus rien du test ne tient le double ni ne survit.
  touch "$vd/go"; wait; rm -rf "$vd"
  [ "$st" -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHEC(S) =="
  return "$st"
}
