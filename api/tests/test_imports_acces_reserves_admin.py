"""Les imports de badges et de télécommandes sont réservés à l'administrateur (#3012).

## Pourquoi (décision du 23/11/2026, par délégation de Philippe, sur #2907)

Vingt routes `/acces/admin/imports*` prenaient `require_cs_or_admin` alors que le seul écran
qui appelle les IMPORTS est l'atelier d'administration (Admin › Imports),
fermé à tout compte qui n'est ni administrateur ni opérateur. L'API s'aligne sur l'écran :
moindre privilège, aucun écran perdu (les apps ne les appellent pas). Dix-neuf passent à
`require_admin` ; la liste des lots où choisir celui d'un badge reste au conseil, que l'Espace
CS lit aussi (relevé le 24/11/2026, le ticket ne l'avait pas vu).

## Ce que ce fichier tient

Toute opération MONTÉE dont le chemin commence par `/acces/admin/imports` prend
`require_admin`, hors des routes déclarées `OUVERTES_AU_CONSEIL` —
lu sur les dépendances que FastAPI lui résout, par l'objet de `deps.py`. Une route neuve
sous ce préfixe, ou une dépendance relâchée, échoue ici.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.auth import deps
from app.main import app
from tests.aides_sources import operations_montees

PREFIXES = ("/acces/admin/imports",)

#: Sous ce préfixe, ce qui n'est PAS un import, et pourquoi la route reste ouverte au
#: conseil. Vérifié dans les deux sens : une entrée sans route, ou qui prend désormais
#: `require_admin`, échoue.
OUVERTES_AU_CONSEIL = {
    ("GET", "/acces/admin/imports-lots"): "la liste des lots où choisir celui d'un badge : "
    "l'Espace CS (`BadgesCopropriete`) la lit aussi — la réserver casserait son écran",
}

#: Le relevé du 24/11/2026 : 22 opérations montées sous ce préfixe.
PLANCHER = 22


def _operations_d_import():
    return [
        (methode, chemin, route)
        for methode, chemin, route in operations_montees(app)
        if methode != "HEAD" and chemin.startswith(PREFIXES) and isinstance(route, APIRoute)
    ]


def _prend_require_admin(route: APIRoute) -> bool:
    return any(d.call is deps.require_admin for d in route.dependant.dependencies)


def test_le_releve_voit_les_imports():
    assert len(_operations_d_import()) >= PLANCHER, "les imports d'accès ont perdu leur portée"


def test_chaque_import_d_acces_est_reserve_a_l_administrateur():
    relachees = sorted(
        f"{methode} {chemin}"
        for methode, chemin, route in _operations_d_import()
        if not _prend_require_admin(route) and (methode, chemin) not in OUVERTES_AU_CONSEIL
    )
    assert not relachees, (
        "Import d'accès ouvert au-delà de l'administrateur — l'écran n'existe que dans "
        "Admin (#3012) :\n  " + "\n  ".join(relachees)
    )


def test_les_routes_ouvertes_au_conseil_servent_encore():
    vues = {(m, c): r for m, c, r in _operations_d_import()}
    for cle in OUVERTES_AU_CONSEIL:
        assert cle in vues, f"{cle} a disparu : retirer sa déclaration"
        assert not _prend_require_admin(vues[cle]), f"{cle} est réservée : retirer sa déclaration"
