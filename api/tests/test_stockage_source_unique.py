"""Un fichier d'une copropriété ne se situe que par `utils/stockage` (#1748).

Chantier multi-copropriétés, lot P2-6 (spec §4.4). L'adresse `/uploads/<clé>` se
traduisait en chemin à trois endroits, dont deux à racine écrite en dur
(`"/app" + url`, `Path("/app")`) ; et quatre modules figeaient la racine à leur
chargement. Ce fichier refuse le retour de l'un comme de l'autre, et éprouve les
bornes du stockage : une clé ne sort jamais du préfixe de sa copropriété.
"""

from __future__ import annotations

import ast
import io
from dataclasses import replace

import pytest

from app import contexte
from app.utils.stockage import (
    CleInvalide,
    StockageDisque,
    cle_de_url,
    cle_valide,
    stockage,
)
from tests.aides_sources import chaines_du_code, modules_app

#: Les deux modules qui connaissent la racine des fichiers d'une copropriété.
LECTEURS_DE_LA_RACINE = {"contexte.py", "utils/stockage.py"}

#: Une racine de conteneur écrite en dur — la forme exacte des trois traductions
#: d'adresse qu'il y avait (`"/app" + url`, `Path("/app")`, `"/app/uploads"`).
RACINES_EN_DUR = {"/app", "/app/", "/app/uploads", "/app/uploads/"}
#: Le seul endroit où la racine par défaut s'écrit : la configuration.
DECLARATION = "config.py"


def acces_a_la_racine(arbre: ast.AST, *, lit_la_racine: bool) -> list[tuple[int, str]]:
    trouves = [
        (n.lineno, ".racine_fichiers")
        for n in ast.walk(arbre)
        if lit_la_racine and isinstance(n, ast.Attribute) and n.attr == "racine_fichiers"
    ]
    trouves += [
        (n.lineno, repr(n.value)) for n in chaines_du_code(arbre) if n.value in RACINES_EN_DUR
    ]
    return sorted(trouves)


def test_aucune_racine_de_fichiers_hors_du_stockage():
    fautes = {}
    for m in modules_app(minimum=300):
        if m.rel == DECLARATION:
            continue
        a = acces_a_la_racine(m.arbre, lit_la_racine=m.rel not in LECTEURS_DE_LA_RACINE)
        if a:
            fautes[m.rel] = a
    assert not fautes, (
        "Racine des fichiers lue ou écrite en dur hors de `utils/stockage` (#1748) — "
        "situer un fichier par `stockage()` (`chemin`, `fichier_de_url`, `cle_de_chemin`, "
        "`url`), la racine entière par `stockage().racine` :\n"
        + "\n".join(
            f"  app/{rel}:{ligne} — {forme}" for rel, a in fautes.items() for ligne, forme in a
        )
    )


def test_le_releve_voit_chaque_forme():
    source = (
        '"""Docstring : "/app" + url, racontée."""\n'
        'a = os.path.realpath("/app" + url)\n'
        'b = Path("/app") / url\n'
        'c = "/app/uploads"\n'
        "d = contexte.courante().racine_fichiers\n"
        'e = "/app/data/app.db"\n'
    )
    assert acces_a_la_racine(ast.parse(source), lit_la_racine=True) == [
        (2, "'/app'"),
        (3, "'/app'"),
        (4, "'/app/uploads'"),
        (5, ".racine_fichiers"),
    ]


# ── Les bornes du stockage ───────────────────────────────────────────────────


@pytest.mark.parametrize("cle", ["", "/etc/passwd", "../x", "a/../../x", "a\\b", "a\x00b"])
def test_une_cle_qui_sortirait_est_refusee(cle):
    with pytest.raises(CleInvalide):
        cle_valide(cle)


def test_une_cle_relative_est_normalisee():
    assert cle_valide("photos/a.jpg") == "photos/a.jpg"
    assert cle_valide("photos//a.jpg") == "photos/a.jpg"
    assert cle_valide("./photos/./a.jpg") == "photos/a.jpg"


@pytest.mark.parametrize(
    "url, attendue",
    [
        ("/uploads/photos/a.jpg", "photos/a.jpg"),
        ("/uploads/../../etc/passwd", None),
        ("/uploads/", None),
        ("https://ailleurs.test/uploads/a.jpg", None),
        (None, None),
    ],
)
def test_seules_nos_adresses_ont_une_cle(url, attendue):
    assert cle_de_url(url) == attendue


def test_ecrire_lire_supprimer_et_l_adresse(tmp_path):
    st = StockageDisque(tmp_path)
    st.ecrire("photos/a.jpg", b"octets")
    assert st.lire("photos/a.jpg") == b"octets" and st.existe("photos/a.jpg")
    assert st.url("photos/a.jpg") == "/uploads/photos/a.jpg"
    assert st.fichier_de_url("/uploads/photos/a.jpg") == (tmp_path / "photos" / "a.jpg").resolve()
    st.ecrire_flux("prive/b.pdf", io.BytesIO(b"%PDF"))
    chemin = str(st.chemin("prive/b.pdf"))
    assert st.cle_de_chemin(chemin) == "prive/b.pdf"
    st.supprimer_chemin(chemin)
    st.supprimer("photos/a.jpg")
    assert not st.existe("photos/a.jpg") and not st.existe("prive/b.pdf")


def test_un_chemin_garde_en_base_hors_de_la_racine_n_est_jamais_touche(tmp_path):
    dehors = tmp_path / "dehors.txt"
    dehors.write_bytes(b"intact")
    st = StockageDisque(tmp_path / "racine")
    (tmp_path / "racine").mkdir()
    assert st.cle_de_chemin(str(dehors)) is None
    st.supprimer_chemin(str(dehors))
    assert dehors.read_bytes() == b"intact"
    assert st.fichier_de_url("/uploads/../dehors.txt") is None


def test_une_ecriture_ne_cree_jamais_la_racine(tmp_path):
    """La racine est le volume : la créer masquerait un montage manquant."""
    st = StockageDisque(tmp_path / "volume-absent")
    with pytest.raises(FileNotFoundError):
        st.ecrire("photos/a.jpg", b"x")
    assert not (tmp_path / "volume-absent").exists()


def test_chaque_copropriete_a_son_prefixe(tmp_path):
    """Le préfixe vient du contexte : deux copropriétés, deux racines."""
    autre = replace(contexte.courante(), identifiant="essai-b", racine_fichiers=tmp_path)
    racine_unique = stockage().racine
    with contexte.dans(autre):
        assert stockage().racine == tmp_path
    assert stockage().racine == racine_unique != tmp_path
