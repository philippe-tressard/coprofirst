"""Réencodage d'images — une seule écriture pour tout le projet.

Deux besoins distincts, un seul moteur :

- **au téléversement** (`routers/uploads.py`) : borner la dimension et normaliser
  le format, une fois pour toutes, avant d'écrire sur le disque ;
- **à la diffusion** (`utils/whatsapp_media.py`) : faire tenir une photo déjà
  stockée sous un **budget d'octets**, parce que le destinataire a un plafond.

Le second n'existait pas avant le 19/09/2026, et l'écrire à côté du premier aurait
donné deux routines de redimensionnement libres de diverger sur l'orientation, le
profil colorimétrique ou la qualité — `standards/02-factorisation.md` §2.

🔴 **Aucune image ne se décode dans le process de l'API** (#2396). Ce module est la
porte : chaque fonction nomme son geste dans `images_moteur`, qui s'exécute dans un
enfant `spawn` jetable (`utils/process_isole`), avec un délai et un plafond de
mémoire. Un fichier piégé n'emporte que l'enfant ; l'appelant reçoit « illisible ».
Ce module n'importe pas Pillow. 🔒 `test_images_hors_process.py`.
"""

import logging

from app.utils.process_isole import EchecIsole, executer_isole

logger = logging.getLogger(__name__)

#: Le module qui lit les images — nommé, jamais importé : l'enfant l'importe seul.
MOTEUR = "app.utils.images_moteur"

#: Au-delà, l'enfant est abattu. Une photo de 12 Mpx (HEIC compris) se lit en
#: quelques secondes sur le RPi ; le délai ne protège que d'un moteur qui boucle.
DELAI_S = 60.0

#: L'espace d'adressage de l'enfant (Linux). Il couvre l'interpréteur, Pillow et
#: ses bibliothèques, et une image au plafond de Pillow (`MAX_IMAGE_PIXELS`) ;
#: au-delà, c'est l'enfant qui meurt, jamais le RPi. Mesure : la PR de #2396.
MEMOIRE_MAX_OCTETS = 1536 * 1024 * 1024


def _isole(fonction: str, *args, nom: str):
    """`images_moteur.fonction(*args)` dans un enfant. Lève `EchecIsole`."""
    valeur, _temoin = executer_isole(
        MOTEUR,
        fonction,
        *args,
        delai_s=DELAI_S,
        nom=nom,
        memoire_max_octets=MEMOIRE_MAX_OCTETS,
    )
    return valeur


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

    Lève `ValueError` si les octets ne sont pas une image lisible — ou si le
    moteur a planté, dépassé son délai ou sa mémoire : c'est à l'appelant de
    décider ce qu'il en dit à l'utilisateur (un routeur rend 400, une diffusion
    se replie sur le texte seul).
    """
    try:
        jpeg = _isole("reencoder", data, max_dim, qualite, nom="image-reencodage")
    except EchecIsole as exc:
        logger.warning("Image non réencodée : %s", exc)
        raise ValueError("image illisible") from exc
    if jpeg is None:
        raise ValueError("image illisible")
    return jpeg


def dimensions(images: list[bytes]) -> list[tuple[int, int] | None]:
    """`(largeur, hauteur)` de chaque image, sans la décoder — None si illisible.

    Toutes dans UN enfant : la relève mesure les images d'un message d'un coup.
    Si l'enfant meurt (une image piégée parmi d'autres), toutes valent None —
    illisibles ici, chacune sera jugée seule au réencodage.
    """
    if not images:
        return []
    try:
        return _isole("mesurer", tuple(images), nom="image-mesure")
    except EchecIsole as exc:
        logger.warning("Images non mesurées : %s", exc)
        return [None] * len(images)


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
    try:
        return _isole("reduire", data, budget_octets, PALIERS_BUDGET, nom="image-budget")
    except EchecIsole as exc:
        logger.warning("Image non réduite : %s", exc)
        return data


def carres_png(data: bytes, tailles: tuple[int, ...]) -> dict[int, bytes]:
    """Octets d'image → `{taille: PNG carré}`, transparence conservée.

    Le logo d'une résidence (#1728) : il sert d'icône d'application, de favicon
    et d'en-tête de document, qui sont tous CARRÉS. Une image qui ne l'est pas
    est centrée sur un fond transparent, jamais rognée. Toutes les tailles dans
    UN enfant (`utils/logo` les garde ensuite en mémoire).

    Lève `ValueError` si les octets ne sont pas une image lisible.
    """
    try:
        rendus = _isole("carres", data, tuple(tailles), nom="image-carres")
    except EchecIsole as exc:
        logger.warning("Image non mise au carré : %s", exc)
        raise ValueError("image illisible") from exc
    if rendus is None:
        raise ValueError("image illisible")
    return rendus


def carre_png(data: bytes, taille: int) -> bytes:
    """Octets d'image → PNG carré de `taille` pixels. Lève `ValueError` si illisible."""
    return carres_png(data, (taille,))[taille]
