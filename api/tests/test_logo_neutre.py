"""Le logo neutre : UN dessin, et tout ce qui le montre en dérive (#1728).

Il existe sous cinq formes, parce que chaque lieu prend son format : le SVG du
front (`favicon.svg`), sa copie dans l'API (les documents imprimés, par
`pdf_theme.logo_svg`), et trois rendus PNG — celui de l'API (courriels, route
publique `GET /config/logo.png`) et les deux icônes de l'application installée.

Rien ne les tenait ensemble : `pdf_theme.logo_svg` recopiait le dessin en
chaîne Python, et changer le logo neutre demandait de penser aux quatre
autres. Ce contrôle refuse qu'ils divergent.

Le 09/11/2026 s'y ajoute le dessin du FOND SOMBRE (`logo-neutre-sombre.svg`, variante
« Ivoire », sans tuile blanche) et son rendu PNG : les mêmes tracés, tenus de même.

Les PNG ne se rendent pas en CI (aucun moteur SVG n'y est installé) : on vérifie
qu'ils SONT le rendu du dessin en lisant leurs pixels aux endroits que le dessin
définit. Pour les refaire après avoir changé le SVG, le rendre à 512 et 192 px
sur fond transparent (un navigateur suffit : Playwright, `omitBackground`).
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest
from PIL import Image

from app.utils import logo, pdf_theme

RACINE = Path(__file__).resolve().parents[2]
SVG_FRONT = RACINE / "front" / "static" / "favicon.svg"
ICONES = RACINE / "front" / "static" / "icons"
IMAGE_README = RACINE / "docs" / "images" / "coprofirst.png"
LICENCE_LOGO = "LicenseRef-CoproFirst-Logo"
#: Un tracé du dessin assez long pour le reconnaître dans une copie.
TRACE_DU_DESSIN = "M137.5 487V137.5"

BLEU, OR, BLANC = (0x1E, 0x3A, 0x5F), (0xC9, 0x98, 0x3A), (0xFF, 0xFF, 0xFF)

#: Des points du dessin, dans le repère du SVG (512 px) AVANT sa mise à l'échelle
#: dans la tuile (`translate(256 256) scale(0.8) translate(-256 -296.25)`), et la
#: couleur qu'ils doivent avoir. Un point par élément qui fait le logo.
POINTS = (
    ((292.5, 177.0), OR, "la fenêtre allumée"),
    ((137.5, 350.0), BLEU, "le mur gauche de la tour"),
    ((219.5, 244.0), BLEU, "une fenêtre éteinte"),
    ((256.0, 487.5), OR, "la ligne de sol"),
    ((256.0, 440.0), BLANC, "l'intérieur de la tour"),
)


def _exige(chemin: Path) -> Path:
    """Jamais `skip` : un fichier disparu doit faire rougir la CI (`standards/04`)."""
    if not chemin.is_file():
        pytest.fail(f"Fichier attendu introuvable : {chemin.relative_to(RACINE)}")
    return chemin


def _dans_la_tuile(x: float, y: float, cote: int) -> tuple[int, int]:
    echelle = cote / 512
    return round((256 + 0.8 * (x - 256)) * echelle), round((256 + 0.8 * (y - 296.25)) * echelle)


def _proche(pixel: tuple, couleur: tuple) -> bool:
    return pixel[3] > 250 and sum(abs(pixel[i] - couleur[i]) for i in range(3)) < 40


def test_l_api_porte_la_copie_exacte_du_dessin_du_front():
    assert _exige(pdf_theme.LOGO_NEUTRE_SVG).read_bytes() == _exige(SVG_FRONT).read_bytes(), (
        "logo-neutre.svg (API) et favicon.svg (front) divergent : recopier le second sur le premier"
    )


def test_le_png_de_l_api_est_l_icone_512_du_front():
    assert _exige(logo.NEUTRE_PNG).read_bytes() == _exige(ICONES / "icon-512.png").read_bytes()


@pytest.mark.parametrize("nom, cote", [("icon-512.png", 512), ("icon-192.png", 192)])
def test_chaque_png_est_le_rendu_du_dessin(nom, cote):
    image = Image.open(_exige(ICONES / nom)).convert("RGBA")
    assert image.size == (cote, cote)
    for (x, y), couleur, quoi in POINTS:
        pixel = image.getpixel(_dans_la_tuile(x, y, cote))
        assert _proche(pixel, couleur), f"{nom} : {quoi} vaut {pixel}, attendu {couleur}"
    #  La tuile est arrondie : son coin reste transparent, son bord est blanc.
    assert image.getpixel((1, 1))[3] == 0, f"{nom} : le coin de la tuile n'est pas transparent"
    assert _proche(image.getpixel((cote // 2, 2)), BLANC), f"{nom} : la tuile n'est pas blanche"


IVOIRE, OR_CLAIR = (0xE8, 0xE6, 0xE1), (0xE0, 0xB0, 0x50)

#: Les mêmes points, dans le repère du dessin sombre (`viewBox="0 40 512 512"`, sans
#: tuile ni mise à l'échelle) : (x, y − 40).
POINTS_SOMBRE = (
    ((292.5, 177.0), OR_CLAIR, "la fenêtre allumée"),
    ((137.5, 350.0), IVOIRE, "le mur gauche de la tour"),
    ((219.5, 244.0), IVOIRE, "une fenêtre éteinte"),
    ((256.0, 487.5), OR, "la ligne de sol"),
)


def test_le_dessin_sombre_reprend_les_traces_sans_la_tuile():
    clair = _exige(pdf_theme.LOGO_NEUTRE_SVG).read_text(encoding="utf-8")
    sombre = _exige(pdf_theme.LOGO_NEUTRE_SOMBRE_SVG).read_text(encoding="utf-8")
    import re

    traces = re.findall(r'<path d="([^"]+)"', clair)
    assert len(traces) == 4, "cas zéro : les tracés du dessin clair ne se lisent plus"
    assert re.findall(r'<path d="([^"]+)"', sombre) == traces, "les deux dessins divergent"
    assert len(re.findall(r"<rect ", sombre)) == len(re.findall(r"<rect ", clair)) - 1, (
        "le dessin sombre porte les mêmes fenêtres, sans la tuile"
    )
    assert 'fill="#FFFFFF"' not in sombre


def test_le_png_sombre_est_le_rendu_du_dessin_sombre():
    image = Image.open(_exige(logo.NEUTRE_SOMBRE_PNG)).convert("RGBA")
    assert image.size == (512, 512)
    for (x, y), couleur, quoi in POINTS_SOMBRE:
        pixel = image.getpixel((round(x), round(y - 40)))
        assert _proche(pixel, couleur), f"{quoi} vaut {pixel}, attendu {couleur}"
    #  Pas de tuile : le coin ET l'intérieur de la tour sont transparents.
    assert image.getpixel((1, 1))[3] == 0
    assert image.getpixel((256, 400))[3] == 0, "l'intérieur de la tour n'est pas transparent"


def test_les_documents_recoivent_le_dessin_a_leur_taille_sans_son_commentaire():
    svg = pdf_theme.logo_svg(48)
    assert svg.startswith('<svg width="48" height="48" ')
    assert "<!--" not in svg, "la provenance du dessin partait dans chaque document"
    assert 'fill="#C9983A"' in svg


def _fichiers_sous_licence_logo() -> set[str]:
    reuse = tomllib.loads((RACINE / "REUSE.toml").read_text(encoding="utf-8"))
    chemins: set[str] = set()
    for bloc in reuse.get("annotations", []):
        if bloc.get("SPDX-License-Identifier") == LICENCE_LOGO:
            chemins |= {bloc["path"]} if isinstance(bloc["path"], str) else set(bloc["path"])
    return chemins


def _copies_du_dessin() -> set[str]:
    """Tout fichier versionné qui recopie le tracé du logo — en dehors de ce test."""
    sortie = subprocess.run(
        ["git", "grep", "-l", "--fixed-strings", TRACE_DU_DESSIN],
        cwd=RACINE,
        capture_output=True,
        text=True,
        check=False,
    )
    if sortie.returncode not in (0, 1):
        pytest.fail(f"`git grep` a échoué : {sortie.stderr}")
    return set(sortie.stdout.split()) - {"api/tests/test_logo_neutre.py"}


def test_le_logo_et_chacun_de_ses_rendus_sont_hors_de_l_agpl():
    """Le logo a sa licence propre (#1736) : un rendu oublié, `**` le rendrait libre.

    Le bloc de `REUSE.toml` doit nommer exactement les fichiers du logo : les
    cinq formes tenues ensemble ci-dessus, l'image du README, et toute copie du
    dessin que le dépôt contiendrait ailleurs.
    """
    attendus = {
        str(_exige(c).relative_to(RACINE).as_posix())
        for c in (
            SVG_FRONT,
            pdf_theme.LOGO_NEUTRE_SVG,
            pdf_theme.LOGO_NEUTRE_SOMBRE_SVG,
            logo.NEUTRE_PNG,
            logo.NEUTRE_SOMBRE_PNG,
            ICONES / "icon-192.png",
            ICONES / "icon-512.png",
            IMAGE_README,
        )
    } | _copies_du_dessin()
    declares = _fichiers_sous_licence_logo()
    assert declares, f"aucun bloc de REUSE.toml n'attribue {LICENCE_LOGO} (cas zéro)"
    assert attendus - declares == set(), f"logo sous l'AGPL par `**` : {attendus - declares}"
    assert declares - attendus == set(), f"déclarés sans être le logo : {declares - attendus}"
    assert (RACINE / "LICENSES" / f"{LICENCE_LOGO}.txt").is_file()
