#!/bin/bash
# =============================================================================
#  lib-ci-base.sh — La base PostgreSQL des TESTS, vue par le rejeu de la CI
#
#  Module SOURCÉ par `lib-ci-replay.sh`, jamais exécuté (pas de bit x). Ses cas
#  d'autotest (`ci_base_cas`) tournent dans `rejouer-ci.sh --selftest`, avec le
#  `t` de `ci_replay_selftest`.
#
#  La suite pytest exige un serveur PostgreSQL (`TESTS_BASE_URL`,
#  `tests/aides_base`) : la CI GitHub l'obtient d'un conteneur de service, le
#  poste d'un PostgreSQL 17 natif (base `essai`, rôle `essai`). Le rejeu pose
#  l'adresse du poste quand personne ne l'a posée, et SONDE le serveur avant
#  l'étape : un serveur arrêté ferait échouer chaque test sur une connexion
#  refusée — un FAIL qui ne dit rien du lot. Il rend alors INCONNU, avec la
#  commande qui répare, jamais OK.
#  Fonctions pures : texte en entrée, texte en sortie.
# =============================================================================

#: L'adresse de la base des tests sur le poste — celle de la CI, à l'hôte près.
CI_BASE_TESTS_DEFAUT="postgresql+psycopg://essai:essai@127.0.0.1:5432/essai"

#: Ce qui répare le cas le plus courant : le service Windows arrêté.
CI_BASE_TESTS_REPARER="net start postgresql-17 (invite en administrateur) — base « essai », rôle « essai »"

#  Une étape LANCE-t-elle pytest ? `pytest …` ou `python -m pytest …` en tête
#  de commande ; jamais un commentaire, jamais l'installation (`pip install
#  pytest`, qui n'est d'ailleurs jamais rejouée). (PURE) Corps sur stdin → oui | non
ci_lance_pytest() {
  #  …ou par son lanceur, `mesure-postgresql.sh` (#2223) : la commande de ci.yml
  #  depuis le 24/10, que ce motif ne voyait plus (#2270).
  local _corps; _corps=$(grep -v '^[[:space:]]*#' || true)
  grep -Eq '(^|[;&|(]|then|do)[[:space:]]*((python[0-9.]*[[:space:]]+-m[[:space:]]+)?pytest([[:space:]]|$)|bash[[:space:]]+[^[:space:]]*/mesure-postgresql\.sh)' <<<"$_corps" \
    && echo oui || echo non
}

#  Ce que la sonde a répondu → "" (mesurable) | motif d'INCONNU. (PURE)
#    ok · « injoignable : <raison> » · « psycopg absent » · vide (python muet)
ci_base_tests_etat() {
  case "${1:-}" in
    ok)             echo "" ;;
    injoignable*)   echo "base des tests ${1} · réparer : $CI_BASE_TESTS_REPARER" ;;
    "psycopg absent") echo "base des tests non sondée : psycopg absent du poste (pip install -r api/requirements-dev.txt)" ;;
    *)              echo "base des tests non sondée : python muet" ;;
  esac
}

#  La sonde : une connexion réelle à `TESTS_BASE_URL`, bornée à 5 s. Sa sortie
#  est la seule entrée de `ci_base_tests_etat`. Python est un binaire Windows
#  sur le poste : le retour chariot de sa sortie est retiré.
ci_sonder_base_tests() {
  python - "${TESTS_BASE_URL:-}" 2>/dev/null <<'PYTHON' | tr -d '\r' | tail -1
import sys
try:
    import psycopg
except ImportError:
    print("psycopg absent")
    sys.exit(0)
url = sys.argv[1].replace("postgresql+psycopg://", "postgresql://", 1)
try:
    psycopg.connect(url, connect_timeout=5).close()
except Exception as erreur:
    raison = (str(erreur).strip().splitlines() or ["sans message"])[0][:160]
    print("injoignable : " + raison)
    sys.exit(0)
print("ok")
PYTHON
}

