"""`start.sh` attend la base et ne migre jamais une base qu'il n'a pas pu lire (#1759, DI-7).

Le serveur de base peut démarrer après l'API ; la migrer pendant qu'il est
injoignable laissait `alembic upgrade head` atteindre une base vide, une seconde
plus tard, sans schéma posé.
"""

from __future__ import annotations

from pathlib import Path

from app.utils.attendre_base import attendre
from tests.aides_base import url_des_tests

START = Path(__file__).resolve().parents[1] / "start.sh"


def test_une_base_qui_repond_rend_vrai():
    assert attendre(url_des_tests(), delai=5) is True


def test_une_base_injoignable_rend_faux_au_bout_du_delai():
    url = "postgresql+psycopg://personne:x@127.0.0.1:9/aucune?connect_timeout=1"
    assert attendre(url, delai=0.5, pas=0.1) is False


def _code_de_start() -> str:
    return "\n".join(
        ligne
        for ligne in START.read_text(encoding="utf-8").splitlines()
        if not ligne.lstrip().startswith("#")
    )


def test_start_sh_attend_la_base_avant_toute_lecture_et_compte_l_echec():
    texte = _code_de_start()
    appel = "JOIGNABLE=$(python -m app.utils.attendre_base)"
    assert texte.count(appel) == 1, "affecté, pas passé à echo : sous `set -e`, l'échec compte"
    assert texte.index(appel) < texte.index("python -m app.utils.revision_base")
    assert texte.index(appel) < texte.index("python -m app.utils.schema_initial")


def test_start_sh_ne_migre_pas_une_base_illisible():
    texte = _code_de_start()
    garde = '[ "$SCHEMA_INITIAL" = "inconnu" ]'
    assert texte.count(garde) == 1
    bloc = texte[texte.index(garde) : texte.index("alembic upgrade head")]
    assert "exit 1" in bloc, "une base illisible arrête le conteneur AVANT `alembic upgrade head`"
