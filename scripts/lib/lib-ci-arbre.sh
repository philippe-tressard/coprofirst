#!/bin/bash
# =============================================================================
#  lib-ci-arbre.sh — L'ARBRE de processus d'un rejeu : le relever, le tuer, et
#  repérer ceux qu'un rejeu mort a laissés derrière lui (#2270)
#
#  Module SOURCÉ par `lib-ci-verrou.sh`, `lib-ci-execution.sh` et le pré-vol ;
#  exécuté seulement pour son `--selftest` (job `test-scripts`). Pas de bit x.
#
#  POURQUOI (28/10/2026). Quatre rejeux se sont figés pendant des heures, et deux
#  arbres pytest d'anciens rejeux arrêtés (graines 764048110 et 591126264) sont
#  restés vivants PLUS DE SIX HEURES après la mort de leur lanceur, tenant des
#  connexions et des schémas sur le PostgreSQL partagé. Mesuré ici, sous Git Bash :
#    - `kill -9` du rejeu laisse TOUT son arbre vivant (shells, python, workers) ;
#    - Windows ne rattache jamais un orphelin : son ppid reste celui du père MORT ;
#    - `taskkill /T /PID <père mort>` répond « introuvable » et ne tue rien ;
#    - en revanche, la FERMETURE par ppid de la table des processus retrouve
#      l'arbre, même quand sa racine n'existe plus.
#  Ce module est cette fermeture, et le geste qui tue ce qu'elle trouve.
#
#  Sous Linux (CI GitHub, sessions cloud), un orphelin est adopté par init : sa
#  racine morte ne se retrouve plus, et seul un arbre RELEVÉ AVANT la mort se tue
#  (le veilleur le fait). Les orphelins d'un rejeu mort ne se repèrent donc que
#  sous Windows — dit, jamais tu (`ci_orphelins_possibles`).
#
#  TABLE (TSV) : pid, ppid, début (secondes unix), nom, ligne de commande.
#  Les fonctions marquées (PURE) ne lisent que leur entrée standard.
# =============================================================================

CI_PS1_PROCESSUS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-ci-processus.ps1"

#: Ce qui fait d'un processus un reste de rejeu : le rejeu lui-même (ses
#: sous-shells portent sa ligne de commande), pytest, et le worker de xdist.
CI_ORPHELINS_MOTIF='(rejouer-ci\.sh|-m +pytest|import sys;exec\(eval\(sys\.stdin\.readline\(\)\)\))'
#: Un processus plus jeune n'est jamais jugé orphelin : son père peut venir de finir.
CI_ORPHELINS_AGE_MIN_S=${CI_ORPHELINS_AGE_MIN_S:-60}

ci_est_windows() {
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) return 0 ;; *) return 1 ;; esac
}
ci_orphelins_possibles() { ci_est_windows; }