# ── Le CATALOGUE de la base des tests (#2399) ───────────────────────────────
#  Le 31/10/2026, deux suites pytest ont gelé au-delà de 45 min au lieu de 686 s :
#  les suites coupées avaient laissé 140 schémas jetables (52 000 relations), et
#  `pg_attribute` pesait 7,6 Go dont 31,9 M de tuples morts. Chaque DDL d'un worker
#  payait le catalogue : un DDL témoin prenait 396 ms, un `CREATE TABLE` sous
#  12 workers 5 à 6 s. Rien ne le disait — la CI GitHub, base neuve à chaque
#  passage, ne le voit jamais. Le pré-vol MESURE donc le catalogue après la purge
#  des schémas abandonnés, le compacte d'office au-delà d'un seuil (le rôle des
#  tests est superutilisateur), puis refuse s'il reste gonflé.

#: Les tables du catalogue que les schémas jetables gonflent — mesurées ET compactées.
CI_CATALOGUE_TABLES="pg_attribute pg_class pg_type pg_depend pg_index pg_constraint"
#: Seuils. Sain le 31/10/2026 : témoin 3 à 16 ms, 22 000 relations, quelques centaines
#: d'octets par ligne vivante après compactage ; gonflé : 396 ms et 22 Ko par ligne.
CI_CATALOGUE_TEMOIN_MS=150        # DDL témoin, meilleur de trois essais
CI_CATALOGUE_MORTS_PCT=20         # tuples morts / (vivants + morts), statistiques du serveur
CI_CATALOGUE_OCTETS_LIGNE=2000    # place des tables (index compris) par ligne vivante : le
                                  # gonflement qu'un VACUUM ordinaire laisse, morts remis à 0
CI_CATALOGUE_RELATIONS=30000      # au-delà, après la purge : des schémas TENUS, que compacter ne retire pas

#: Ce qui répare à la main, hors de tout rejeu.
CI_CATALOGUE_REPARER="psql -h 127.0.0.1 -U essai -d essai -c \"VACUUM (FULL, ANALYZE) $(printf 'pg_catalog.%s, ' $CI_CATALOGUE_TABLES | sed 's/, $//')\""

#  Le verdict, de la sonde. (PURE)
#    $1 = sonde : « relations=N jetables=N morts=P octets=N temoin=N » | « illisible : … » | vide
#    $2 = oui si le catalogue vient d'être compacté
#    → "" (sain) | "COMPACTER <motifs>" | "REFUS <motif>"
ci_catalogue_verdict() {
  local s="${1:-}" cle val r="" j="" m="" o="" t="" motifs=""
  case "$s" in
    relations=*) ;;
    illisible*) echo "REFUS catalogue de la base des tests ${s} — INCONNU, jamais OK"; return ;;
    *) echo "REFUS catalogue de la base des tests non mesuré (sonde muette) — INCONNU, jamais OK"; return ;;
  esac
  for cle in $s; do
    val=${cle#*=}
    case "$val" in ''|*[!0-9]*) echo "REFUS catalogue de la base des tests illisible ($s) — INCONNU, jamais OK"; return ;; esac
    case "${cle%%=*}" in relations) r=$val ;; jetables) j=$val ;; morts) m=$val ;; octets) o=$val ;; temoin) t=$val ;; esac
  done
  [ -n "$r" ] && [ -n "$j" ] && [ -n "$m" ] && [ -n "$o" ] && [ -n "$t" ] \
    || { echo "REFUS catalogue de la base des tests incomplet ($s) — INCONNU, jamais OK"; return; }
  if [ "$r" -ge "$CI_CATALOGUE_RELATIONS" ]; then
    echo "REFUS $r relations au catalogue (seuil $CI_CATALOGUE_RELATIONS), $j schémas jetables gardés par la purge (créateur vivant ou connexion ouverte) · attendre la fin de leur suite, ou l'arrêter — puis relancer"
    return
  fi
  [ "$t" -ge "$CI_CATALOGUE_TEMOIN_MS" ] && motifs+=", DDL témoin ${t} ms (seuil $CI_CATALOGUE_TEMOIN_MS)"
  [ "$m" -ge "$CI_CATALOGUE_MORTS_PCT" ] && motifs+=", ${m} % de tuples morts (seuil $CI_CATALOGUE_MORTS_PCT)"
  [ "$o" -ge "$CI_CATALOGUE_OCTETS_LIGNE" ] && motifs+=", ${o} octets par ligne vivante (seuil $CI_CATALOGUE_OCTETS_LIGNE)"
  if [ -z "$motifs" ]; then echo ""
  elif [ "${2:-non}" = oui ]; then
    echo "REFUS catalogue encore gonflé après compactage (${motifs#, }) · réparer, hors de tout rejeu : $CI_CATALOGUE_REPARER"
  else
    echo "COMPACTER ${motifs#, }"
  fi
}

