"""Ce qui, dans un courriel, est la SIGNATURE et non une pièce (#2388, #2515).

Extrait de `courriel_pieces_jointes.py` le 04/11/2026, qui passait 500 lignes :
la règle y est expliquée (« Ce qui n'est pas une pièce ») ; elle s'écrit ici.

Deux lectures, et deux moments :

- **au tri**, sans ouvrir aucune image : le type d'un fichier de signature
  (`TYPES_DE_SIGNATURE`), et la taille à laquelle le HTML AFFICHE une image
  intégrée (`_tailles_affichees`) — c'est du texte ;
- **à la retenue**, pour un expéditeur autorisé seulement : la taille réelle de
  l'image, mesurée hors du process (`images.dimensions`), jugée par
  `_image_de_signature`.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING

from app.utils.courriel_decodage import _charge

if TYPE_CHECKING:  # pragma: no cover - `courriel_pieces_jointes` importe ce module
    from app.utils.courriel_pieces_jointes import Piece

#: En deçà, sur son plus grand côté, une image est un élément de signature.
COTE_MIN_SIGNATURE = 300
#: En deçà, sur son PETIT côté, une image intégrée au corps est un bandeau ou un
#: logo de signature (#2515 : 501 × 146 px). Un document ou une photo n'est
#: jamais aussi plat.
COTE_MIN_BANDEAU = 200

#: Des fichiers que les clients de messagerie ajoutent d'eux-mêmes à la signature.
TYPES_DE_SIGNATURE = frozenset(
    {
        "application/pkcs7-signature",
        "application/x-pkcs7-signature",
        "application/pgp-signature",
        "application/pgp-keys",
        "text/vcard",
        "text/x-vcard",
        "text/directory",
    }
)


class _TaillesAffichees(HTMLParser):
    """Les `<img src="cid:…">` du corps, et la taille à laquelle il les AFFICHE.

    Lue dans le texte du HTML, sans ouvrir aucune image : permise au tri.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tailles: dict[str, tuple[int | None, int | None]] = {}

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): v or "" for k, v in attrs}
        src = a.get("src", "")
        if tag != "img" or not src.lower().startswith("cid:"):
            return
        style = dict(
            re.findall(
                r"(?<![\w-])(width|height)\s*:\s*([\d.]+\s*[a-z%]*)", a.get("style", ""), re.I
            )
        )
        self.tailles[_cid(src[4:])] = (
            _en_pixels(style.get("width") or a.get("width", "")),
            _en_pixels(style.get("height") or a.get("height", "")),
        )


#: Une mesure CSS ou HTML en pixels — le pouce vaut 96 px en CSS.
_UNITES = {"": 1.0, "px": 1.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4, "pt": 96 / 72}


def _en_pixels(mesure: str) -> int | None:
    trouve = re.fullmatch(r"\s*([\d.]+)\s*([a-z%]*)\s*", mesure or "", re.I)
    if not trouve or trouve.group(2).lower() not in _UNITES:
        return None  # un pourcentage, « auto » : rien ne se déduit
    try:
        return round(float(trouve.group(1)) * _UNITES[trouve.group(2).lower()])
    except ValueError:
        return None


def _cid(valeur: str) -> str:
    return valeur.strip().strip("<>").strip().lower()


def _tailles_affichees(propres) -> dict[str, tuple[int | None, int | None]]:
    lecteur = _TaillesAffichees()
    for partie in propres:
        if partie.get_content_type() == "text/html":
            lecteur.feed(_charge(partie))
    return lecteur.tailles


def _de_signature(type_: str) -> bool:
    """Un fichier que le client ajoute à la signature, reconnu à son type seul."""
    return type_ in TYPES_DE_SIGNATURE


def _petite(largeur: int | None, hauteur: int | None) -> bool:
    """Un côté sous `COTE_MIN_BANDEAU`, ou les deux connus sous `COTE_MIN_SIGNATURE`."""
    connus = [c for c in (largeur, hauteur) if c]
    return bool(connus) and (
        min(connus) < COTE_MIN_BANDEAU or (len(connus) == 2 and max(connus) < COTE_MIN_SIGNATURE)
    )


def _image_de_signature(piece: Piece, taille: tuple[int, int] | None) -> bool:
    """Un logo, un bandeau, une icône : la signature, et non une pièce.

    Toute image sous `COTE_MIN_SIGNATURE` sur son plus grand côté. Et pour une
    image INTÉGRÉE au corps — c'est ainsi que les clients posent une signature —
    un petit côté sous `COTE_MIN_BANDEAU`, ou un affichage déclaré aussi petit.
    """
    if taille is not None and max(taille) < COTE_MIN_SIGNATURE:
        return True
    if not piece.integree:
        return False
    return (taille is not None and min(taille) < COTE_MIN_BANDEAU) or (
        piece.affichee is not None and _petite(*piece.affichee)
    )
