#!/bin/bash
# =============================================================================
#  lib-ci-gel.sh — Un rejeu ne se FIGE plus en silence (#2270)
#
#  Module SOURCÉ par `lib-ci-replay.sh`, jamais exécuté (pas de bit x). Ses cas
#  d'autotest (`ci_gel_cas`) tournent dans `rejouer-ci.sh --selftest`.
#
#  POURQUOI (27-28/10/2026). Quatre rejeux complets se sont figés des heures
#  sans rouge ni message — verrou vivant, pouls frais, étape inchangée —, leurs
#  workers pytest à CPU nul : 44 min, 58 min, 5 h 46. Chacun suivait de près un
#  rejeu interrompu ou un pytest lancé hors rejeu, et des arbres pytest de
#  graines anciennes vivaient encore six heures après la mort de leur lanceur,
#  tenant connexions et schémas sur le PostgreSQL partagé.
#  L'arrêt d'une étape PAR le rejeu emporte bien son arbre (`ci_arreter_pids`,
#  reproduit le 28/10) ; ce qui échappe, c'est l'arbre dont le lanceur meurt
#  sans trap — un outil arrêté, une fenêtre fermée : sous Windows, `taskkill /T`
#  ne retrouve plus des enfants dont le parent est mort.
#  Trois réponses, de la plus tôt à la plus tard :
#    1. le pré-vol TUE les arbres d'un rejeu mort (`lib-ci-arbre.sh` : la fermeture par
#       ppid les retrouve même racine morte) et retire les schémas de test qu'ils
#       tenaient — un reste qui résiste refuse le rejeu, avec sa commande ;
#    2. une étape à la fois LONGUE (au-delà de son plafond, tiré de sa durée
#       mesurée) et MUETTE (sortie inchangée) est déclarée figée : arrêtée,
#       INCONNU, le verrou rendu ;
#    3. au gel, `pg_stat_activity` de la base des tests est relevé dans la
#       sortie de l'étape — la cause se lit au lieu de se supposer.
#  Les décisions sont pures ; les sondes ne font que lire ; le seul geste est
#  l'arrêt de l'étape figée, qui appartient au rejeu.
# =============================================================================

#: Plafond d'une étape sans durée mesurée, et plancher de tout plafond (s).
CI_GEL_PLAFOND_INCONNU=3600
CI_GEL_PLANCHER=1200
#: Facteur appliqué à la durée mesurée : une étape lente sous la charge des
#: sessions voisines a déjà pris 3,5 fois sa durée (self-tests, 1 830 s).
CI_GEL_FACTEUR=4
#: Silence exigé, en plus du plafond, avant de déclarer le gel (s).
CI_GEL_SILENCE="${REJEU_GEL_SILENCE_S:-900}"
#: Intervalle de la surveillance (s).
CI_GEL_INTERVALLE="${REJEU_GEL_INTERVALLE_S:-30}"

# ── Décisions (PURES) ───────────────────────────────────────────────────────
#  Les orphelins (détection ET arrêt) vivent dans `lib-ci-arbre.sh` : `ci_orphelins_traiter`.

#  Le plafond d'une étape, de sa durée mesurée (vide : jamais mesurée).
ci_plafond_etape() {           # $1 = durée mesurée (s) → plafond (s)
  case "${1:-}" in
    ''|*[!0-9]*) echo "$CI_GEL_PLAFOND_INCONNU"; return ;;
  esac
  local p=$(( $1 * CI_GEL_FACTEUR ))
  [ "$p" -lt "$CI_GEL_PLANCHER" ] && p=$CI_GEL_PLANCHER
  echo "$p"
}

#  Figée : au-delà de son plafond ET muette depuis le silence exigé. Une étape
#  longue qui écrit encore travaille ; une étape muette sous son plafond aussi.
ci_gel_verdict() {             # $1 = écoulé · $2 = silence · $3 = plafond · $4 = silence exigé → fige|continue
  if [ "$1" -ge "$3" ] && [ "$2" -ge "$4" ]; then echo fige; else echo continue; fi
}

# ── Sondes (lecture seule) ───────────────────────────────────────────────────
#  L'activité de la base des tests, au moment du gel : qui attend quoi.
ci_activite_base() {
  python - "${TESTS_BASE_URL:-}" 2>&1 <<'PYTHON' | tr -d '\r'
import sys
try:
    import psycopg
    url = sys.argv[1].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, connect_timeout=5) as c:
        lignes = c.execute(
            "SELECT pid, state, wait_event_type, wait_event,"
            " extract(epoch FROM now() - coalesce(xact_start, query_start))::int,"
            " left(regexp_replace(query, '\\s+', ' ', 'g'), 90)"
            " FROM pg_stat_activity WHERE datname = current_database()"
            " AND pid <> pg_backend_pid() ORDER BY 5 DESC NULLS LAST LIMIT 30"
        ).fetchall()
    print(f"{len(lignes)} connexion(s) à la base des tests")
    for l in lignes:
        print("  pid=%s %s attente=%s/%s depuis=%ss · %s" % l)
