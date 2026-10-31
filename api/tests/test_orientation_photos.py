"""Une photo téléversée est stockée À L'ENDROIT (vérification du 08/09/2026).

## Ce que la vérification a trouvé

Le code est **correct** : `utils/images.py` applique `ImageOps.exif_transpose`
avant d'enregistrer, donc la rotation est cuite dans le JPEG écrit et le fichier
servi est droit quel que soit le lecteur.

Mais **aucun test ne le tenait**. Une photo prise au téléphone porte presque
toujours une orientation EXIF ; la ligne qui la corrige est une ligne comme une
autre, qu'un nettoyage d'imports ou une réécriture du redimensionnement peut
emporter sans que rien ne bouge — l'image reste valide, elle est simplement
couchée. C'est `standards/05` : *un défaut corrigé sans garde-fou revient*, et
celui-ci n'aurait même pas besoin de revenir, il suffirait qu'on le retire.

## 🔴 Ce que ces tests ne tenaient PAS non plus, jusqu'au 17/09/2026

Ils appelaient un `_traiter()` local, présenté comme « le geste d'`uploads.py`,
dans le même ordre » — c'est-à-dire une **recopie** du pipeline. Un contrôle qui
rejoue sa propre copie mesure la copie : retirer `exif_transpose` de
`routers/uploads.py` les laissait tous verts, et la photo partait couchée en
production. L'en-tête affirmait pourtant l'inverse — *« ils regardent les pixels
du fichier écrit, jamais le code qui l'écrit »*.

Deux photos de ticket stockées couchées ont été constatées à l'écran le
17/09/2026 (téléversées en avril 2026, avant l'unification des téléversements —
noms sans radical). Elles ont dû être redressées **à la main**, fichier par
fichier : l'EXIF étant retiré à l'enregistrement, plus rien ne permet de deviner
le bon sens après coup. C'est ce qui rend ce garde-fou irremplaçable — le défaut
qu'il prévient ne se répare pas par un correctif de code.

Ils appellent donc désormais `uploads._save_image`, la fonction de production,
avec la racine du stockage (`uploads_dir`) détournée vers un répertoire temporaire, et relisent le
fichier réellement écrit. `test_cas_zero_…` le prouve en neutralisant
`exif_transpose` **dans le moteur de production** (nommé à l'enfant, #2396) : si ces tests mesuraient
encore une copie, il échouerait.

## ⚠️ Ce que j'ai cru, et qui était faux

J'ai d'abord écrit ici que l'ORDRE des deux appels était le sujet — que
`convert("RGB")` perdait la balise EXIF et qu'appeler `exif_transpose` après
laisserait la photo couchée. **C'est faux** : Pillow reporte `info` à travers
`convert`, et les deux ordres redressent. Le test qui devait le prouver a
échoué, et il avait raison.

Ce qui compte est donc la **présence** de `exif_transpose`, et le fait que le
JPEG écrit ne reporte pas la balise — `save()` ne l'écrit que si on la lui passe.
Le commentaire d'`uploads.py` (« Corriger l'orientation AVANT convert ») dit une
prudence exacte mais pas nécessaire ; ces tests, eux, mesurent le résultat.
"""

from __future__ import annotations

import io
import pathlib

import pytest

Image = pytest.importorskip(
    "PIL.Image",
    reason="Pillow est une dépendance de production ; son absence rend ces "
    "tests INCONNUS, pas verts",
)
from fastapi import UploadFile  # noqa: E402
from starlette.datastructures import Headers  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.routers import uploads  # noqa: E402
from app.utils import images  # noqa: E402
from sqlmodel import Session  # noqa: E402
from tests.aides_base import compte, moteur_de_test  # noqa: E402


def _image_couchee() -> bytes:
    """Un JPEG de 40×20 dont l'EXIF dit « tourne-moi d'un quart de tour ».

    L'orientation 6 est celle d'un téléphone tenu à la verticale : c'est le cas
    le plus fréquent, et celui que personne ne pense à essayer.
    """
    img = Image.new("RGB", (40, 20), "white")
    #  Un repère asymétrique : sans lui, une image unie passerait tous les tests
    #  quelle que soit sa rotation.
    for x in range(10):
        for y in range(5):
            img.putpixel((x, y), (255, 0, 0))

    exif = img.getexif()
    exif[274] = 6  # Orientation : rotation de 90° dans le sens horaire
    tampon = io.BytesIO()
    img.save(tampon, format="JPEG", exif=exif, quality=95)
    return tampon.getvalue()


def _image_droite() -> bytes:
    """La même, sans orientation EXIF : elle ne doit PAS bouger."""
    img = Image.new("RGB", (40, 20), "white")
    tampon = io.BytesIO()
    img.save(tampon, format="JPEG", quality=95)
    return tampon.getvalue()


def _televerser(donnees: bytes, racine: pathlib.Path, patch) -> Image.Image:
    """🔴 La VRAIE fonction de `routers/uploads.py`, et le fichier qu'elle écrit.

    C'est tout l'intérêt : `_save_image` est le seul endroit du produit qui
    enregistre une image, et il est appelé ici tel quel. Seule la racine du
    volume est détournée — `/app/uploads` n'existe pas sur un poste.
    """
    patch.setattr(get_settings(), "uploads_dir", str(racine))
    fichier = UploadFile(
        file=io.BytesIO(donnees),
        filename="photo-de-ticket.jpg",
        headers=Headers({"content-type": "image/jpeg"}),
    )
    #  « essai » est un dossier SERVI : l'image note son auteur (#2154).
    with Session(moteur_de_test()) as session:
        url = uploads._save_image(fichier, "essai", session, compte(session))
    ecrit = racine / "essai" / url.rsplit("/", 1)[-1]
    assert ecrit.is_file(), f"aucun fichier écrit pour {url}"
    return Image.open(ecrit)


