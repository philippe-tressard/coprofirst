"""Remplacer un texte livré en base — une règle, plus quinze copies (24/09/2026).

`_remplacer` était recopié dans quinze migrations, chacune avec sa requête SQL
écrite à la main. Une migration qui remplace un texte appelle
`utils/textes_livres.remplacer_si_intact` : une copie est refusée.
"""

from __future__ import annotations

import pathlib

import sqlalchemy as sa

from app.utils.textes_livres import remplacer_passage, remplacer_si_intact
from tests.aides_base import moteur_de_test

_VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _copies(sources: dict[str, str]) -> set[str]:
    return {nom for nom, texte in sources.items() if "def _remplacer" in texte}


def test_aucune_copie_de_remplacer():
    migrations = {f.name: f.read_text(encoding="utf-8") for f in _VERSIONS.glob("*.py")}
    assert migrations, "cas zéro : aucune migration lue — ce contrôle ne mesure plus rien"
    assert not _copies(migrations), f"copie de `_remplacer` : {sorted(_copies(migrations))}"
    #  Le témoin : une copie forgée est vue.
    assert _copies({"forge.py": "def _remplacer(conn):\n    pass\n"}) == {"forge.py"}


def test_seul_le_texte_intact_est_remplace():
    moteur = moteur_de_test(schema=False)
    with moteur.begin() as conn:
        conn.execute(sa.text("CREATE TABLE faq_item (question TEXT, reponse TEXT)"))
        conn.execute(
            sa.text("INSERT INTO faq_item VALUES ('Q', 'livré'), ('Q', 'reformulé par le conseil')")
        )
        n = remplacer_si_intact(
            conn, "faq_item", {"question": "Q", "reponse": "livré"}, {"reponse": "corrigé"}
        )
        lignes = sorted(r[0] for r in conn.execute(sa.text("SELECT reponse FROM faq_item")))
    assert n == 1
    assert lignes == ["corrigé", "reformulé par le conseil"]


def test_un_passage_n_est_remplace_que_s_il_figure_tel_quel():
    moteur = moteur_de_test(schema=False)
    with moteur.begin() as conn:
        conn.execute(sa.text("CREATE TABLE config_site (cle TEXT, valeur TEXT)"))
        conn.execute(
            sa.text("INSERT INTO config_site VALUES ('a', 'avant FAUX après'), ('b', 'reformulé')")
        )
        n_a = remplacer_passage(conn, "config_site", {"cle": "a"}, "valeur", "FAUX", "JUSTE")
        n_b = remplacer_passage(conn, "config_site", {"cle": "b"}, "valeur", "FAUX", "JUSTE")
        n_c = remplacer_passage(conn, "config_site", {"cle": "absente"}, "valeur", "FAUX", "JUSTE")
        lignes = dict(conn.execute(sa.text("SELECT cle, valeur FROM config_site")).all())
    assert (n_a, n_b, n_c) == (1, 0, 0)
    assert lignes == {"a": "avant JUSTE après", "b": "reformulé"}
