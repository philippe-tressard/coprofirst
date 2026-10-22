"""La synthèse ne choisit pas ses affaires par catégorie ; le carnet, si (#1643).

Arbitré le 03/10/2026 : « uniquement les affaires du carnet sont éligibles » —
remplacé le 21/10/2026 : **toute affaire close** reçoit sa synthèse (une
question close au point CS / Syndic n'en avait pas, lu comme une anomalie).
Le carnet ne range toujours que les catégories du bâti, et c'est sa règle
(`carnet_entretien` : `est_du_bati`, `contribue_au_carnet`) qui fait les
moyennes de son bilan (`synthese_affaire/agregats`).

Ce contrôle lit l'AST de `app/` :

1. `CATEGORIES_BATI` n'est lu que dans `utils/carnet_entretien.py` ;
2. le paquet `utils/synthese_affaire/` ne nomme aucune catégorie
   (`CategorieTicket`) ; seul `agregats` lit la règle du carnet ;
3. une affaire close d'une catégorie hors du bâti peut être produite.
"""

from __future__ import annotations

import ast

from tests.aides_sources import module_app, modules_app

SOURCE = "utils/carnet_entretien.py"
PAQUET = "utils/synthese_affaire"


def _noms(arbre: ast.AST) -> set[str]:
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name):
            noms.add(noeud.id)
        elif isinstance(noeud, ast.Attribute):
            noms.add(noeud.attr)
        elif isinstance(noeud, ast.alias):
            noms.add(noeud.asname or noeud.name.rsplit(".", 1)[-1])
        elif isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            noms.add(noeud.name)
    return noms


def test_cas_zero_la_source_porte_la_regle():
    noms = _noms(module_app(SOURCE).arbre)
    assert {"CATEGORIES_BATI", "est_du_bati", "contribue_au_carnet"} <= noms


def test_categories_bati_ne_se_lit_que_dans_le_carnet():
    fautifs = [
        m.rel for m in modules_app() if m.rel != SOURCE and "CATEGORIES_BATI" in _noms(m.arbre)
    ]
    assert not fautifs, (
        "`CATEGORIES_BATI` lu hors du carnet — passer par `est_du_bati` ou "
        f"`contribue_au_carnet` : {fautifs}"
    )


def test_la_synthese_ne_nomme_aucune_categorie_et_seul_le_bilan_lit_le_carnet():
    modules = modules_app(PAQUET, minimum=5)
    fautifs = [m.rel for m in modules if "CategorieTicket" in _noms(m.arbre)]
    assert not fautifs, f"la synthèse nomme des catégories elle-même : {fautifs}"
    appels = [m.rel for m in modules if "contribue_au_carnet" in _noms(m.arbre)]
    assert appels == [f"{PAQUET}/agregats.py"], (
        "la règle du carnet ne fait que les moyennes du bilan ; l'éligibilité d'une "
        f"synthèse ne la lit plus (21/10/2026) : {appels}"
    )


def test_toute_affaire_close_peut_etre_produite():
    from datetime import datetime

    from app.models.tickets import Ticket
    from app.utils.synthese_affaire.production import peut_etre_produite

    for categorie in ("question", "nuisance", "acces_accueil", "panne"):
        t = Ticket(numero="X", titre="x", categorie=categorie, statut="résolu")
        t.ferme_le = datetime(2026, 10, 21, 4, 4)
        assert peut_etre_produite(t), categorie
    assert not peut_etre_produite(Ticket(numero="Y", titre="y", statut="en_cours"))
