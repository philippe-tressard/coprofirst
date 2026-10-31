"""La vérification HEIC de l'image (#2389) refuse ce qu'elle doit refuser.

`scripts/verifier_heif.py` tourne à la construction de l'image, où la CI de la PR
ne le voit pas : ses règles s'éprouvent donc ici, sur des mesures posées — et
sur la roue PyPI que la CI et le poste installent pour les tests, qui embarque
précisément l'encodeur x265 que l'image refuse.
"""

from __future__ import annotations

import pathlib

import pillow_heif

from tests.aides_migrations import charger_migration

API = pathlib.Path(__file__).resolve().parents[1]
#  Un script hors paquet, chargé par son chemin — l'aide sert aussi bien qu'à une migration.
verifier_heif = charger_migration("verifier_heif", API / "scripts")

_LDD_SYSTEME = "\tlibheif.so.1 => /lib/aarch64-linux-gnu/libheif.so.1 (0x0000)\n"
_INFO_SYSTEME = {
    "libheif": "1.23.6",
    "HEIF": None,
    "encoders": {"mask": "mask"},
    "decoders": {"libde265": "libde265 HEVC decoder"},
}
_CONFORME = dict(
    paquets=["libheif1", "libheif-plugin-libde265", "libde265-0"],
    fichiers_interdits=[],
    fichiers_parcourus=12000,
    ldd=_LDD_SYSTEME,
    libs_embarquees=False,
    info=_INFO_SYSTEME,
    taille=verifier_heif.TAILLE_TEMOIN,
)


def _constats(**ecarts) -> list[str]:
    return verifier_heif.constats(**{**_CONFORME, **ecarts})


def test_l_image_attendue_est_conforme():
    assert _constats() == []


def test_chaque_manquement_est_refuse():
    fautes = {
        "paquet x265": dict(paquets=["libheif1", "libheif-plugin-x265"]),
        "fichier x265": dict(fichiers_interdits=["/usr/lib/libx265.so.215"]),
        "libheif embarquée": dict(
            ldd="\tlibheif-f59036f4.so.1.23.6 => /usr/local/lib/python3.12/site-packages/"
            "pillow_heif.libs/libheif-f59036f4.so.1.23.6\n"
        ),
        "libheif usr/lib": dict(ldd="\tlibheif.so.1 => /usr/local/lib/libheif.so.1\n"),
        "roue PyPI": dict(libs_embarquees=True),
        "encodeur HEVC": dict(info={**_INFO_SYSTEME, "HEIF": "x265 HEVC encoder"}),
        "sans libde265": dict(info={**_INFO_SYSTEME, "decoders": {}}),
        "photo non décodée": dict(taille=None),
    }
    for nom, ecart in fautes.items():
        assert len(_constats(**ecart)) == 1, nom


def test_un_controle_qui_ne_peut_pas_s_executer_echoue():
    """dpkg muet, rien parcouru, `ldd` absent : INCONNU n'est jamais conforme."""
    assert len(_constats(paquets=[], fichiers_parcourus=0, ldd=None)) == 3


def test_la_roue_pypi_des_tests_serait_refusee_dans_l_image():
    """La roue installée ici embarque x265 : si l'image la recevait, la construction
    échouerait. Si ce test tombe, la CI ne prend plus la roue PyPI — relire le
    commentaire de `pillow-heif` dans `api/requirements.txt`."""
    echecs = _constats(info=pillow_heif.libheif_info())
    assert any("encodeur HEVC" in e for e in echecs), echecs


def test_l_image_lance_la_verification_sur_la_photo_temoin():
    dockerfile = (API / "Dockerfile").read_text(encoding="utf-8")
    assert "RUN python -I scripts/verifier_heif.py tests/donnees/photo.heic" in dockerfile
    assert (API / "tests" / "donnees" / "photo.heic").is_file()
    assert not (API / ".dockerignore").exists(), "la photo témoin doit entrer dans l'image"
