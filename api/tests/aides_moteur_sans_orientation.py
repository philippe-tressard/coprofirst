"""Le moteur d'images de production, privé de `exif_transpose` — pour un cas zéro.

Depuis #2396, le réencodage s'exécute dans un enfant `spawn` : un `monkeypatch`
posé dans le process des tests n'y arrive pas. Le cas zéro de
`test_orientation_photos.py` NOMME donc ce module à la place du moteur
(`images.MOTEUR`) ; l'enfant l'importe, et y trouve le vrai moteur sans la ligne
qui redresse. Tout le reste du chemin — la route, la porte, l'enfant — est celui de
la production.
"""

from app.utils import images_moteur
from app.utils.images_moteur import carres, mesurer, reduire, reencoder  # noqa: F401

images_moteur.ImageOps.exif_transpose = lambda img: img