except Exception as erreur:
    print("pg_stat_activity illisible : " + (str(erreur).strip().splitlines() or ["?"])[0][:160])
PYTHON
}

#  La fin du journal de pytest, dont le chemin est annoncé dans la sortie de l'étape
#  (`mesure-postgresql.sh`) : `faulthandler_timeout` y écrit la pile de chaque test resté
#  bloqué — la cause d'un gel se lit là, au lieu de se supposer.
CI_GEL_LIGNES_PYTEST=${CI_GEL_LIGNES_PYTEST:-80}
ci_gel_journal_pytest() {      # $1 = sortie de l'étape (fichier)
  local j; j=$(sed -n 's/^Journal pytest : //p' "$1" 2>/dev/null | tail -1 | tr -d '')
  [ -n "$j" ] && [ -f "$j" ] || { echo "journal de pytest non annoncé par l'étape"; return 0; }
  echo "── fin de $j ──"
  tail -n "$CI_GEL_LIGNES_PYTEST" "$j" | tr -d ''
}

#  Les schémas de test qu'un arbre mort a laissés : ceux de plus d'une heure (aucune suite
#  n'en dure une, et le rejeu tient le verrou) ; la suite, elle, n'en retire que de plus de
#  6 h. Par `app.dialecte`, jamais une seconde écriture de la règle. Une ligne de sortie.
ci_gel_schemas_purger() {      # $1 = racine du dépôt
  [ -n "${TESTS_BASE_URL:-}" ] || { echo "· schémas de test : TESTS_BASE_URL absent, non purgés"; return 0; }
  (cd "$1/api" && PYTHONUTF8=1 timeout 60 python - <<'PYTHON' 2>&1 | tr -d '' | tail -1)
import os
import sys
from datetime import timedelta

sys.path.insert(0, ".")
try:
    from app.dialecte import retirer_schemas_jetables_perimes

    n = retirer_schemas_jetables_perimes(os.environ["TESTS_BASE_URL"], plus_vieux_que=timedelta(hours=1))
    print(f"· schémas de test de plus d'une heure : {n} retiré(s)")
except Exception as erreur:  # noqa: BLE001 — une purge manquée ne change pas le verdict
    print("· schémas de test non purgés :", (str(erreur).strip().splitlines() or ["sans message"])[0][:140])
PYTHON
}

# ── Le geste : surveiller UNE étape, l'arrêter si elle est figée ────────────
#  Tourne en arrière-plan à côté de l'étape ; s'éteint avec elle. Au gel :
#  `$d/gel` porte le motif, la sortie reçoit l'activité de la base, puis
#  l'étape est arrêtée avec son arbre.
ci_surveiller_etape() {        # $1 = dossier de l'étape · $2 = pid de l'étape
  local d="$1" pid="$2" t0=$EPOCHSECONDS plafond silence
  plafond=$(ci_plafond_etape "$(cat "$d/mesuree" 2>/dev/null)")
  while kill -0 "$pid" 2>/dev/null; do
    sleep "$CI_GEL_INTERVALLE"
    silence=$(( EPOCHSECONDS - $(stat -c %Y "$d/sortie" 2>/dev/null || echo "$EPOCHSECONDS") ))
    [ "$(ci_gel_verdict $(( EPOCHSECONDS - t0 )) "$silence" "$plafond" "$CI_GEL_SILENCE")" = fige ] || continue
    echo "figée : $(( (EPOCHSECONDS - t0) / 60 )) min (plafond $(( plafond / 60 )) min), muette depuis $(( silence / 60 )) min — arrêtée" > "$d/gel"
    { echo; echo "── Gel (#2270) : activité de la base des tests ──"
      ci_dans_etape "$(<"$d/rep")" "$d/env" ci_activite_base
      echo "── Gel (#2270) : fin du journal de pytest ──"; ci_gel_journal_pytest "$d/sortie"; } >> "$d/sortie" 2>&1
    ci_arreter_pids "$pid"
    return 0
  done
}

# ── Cas d'autotest — appelés par `ci_replay_selftest`, avec son `t` ─────────
ci_gel_cas() {
  t "plafond — jamais mesurée" "$(ci_plafond_etape '')" "3600"
  t "plafond — étape courte : le plancher" "$(ci_plafond_etape 60)" "1200"
  t "plafond — pytest (521 s)" "$(ci_plafond_etape 521)" "2084"
  t "plafond — mesure illisible : comme jamais mesurée" "$(ci_plafond_etape 5x)" "3600"
  t "gel — longue ET muette" "$(ci_gel_verdict 2100 900 2084 900)" "fige"
  t "gel — longue mais elle écrit" "$(ci_gel_verdict 9000 30 2084 900)" "continue"
  t "gel — muette sous son plafond" "$(ci_gel_verdict 1500 1500 2084 900)" "continue"
}
