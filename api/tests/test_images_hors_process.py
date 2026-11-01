"""Aucune image ne se décode dans le process de l'API (#2396) — et elle n'y revient pas.

## Pourquoi

Pillow s'appuie sur des bibliothèques C (libtiff, libwebp, libavif, libheif…) dont
l'historique compte des corruptions de mémoire. Un fichier piégé qui fait planter
le décodeur emportait le worker de l'API : la règle même qui a sorti WeasyPrint du
process le 16/09/2026 (`pdf_rendu`, `test_pdf_hors_process.py`). Toute lecture
d'image vit donc dans `utils/images_moteur`, exécuté par `utils/process_isole` dans
un enfant `spawn`, et `utils/images` est la seule porte.

## Ce qui est tenu

1. **la porte** — `Image.open`, `pillow_heif` et Pillow ne s'emploient que dans le
   moteur ; aucun module de l'API n'importe le moteur (on le NOMME) ;
2. **le comportement** — chaque geste de `images` rend le bon résultat sans que
   Pillow s'ouvre dans ce process, et l'enfant n'a pas la base (donc pas un `fork`) ;
3. **l'isolement** — un décodeur qui avorte, boucle ou gonfle ne coûte qu'une
   image illisible, et ce process continue.
"""

from __future__ import annotations

import ast
import importlib.util
import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

from app.utils import images
from tests.aides_sources import modules_app

MOTEUR_REL = "utils/images_moteur.py"

#: Les modules qui importent Pillow sans LIRE une image — déclarés, avec leur raison.
IMPORTS_PIL_ADMIS = {
    "demo/fichiers.py": "dessine les fichiers de la démonstration (Image.new) ; n'en lit aucun",
}

#: Les gestes que `images` confie au moteur — chacun nommé, aucun importé.
GESTES = {"reencoder", "mesurer", "reduire", "carres"}

#: Le nom du process d'essai — une constante : un littéral passé à `nom=` serait lu
#: comme un nom de personne par `test_identites_fictives.py`.
ENFANT_D_ESSAI = "essai-images"


