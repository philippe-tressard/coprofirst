"""Une affiche de hall avec photo : la plus petite possible, la photo entière (24/10/2026).

Signalé : une annonce de 150 caractères et une capture d'écran sortait sur un A5
à moitié blanc, la capture rognée à sa bande du milieu. Deux causes — toute
affiche avec photo était forcée en A5, et la galerie avait une hauteur FIXE avec
`object-fit: cover`.

Ce que ces tests ne voient pas : la page RENDUE. WeasyPrint ne s'installe pas sur
tous les postes ; les seuils ont été relevés au rendu réel, dans l'image de l'API
(commentaire de `SEUILS_FORMAT_AVEC_PHOTOS`).
"""

from __future__ import annotations

import re

from app.utils import annonce_hall as ah
from app.utils.annonce_hall import (
    FORMAT_MIN_AVEC_PHOTOS,
    FORMATS,
    SEUILS_FORMAT,
    SEUILS_FORMAT_AVEC_PHOTOS,
    choisir_format,
)

_TITRE = "Ne restez pas sur le carreau ! Consultez régulièrement le site de la copropriété."
_MESSAGE = "<p>Consultez le site de la copropriété pour être informé des dernières nouveautés !</p>"


def test_une_annonce_courte_avec_photo_sort_dans_le_plus_petit_format_qui_porte_une_photo():
    assert choisir_format(_MESSAGE, titre=_TITRE, avec_photos=True) == FORMAT_MIN_AVEC_PHOTOS
    assert FORMAT_MIN_AVEC_PHOTOS == "a6"


def test_les_seuils_avec_photo_commencent_au_format_minimal_et_restent_sous_ceux_sans_photo():
    assert SEUILS_FORMAT_AVEC_PHOTOS[0][0] == FORMAT_MIN_AVEC_PHOTOS
    sans = dict(SEUILS_FORMAT)
    for fmt, seuil in SEUILS_FORMAT_AVEC_PHOTOS:
        assert 0 < seuil < sans[fmt], f"{fmt} : la galerie prend de la place, le seuil baisse"


def test_chaque_format_qui_admet_une_photo_lui_donne_une_hauteur():
    """Un format choisi « avec photo » dont la galerie mesure 0 mm la perdrait."""
    for fmt, _ in SEUILS_FORMAT_AVEC_PHOTOS:
        hauteur = float(ah._GABARITS[fmt]["galerie_max"].removesuffix("mm"))
        assert hauteur > 0, fmt
    for fmt in FORMATS[FORMATS.index(FORMAT_MIN_AVEC_PHOTOS) + 1 :]:
        assert ah._GABARITS[fmt]["galerie_max"] == "0mm", fmt


def _regle_galerie(fmt: str) -> str:
    css = ah._css(fmt)
    return re.search(r"\.galerie img \{([^}]*)\}", css).group(1)


def test_la_photo_n_est_jamais_rognee():
    """Proportions gardées : dimensions `auto`, bornées par des `max-*`, sans recadrage."""
    for fmt, _ in SEUILS_FORMAT_AVEC_PHOTOS:
        regle = _regle_galerie(fmt)
        assert "object-fit" not in regle, fmt
        assert re.search(r"(?<![-\w])height:\s*auto", regle), fmt
        assert re.search(r"(?<![-\w])width:\s*auto", regle), fmt
        assert "max-height" in regle and "max-width" in regle, fmt


def test_la_photo_figure_dans_l_affiche_du_format_minimal(monkeypatch):
    monkeypatch.setattr(ah, "image_data_uri", lambda u: "data:image/png;base64,AAAA")
    html = ah.construire_html(
        titre=_TITRE,
        message_html=_MESSAGE,
        perimetre_label="Copropriété entière",
        format_effectif=FORMAT_MIN_AVEC_PHOTOS,
        site_nom="Résidence",
        site_url="https://exemple.fr",
        logo_png=None,
        images=["/uploads/photos/capture.png"],
    )
    assert 'class="galerie galerie-1"' in html
    assert html.count('src="data:image/png;base64,AAAA"') == 1
