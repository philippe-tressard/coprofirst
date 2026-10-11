"""Aucun couple (méthode, chemin) n'est déclaré deux fois (#876 → 18/09/2026).

## Le défaut que ce contrôle vient d'attraper

`POST /admin/telemetry/agreger` existait dans **deux** sous-routeurs montés sur
le même préfixe : `admin/communications.py` et `admin/exploitation.py`. Le
second l'avait ajouté pour que le bouton de `TachesPlanifiees` cesse de rendre
404 — sans voir que le premier le déclarait déjà.

🔴 Starlette retient la **première** route qui correspond : le gestionnaire de
`communications` n'a donc plus jamais répondu. Rien ne le signalait — pas
d'erreur au démarrage, pas d'avertissement, et le code mort restait lisible et
plausible, avec son propre message de réponse.

⚠️ **Le schéma OpenAPI disait même le contraire.** Sa génération écrase l'entrée
d'un chemin par la DERNIÈRE rencontrée : `/admin/telemetry/agreger` y était donc
documenté par le gestionnaire qui ne s'exécute pas. Un schéma qui décrit autre
chose que ce qui répond est pire qu'un schéma absent — c'est pourquoi ce
contrôle ne lit PAS l'OpenAPI, qui dédoublonne et rendrait donc toujours vert.

## Comment il regarde

Il aplatit les routeurs **tels qu'ils sont montés**, en suivant
`original_router` et les préfixes. C'est la seule vue qui montre les deux
déclarations d'un même chemin : `app.routes` n'expose que des nœuds de routeurs
inclus, et `app.openapi()` a déjà choisi.
"""

from __future__ import annotations

import collections

import pytest

from app.main import app
from tests.aides_sources import operations_montees


@pytest.fixture(scope="module")
def operations() -> list[tuple[str, str, str]]:
    return [(m, c, r.name) for m, c, r in operations_montees(app)]


def test_cas_zero_le_balayage_voit_bien_l_application(operations):
    """🔴 Sans routes lues, le test suivant serait vert sur une application vide.

    Le compte n'est pas une valeur figée — il grandit avec le produit — mais un
    ordre de grandeur : `app.routes` rendait UNE route avec un parcours naïf, et
    un contrôle bâti dessus n'aurait rien mesuré du tout.
    """
    assert len(operations) > 200, (
        f"{len(operations)} opération(s) lues : le parcours ne descend plus dans "
        "les sous-routeurs, et ce fichier ne mesure plus rien."
    )
    chemins = {c for _m, c, _n in operations}
    assert any(c.startswith("/admin/") for c in chemins), "les routeurs admin manquent"
    assert any(c.startswith("/auth/") for c in chemins), "les routeurs d'auth manquent"


def test_aucune_route_n_est_declaree_deux_fois(operations):
    """Une route masquée est du code mort que rien ne signale.

    Elle se lit, elle se maintient, elle passe en revue — et elle ne répond
    jamais. Pire : c'est souvent la PLUS RÉCENTE qui est masquée, parce qu'on
    ajoute à la fin.
    """
    compte = collections.Counter((m, c) for m, c, _n in operations)
    doublons = {
        cle: [nom for m, c, nom in operations if (m, c) == cle]
        for cle, n in compte.items()
        if n > 1
    }
    assert not doublons, (
        "Ces routes sont déclarées plusieurs fois — seule la PREMIÈRE répond, "
        f"les autres sont du code mort : {doublons}. Retirer la déclaration "
        "superflue, ou donner un chemin distinct à ce qui est un geste distinct."
    )
