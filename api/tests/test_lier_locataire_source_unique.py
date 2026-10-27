"""Un lien `locataire` ne s'écrit que par `rattachement_locataire.lier_locataire` (#2267).

Quatre chemins posaient ce lien, et un seul remettait les badges du lot : le
locataire rattaché par les trois autres avait son lot sans Vigik ni
télécommande, et l'administration les lui remettait à la main.

Le contrôle lit l'AST de `app/` : un `UserLot(...)` dont le `type_lien` est
`TypeLien.locataire` hors de la porte est refusé. ⚠️ Il ne voit pas un type de
lien porté par une VARIABLE : `resolution_lots` et `auto_match_service` se
bornent aux types copropriétaires (`TYPES_COPROPRIETAIRES`), et la résolution
d'un import par l'administration aiguille le locataire vers la porte — c'est
`test_rattachement_locataire.py` qui l'éprouve.
"""

from __future__ import annotations

import ast

from tests.aides_sources import modules_app

PORTE = "utils/rattachement_locataire.py"


def _liens_locataire(arbre: ast.AST) -> list[int]:
    lignes = []
    for noeud in ast.walk(arbre):
        if not (isinstance(noeud, ast.Call) and getattr(noeud.func, "id", None) == "UserLot"):
            continue
        for kw in noeud.keywords:
            v = kw.value
            if kw.arg == "type_lien" and isinstance(v, ast.Attribute) and v.attr == "locataire":
                lignes.append(noeud.lineno)
    return lignes


def test_la_porte_existe_et_ecrit_le_lien():
    (porte,) = [m for m in modules_app("utils") if m.rel == PORTE]
    assert _liens_locataire(ast.parse(porte.source)), "témoin mort"


def test_aucun_lien_locataire_hors_de_la_porte():
    hors = [
        f"{m.rel}:{ligne}"
        for m in modules_app()
        if m.rel != PORTE
        for ligne in _liens_locataire(ast.parse(m.source))
    ]
    assert hors == [], f"lien locataire écrit hors de lier_locataire : {hors}"