def test_la_ROTATION_est_cuite_dans_le_fichier_ecrit(tmp_path, monkeypatch):
    """🔴 Ce que le navigateur recevra, et lui seul.

    Corriger l'orientation en mémoire ne sert à rien si le fichier écrit garde
    la balise : chaque lecteur déciderait alors pour lui-même. Le fichier servi
    doit être droit **sans** balise à interpréter.

    Le cas de la photo prise au téléphone : 40×20 avec une orientation 6 doit
    devenir 20×40 — les dimensions prouvent la rotation sans inspecter un pixel.
    """
    relue = _televerser(_image_couchee(), tmp_path, monkeypatch)
    assert relue.size == (20, 40), (
        f"la photo n'a pas été redressée : {relue.size} au lieu de (20, 40). "
        "`ImageOps.exif_transpose` n'est plus appliqué au téléversement."
    )
    assert relue.getexif().get(274) in (None, 1), (
        "le fichier écrit porte encore une orientation EXIF : un lecteur qui "
        "l'applique montrera la photo tournée une seconde fois."
    )


def test_une_photo_DROITE_n_est_pas_tournee(tmp_path, monkeypatch):
    """Le pendant, sans lequel « redresser » pourrait vouloir dire « tourner ».

    Un contrôle qui n'exige que le changement est satisfait par un traitement qui
    tourne tout le monde — y compris ce qui était déjà droit.
    """
    assert _televerser(_image_droite(), tmp_path, monkeypatch).size == (40, 20), (
        "une photo sans orientation EXIF a été tournée."
    )


def test_cas_zero_SANS_exif_transpose_dans_uploads_la_photo_reste_couchee(tmp_path, monkeypatch):
    """🔴 La preuve que ces tests mesurent le MODULE DE PRODUCTION.

    On neutralise `exif_transpose` là où il est appelé — dans
    `app.utils.images`, où le réencodage vit depuis le 19/09/2026 (#1057) — et la
    photo doit repartir couchée. Deux choses en découlent : les tests ci-dessus
    mesurent bien quelque chose, et ils le mesurent **au bon endroit**. Tant
    qu'ils rejouaient une copie locale du pipeline, ce cas zéro passait aussi…
    sans rien prouver de la production.

    🔴 **Ce test a échoué le jour où le geste a déménagé, et c'est exactement ce
    qu'on lui demande.** Le réencodage a quitté `routers/uploads.py` pour
    `utils/images.py`, partagé avec la diffusion WhatsApp ; ce cas zéro visait
    `uploads.ImageOps`, qui n'existait plus. Il a donc suivi la logique — il ne
    s'est pas affaibli pour la laisser partir sans lui
    (`standards/02-factorisation.md` §4 ter : extraire, c'est emporter ce que le
    compilateur ne vérifie pas).

    ⚠️ Un cas zéro antérieur a corrigé une erreur de ma part : j'avais écrit que
    l'ORDRE des deux appels décidait, et il a montré que non. Un cas zéro ne sert
    pas seulement à éprouver le contrôle — il éprouve aussi ce qu'on croit savoir.

    🔴 Depuis #2396, le réencodage s'exécute dans un enfant `spawn`, où un
    `monkeypatch` du parent n'arrive pas : ce cas zéro NOMME un moteur privé de
    `exif_transpose` (`tests/aides_moteur_sans_orientation.py`) à la place du
    vrai. Il échouerait si `_televerser` cessait de passer par le moteur nommé.
    """
    monkeypatch.setattr(images, "MOTEUR", "tests.aides_moteur_sans_orientation")
    couchee = _televerser(_image_couchee(), tmp_path, monkeypatch)
    assert couchee.size == (40, 20), (
        "l'image se redresse sans `exif_transpose` : ces tests ne prouvent plus "
        "que le réencodage partagé la redresse."
    )


def test_le_courriel_joint_la_photo_TELLE_QUELLE(tmp_path):
    """L'orientation a UN propriétaire : le téléversement (17/09/2026).

    `utils/email/pieces_jointes.py` corrigeait l'EXIF une seconde fois, en
    écrivant un `exif_XXXX.jpg` à côté de chaque image. Comme
    `ImageOps.exif_transpose` renvoie une copie même quand il n'y a rien à
    appliquer, ce n'était pas un filet de sécurité inerte : chaque photo partait
    réencodée en qualité 92, et son nom devait être recomposé.

    Ce test tient la règle dans l'autre sens : le courriel joint le fichier tel
    qu'il est sur le disque. Il échouera si un second traitement d'image
    réapparaît sur ce chemin.
    """
    from app.utils.email.pieces_jointes import _preparer_pieces_jointes

    photo = tmp_path / "abcdef0123456789abcdef0123456789_balcon.jpg"
    photo.write_bytes(_image_couchee())
    octets = photo.read_bytes()

    prets = _preparer_pieces_jointes([str(photo)])

    assert [pj["file"] for pj in prets] == [str(photo)], (
        "la pièce jointe ne pointe plus le fichier du volume : un traitement "
        "intermédiaire s'est réinstallé entre le disque et le message."
    )
    assert photo.read_bytes() == octets, "le fichier du volume a été réécrit"
    assert not list(tmp_path.glob("exif_*")), (
        "un fichier temporaire de correction EXIF a été écrit ; l'orientation "
        "est déjà cuite au téléversement (`routers/uploads.py`)."
    )
