"""Une route à chemin littéral ne doit pas être avalée par un joker (#1151).

## Le blocage du 22/09/2026, signalé à l'écran

> « Blocage : j'ai une erreur » — *Type invalide : vigik ou telecommande*

Écran **Import télécommandes**, bouton Enregistrer d'une ligne à lier. Le front
appelle `PATCH /acces/admin/imports/{id}`. Or `routers/acces/parc` déclare
`PATCH /admin/{type_cle}/{objet_id}`, et son routeur est inclus **en premier** :
FastAPI retient la première route qui correspond, donc `type_cle="imports"`, et
la garde d'entrée refuse en 422. Le geste était mort pour les deux imports.

## 🔴 Le fichier SAVAIT — pour les GET seulement

`routers/acces/__init__.py` explique en vingt lignes pourquoi `parc` passe en
premier : *« un `{type_cle}` avalerait les listes d'import »*. C'est vrai des
`GET /admin/imports` et `/admin/imports-vigik`, qui sont des chemins d'un seul
segment ; c'est **faux** des `PATCH /admin/imports/{id}`, qui ont exactement la
forme du joker à deux segments — et l'ordre choisi les tue.

⚠️ Une note qui explique un piège au singulier laisse croire qu'il n'y en a
qu'un. C'est ce qui a fait tenir la conclusion (« parc avant ») alors que sa
prémisse ne couvrait que la moitié des routes.

## Ce que ce test mesure, et ce qu'il ne mesure pas

Il lit les **sous-routeurs** de `acces` et l'ordre dans lequel `__init__` les
inclut, puis vérifie qu'aucune route n'est interceptée par une route déclarée
avant elle. C'est l'ordre qui décide à l'exécution.

⚠️ Il ne monte pas l'application entière : importée seule, elle n'expose qu'une
route (le montage dépend du démarrage). Ce test ne couvre donc QUE le module
`acces` — celui où le défaut s'est produit, et le seul du dépôt à empiler
quatre sous-routeurs sur le même préfixe. Le dire plutôt que de laisser croire
à une garantie générale (`standards/04` §12).
"""

from __future__ import annotations

import re

from fastapi.routing import APIRoute

from app.routers.acces import imports_telecommandes, imports_vigik, parc, portes, resident

#: L'ordre d'inclusion réel, lu dans `routers/acces/__init__.py`.
#:
#: ⚠️ Il est recopié ici, et c'est la seule solution : `acces.router.routes`
#: rend une liste incomplète à l'import (les sous-routeurs ne sont pas encore
#: peuplés quand `include_router` les copie). Le cas zéro ci-dessous compare
#: donc cette liste au FICHIER, pour qu'une divergence échoue.
ORDRE = [
    ("resident", resident),
    #  🔴 Les imports AVANT `parc` depuis le 22/09/2026 : son joker
    #  `/admin/{type_cle}/{objet_id}` avalait `PATCH /admin/imports/{id}`.
    ("imports_vigik", imports_vigik),
    ("imports_telecommandes", imports_telecommandes),
    #  Les lectures de ce qu'un badge ouvre (#2217) : chemins fixes à un segment,
    #  avant le joker `/admin/{type_cle}` du parc.
    ("portes", portes),
    ("parc", parc),
]

PARAM = re.compile(r"^\{[^}]+\}$")


def test_l_ordre_declare_ici_est_celui_du_fichier():
    """🔴 Cas zéro : une liste recopiée diverge, et le test mesurerait un autre
    programme que celui qui tourne."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "app" / "routers" / "acces" / "__init__.py"
    ).read_text(encoding="utf-8")
    trouves = re.findall(r"router\.include_router\((\w+)\.router\)", source)
    assert trouves == [nom for nom, _ in ORDRE], (
        f"l'ordre d'inclusion a changé — fichier : {trouves}, test : {[n for n, _ in ORDRE]}.\n"
        "Mettre ORDRE à jour, puis relire ce que le nouvel ordre masque."
    )


def _routes() -> list[tuple[str, APIRoute]]:
    return [
        (nom, r) for nom, module in ORDRE for r in module.router.routes if isinstance(r, APIRoute)
    ]


def test_le_controle_lit_bien_des_routes():
    """Sans routes, tout ce qui suit serait vert sans rien mesurer."""
    routes = _routes()
    assert len(routes) > 20, (
        f"seulement {len(routes)} route(s) lues dans le module accès : le contrôle ne mesure rien."
    )


def _interceptee_par(route: APIRoute, avant: list[tuple[str, APIRoute]]):
    """La première route, parmi celles déclarées AVANT, qui intercepte celle-ci.

    Elle intercepte quand elle a le même nombre de segments, une méthode en
    commun, et qu'elle est STRICTEMENT plus permissive : un paramètre là où
    l'autre porte un littéral, et rien d'incompatible ailleurs.
    """
    cible = route.path.strip("/").split("/")
    for nom, autre in avant:
        if autre is route or not (autre.methods & route.methods):
            continue
        sien = autre.path.strip("/").split("/")
        if len(sien) != len(cible):
            continue
        plus_permissif = False
        for s, c in zip(sien, cible):
            if s == c:
                continue
            if PARAM.match(s):
                #  ⚠️ Deux paramètres au même rang sont COMPATIBLES, même de noms
                #  différents : `{type_cle}/{objet_id}` accepte tout ce que
                #  `imports/{import_id}` accepte. Ma première rédaction cassait
                #  dès que les noms différaient, et le contrôle passait au vert
                #  sur le défaut même qu'il existe pour attraper.
                if not PARAM.match(c):
                    plus_permissif = True
                continue
            break
        else:
            if plus_permissif:
                return nom, autre
    return None


def test_aucune_route_n_est_masquee_par_un_joker_declare_avant():
    """🔴 Le défaut vécu : `PATCH /admin/imports/{id}` avalé par `{type_cle}`."""
    routes = _routes()
    fautes = []
    for i, (nom, route) in enumerate(routes):
        vol = _interceptee_par(route, routes[:i])
        if vol is not None:
            fautes.append(
                f"{nom} · {sorted(route.methods)} {route.path}\n"
                f"      interceptée par  {vol[0]} · {sorted(vol[1].methods)} {vol[1].path}"
            )
    assert not fautes, (
        f"{len(fautes)} route(s) ne seront JAMAIS atteintes — une route incluse "
        "avant elles porte un paramètre là où elles portent un segment fixe, et "
        "FastAPI retient la première correspondance :\n\n  "
        + "\n\n  ".join(fautes)
        + "\n\n  → inclure le sous-routeur le plus SPÉCIFIQUE en premier.\n"
    )
