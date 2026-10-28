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
  grep -v '^[[:space:]]*#' \
    | grep -Eq '(^|[;&|(]|then|do)[[:space:]]*((python[0-9.]*[[:space:]]+-m[[:space:]]+)?pytest([[:space:]]|$)|bash[[:space:]]+[^[:space:]]*/mesure-postgresql\.sh)' \
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
}
