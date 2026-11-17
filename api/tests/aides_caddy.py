"""Le `Caddyfile` versionné, lu et découpé en blocs à UN endroit pour les tests (#1612).

## Pourquoi cette aide existe (04/10/2026)

Six tests extrayaient un bloc `handle …` par la même expression, recopiée :
`handle\\s+X\\s*\\{(.*?)\\n    \\}` — la fin du bloc reconnue à QUATRE ESPACES.
Le jour où le fichier est passé dans la forme de `caddy fmt` (tabulations),
les six ont échoué ensemble : une forme recopiée casse partout à la fois, et
seulement là où quelqu'un pense à la chercher.

La forme du fichier est tenue par `test_caddyfile_format.py` : une tabulation
par niveau. Un bloc `handle` de premier niveau se ferme donc par `\\n\\t}`.
"""

from __future__ import annotations

import pathlib
import re

CADDYFILE = pathlib.Path(__file__).resolve().parents[2] / "Caddyfile"


def caddyfile() -> str:
    """Le texte du `Caddyfile` versionné — cas zéro compris."""
    contenu = CADDYFILE.read_text(encoding="utf-8")
    # Cible introuvable ⇒ INCONNU, jamais OK.
    assert len(contenu) > 200, "Caddyfile vide ou illisible : contrôle impossible"
    return contenu


def blocs_handle(contenu: str, chemin: str = r"\S+") -> list[tuple[str, str]]:
    """Chaque bloc `handle <chemin> { … }` de premier niveau : (chemin, corps).

    :param chemin: une EXPRESSION — `/uploads/\\S*` les prend tous.
    """
    motif = rf"handle\s+({chemin})\s*\{{(.*?)\n\t\}}"
    return [(m.group(1), m.group(2)) for m in re.finditer(motif, contenu, re.S)]


def bloc_handle(contenu: str, chemin: str) -> str | None:
    """Le corps du bloc `handle <chemin>` (chemin LITTÉRAL), ou `None`.

    Un matcher nommé se passe par son nom : `bloc_handle(contenu, "@nom")`.
    """
    blocs = blocs_handle(contenu, re.escape(chemin))
    return blocs[0][1] if blocs else None


def chemins_du_matcher(contenu: str, nom: str) -> list[str] | None:
    """Les chemins d'un matcher nommé de premier niveau, `@nom path /a /b`, ou `None`."""
    trouve = re.search(rf"^\t{re.escape(nom)} path ((?:\S+ ?)+)$", contenu, re.M)
    return trouve.group(1).split() if trouve else None