# ── Relever la table ─────────────────────────────────────────────────────────
#  Le ppid de Windows ment pour les programmes de Cygwin/MSYS : un `fork` suivi d'un
#  `exec` (sleep, awk, un sous-shell) laisse l'enfant rattaché à un intermédiaire déjà
#  mort. MSYS, lui, sait qui est le père — tant que ce père vit. La table prend donc le
#  père de MSYS quand il existe (traduit en pid Windows), celui de Windows sinon : un
#  orphelin MSYS est rattaché à 1, et c'est alors Windows qui garde la trace du père mort.
ci_proc_table_windows() {
  command -v powershell.exe >/dev/null 2>&1 || return 1
  awk -F'\t' -v OFS='\t' '
    f == 1 { split($0, a, " "); n++; mq[n] = a[2]; mw[n] = a[3]; wm[a[1]] = a[3]; next }
    f == 2 {
      if (!pret) { for (i = 1; i <= n; i++) if (mq[i] > 1 && (mq[i] in wm)) over[mw[i]] = wm[mq[i]]; pret = 1 }
      if ($1 in over) $2 = over[$1]
      print
    }' f=1 <(ps -e 2>/dev/null | awk 'NR > 1 { sub(/^[^0-9]+/, ""); print $1, $2, $4 }') \
       f=2 <(powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "$CI_PS1_PROCESSUS")" 2>/dev/null | tr -d '\r')
}
#  macOS (#2419) : `ps` n'y connaît pas `etimes`, et un mot-clé inconnu ne l'arrête
#  pas — il sort les autres colonnes, décalées, et l'âge se lisait dans le nom.
#  L'âge s'y lit dans `etime` ([[j-]hh:]mm:ss) ; le nom, dans le premier mot de la
#  ligne de commande (`comm` y est un chemin, qui peut porter des espaces). PURE :
#  $1 = maintenant (epoch), l'entrée est la sortie de `ps -A -o pid=,ppid=,etime=,args=`.
ci_ps_bsd_lire() {
  awk -v now="$1" '
    function secondes(s,   j, d, a, n) {
      j = 0
      if (s ~ /-/) { split(s, d, "-"); j = d[1]; s = d[2] }
      n = split(s, a, ":")
      if (n == 3) return j * 86400 + a[1] * 3600 + a[2] * 60 + a[3]
      if (n == 2) return j * 86400 + a[1] * 60 + a[2]
      return -1
    }
    NF >= 4 {
      e = secondes($3); if (e < 0) next
      pid = $1; ppid = $2; nom = $4; sub(/.*\//, "", nom)
      $1 = $2 = $3 = ""; sub(/^ +/, "")
      printf "%s\t%s\t%d\t%s\t%s\n", pid, ppid, now - e, nom, $0
    }'
}
ci_proc_table() {          # → la table de TOUS les processus (lecture seule) ; code ≠ 0 si illisible
  local t
  if ci_est_windows; then
    t=$(ci_proc_table_windows) || return 1
  elif [ "$(uname -s)" = Darwin ]; then
    t=$(ps -A -o pid=,ppid=,etime=,args= 2>/dev/null | ci_ps_bsd_lire "$(date +%s)")
  else
    t=$(ps -eo pid=,ppid=,etimes=,comm=,args= 2>/dev/null | awk -v now="$(date +%s)" '
      { pid = $1; ppid = $2; e = $3; nom = $4; $1 = $2 = $3 = $4 = ""; sub(/^ +/, "")
        printf "%s\t%s\t%d\t%s\t%s\n", pid, ppid, now - e, nom, $0 }')
  fi
  [ -n "$t" ] || return 1     # une table vide n'est pas « aucun processus » : c'est une lecture ratée
  printf '%s\n' "$t"
}
ci_winpid() {              # $1 = pid MSYS → son pid Windows (le même hors MSYS)
  local w=""
  [ -r "/proc/$1/winpid" ] && w=$(<"/proc/$1/winpid")
  echo "${w:-$1}"
}

# ── Décisions (PURES) ────────────────────────────────────────────────────────
#  Les descendants STRICTS de la racine, par fermeture des ppid — la racine peut
#  ne plus exister. Deux gardes contre la réutilisation d'un pid, que Windows
#  recycle vite : un enfant plus VIEUX que son père (présent dans la table) lui
#  fait référence par un pid recyclé, et la fenêtre [début, fin] écarte ce qui a
#  été créé hors de la vie du rejeu.
#    $1 = racine · $2 = début min · $3 = fin max (secondes unix ; vides : sans borne)
ci_proc_descendants() {
  awk -F'\t' -v r="$1" -v dmin="${2:-0}" -v dmax="${3:-99999999999}" '
    { deb[$1] = $3; kids[$2] = kids[$2] " " $1 }
    END {
      h = 1; t = 1; q[1] = r; vu[r] = 1
      while (h <= t) {
        p = q[h++]; m = split(kids[p], a, " ")
        for (i = 1; i <= m; i++) {
          c = a[i]
          if (c in vu) continue
          if (deb[c] + 0 < dmin + 0 || deb[c] + 0 > dmax + 0) continue
          if ((p in deb) && deb[c] + 0 < deb[p] + 0) continue
          vu[c] = 1; q[++t] = c; print c
        }
      }
    }'
}
#  Le processus et ses ancêtres, jusqu'au premier absent de la table : ce qu'un
#  tueur ne doit JAMAIS emporter, car c'est lui.
ci_proc_ancetres() {       # $1 = pid
  awk -F'\t' -v p="$1" '
    { par[$1] = $2 }
    END { n = 0; while ((p in par) && !(p in vu) && n < 64) { print p; vu[p] = 1; p = par[p]; n++ } }'
}
#  Les RACINES des restes d'un rejeu : un processus qui porte le motif et dont le
#  père n'existe plus (ou est plus jeune que lui — pid recyclé). Un père absent
#  ne suffit pas à lui seul : l'explorateur Windows en a un, et tout ce qu'on
#  lance depuis un terminal en descend.
#    $1 = maintenant · $2 = âge minimal (s) → « pid<TAB>âge<TAB>ligne »
ci_proc_orphelins() {
  #  Le motif passe par l'environnement : `-v` interprète les barres inverses de l'expression.
  MOTIF="$CI_ORPHELINS_MOTIF" awk -F'\t' -v now="$1" -v amin="${2:-60}" '
    BEGIN { motif = ENVIRON["MOTIF"] }
    { n++; id[n] = $1; par[$1] = $2; deb[$1] = $3; lig[$1] = $5 }
    END {
      for (i = 1; i <= n; i++) {
        p = id[i]
        if (lig[p] !~ motif) continue
        q = par[p]
        if (q == "" || q + 0 <= 4) continue                       # système : pas un lanceur
        if ((q in deb) && deb[q] + 0 <= deb[p] + 0) continue      # père vivant
        if (now - deb[p] < amin) continue
        printf "%s\t%d\t%s\n", p, now - deb[p], substr(lig[p], 1, 160)
      }
    }'
}

# ── Tuer ─────────────────────────────────────────────────────────────────────
ci_proc_tuer_liste() {     # $@ = pids (Windows : ceux de la table) → tués d'un coup, sans les arbres
  [ $# -gt 0 ] || return 0
  if ci_est_windows && command -v taskkill >/dev/null 2>&1; then
    local args=() p
    for p in "$@"; do args+=(//PID "$p"); done
    taskkill //F "${args[@]}" >/dev/null 2>&1
  else
    kill -KILL "$@" 2>/dev/null
  fi
  return 0
}
#  Tue l'arbre de chaque racine, racine comprise (`avec`) ou non (`sous`), SAUF
#  l'appelant et ses ancêtres (il se tuerait lui-même : une substitution de
#  commande est un descendant du rejeu), et les `épargnés` avec leurs descendants
#  (le veilleur). Plusieurs passes : un processus lancé entre le relevé et le
#  coup de grâce y passe aussi. Code 0 si plus rien ne vit, 1 sinon (et les
#  survivants sont nommés sur la sortie d'erreur).
#    $1 = avec|sous · $2 = racines (pids de la table) · $3 = épargnés · $4 = table relevée avant
ci_proc_tuer() {
  local mode="$1" racines="$2" epargnes="${3:-}" table="${4:-}" passe r e cibles exclus moi vises
  moi=$(ci_winpid "${BASHPID:-$$}")
  for passe in 1 2 3 4 5 6; do
    if [ "$passe" -gt 1 ] || [ -z "$table" ]; then table=$(ci_proc_table) || return 1; fi
    exclus=" $(printf '%s\n' "$table" | ci_proc_ancetres "$moi" | tr '\n' ' ') "
    for e in $epargnes; do
      exclus="$exclus$e $(printf '%s\n' "$table" | ci_proc_descendants "$e" | tr '\n' ' ') "
    done
    cibles=""
    for r in $racines; do
      [ "$mode" = avec ] && printf '%s\n' "$table" | awk -F'\t' -v p="$r" '$1 == p { f = 1 } END { exit !f }' && cibles="$cibles $r"
      cibles="$cibles $(printf '%s\n' "$table" | ci_proc_descendants "$r" | tr '\n' ' ')"
    done
    vises=""
    for r in $cibles; do
      case "$exclus" in *" $r "*) ;; *) vises="$vises $r" ;; esac
    done
    # shellcheck disable=SC2086  # liste de pids
    [ -n "${vises// /}" ] || return 0
    if [ "$passe" -eq 6 ]; then echo "⚠ survivants après 5 passes :${vises}" >&2; return 1; fi
    # shellcheck disable=SC2086
    ci_proc_tuer_liste $vises
    sleep 0.5
  done
}

# ── Les restes d'un rejeu mort ───────────────────────────────────────────────
#  Relève, nomme et tue les arbres dont la racine est un reste de rejeu (motif)
#  au père disparu. Sort une ligne par arbre, puis « tués N arbre(s) » ; code 0
#  si rien ne reste, 1 si un survivant résiste, 2 si la table est illisible.
#    $1 = tuer|signaler
ci_orphelins_traiter() {
  local mode="${1:-tuer}" table racines n=0 pid age ligne
  ci_orphelins_possibles || { echo "· restes d'un rejeu mort : non repérables hors Windows (init adopte les orphelins)"; return 0; }
  table=$(ci_proc_table) || { echo "? table des processus illisible : les restes d'un rejeu mort ne sont pas recherchés"; return 2; }
  racines=$(printf '%s\n' "$table" | ci_proc_orphelins "$(date +%s)" "$CI_ORPHELINS_AGE_MIN_S")
  [ -n "$racines" ] || { echo "· aucun reste de rejeu mort"; return 0; }
  while IFS=$'\t' read -r pid age ligne; do
    n=$((n + 1))
    echo "  ⚠ reste d'un rejeu mort : pid $pid, depuis $((age / 60)) min — ${ligne:0:110}"
  done <<< "$racines"
  if [ "$mode" = signaler ]; then
    echo "  (REJEU_ORPHELINS=signaler : rien n'est tué — en root de l'arbre, taskkill //F //T //PID <pid>)"
    return 0
  fi
  ci_proc_tuer avec "$(printf '%s\n' "$racines" | cut -f1 | tr '\n' ' ')" "" "$table" \
    || { echo "  ✗ un reste de rejeu mort résiste : il tient peut-être des connexions sur la base des tests"; return 1; }
  echo "  ✓ $n arbre(s) de rejeu mort tué(s) — connexions et schémas qu'ils tenaient libérés"
  return 0
}

# ── Self-test ────────────────────────────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  # shellcheck source=lib-ci-arbre.selftest.sh
  . "$(dirname "${BASH_SOURCE[0]}")/lib-ci-arbre.selftest.sh"
  ci_arbre_selftest
  exit $?
fi
