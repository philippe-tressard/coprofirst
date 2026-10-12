"""Les conditions d'inscription d'une installation — un fichier par version (R0 #1876).

Un contrat d'engagements réciproques entre l'exploitant d'une installation et celui
de la référence, accepté par l'administrateur quand il valide l'inscription. La référence en
ARCHIVE, pour chaque installation, le texte exact accepté (`AcceptationConditions`).

## Les règles

1. **Une version publiée ne change plus** : sa preuve d'acceptation serait sinon un
   texte que personne n'a lu. Une rédaction nouvelle est un fichier `vN.md` neuf.
   🔒 `EMPREINTES` fige l'empreinte de chaque version, et
   `tests/test_registre_conditions.py` refuse un fichier qui ne la porte plus.
2. **La version en vigueur est la plus haute** ; l'installation déclare la version
   ET l'empreinte du texte qu'elle a montré, et la référence refuse un écart : on ne
   s'engage pas sur un texte que l'autre partie n'a pas.
3. Le texte vit ICI, dans le code de l'API, et non sous `docs/` : l'image de l'API ne
   contient que `api/`, et la référence doit pouvoir archiver ce qu'elle a fait accepter.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent

#: L'empreinte (SHA-256 des octets du fichier) de chaque version PUBLIÉE.
#: ⚠️ La v1 est un PROJET tant que #1876 (relecture juridique) n'est pas fermé :
#: elle peut encore changer, en mettant à jour cette ligne — jamais après la
#: première inscription réelle.
EMPREINTES: dict[int, str] = {
    1: "b203d53e0792f7151da675cd80487338c53b12025db065c9126aca9fcac41a52",
}


def versions() -> list[int]:
    """Les versions présentes dans le dossier, croissantes."""
    return sorted(
        int(m.group(1)) for f in DOSSIER.glob("v*.md") if (m := re.fullmatch(r"v(\d+)\.md", f.name))
    )


def texte(version: int) -> str:
    """Le texte d'une version, tel qu'il s'archive à l'acceptation."""
    return (DOSSIER / f"v{version}.md").read_text(encoding="utf-8")


def empreinte(version: int) -> str:
    """L'empreinte d'une version : SHA-256 de ses octets, en hexadécimal."""
    return hashlib.sha256((DOSSIER / f"v{version}.md").read_bytes()).hexdigest()


def version_en_vigueur() -> int:
    """La version qu'une inscription doit accepter : la plus haute."""
    return versions()[-1]