#  La sonde : nombre de relations et de schémas jetables, part de tuples morts et
#  place par ligne vivante des tables du catalogue, DDL témoin (meilleur de trois,
#  dans une transaction ANNULÉE : interrompu, il ne laisse rien). Lecture seule — sauf, sur une
#  base neuve sans statistiques, l'ANALYZE du catalogue qui les pose (#2419).
ci_sonder_catalogue() {
  # shellcheck disable=SC2086  # la liste des tables, mot par mot
  python - "${TESTS_BASE_URL:-}" $CI_CATALOGUE_TABLES 2>/dev/null <<'PYTHON' | tr -d '\r' | tail -1
import sys, time
try:
    import psycopg
    url = sys.argv[1].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, connect_timeout=5, autocommit=True) as c:
        c.execute("SET statement_timeout = '60s'")
        relations, jetables = c.execute(
            "SELECT (SELECT count(*) FROM pg_class),"
            " (SELECT count(*) FROM pg_namespace WHERE nspname ~ '^t_[0-9]{14}_[0-9a-f]{12}$')"
        ).fetchone()
        stats = (
            "SELECT sum(n_live_tup), sum(n_dead_tup), sum(pg_total_relation_size(relid)), count(*)"
            " FROM pg_stat_sys_tables WHERE schemaname = 'pg_catalog' AND relname = ANY(%s)"
        )
        vivants, morts, octets, lues = c.execute(stats, (sys.argv[2:],)).fetchone()
        if lues == len(sys.argv[2:]) and not vivants:
            # Base neuve (poste neuf, #2419) : aucune statistique encore, rien de mesuré.
            # ANALYZE ne pose que les statistiques ; les noms viennent de CI_CATALOGUE_TABLES.
            c.execute("ANALYZE " + ", ".join(f"pg_catalog.{t}" for t in sys.argv[2:]))
            vivants, morts, octets, lues = c.execute(stats, (sys.argv[2:],)).fetchone()
        if lues != len(sys.argv[2:]) or not vivants:
            raise RuntimeError(f"statistiques du catalogue incomplètes ({lues} table(s) lue(s))")
        essais = []
        for _ in range(3):
            debut = time.perf_counter()
            with c.transaction(force_rollback=True):
                c.execute("CREATE SCHEMA prevol_temoin")
                c.execute("CREATE TABLE prevol_temoin.t (id int PRIMARY KEY, x text)")
                c.execute("DROP SCHEMA prevol_temoin CASCADE")
            essais.append(time.perf_counter() - debut)
    print(f"relations={relations} jetables={jetables} morts={100 * morts // (vivants + morts)}"
          f" octets={octets // vivants} temoin={round(min(essais) * 1000)}")
except Exception as erreur:
    print("illisible : " + (str(erreur).strip().splitlines() or ["sans message"])[0][:160])
PYTHON
}

