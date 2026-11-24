"""Les aides des migrations — une règle, plus des copies (24/09/2026, #2950).

`_remplacer` était recopié dans quinze migrations, chacune avec sa requête SQL
écrite à la main. Une migration qui remplace un texte appelle
`utils/textes_livres.remplacer_si_intact` : une copie est refusée.

Depuis #2950, deux autres aides : la lecture des colonnes présentes d'une table
(seize migrations l'écrivaient, sous quatre noms — `_colonnes`, `_presentes`,
`_presente`, `_existe` — et d'autres en ligne) passe par
`utils/colonnes_presentes`, et la lecture d'un texte servi (`_texte_servi`, trois
copies) par `utils/textes_livres.lire_texte`. Les migrations existantes ne se
modifient jamais : elles sont FIGÉES jusqu'à `DERNIERE_FIGEE`. Une migration plus
récente qui recopie un corps d'aide (même empreinte d'AST qu'une fonction recopiée
dans deux migrations figées) ou qui lit `get_columns` elle-même échoue.
"""

from __future__ import annotations

import ast
import pathlib
import re
from collections import defaultdict

import sqlalchemy as sa

from app.utils.colonnes_presentes import colonnes_presentes
from app.utils.textes_livres import remplacer_passage, remplacer_si_intact
from tests.aides_base import moteur_de_test
from tests.aides_sources import empreinte_du_corps

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


# ── Les aides des migrations à venir : empreinte, pas nom (#2950) ──────────────

#: La dernière migration écrite avant la règle : elle et les précédentes sont
#: figées (une migration appliquée ne se modifie jamais), leurs copies restent.
#: 0348 à 0350 ont été fusionnées avant la règle, dans le train qui la livre.
DERNIERE_FIGEE = 350

#: Migrations plus récentes qui ont le droit de lire `get_columns` elles-mêmes,
#: avec leur raison (une colonne dont il faut le TYPE, pas seulement le nom).
#: Une entrée qui ne sert plus fait échouer.
LECTURES_ADMISES: dict[str, str] = {}

_NUMERO = re.compile(r"^(\d{4})_")
_FONCTIONS_DE_MIGRATION = {"upgrade", "downgrade"}


def _numero(nom: str) -> int | None:
    m = _NUMERO.match(nom)
    return int(m.group(1)) if m else None


def _aides(source: str) -> dict[str, str]:
    """{empreinte du corps: nom} des fonctions de niveau module, hors upgrade/downgrade."""
    return {
        empreinte_du_corps(n): n.name
        for n in ast.parse(source).body
        if isinstance(n, ast.FunctionDef) and n.name not in _FONCTIONS_DE_MIGRATION
    }


def _lit_get_columns(source: str) -> bool:
    return any(
        isinstance(n, ast.Attribute) and n.attr == "get_columns"
        for n in ast.walk(ast.parse(source))
    )


def ecarts_des_aides(migrations: dict[str, str]) -> list[str]:
    """Ce qu'une migration plus récente que `DERNIERE_FIGEE` recopie. PURE."""
    figees = {n: t for n, t in migrations.items() if (_numero(n) or 0) <= DERNIERE_FIGEE}
    neuves = {n: t for n, t in migrations.items() if (_numero(n) or 0) > DERNIERE_FIGEE}
    porteurs: dict[str, set[str]] = defaultdict(set)
    for nom, texte in figees.items():
        for empreinte in _aides(texte):
            porteurs[empreinte].add(nom)
    recopiees = {e for e, noms in porteurs.items() if len(noms) > 1}
    ecarts = []
    for nom, texte in sorted(neuves.items()):
        ecarts += [
            f"{nom} : `{fonction}` recopie une aide déjà écrite dans plusieurs migrations"
            for empreinte, fonction in _aides(texte).items()
            if empreinte in recopiees
        ]
        if _lit_get_columns(texte) and nom not in LECTURES_ADMISES:
            ecarts.append(
                f"{nom} : lit `get_columns` — `colonnes_presentes(op.get_bind(), TABLE)` "
                "(`app/utils/colonnes_presentes`)"
            )
    return ecarts


def _migrations() -> dict[str, str]:
    return {f.name: f.read_text(encoding="utf-8") for f in _VERSIONS.glob("*.py")}


def test_une_migration_neuve_ne_recopie_aucune_aide():
    migrations = _migrations()
    assert any((_numero(n) or 0) == DERNIERE_FIGEE for n in migrations), (
        f"la migration {DERNIERE_FIGEE:04d} a disparu : le plancher ne désigne plus rien"
    )
    assert not ecarts_des_aides(migrations), "\n".join(ecarts_des_aides(migrations))
    neuves = {n for n in migrations if (_numero(n) or 0) > DERNIERE_FIGEE}
    mortes = sorted(set(LECTURES_ADMISES) - {n for n in neuves if _lit_get_columns(migrations[n])})
    assert not mortes, f"lecture(s) admise(s) qui ne servent plus — à retirer : {mortes}"


def test_l_empreinte_des_aides_sait_REFUSER():
    """Le cas fautif d'abord : les copies figées sont vues, et une neuve est refusée."""
    migrations = _migrations()
    colonnes = migrations[next(n for n in migrations if n.startswith("0316_"))]
    texte_servi = migrations[next(n for n in migrations if n.startswith("0300_"))]
    forge = {
        **migrations,
        "9998_copie_colonnes.py": colonnes,
        "9999_copie_texte.py": texte_servi.replace("def _texte_servi", "def _lu"),
    }
    ecarts = ecarts_des_aides(forge)
    assert any(e.startswith("9998_copie_colonnes.py : lit `get_columns`") for e in ecarts), ecarts
    assert any(e.startswith("9999_copie_texte.py : `_lu` recopie") for e in ecarts), ecarts


def test_colonnes_presentes():
    moteur = moteur_de_test(schema=False)
    with moteur.begin() as conn:
        conn.execute(sa.text("CREATE TABLE essai_colonnes (cle TEXT, valeur TEXT)"))
        assert colonnes_presentes(conn, "essai_colonnes") == {"cle", "valeur"}
