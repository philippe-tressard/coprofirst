"""Le fichier d'une ligne de la base se situe par sa CLÉ, et par `stockage()` seul (#1816).

Le document, le rapport de diagnostic et l'affiche de hall gardaient le chemin
ABSOLU écrit sur le disque du conteneur, relu à onze endroits — `os.path.isfile`,
`os.remove`, `open`, une pièce jointe de courriel. Un stockage objet n'a pas de
chemin, et un volume monté ailleurs les rendait tous faux. Ils gardent désormais
la clé (`fichier_cle`, `pdf_cle`), et toute lecture passe par
`stockage().cle_de / fichier_de / supprimer_de` ; une écriture par
`stockage().colonnes(cle)`.

Ce fichier refuse le retour d'un `.fichier_chemin` ou d'un `.pdf_chemin` lu ou
écrit ailleurs, et éprouve les gestes : la clé prime, le chemin d'une ligne
ancienne se relit borné, rien ne sort de la racine.
"""

from __future__ import annotations

import ast
import io
from types import SimpleNamespace

from app.utils.stockage import StockageDisque
from tests.aides_sources import modules_app

#: Les colonnes de chemin absolu, en partance (second temps : `CONTRACTIONS`).
COLONNES_DE_CHEMIN = {"fichier_chemin", "pdf_chemin"}

#: Les modules qui ont le droit de les nommer — avec leur raison.
EXCEPTIONS = {
    #  `HistoriqueSauvegarde.fichier_chemin` : l'archive d'une sauvegarde, écrite
    #  dans le répertoire des sauvegardes de la plateforme — pas un fichier du
    #  stockage d'une copropriété. Autre objet, même nom de colonne.
    "utils/backup.py": "l'archive d'une sauvegarde, hors du stockage",
}


def acces_aux_chemins(arbre: ast.AST) -> list[tuple[int, str]]:
    """`x.fichier_chemin` (lu ou écrit) et `Modele(fichier_chemin=…)`."""
    trouves = [
        (n.lineno, f".{n.attr}")
        for n in ast.walk(arbre)
        if isinstance(n, ast.Attribute) and n.attr in COLONNES_DE_CHEMIN
    ]
    trouves += [
        (n.value.lineno, f"{n.arg}=")
        for n in ast.walk(arbre)
        if isinstance(n, ast.keyword) and n.arg in COLONNES_DE_CHEMIN
    ]
    return sorted(trouves)


def test_aucun_chemin_de_fichier_lu_hors_du_stockage():
    fautes, servies = {}, set()
    for m in modules_app(minimum=300):
        if m.rel.startswith("models/"):
            continue  # la déclaration des colonnes
        a = acces_aux_chemins(m.arbre)
        if a and m.rel in EXCEPTIONS:
            servies.add(m.rel)
        elif a:
            fautes[m.rel] = a
    assert not fautes, (
        "Chemin absolu d'un fichier lu ou écrit hors de `utils/stockage` (#1816) — "
        "lire par `stockage().cle_de(ligne)` / `fichier_de(ligne)` / `supprimer_de(ligne)`, "
        "écrire par `**stockage().colonnes(cle)` :\n"
        + "\n".join(f"  app/{rel}:{ligne} — {f}" for rel, a in fautes.items() for ligne, f in a)
    )
    inutiles = set(EXCEPTIONS) - servies
    assert not inutiles, f"Exception qui ne sert plus — la retirer : {sorted(inutiles)}"


def test_le_releve_voit_chaque_forme():
    source = (
        "a = doc.fichier_chemin\n"
        "annonce.pdf_chemin = x\n"
        "Document(titre='t', fichier_chemin=dest)\n"
        "b = doc.fichier_cle\n"
    )
    assert acces_aux_chemins(ast.parse(source)) == [
        (1, ".fichier_chemin"),
        (2, ".pdf_chemin"),
        (3, "fichier_chemin="),
    ]


# ── Les gestes du stockage ───────────────────────────────────────────────────


def _st(tmp_path) -> StockageDisque:
    (tmp_path / "racine").mkdir()
    st = StockageDisque(tmp_path / "racine")
    st.ecrire_flux("prive/a.pdf", io.BytesIO(b"%PDF"))
    return st


def test_une_ligne_neuve_garde_la_cle_et_le_chemin(tmp_path):
    st = _st(tmp_path)
    assert st.colonnes("prive/a.pdf") == {
        "fichier_cle": "prive/a.pdf",
        "fichier_chemin": str(st.chemin("prive/a.pdf")),
    }
    assert set(st.colonnes("annonces-hall/b.pdf", "pdf")) == {"pdf_cle", "pdf_chemin"}


def test_la_cle_prime_sur_un_chemin_perime(tmp_path):
    """Le volume monté ailleurs : le chemin ne mène plus nulle part, la clé si."""
    st = _st(tmp_path)
    doc = SimpleNamespace(fichier_cle="prive/a.pdf", fichier_chemin="/ancien/volume/prive/a.pdf")
    assert st.cle_de(doc) == "prive/a.pdf"
    assert st.fichier_de(doc) == st.chemin("prive/a.pdf")


def test_une_ligne_ancienne_se_relit_par_son_chemin_borne(tmp_path):
    st = _st(tmp_path)
    ancienne = SimpleNamespace(fichier_cle=None, fichier_chemin=str(st.chemin("prive/a.pdf")))
    assert st.cle_de(ancienne) == "prive/a.pdf"
    affiche = SimpleNamespace(pdf_cle=None, pdf_chemin=str(st.chemin("prive/a.pdf")))
    assert st.fichier_de(affiche, "pdf") == st.chemin("prive/a.pdf")


def test_rien_ne_sort_de_la_racine(tmp_path):
    st = _st(tmp_path)
    dehors = tmp_path / "dehors.txt"
    dehors.write_bytes(b"intact")
    for ligne in (
        SimpleNamespace(fichier_cle="../dehors.txt", fichier_chemin=None),
        SimpleNamespace(fichier_cle=None, fichier_chemin=str(dehors)),
    ):
        assert st.fichier_de(ligne) is None
        st.supprimer_de(ligne)
    assert dehors.read_bytes() == b"intact"


def test_un_fichier_absent_ne_se_sert_pas_et_se_supprime_sans_erreur(tmp_path):
    st = _st(tmp_path)
    doc = SimpleNamespace(fichier_cle="prive/a.pdf", fichier_chemin="")
    st.supprimer_de(doc)
    assert st.fichier_de(doc) is None
    st.supprimer_de(doc)
