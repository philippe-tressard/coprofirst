"""Une affiche de hall avec photo : la plus petite possible, la photo entière (24/10/2026).

Signalé : une annonce de 150 caractères et une capture d'écran sortait sur un A5
à moitié blanc, la capture rognée à sa bande du milieu. Puis demandé : *« texte
et/ou image, et si image seule, adapte au plus petit format l'affichette »*, la
photo ajustée dans la zone affichée.

Ce que ces tests ne voient pas : la page RENDUE. WeasyPrint ne s'installe pas sur
tous les postes ; seuils et zones ont été relevés au rendu réel, dans l'image de
l'API (`annonce_hall_photos`).
"""

from __future__ import annotations

import re

import pytest
from fastapi import HTTPException

from app.routers import annonces_hall
from app.utils import annonce_hall as ah
from app.utils.annonce_hall import FORMATS, SEUILS_FORMAT, choisir_format
from app.utils.annonce_hall_photos import (
    FORMAT_MIN_AVEC_PHOTOS,
    HAUTEUR_IMAGE_MIN_MM,
    SEUILS_FORMAT_AVEC_PHOTOS,
    ZONE_IMAGE_SEULE_MM,
    hauteur_image_seule,
)

_TITRE = "Ne restez pas sur le carreau ! Consultez régulièrement le site de la copropriété."
_MESSAGE = "<p>Consultez le site de la copropriété pour être informé des dernières nouveautés !</p>"
_PHOTO = "data:image/png;base64,AAAA"


def _html(fmt: str, message: str, photos: int, monkeypatch, titre: str = _TITRE) -> str:
    monkeypatch.setattr(ah, "image_data_uri", lambda u: _PHOTO)
    return ah.construire_html(
        titre=titre,
        message_html=message,
        perimetre_label="Copropriété entière",
        format_effectif=fmt,
        site_nom="Résidence",
        site_url="https://exemple.fr",
        logo_png=None,
        images=["/uploads/photos/capture.png"] * photos,
    )


def test_une_annonce_courte_avec_photo_sort_dans_le_plus_petit_format_qui_porte_une_photo():
    assert choisir_format(_MESSAGE, titre=_TITRE, avec_photos=True) == FORMAT_MIN_AVEC_PHOTOS
    assert FORMAT_MIN_AVEC_PHOTOS == "a6"


def test_une_photo_sans_texte_sort_au_plus_petit_format_qui_porte_une_photo():
    assert choisir_format("", titre=_TITRE, avec_photos=True) == FORMAT_MIN_AVEC_PHOTOS


def test_les_seuils_avec_photo_commencent_au_format_minimal_et_restent_sous_ceux_sans_photo():
    assert SEUILS_FORMAT_AVEC_PHOTOS[0][0] == FORMAT_MIN_AVEC_PHOTOS
    sans = dict(SEUILS_FORMAT)
    for fmt, seuil in SEUILS_FORMAT_AVEC_PHOTOS:
        assert 0 < seuil < sans[fmt], f"{fmt} : la galerie prend de la place, le seuil baisse"


def test_chaque_format_qui_admet_une_photo_lui_donne_une_hauteur_et_une_zone():
    """Un format choisi « avec photo » dont la galerie mesure 0 mm la perdrait."""
    for fmt, _ in SEUILS_FORMAT_AVEC_PHOTOS:
        assert float(ah._GABARITS[fmt]["galerie_max"].removesuffix("mm")) > 0, fmt
        assert ZONE_IMAGE_SEULE_MM[fmt] > HAUTEUR_IMAGE_MIN_MM, fmt
    for fmt in FORMATS[FORMATS.index(FORMAT_MIN_AVEC_PHOTOS) + 1 :]:
        assert ah._GABARITS[fmt]["galerie_max"] == "0mm", fmt


def test_la_photo_n_est_jamais_rognee():
    """Proportions gardées : dimensions `auto`, bornées par des `max-*`, sans recadrage."""
    for fmt, _ in SEUILS_FORMAT_AVEC_PHOTOS:
        regle = re.search(r"\.galerie img \{([^}]*)\}", ah._css(fmt)).group(1)
        assert "object-fit" not in regle, fmt
        assert re.search(r"(?<![-\w])height:\s*auto", regle), fmt
        assert re.search(r"(?<![-\w])width:\s*auto", regle), fmt
        assert "max-height" in regle and "max-width" in regle, fmt


def test_avec_du_texte_la_photo_reste_en_pied_dans_sa_galerie(monkeypatch):
    html = _html(FORMAT_MIN_AVEC_PHOTOS, _MESSAGE, 1, monkeypatch)
    assert 'class="galerie galerie-1"' in html
    assert 'class="corps"' in html
    assert "max-height: " not in html.split('class="galerie')[1].split("</div>")[0]


@pytest.mark.parametrize("fmt", [f for f, _ in SEUILS_FORMAT_AVEC_PHOTOS])
def test_sans_texte_la_photo_occupe_la_zone_bornee_en_millimetres(monkeypatch, fmt):
    """Une borne en % est ignorée par WeasyPrint dans une zone flexible : mesuré."""
    html = _html(fmt, "<p> </p>", 1, monkeypatch)
    assert 'class="corps corps-image"' in html
    borne = re.search(r'<img src="[^"]+" alt="[^"]*" style="max-height: ([\d.]+)mm">', html)
    assert borne, "la photo seule doit porter sa hauteur en millimètres"
    assert float(borne.group(1)) == pytest.approx(
        hauteur_image_seule(fmt, _TITRE, ah._GABARITS[fmt]["titre"]), abs=0.05
    )


def test_un_titre_plus_long_laisse_moins_de_place_a_la_photo_sans_la_faire_disparaitre():
    taille = ah._GABARITS["a6"]["titre"]
    court = hauteur_image_seule("a6", "Info", taille)
    long = hauteur_image_seule("a6", "Une information importante " * 3, taille)
    assert court == ZONE_IMAGE_SEULE_MM["a6"]
    assert HAUTEUR_IMAGE_MIN_MM <= long < court
    assert hauteur_image_seule("a6", "x" * 2000, taille) == HAUTEUR_IMAGE_MIN_MM


def _corps(**champs):
    base = {"titre": "Information", "message": "", "perimetre_cible": ["résidence"], "images": []}
    return annonces_hall.AnnonceHallCreate(**(base | champs))


def test_l_api_accepte_une_affiche_faite_d_une_photo_et_refuse_une_affiche_vide():
    annonces_hall._valider(_corps(images=["/uploads/photos/capture.png"]))
    with pytest.raises(HTTPException) as refus:
        annonces_hall._valider(_corps())
    assert refus.value.status_code == 422
