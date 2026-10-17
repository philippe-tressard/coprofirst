"""Un texte ramené à un SLUG ASCII : minuscules, chiffres et tirets — écrit une fois.

`Août à l'Étang` → `aout-a-l-etang`. Les accents sont translittérés, tout le reste
(espaces, ponctuation, apostrophes, `_`) devient un tiret, jamais deux de suite ni
aux bords. Deux lecteurs, qui demandent la même chose pour deux raisons :

- le nom d'un fichier proposé au téléchargement (`utils/annonce_hall.nom_fichier`) —
  il traverse SMTP et des systèmes de fichiers variés ;
- l'alias d'une copropriété dans une installation commune
  (`installation_commune/alias.py`, #1894) — il devient un nom d'hôte, où seuls les
  lettres, les chiffres et le tiret sont admis (`_` y est interdit).
"""

from __future__ import annotations

import re
import unicodedata


def en_slug(texte: str) -> str:
    """Le slug de `texte` ; vide s'il ne contient ni lettre ni chiffre."""
    ascii_seul = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", ascii_seul).strip("-").lower()
