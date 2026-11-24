"""`Content-Disposition` s'écrit par UNE porte : `utils/en_tete_fichier` (#2985).

Un nom accentué partait en latin-1 dans l'en-tête (« ma-résidence ») : six
écritures `f'attachment; filename="{nom}"'`, aucune porte. Ce fichier tient la
forme de la porte (RFC 6266) et refuse la clé écrite ailleurs dans `app/`.

La clé se cherche dans l'AST, comme chaîne littérale égale à l'en-tête (casse
ignorée) : une docstring qui en parle n'est pas une chaîne égale, et un
`add_header("Content-Disposition", …)` écrit en ligne serait vu aussi.
"""

from __future__ import annotations

import ast

import pytest

from app.utils.en_tete_fichier import CLE, en_tete_fichier, valeur_disposition
from tests.aides_sources import chaines_du_code, modules_app

PORTE = "utils/en_tete_fichier.py"


def test_un_nom_ascii_garde_son_en_tete_d_avant():
    assert valeur_disposition("suivi-des-affaires-2026-11-24.pdf") == (
        'attachment; filename="suivi-des-affaires-2026-11-24.pdf"'
    )
    assert valeur_disposition("a.pdf", mode="inline") == 'inline; filename="a.pdf"'


def test_un_nom_accentue_part_en_ascii_et_en_utf8():
    valeur = valeur_disposition("manuel-ma-résidence.pdf", mode="inline")
    assert valeur == (
        "inline; filename=\"manuel-ma-residence.pdf\"; filename*=UTF-8''manuel-ma-r%C3%A9sidence.pdf"
    )
    valeur.encode("ascii")  # un en-tête HTTP n'admet que l'ASCII


def test_un_caractere_sans_equivalent_latin_devient_un_tiret_bas():
    assert valeur_disposition("plan 漢.pdf").startswith(
        'attachment; filename="plan _.pdf"; filename*='
    )


@pytest.mark.parametrize("piege", ['a"b.pdf', "a\r\nX-Pirate: 1.pdf", "a\\b.pdf", "a\x00b.pdf"])
def test_guillemet_et_saut_de_ligne_ne_cassent_pas_l_en_tete(piege):
    valeur = valeur_disposition(piege)
    assert valeur.count('"') == 2, valeur
    assert not any(c in valeur for c in "\r\n\\\x00"), valeur


def test_le_dictionnaire_porte_la_cle():
    assert en_tete_fichier("a.pdf") == {"Content-Disposition": 'attachment; filename="a.pdf"'}


def ecritures_hors_porte(arbre: ast.AST) -> list[int]:
    """Les lignes où une chaîne littérale du code est la clé de l'en-tête. PURE."""
    return [
        c.lineno
        for c in chaines_du_code(arbre)
        if isinstance(c.value, str) and c.value.lower() == CLE.lower()
    ]


def test_le_garde_voit_l_ecriture_en_ligne():
    fautif = 'def f(nom):\n    return {"Content-Disposition": f\'attachment; filename="{nom}"\'}\n'
    assert ecritures_hors_porte(ast.parse(fautif)) == [2]
    assert ecritures_hors_porte(ast.parse('part.add_header("content-disposition", "inline")')) == [
        1
    ]
    assert ecritures_hors_porte(ast.parse('"""Écrit le Content-Disposition."""')) == []


def test_aucune_cle_content_disposition_hors_de_la_porte():
    fautes = [
        f"{m.rel}:{ligne}"
        for m in modules_app(minimum=100)
        if m.rel != PORTE
        for ligne in ecritures_hors_porte(m.arbre)
    ]
    assert not fautes, (
        "Content-Disposition écrit hors de `utils/en_tete_fichier` — passer par "
        f"`en_tete_fichier(nom)` (un nom accentué partirait en latin-1, #2985) : {fautes}"
    )