#  Le geste : compacter les tables du catalogue. Superutilisateur ; verrou exclusif sur
#  le catalogue le temps du compactage (18 s pour 7,6 Go le 31/10/2026) — une suite
#  d'une autre session attendrait ce temps. Borné : 30 s d'attente de verrou, 5 min en tout.
#    → « ok » | « échec : <raison> »
ci_compacter_catalogue() {
  # shellcheck disable=SC2086  # la liste des tables, mot par mot
  timeout 300 python - "${TESTS_BASE_URL:-}" $CI_CATALOGUE_TABLES 2>/dev/null <<'PYTHON' | tr -d '\r' | tail -1
import re, sys
try:
    import psycopg
    tables = [t for t in sys.argv[2:] if re.fullmatch(r"pg_[a-z_]+", t)]
    url = sys.argv[1].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, connect_timeout=5, autocommit=True) as c:
        c.execute("SET lock_timeout = '30s'")
        c.execute("VACUUM (FULL, ANALYZE) " + ", ".join(f"pg_catalog.{t}" for t in tables))
    print("ok")
except Exception as erreur:
    print("échec : " + (str(erreur).strip().splitlines() or ["sans message"])[0][:160])
PYTHON
}

#  Au pré-vol, après la purge : mesurer, compacter d'office, remesurer. Un refus s'écrit
#  dans le fichier des refus (`job<TAB>motif`), un catalogue sain dans celui des faits.
ci_catalogue_prevol() {        # $1 = dossier de l'étape pytest · $2 = refus · $3 = faits
  local rep env mesure verdict geste t0 compacte=""
  rep=$(<"$1/rep"); env="$1/env"
  mesure=$(ci_dans_etape "$rep" "$env" ci_sonder_catalogue)
  verdict=$(ci_catalogue_verdict "$mesure" non)
  if [ "${verdict%% *}" = COMPACTER ]; then
    echo "· catalogue de la base des tests : ${verdict#COMPACTER } — compactage d'office (#2399)"
    t0=$EPOCHSECONDS
    geste=$(ci_dans_etape "$rep" "$env" ci_compacter_catalogue)
    mesure=$(ci_dans_etape "$rep" "$env" ci_sonder_catalogue)
    verdict=$(ci_catalogue_verdict "$mesure" oui)
    #  Un compactage manqué ne refuse que si le catalogue reste gonflé — et le dit.
    [ "$geste" = ok ] || [ -z "$verdict" ] || verdict="$verdict · compactage : ${geste:-muet}"
    compacte=", compacté en $(( EPOCHSECONDS - t0 )) s"
  fi
  if [ -n "$verdict" ]; then printf '%s\t%s\n' "$(<"$1/job")" "${verdict#REFUS }" >> "$2"
  else echo "catalogue sain (${mesure// /, }$compacte)" >> "$3"; fi
}

