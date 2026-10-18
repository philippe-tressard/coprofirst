"""Les seuils d'un avis, écrits deux fois — et tenus ensemble (#2075).

`front/src/lib/avis.ts` décide de ce que le formulaire DEMANDE (la remarque sous
3 étoiles, la question de diffusion à partir de 4) ; `app/utils/avis.py` de ce
que le serveur ACCEPTE. Les contextes de build interdisent de partager un
fichier entre les deux (mémoire `project_partage_front_api_impossible`) : ce
test lit le fichier front et compare. Un seuil déplacé d'un seul côté, et
l'écran poserait une question que le serveur n'exige pas — ou l'inverse.
"""

from __future__ import annotations

import pathlib
import re

from app.utils import avis

FRONT = pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "avis.ts"


def _constante(nom: str) -> int:
    source = FRONT.read_text(encoding="utf-8")
    trouve = re.search(rf"export const {nom} = (\d+);", source)
    assert trouve, f"{nom} introuvable dans {FRONT.name} : le contrôle ne mesure plus rien"
    return int(trouve.group(1))


def test_les_seuils_du_front_sont_ceux_du_serveur():
    assert _constante("NOTE_REMARQUE") == avis.NOTE_REMARQUE
    assert _constante("NOTE_PUBLIABLE") == avis.NOTE_PUBLIABLE