def _png(largeur: int, couleur=(200, 30, 30)) -> bytes:
    sortie = io.BytesIO()
    Image.new("RGB", (largeur, largeur // 2), couleur).save(sortie, format="PNG")
    return sortie.getvalue()


def _importe(noeud: ast.AST) -> list[str]:
    if isinstance(noeud, ast.Import):
        return [a.name for a in noeud.names]
    if isinstance(noeud, ast.ImportFrom) and noeud.module:
        return [noeud.module] + [f"{noeud.module}.{a.name}" for a in noeud.names]
    return []


def _usages():
    """`(fichier, nature)` pour chaque import de Pillow ou de pillow_heif, chaque
    `Image.open(...)`, et chaque import du moteur."""
    for m in modules_app():
        for n in ast.walk(m.arbre):
            for nom in _importe(n):
                racine = nom.split(".")[0]
                if racine == "PIL":
                    yield m.rel, "PIL"
                elif racine == "pillow_heif":
                    yield m.rel, "pillow_heif"
                elif nom.startswith("app.utils.images_moteur"):
                    yield m.rel, "moteur"
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "open"
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "Image"
            ):
                yield m.rel, "Image.open"


def test_pillow_ne_s_emploie_que_dans_le_moteur():
    hors = sorted(
        {
            (f, nature)
            for f, nature in _usages()
            if f != MOTEUR_REL and not (nature == "PIL" and f in IMPORTS_PIL_ADMIS)
        }
    )
    assert not hors, (
        f"une image se lirait dans le process de l'API : {hors}. Toute lecture passe "
        "par `utils/images` (la porte), qui l'exécute dans un enfant (`images_moteur`)."
    )


def test_cas_zero_et_exceptions_qui_servent():
    usages = set(_usages())
    assert (MOTEUR_REL, "Image.open") in usages and (MOTEUR_REL, "pillow_heif") in usages, (
        "le balayage ne trouve plus la lecture du moteur : il ne mesure plus rien"
    )
    for fichier in IMPORTS_PIL_ADMIS:
        assert (fichier, "PIL") in usages, f"exception sans usage, à retirer : {fichier}"


def test_aucun_module_n_importe_le_moteur_il_se_nomme():
    """L'importer le ferait tourner dans l'API : `images` le NOMME à l'enfant."""
    assert not [f for f, nature in _usages() if nature == "moteur"]
    assert images.MOTEUR == "app.utils.images_moteur"
    arbre = ast.parse(Path(images.__file__).read_text(encoding="utf-8"))
    nommes = {
        n.args[0].value
        for n in ast.walk(arbre)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "_isole"
        and isinstance(n.args[0], ast.Constant)
    }
    assert nommes == GESTES, nommes
    source = Path(importlib.util.find_spec(images.MOTEUR).origin).read_text(encoding="utf-8")
    for geste in GESTES:
        assert f"def {geste}(" in source, f"le moteur n'a pas `{geste}`"


# ── Le comportement ───────────────────────────────────────────────────────────


@pytest.fixture
def pillow_espionne(monkeypatch):
    """Toute ouverture d'image DANS ce process — l'enfant `spawn` n'hérite pas de l'espion."""
    vues: list[int] = []
    ouvrir = Image.open

    def _ouvrir(*a, **k):
        vues.append(1)
        return ouvrir(*a, **k)

    monkeypatch.setattr(Image, "open", _ouvrir)
    return vues


def test_chaque_geste_rend_son_resultat_sans_ouvrir_pillow_ici(pillow_espionne):
    photo = _png(2000)
    assert images.reencoder_jpeg(photo, max_dim=400)[:3] == b"\xff\xd8\xff"
    assert images.dimensions([photo, b"pas une image"]) == [(2000, 1000), None]
    reduite = images.reduire_sous_budget(photo, 4_000)
    assert len(reduite) < len(photo) and reduite[:3] == b"\xff\xd8\xff"
    carres = images.carres_png(photo, (16, 64))
    assert sorted(carres) == [16, 64] and carres[64][:4] == b"\x89PNG"
    with pytest.raises(ValueError):
        images.reencoder_jpeg(b"GIF89a tronque")
    assert pillow_espionne == [], "une image s'est ouverte dans le process de l'API"


def test_l_enfant_n_a_pas_la_base_donc_ce_n_est_pas_un_fork():
    import app.database  # noqa: F401 — l'import EST le dispositif du test
    from app.utils.process_isole import executer_isole

    tailles, temoin = executer_isole(
        images.MOTEUR,
        "mesurer",
        (_png(40),),
        delai_s=60,
        nom=ENFANT_D_ESSAI,
        memoire_max_octets=images.MEMOIRE_MAX_OCTETS,
    )
    assert tailles == [(40, 20)]
    assert temoin["pid"] != os.getpid(), "la mesure s'est faite DANS le process de l'API"
    assert temoin["base_chargee"] is False, f"l'enfant a la base : c'est un fork ({temoin})"
    #  Le plafond se pose sous Linux (le RPi, la CI) ; sur le poste (Windows, macOS),
    #  le témoin dit qu'il manque — il ne prétend pas l'avoir posé (#2419).
    assert temoin["plafond_memoire"] is sys.platform.startswith("linux")


# ── L'isolement : ce qui se passe dans l'enfant y reste ───────────────────────


@pytest.fixture
def moteur_piege(monkeypatch):
    monkeypatch.setattr(images, "MOTEUR", "tests.aides_moteur_piege")


def test_un_decodeur_qui_avorte_ne_coute_qu_une_image_illisible(moteur_piege):
    with pytest.raises(ValueError, match="illisible"):
        images.reencoder_jpeg(_png(40))


def test_un_decodeur_qui_boucle_est_abattu(moteur_piege, monkeypatch):
    monkeypatch.setattr(images, "DELAI_S", 3.0)
    assert images.dimensions([_png(40), _png(50)]) == [None, None]


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="RLIMIT_AS ne se pose que sous Linux : le plafond se mesure en CI (#2419)",
)
def test_un_decodeur_qui_gonfle_bute_sur_le_plafond(moteur_piege):
    with pytest.raises(ValueError, match="illisible"):
        images.carres_png(_png(40), (16,))
