"""Réencodage d'images — une seule écriture pour tout le projet.

Deux besoins distincts, un seul moteur :

- **au téléversement** (`routers/uploads.py`) : borner la dimension et normaliser
  le format, une fois pour toutes, avant d'écrire sur le disque ;
- **à la diffusion** (`utils/whatsapp_media.py`) : faire tenir une photo déjà
  stockée sous un **budget d'octets**, parce que le destinataire a un plafond.

Le second n'existait pas avant le 19/09/2026, et l'écrire à côté du premier aurait
donné deux routines de redimensionnement libres de diverger sur l'orientation, le
profil colorimétrique ou la qualité — `standards/02-factorisation.md` §2.

⚠️ `exif_transpose` **avant** `convert("RGB")` : la conversion jette les
métadonnées, donc l'orientation avec elles. L'ordre inverse stocke la photo de
travers, et plus rien ensuite ne sait la redresser
(cf. mémoire « Orientation des photos », 18/09/2026).
"""

import io

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

#  Les photos HEIC/HEIF d'iPhone (#2389) : Pillow les ouvre comme les autres, et
#  elles repartent en JPEG. Décodage seul — l'image n'embarque aucun encodeur HEVC
#  (`api/Dockerfile`, `scripts/verifier_heif.py`).
register_heif_opener()

#: Dimension maximale d'une image stockée, en pixels (côté le plus long).
DIMENSION_MAX = 1600

#: Qualité JPEG d'une image stockée.
QUALITE = 85

#: Paliers de repli quand une image doit tenir sous un budget d'octets, du plus
#: fidèle au plus économe. Le dernier est volontairement bas : mieux vaut une
#: photo médiocre qui arrive qu'une photo parfaite que le destinataire refuse.
PALIERS_BUDGET: tuple[tuple[int, int], ...] = (
    (1280, 80),
    (1024, 75),
    (800, 70),
    (640, 60),
)


def reencoder_jpeg(data: bytes, max_dim: int = DIMENSION_MAX, qualite: int = QUALITE) -> bytes:
    """Octets d'image → JPEG borné à `max_dim`, orientation redressée.

    Lève `ValueError` si les octets ne sont pas une image lisible : c'est à
    l'appelant de décider ce qu'il en dit à l'utilisateur (un routeur rend 400,
    une diffusion se replie sur le texte seul).
    """
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img) or img
        img = img.convert("RGB")
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        sortie = io.BytesIO()
        img.save(sortie, format="JPEG", quality=qualite, optimize=True)
        return sortie.getvalue()
    except Exception as exc:  # noqa: BLE001 — toute erreur Pillow vaut « illisible »
        raise ValueError("image illisible") from exc


def dimensions(data: bytes) -> tuple[int, int] | None:
    """`(largeur, hauteur)` d'une image, sans la décoder — None si illisible."""
    try:
        return Image.open(io.BytesIO(data)).size
    except Exception:  # noqa: BLE001 — toute erreur Pillow vaut « illisible »
        return None


def enregistrer_image_recue(
    data: bytes,
    nom_origine: str | None,
    content_type: str | None,
    dossier: str,
    *,
    user=None,
    session=None,
    max_dim: int = DIMENSION_MAX,
) -> str:
    """Contrôle, réencode puis écrit une image REÇUE. Rend son URL.

    Le geste du téléversement (`routers/uploads`) et de la relève des courriels
    (`utils/courriel_pieces_jointes`) : écrit une fois, sans quoi deux chemins
    d'entrée d'une image divergeraient sur le contrôle ou le réencodage.

    ⚠️ Le contrôle porte sur ce qui ARRIVE, avant réencodage : c'est l'octet reçu
    qui peut mentir, pas celui que nous produisons. L'extension écrite est
    `.jpg`, celle du réencodage ; le radical du nom d'origine est gardé
    (`nom_stocke`) — une photo arrivait sinon dans l'e-mail sous un nom d'UUID.

    Lève une `HTTPException` (400 ou 413) au premier refus.
    """
    from fastapi import HTTPException

    from app.utils.fichiers import enregistrer_fichier_recu, verifier_fichier_recu
    from app.utils.stockage import stockage

    verifier_fichier_recu(data, nom_origine, content_type, "image", user)
    try:
        data = reencoder_jpeg(data, max_dim=max_dim)
    except ValueError:
        raise HTTPException(400, "Impossible de lire l'image.")
    #  🔴 Le type ÉCRIT est celui des octets écrits : du JPEG. Avec le type reçu,
    #  la signature du JPEG produit était confrontée à `.png` — toute image PNG,
    #  WebP ou GIF était refusée en 400, et seules les photos JPEG passaient
    #  (trouvé le 31/10/2026, en versant les pièces jointes des courriels).
    nom = enregistrer_fichier_recu(
        data,
        nom_origine,
        "image/jpeg",
        "image",
        dossier,
        user=user,
        extension_forcee=".jpg",
        session=session,
    )
    return stockage().url(f"{dossier}/{nom}")


def reduire_sous_budget(data: bytes, budget_octets: int) -> bytes:
    """Ramène l'image sous `budget_octets`, au mieux — rend les octets à envoyer.

    Rend les octets **d'origine** si elle tient déjà : le cas courant ne doit rien
    recompresser, sans quoi chaque diffusion dégraderait une photo qui allait
    bien.

    Si aucun palier n'atteint le budget, rend le plus petit résultat obtenu
    plutôt que d'échouer : c'est à l'appelant de constater le dépassement. Une
    fonction qui lèverait ici ferait perdre le message entier, alors que le
    destinataire acceptera peut-être quand même.
    """
    if len(data) <= budget_octets:
        return data
    meilleur = data
    for max_dim, qualite in PALIERS_BUDGET:
        try:
            candidat = reencoder_jpeg(data, max_dim=max_dim, qualite=qualite)
        except ValueError:
            return meilleur
        if len(candidat) < len(meilleur):
            meilleur = candidat
        if len(candidat) <= budget_octets:
            return candidat
    return meilleur


def carre_png(data: bytes, taille: int) -> bytes:
    """Octets d'image → PNG carré de `taille` pixels, transparence conservée.

    Le logo d'une résidence (#1728) : il sert d'icône d'application, de favicon
    et d'en-tête de document, qui sont tous CARRÉS. Une image qui ne l'est pas
    est centrée sur un fond transparent, jamais rognée — on ne coupe pas un
    nom écrit dans un logo. Orientation redressée comme pour une photo.

    Lève `ValueError` si les octets ne sont pas une image lisible.
    """
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img) or img
        img = img.convert("RGBA")
        cote = max(img.size)
        fond = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
        fond.paste(img, ((cote - img.width) // 2, (cote - img.height) // 2))
        fond = fond.resize((taille, taille), Image.LANCZOS)
        sortie = io.BytesIO()
        fond.save(sortie, format="PNG", optimize=True)
        return sortie.getvalue()
    except Exception as exc:  # noqa: BLE001 — toute erreur Pillow vaut « illisible »
        raise ValueError("image illisible") from exc
