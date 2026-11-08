"""La table des sections essentielles : le front et l'API disent la même chose (#2595).

Le front ne charge pas `GET /tickets/referentiels` : sa table se déclare dans
`saisie-affaire.ts`, comme les catégories dans `tickets-categories.ts`. Ce test les
compare, dans les deux sens, et vérifie que les identifiants sont ceux du cadre.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.utils.saisie_affaire import SECTIONS_DE_BASE, SECTIONS_ESSENTIELLES_PAR_CATEGORIE

_RACINE = Path(__file__).resolve().parents[2] / "front" / "src" / "lib"
_SAISIE = _RACINE / "saisie-affaire.ts"
_CADRE = _RACINE / "entites" / "types.ts"


def _sans_commentaires(texte: str) -> str:
    texte = re.sub(r"/\*.*?\*/", "", texte, flags=re.S)
    return re.sub(r"^\s*//.*$", "", texte, flags=re.M)


def _liste(bloc: str) -> tuple[str, ...]:
    return tuple(re.findall(r"'([a-z_]+)'", bloc))


def _base_du_front() -> tuple[str, ...]:
    source = _sans_commentaires(_SAISIE.read_text(encoding="utf-8"))
    m = re.search(r"export const SECTIONS_DE_BASE[^=]*=\s*\[(.*?)\];", source, re.S)
    assert m, "SECTIONS_DE_BASE introuvable dans saisie-affaire.ts : le motif a vieilli"
    return _liste(m.group(1))


def _table_du_front() -> dict[str, tuple[str, ...]]:
    source = _sans_commentaires(_SAISIE.read_text(encoding="utf-8"))
    m = re.search(
        r"export const SECTIONS_ESSENTIELLES_PAR_CATEGORIE[^=]*=\s*\{(.*?)\n\};", source, re.S
    )
    assert m, "SECTIONS_ESSENTIELLES_PAR_CATEGORIE introuvable : le motif a vieilli"
    return {
        cat: _liste(sections)
        for cat, sections in re.findall(r"([a-z_]+):\s*\[([^\]]*)\]", m.group(1))
    }


def _sections_du_cadre() -> set[str]:
    source = _sans_commentaires(_CADRE.read_text(encoding="utf-8"))
    m = re.search(r"export type IdSection\s*=(.*?);", source, re.S)
    assert m, "IdSection introuvable dans types.ts"
    return set(_liste(m.group(1)))


def test_le_motif_de_lecture_trouve_encore_quelque_chose():
    """Cas zéro : un relevé vide se lirait « tout concorde »."""
    assert len(_table_du_front()) >= 5
    assert len(_base_du_front()) >= 3
    assert len(_sections_du_cadre()) >= 10


def test_les_sections_de_base_sont_les_memes():
    assert _base_du_front() == SECTIONS_DE_BASE


def test_la_table_par_categorie_est_la_meme_des_deux_cotes():
    assert _table_du_front() == SECTIONS_ESSENTIELLES_PAR_CATEGORIE


def test_tous_les_identifiants_sont_ceux_du_cadre():
    cadre = _sections_du_cadre()
    utilises = set(SECTIONS_DE_BASE).union(*SECTIONS_ESSENTIELLES_PAR_CATEGORIE.values())
    assert utilises <= cadre, sorted(utilises - cadre)
