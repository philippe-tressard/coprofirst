"""La signature d'une installation se vérifie à UNE porte : `registre/gardes.exiger_signature`.

## Pourquoi (#2953, audit du 23/11/2026)

Les trois envois qu'une installation signe — inscription et bail
(`registre/routeur._lire_signee`), rapport nocturne (`registre/routeur.recevoir_rapport`),
notification relayée (`registre/relais.relayer`) — écrivaient chacun leurs gardes :
taille, contrat, version, signature, mêmes messages. L'en-tête du relais disait ces
gardes « APPELÉES, jamais recopiées » ; il les recopiait. Tant que les copies
concordaient, rien n'était exposé — mais une garde qui apprend quelque chose (un
plafond, une forme de clé) devait l'apprendre à trois endroits.

## Ce que ce fichier tient

1. `signature.verifier` n'est appelée que par ses appelants déclarés (`APPELANTS`) —
   la porte des envois, et le constat du bail chez l'installation, qui vérifie l'AUTRE
   sens (la clé de la référence) ;
2. le refus 401 n'est écrit qu'à la porte ;
3. chaque route déclarée sous `app/registre/` atteint la porte, directement ou par une
   fonction de son module — une route neuve du registre qui l'oublie échoue ici.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.aides_sources import PLANCHER_APP, Module, modules_app

#: (module relatif à `app/`, fonction) — les seuls appelants de `signature.verifier`.
APPELANTS = {
    #  La porte : la signature d'une installation sur les octets qu'elle envoie.
    ("registre/gardes.py", "exiger_signature"),
    #  Chez l'installation : le bail que la référence a signé de SA clé (R2).
    ("inscription/constat.py", "bail_valide"),
}

PORTE = "exiger_signature"
REFUS = "Signature de l'installation absente ou invalide"
_VERBES = {"get", "post", "put", "patch", "delete"}


def _app() -> tuple[Module, ...]:
    return modules_app(minimum=PLANCHER_APP)


def appelants_de_verifier(modules) -> set[tuple[str, str]]:
    """(module, fonction englobante) de chaque appel à `signature.verifier`."""
    trouves = set()
    for module in modules:
        for fonction in ast.walk(module.arbre):
            if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for noeud in ast.walk(fonction):
                if (
                    isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Attribute)
                    and noeud.func.attr == "verifier"
                    and getattr(noeud.func.value, "id", None) == "signature"
                ):
                    trouves.add((module.rel, fonction.name))
    return trouves


def routes_sans_porte(modules) -> list[str]:
    """Les routes d'un module qui n'atteignent pas la porte, même par une fonction du module."""
    manquantes = []
    for module in modules:
        fonctions = {
            n.name: n
            for n in ast.walk(module.arbre)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        def appels(nom: str) -> set[str]:
            return {
                getattr(c.func, "id", None) or getattr(c.func, "attr", None)
                for c in ast.walk(fonctions[nom])
                if isinstance(c, ast.Call)
            } - {None}

        for nom, fonction in fonctions.items():
            est_route = any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and d.func.attr in _VERBES
                for d in fonction.decorator_list
            )
            if not est_route:
                continue
            vus, a_voir = set(), [nom]
            while a_voir:
                courant = a_voir.pop()
                if courant in vus:
                    continue
                vus.add(courant)
                suivants = appels(courant)
                if PORTE in suivants:
                    break
                a_voir.extend(s for s in suivants if s in fonctions)
            else:
                manquantes.append(f"{module.rel}::{nom}")
    return manquantes


def _registre() -> list[Module]:
    return [m for m in _app() if m.rel.startswith("registre/")]


def test_signature_verifier_n_a_que_ses_appelants_declares():
    trouves = appelants_de_verifier(_app())
    assert trouves == APPELANTS, (
        "`signature.verifier` est appelée hors de ses appelants déclarés — la vérification "
        "d'une installation passe par `registre/gardes.exiger_signature` :\n"
        f"  en trop : {sorted(trouves - APPELANTS)}\n  disparus : {sorted(APPELANTS - trouves)}"
    )


def test_le_refus_de_signature_n_est_ecrit_qu_a_la_porte():
    ecrits = sorted(
        m.rel
        for m in _app()
        for n in ast.walk(m.arbre)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and REFUS in n.value
    )
    assert ecrits == ["registre/gardes.py"], f"le refus 401 est écrit ici : {ecrits}"


def test_chaque_route_du_registre_atteint_la_porte():
    modules = _registre()
    assert len(modules) >= 10, "le registre a perdu sa portée"
    nb_routes = sum(
        1
        for m in modules
        for f in ast.walk(m.arbre)
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            isinstance(d, ast.Call) and getattr(d.func, "attr", None) in _VERBES
            for d in f.decorator_list
        )
    )
    #  Cas zéro : inscription, bail, rapport, relais.
    assert nb_routes >= 4, f"{nb_routes} route(s) relevée(s) sous registre/ : portée perdue"
    assert not routes_sans_porte(modules), (
        "Route(s) du registre qui ne vérifient pas la signature de l'installation :\n  "
        + "\n  ".join(routes_sans_porte(modules))
    )


def _forge(source: str) -> list[Module]:
    return [Module(chemin=Path("forge.py"), rel="registre/forge.py", source=source)]


def test_temoins_les_trois_detecteurs_voient_la_faute():
    """Le contrôle refuse ce qu'il annonce : une vérification recopiée, une route sans porte."""
    recopie = _forge(
        "def recevoir(request):\n"
        "    if not signature.verifier(cle, corps, entete):\n"
        "        raise HTTPException(401)\n"
    )
    assert appelants_de_verifier(recopie) == {("registre/forge.py", "recevoir")}

    sans_porte = _forge(
        "@router.post('/x')\nasync def x(request):\n    return _aide(request)\n"
        "def _aide(request):\n    return 1\n"
    )
    assert routes_sans_porte(sans_porte) == ["registre/forge.py::x"]

    par_une_aide = _forge(
        "@router.post('/x')\nasync def x(request):\n    return _aide(request)\n"
        "def _aide(request):\n    exiger_signature(cle, corps, request)\n"
    )
    assert routes_sans_porte(par_une_aide) == []
