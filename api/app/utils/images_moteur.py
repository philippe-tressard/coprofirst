"""Le moteur d'images — **exécuté dans un process jetable, jamais dans l'API** (#2396).

Pillow s'appuie sur des bibliothèques C (libjpeg, libpng, libtiff, libwebp,
libavif, libheif…) dont l'historique compte des corruptions de mémoire : un
fichier piégé qui fait planter le décodeur emporterait le worker de l'API. Toute
lecture d'une image vit donc ICI, et ce module n'est atteint que par
`utils/process_isole`, qui l'importe dans un enfant `spawn` à chaque appel.

🔒 `test_images_hors_process.py` : `Image.open`, `pillow_heif` et Pillow lui-même
ne s'emploient nulle part ailleurs dans l'API, et aucun module ne l'importe — on le
NOMME (`images.MOTEUR`). La porte de l'API est `utils/images`.

⚠️ `exif_transpose` **avant** `convert("RGB")` : la conversion jette les
métadonnées, donc l'orientation avec elles. L'ordre inverse stocke la photo de
travers, et plus rien ensuite ne sait la redresser
(cf. mémoire « Orientation des photos », 18/09/2026).
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

#  Les photos HEIC/HEIF d'iPhone (#2389) : Pillow les ouvre comme les autres, et
#  elles repartent en JPEG. Décodage seul — l'image n'embarque aucun encodeur HEVC
#  (`api/Dockerfile`, `scripts/verifier_heif.py`).
register_heif_opener()


def _ouvrir(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    return ImageOps.exif_transpose(img) or img


def reencoder(data: bytes, max_dim: int, qualite: int) -> bytes | None:
    """Octets d'image → JPEG borné à `max_dim`, orientation redressée ; None si illisible."""
    try:
        img = _ouvrir(data).convert("RGB")
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        sortie = io.BytesIO()
        img.save(sortie, format="JPEG", quality=qualite, optimize=True)
        return sortie.getvalue()
    except Exception:  # noqa: BLE001 — toute erreur Pillow vaut « illisible »
        return None


def reduire(data: bytes, budget_octets: int, paliers: tuple[tuple[int, int], ...]) -> bytes:
    """Le plus petit JPEG des `paliers` qui tient sous le budget — sinon le plus petit obtenu.

    Les paliers se jouent dans le MÊME enfant : un enfant par palier paierait
    l'import de Pillow jusqu'à quatre fois pour une seule photo.
    """
    meilleur = data
    for max_dim, qualite in paliers:
        candidat = reencoder(data, max_dim, qualite)
        if candidat is None:
            return meilleur
        if len(candidat) < len(meilleur):
            meilleur = candidat
        if len(candidat) <= budget_octets:
            return candidat
    return meilleur


def mesurer(images: tuple[bytes, ...]) -> list[tuple[int, int] | None]:
    """`(largeur, hauteur)` de chaque image, sans la décoder — None si illisible."""
    tailles: list[tuple[int, int] | None] = []
    for data in images:
        try:
            tailles.append(Image.open(io.BytesIO(data)).size)
        except Exception:  # noqa: BLE001 — toute erreur Pillow vaut « illisible »
            tailles.append(None)
    return tailles


def carres(data: bytes, tailles: tuple[int, ...]) -> dict[int, bytes] | None:
    """L'image en PNG carrés de chaque taille, transparence conservée ; None si illisible.

    Une image qui n'est pas carrée est centrée sur un fond transparent, jamais
    rognée — on ne coupe pas un nom écrit dans un logo.
    """
    try:
        img = _ouvrir(data).convert("RGBA")
        cote = max(img.size)
        fond = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
        fond.paste(img, ((cote - img.width) // 2, (cote - img.height) // 2))
        rendus: dict[int, bytes] = {}
        for taille in tailles:
            sortie = io.BytesIO()
            fond.resize((taille, taille), Image.LANCZOS).save(sortie, format="PNG", optimize=True)
            rendus[taille] = sortie.getvalue()
        return rendus
    except Exception:  # noqa: BLE001 — toute erreur Pillow vaut « illisible »
        return None