# ── Cas d'autotest — appelés par `ci_replay_selftest`, avec son `t` ─────────
ci_base_cas() {
  t "pytest — la commande de ci.yml"        "$(printf 'pytest tests/ -q\n' | ci_lance_pytest)" "oui"
  t "pytest — par python -m"                "$(printf 'python -m pytest tests/test_x.py -q\n' | ci_lance_pytest)" "oui"
  t "pytest — après un cd"                  "$(printf 'cd api && pytest -q\n' | ci_lance_pytest)" "oui"
  t "pytest — par son lanceur (#2223)"      "$(printf 'bash ../scripts/ci/mesure-postgresql.sh\n' | ci_lance_pytest)" "oui"
  t "pytest — l'installation n'en est pas"  "$(printf 'pip install pytest\n' | ci_lance_pytest)" "non"
  t "pytest — un commentaire n'en est pas"  "$(printf '# pytest tests/\nruff check .\n' | ci_lance_pytest)" "non"
  t "pytest — un mot voisin n'en est pas"   "$(printf 'bash scripts/ci/pytest-resume.sh\n' | ci_lance_pytest)" "non"
  t "base — serveur joint : mesurable"      "$(ci_base_tests_etat ok)" ""
  t "base — serveur arrêté : INCONNU, avec la réparation" \
    "$(ci_base_tests_etat 'injoignable : connection refused')" \
    "base des tests injoignable : connection refused · réparer : $CI_BASE_TESTS_REPARER"
  t "base — psycopg absent : INCONNU nommé" "$(ci_base_tests_etat 'psycopg absent')" \
    "base des tests non sondée : psycopg absent du poste (pip install -r api/requirements-dev.txt)"
  #  🔴 Le cas zéro : une sonde muette n'autorise pas l'étape.
  t "base — sonde muette : INCONNU, jamais OK" "$(ci_base_tests_etat '')" "base des tests non sondée : python muet"
  t "base — adresse par défaut : celle de la CI, à l'hôte près" \
    "${CI_BASE_TESTS_DEFAUT#*@}" "127.0.0.1:5432/essai"
  #  Le catalogue (#2399). Une sonde réaliste, puis chaque seuil seul.
  local sain="relations=21904 jetables=43 morts=0 octets=310 temoin=3"
  t "catalogue — sain : rien à faire"       "$(ci_catalogue_verdict "$sain" non)" ""
  t "catalogue — sain après compactage"     "$(ci_catalogue_verdict "$sain" oui)" ""
  #  Le 31/10/2026 : 52 000 relations, témoin 396 ms, pg_attribute à 7,6 Go.
  t "catalogue — trop de relations : refus, compacter n'y peut rien" \
    "$(ci_catalogue_verdict "relations=52570 jetables=139 morts=99 octets=22000 temoin=396" non | cut -c1-31)" \
    "REFUS 52570 relations au catalo"
  t "catalogue — témoin lent : compacter" \
    "$(ci_catalogue_verdict "relations=22000 jetables=48 morts=0 octets=300 temoin=396" non)" \
    "COMPACTER DDL témoin 396 ms (seuil $CI_CATALOGUE_TEMOIN_MS)"
  t "catalogue — tuples morts : compacter" \
    "$(ci_catalogue_verdict "relations=900 jetables=0 morts=98 octets=300 temoin=4" non)" \
    "COMPACTER 98 % de tuples morts (seuil $CI_CATALOGUE_MORTS_PCT)"
  t "catalogue — gonflé sans morts comptés (VACUUM ordinaire) : compacter" \
    "$(ci_catalogue_verdict "relations=21904 jetables=43 morts=0 octets=4932 temoin=3" non)" \
    "COMPACTER 4932 octets par ligne vivante (seuil $CI_CATALOGUE_OCTETS_LIGNE)"
  t "catalogue — encore gonflé après compactage : refus, avec la commande" \
    "$(ci_catalogue_verdict "relations=22000 jetables=48 morts=0 octets=300 temoin=396" oui)" \
    "REFUS catalogue encore gonflé après compactage (DDL témoin 396 ms (seuil $CI_CATALOGUE_TEMOIN_MS)) · réparer, hors de tout rejeu : $CI_CATALOGUE_REPARER"
  #  🔴 Le cas zéro : un catalogue qu'on ne lit pas n'est pas sain.
  t "catalogue — sonde muette : INCONNU, jamais OK" "$(ci_catalogue_verdict "" non | cut -c1-5)" "REFUS"
  t "catalogue — illisible : INCONNU, la raison dite" \
    "$(ci_catalogue_verdict "illisible : permission denied" non)" \
    "REFUS catalogue de la base des tests illisible : permission denied — INCONNU, jamais OK"
  t "catalogue — valeur non numérique : INCONNU" \
    "$(ci_catalogue_verdict "relations=22000 jetables=x morts=0 octets=300 temoin=3" non | cut -c1-5)" "REFUS"
  t "catalogue — mesure incomplète : INCONNU" \
    "$(ci_catalogue_verdict "relations=22000 temoin=3" non | cut -c1-5)" "REFUS"
  t "catalogue — la réparation compacte les six tables" \
    "$(grep -o 'pg_catalog\.pg_[a-z]*' <<<"$CI_CATALOGUE_REPARER" | wc -l | tr -d ' ')" "6"
}
