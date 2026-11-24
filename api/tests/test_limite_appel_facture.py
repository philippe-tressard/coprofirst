"""Un point d'entrée qui FACTURE est borné — sans exception (#1299).

## Pourquoi

Un appel au fournisseur d'IA (`utils.llm.demander`) se lit sur une facture.
Partout ailleurs, une requête en trop coûte du CPU ; ici un double-clic, une
tempête de réessais ou un onglet qui se recharge se paient. La limite sur la
synthèse de contrat avait été écrite le 15/09/2026, sur une branche jamais
fusionnée : `main` n'en portait aucune, sur aucun des trois points d'entrée.

## Ce que ce test mesure

1. toute ROUTE qui atteint `demander` — relevée dans le code par
   `aides_sources.routes_qui_atteignent`, aides résolues par leurs imports, cinq niveaux ;
2. elle porte `@limiter.limit(LIMITE_APPEL_FACTURE)` — ou la limite déclarée pour elle
   dans `LIMITES_ADMISES`, avec sa raison —, sous son décorateur de route, et reçoit une
   `request` (sans elle, slowapi lève au premier appel).

## La portée (#3005, 24/11/2026)

Le relevé s'écrivait ici, à DEUX niveaux d'appel : le classement d'un courriel reçu, qui
atteint le modèle par cinq (classement, versement au fil, mise en forme, porte de lecture
du courriel, `demander`), n'avait aucune limite. Le relevé commun le voit.
"""

from __future__ import annotations

import ast

from tests.aides_sources import module_app, routes_qui_atteignent

_CIBLE = "demander"
_LIMITE = "LIMITE_APPEL_FACTURE"

#: Les routes facturées qui portent une AUTRE limite, et pourquoi. Vérifié dans les deux
#: sens : une entrée qui n'est plus une route facturée échoue.
LIMITES_ADMISES = {
    ("routers/courriels_affaires.py", "creer"): (
        "LIMITE_CLASSEMENT_COURRIEL",
        "le classement à la main d'un courriel reçu : une décision du conseil par message, "
        "qui n'appelle le modèle que si l'usage est activé — la limite des appels facturés "
        "freinerait un tri de plusieurs messages d'affilée (aucune régression, 24/11/2026)",
    ),
    ("routers/courriels_affaires.py", "rattacher"): (
        "LIMITE_CLASSEMENT_COURRIEL",
        "idem : verser un message reçu au fil d'une affaire ouverte",
    ),
}


def routes_facturees() -> dict[str, ast.AST]:
    trouvees = {}
    for rel, nom in routes_qui_atteignent({_CIBLE}):
        fonction = next(
            n
            for n in module_app(rel).arbre.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == nom
        )
        trouvees[f"{rel}::{nom}"] = fonction
    return trouvees


def test_toute_route_facturee_est_bornee():
    routes = routes_facturees()
    assert routes, "aucune route n'appelle le fournisseur d'IA — le contrôle ne mesure rien"
    fautes = []
    for nom, f in routes.items():
        rel, fonction = nom.split("::")
        attendue = LIMITES_ADMISES.get((rel, fonction), (_LIMITE, ""))[0]
        decores = [ast.unparse(d) for d in f.decorator_list]
        limites = [i for i, d in enumerate(decores) if "limiter.limit" in d]
        if not limites or attendue not in decores[limites[0]]:
            fautes.append(f"{nom} : pas de @limiter.limit({attendue})")
            continue
        if limites[0] < min(i for i, d in enumerate(decores) if "router." in d):
            fautes.append(f"{nom} : @limiter.limit posé AU-DESSUS de la route (sans effet)")
        if "request" not in [a.arg for a in f.args.args]:
            fautes.append(f"{nom} : limitée sans paramètre `request`")
    assert not fautes, "Appel facturé non borné :\n  " + "\n  ".join(fautes)


def test_les_limites_admises_servent_encore():
    facturees = {tuple(n.split("::")) for n in routes_facturees()}
    perimees = sorted(set(LIMITES_ADMISES) - facturees)
    assert not perimees, f"limites admises pour des routes qui ne facturent plus : {perimees}"


def test_les_routes_connues_sont_vues():
    """Le relevé retrouve les trois points d'entrée facturés du 25/09/2026, et le
    classement d'un courriel (#3005) — cinq niveaux d'appel sous la route."""
    noms = {n.split("::")[1] for n in routes_facturees()}
    assert {"proposer_synthese", "proposer_description", "llm_test", "creer", "rattacher"} <= noms
