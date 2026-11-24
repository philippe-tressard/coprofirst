"""L'en-tête `Content-Disposition` d'un fichier servi ou joint — écrit ici, une fois (#2985).

Six endroits écrivaient `f'attachment; filename="{nom}"'` chacun de son côté.
Le nom du manuel porte celui de la résidence, « Ma Résidence » par défaut :
l'en-tête partait avec un `é`, que Starlette encode en latin-1 (octet `0xE9`).
Un en-tête HTTP n'admet que l'ASCII ; `TestClient` levait `UnicodeDecodeError`
en le lisant, et chaque navigateur l'interprétait à sa façon.

## La forme (RFC 6266, §4.3)

- `filename="<repli ASCII>"` — lu par tous les clients : accents retirés
  (« é » → « e »), tout autre caractère hors ASCII remplacé par `_` ;
- `filename*=UTF-8''<nom encodé>` — le vrai nom, préféré par les clients qui le
  comprennent. Ajouté **seulement** quand le repli diffère du nom : un nom déjà
  ASCII garde son en-tête d'avant, octet pour octet.

Guillemets, barres obliques inverses, retours chariot, sauts de ligne et autres
caractères de contrôle sont neutralisés dans les deux formes : ils fermeraient
la chaîne ou ouvriraient un second en-tête.

La même valeur sert une pièce jointe de courriel : `fastapi-mail` la pose par
`add_header`, et `filename*` est la forme de la RFC 2231, que MIME lit aussi.

🔒 `tests/test_en_tete_fichier.py` : la forme, et le refus d'une clé
`Content-Disposition` écrite ailleurs dans `app/`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal
from urllib.parse import quote

CLE = "Content-Disposition"

#: Ce qui casserait l'en-tête : la fin de la chaîne, l'échappement, une ligne neuve.
_DANGEREUX = re.compile(r'["\\\x00-\x1f\x7f]')


def _repli_ascii(nom: str) -> str:
    """Le nom en ASCII : la lettre sans son accent, un `_` pour ce qui n'a pas d'équivalent."""
    return "".join(
        "" if unicodedata.combining(c) else (c if c.isascii() else "_")
        for c in unicodedata.normalize("NFKD", nom)
    )


def valeur_disposition(nom: str, *, mode: Literal["attachment", "inline"] = "attachment") -> str:
    """La valeur de l'en-tête pour un fichier nommé `nom`. PURE."""
    propre = _DANGEREUX.sub("_", nom)
    repli = _repli_ascii(propre)
    valeur = f'{mode}; filename="{repli}"'
    if repli != propre:
        valeur += f"; filename*=UTF-8''{quote(propre, safe='')}"
    return valeur


def en_tete_fichier(
    nom: str, *, mode: Literal["attachment", "inline"] = "attachment"
) -> dict[str, str]:
    """`{"Content-Disposition": …}`, prêt pour `headers=` d'une réponse ou d'une pièce jointe."""
    return {CLE: valeur_disposition(nom, mode=mode)}
