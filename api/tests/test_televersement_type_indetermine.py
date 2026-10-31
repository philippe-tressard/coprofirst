"""Un fichier sans type MIME connu du poste se juge à son extension, puis à son contenu (#2389).

🔴 Le défaut, le 31/10/2026 : une photo HEIC d'iPhone, jointe à une affaire depuis
un PC Windows, était refusée — « Format non supporté : application/octet-stream ».
Windows ne connaît pas toujours de type pour `.heic` (ni `.heif`, `.avif`…) : le
navigateur l'envoie alors sans type, ou en `application/octet-stream`. Le routeur
choisissait la famille sur ce type seul, et la signature n'était même pas lue.

La règle — `fichiers.type_annonce`, appliquée par `verifier_fichier_recu`, la porte
unique : un type INDÉTERMINÉ se déduit de l'extension, parmi les types de la famille
seulement ; la signature du contenu tranche ensuite. Une extension `.heic` sur des
octets qui ne sont pas un HEIF reste refusée.
"""

from __future__ import annotations

import io
import pathlib

import pytest
from fastapi import HTTPException
from PIL import Image

from app.models.core import RoleUtilisateur
from app.utils.fichiers import FAMILLES, TYPES_INDETERMINES, verifier_fichier_recu
from tests.aides_http import base_http, client_http

_PHOTO_HEIC = (pathlib.Path(__file__).parent / "donnees" / "photo.heic").read_bytes()
_EXE = b"MZ\x90\x00" + b"\x00" * 60


def _png() -> bytes:
    sortie = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 120, 200)).save(sortie, format="PNG")
    return sortie.getvalue()


@pytest.mark.parametrize("indetermine", sorted(TYPES_INDETERMINES))
@pytest.mark.parametrize("extension", [".heic", ".HEIC", ".heif"])
def test_une_photo_heic_sans_type_passe_la_porte(indetermine, extension):
    """Le cas de Windows : `IMG_1830.HEIC`, annoncée sans type."""
    assert verifier_fichier_recu(_PHOTO_HEIC, f"IMG_1830{extension}", indetermine, "image") in (
        ".heic",
        ".heif",
    )


@pytest.mark.parametrize("famille", ["image", "document", "document_prive", "tableur"])
def test_chaque_extension_de_la_famille_se_deduit(famille):
    """Toute extension d'une famille — `.avif`, `.webp`, `.docx` sans Office… —
    se déduit sans type : la règle ne connaît pas de format à part."""
    from app.utils.fichiers import type_annonce

    for type_, extension in FAMILLES[famille].types.items():
        assert type_annonce("application/octet-stream", f"x{extension}", famille) == type_


def test_une_extension_heic_sur_des_octets_png_est_refusee():
    """Le contenu décide : un PNG nommé `.heic` n'est pas un HEIF."""
    with pytest.raises(HTTPException) as refus:
        verifier_fichier_recu(_png(), "photo.heic", "application/octet-stream", "image")
    assert refus.value.status_code == 400
    assert "ne correspond pas" in refus.value.detail


def test_un_executable_renomme_heic_est_refuse():
    with pytest.raises(HTTPException) as refus:
        verifier_fichier_recu(_EXE, "photo.heic", "application/octet-stream", "image")
    assert refus.value.status_code == 400


def test_une_extension_hors_famille_reste_refusee_et_le_message_la_nomme():
    """Sans type, le message nomme l'extension : « application/octet-stream »
    n'apprenait rien à l'utilisateur."""
    with pytest.raises(HTTPException) as refus:
        verifier_fichier_recu(_EXE, "outil.exe", "application/octet-stream", "image")
    assert refus.value.status_code == 400
    assert ".exe" in refus.value.detail and "octet-stream" not in refus.value.detail


def test_un_type_annonce_n_est_jamais_remplace_par_l_extension():
    """Un type DÉTERMINÉ reste celui qu'on juge : l'extension ne le corrige pas."""
    with pytest.raises(HTTPException):
        verifier_fichier_recu(_PHOTO_HEIC, "photo.heic", "image/svg+xml", "image")


def test_par_la_porte_reelle_depuis_windows(disque_jetable):
    """`/uploads/fichier` (pièce jointe) et `/uploads/avatar` : la photo d'iPhone
    envoyée en `application/octet-stream` entre, réencodée en JPEG ; le PNG nommé
    `.heic` et l'exécutable renommé sont refusés."""
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.résident)
        for route in ("/uploads/fichier", "/uploads/avatar"):
            r = http.post(
                route,
                files={"file": ("IMG_1830.HEIC", _PHOTO_HEIC, "application/octet-stream")},
            )
            assert r.status_code == 200, (route, r.text)
            assert r.json()["url"].endswith(".jpg"), r.json()
        #  Sans aucun type, comme le fait aussi le navigateur.
        sans_type = http.post(
            "/uploads/fichier", files={"file": ("IMG_1830.HEIC", _PHOTO_HEIC, "")}
        )
        assert sans_type.status_code == 200 and sans_type.json()["type"] == "image", sans_type.text
        for nom, octets in (("photo.heic", _png()), ("photo.heic", _EXE), ("outil.exe", _EXE)):
            refus = http.post(
                "/uploads/fichier", files={"file": (nom, octets, "application/octet-stream")}
            )
            assert refus.status_code == 400, (nom, refus.text)
        #  Un document sans type se range dans SA famille, et garde son extension.
        doc = http.post(
            "/uploads/fichier",
            files={"file": ("pv.pdf", b"%PDF-1.4\n%%EOF\n", "application/octet-stream")},
        )
        assert doc.status_code == 200 and doc.json()["type"] == "document", doc.text
        assert doc.json()["url"].endswith(".pdf")
