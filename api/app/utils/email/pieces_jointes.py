"""Courriels — préparation des pièces jointes avant envoi.

Extrait de `email.py` le 11/08/2026. Voir `gabarit.py` pour la règle de partage.
"""

from app.utils.en_tete_fichier import en_tete_fichier
from app.utils.fichiers import nom_lisible


def _preparer_pieces_jointes(paths: list[str]) -> list[dict]:
    """Les pièces jointes prêtes pour le message, avec leur nom d'origine.

    Le préfixe UUID de `nom_stocke` faisait perdre ce nom dans la messagerie
    du destinataire — « 0d41107a6c…lasseurs.pdf ». Le nom affiché est donc
    calculé sur le chemin, et transmis explicitement en `Content-Disposition`.

    Écrit une fois : `send_email` et `send_email_group` faisaient chacun ce
    même travail de leur côté.

    ## 🔴 L'orientation EXIF n'est PAS corrigée ici (17/09/2026)

    Elle l'était, par un `_fix_image_orientations` qui écrivait un
    `exif_XXXX.jpg` temporaire à côté de chaque image. C'était la **seconde**
    réponse à une question qui a déjà son propriétaire : `routers/uploads.py`
    cuit la rotation dans le JPEG au téléversement et n'écrit aucune balise.
    Une image de `/uploads/` n'en porte donc aucune — vérifié sur les 52 du
    volume de production le 17/09/2026.

    Ce second passage ne corrigeait plus rien, et il coûtait : `exif_transpose`
    renvoie une **copie** même sans balise à appliquer (Pillow 12), donc le
    test `corrected is img` était toujours faux et CHAQUE photo partait
    réencodée en qualité 92 — une perte de qualité, un fichier temporaire et
    un nom à recomposer, pour une correction déjà faite au téléversement.
    """
    prets: list[dict] = []
    for chemin in paths:
        # Le nom vient de `nom_stocke`, donc déjà réduit à [A-Za-z0-9_.-] ; la
        # porte neutralise malgré tout guillemets et sauts de ligne, qui
        # casseraient l'en-tête pour les fichiers plus anciens, aux noms non
        # assainis, et donne un repli ASCII à un nom accentué (#2985).
        prets.append({"file": chemin, "headers": en_tete_fichier(nom_lisible(chemin))})
    return prets
