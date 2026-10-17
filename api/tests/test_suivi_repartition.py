"""La répartition croisée du Suivi des affaires et le mode entretien (#2043).

Ce qui est tenu :
- **où se compte une affaire** : un bâtiment → sa ligne et sa tranche ; plusieurs
  → la ligne de CHACUN, mais une seule tranche « Plusieurs bâtiments » dans sa
  catégorie (une barre ne compte jamais deux fois une affaire) ; aucun → la
  ligne et la tranche de la racine ;
- **l'ordre** : la racine en tête des bâtiments, les tranches dans l'ordre fixe
  des catégories et des bâtiments (une couleur suit l'entité, jamais son rang) ;
- **le mode entretien** : les affaires d'entretien périodique non closes, avec
  l'état de leur visite, et sans résumé de l'assistant ; un mode inconnu → 422.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.models.core import RoleUtilisateur
from app.utils.suivi_affaires.repartition import (
    CLE_PLUSIEURS,
    CLE_RACINE,
    par_batiment,
    par_categorie,
)
from tests.aides_http import base_http, client_http
from tests.aides_suivi import affaire_ouverte


@dataclass
class _Affaire:
    categorie: str
    batiments: list[int] = field(default_factory=list)


LIBELLES_CAT = {"panne": "Panne", "nuisance": "Nuisance"}
ORDRE_CAT = ["nuisance", "panne"]
LIBELLES_BAT = {CLE_RACINE: "Résidence", "bat:1": "Bât. A", "bat:2": "Bât. B"}
ORDRE_BAT = ["bat:1", "bat:2"]

AFFAIRES = [
    _Affaire("panne", [1]),
    _Affaire("panne", [1, 2]),
    _Affaire("panne"),
    _Affaire("nuisance", [2]),
]


def _barres(fonction):
    return {
        b.cle: (b.nombre, [(t.cle, t.nombre) for t in b.tranches])
        for b in fonction(AFFAIRES, LIBELLES_CAT, ORDRE_CAT, LIBELLES_BAT, ORDRE_BAT)
    }


def test_par_categorie_une_affaire_multi_batiments_ne_compte_qu_une_fois():
    assert _barres(par_categorie) == {
        "panne": (3, [(CLE_RACINE, 1), ("bat:1", 1), (CLE_PLUSIEURS, 1)]),
        "nuisance": (1, [("bat:2", 1)]),
    }


def test_par_batiment_une_affaire_multi_batiments_compte_dans_chacun():
    barres = par_batiment(AFFAIRES, LIBELLES_CAT, ORDRE_CAT, LIBELLES_BAT, ORDRE_BAT)
    assert [b.cle for b in barres] == [CLE_RACINE, "bat:1", "bat:2"], "la racine en tête"
    assert _barres(par_batiment) == {
        CLE_RACINE: (1, [("panne", 1)]),
        "bat:1": (2, [("panne", 2)]),
        #  Les tranches suivent l'ordre FIXE des catégories, pas leur nombre.
        "bat:2": (2, [("nuisance", 1), ("panne", 1)]),
    }


# ── Le mode entretien ───────────────────────────────────────────────────────


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def test_le_mode_entretien_ne_lit_que_l_entretien_periodique_non_clos(moteur):
    visite = affaire_ouverte(moteur, "Visite ascenseur", categorie="entretien", contrat_id=1)
    affaire_ouverte(moteur, "Visite faite", categorie="entretien", contrat_id=1, statut="résolu")
    panne = affaire_ouverte(moteur, "Interphone muet")
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    entretien = http.get("/suivi-affaires?mode=entretien").json()
    assert [a["id"] for a in entretien["affaires"]] == [visite]
    assert entretien["affaires"][0]["etat_visite"] == "a_planifier"
    assert entretien["mode"] == "entretien"
    assert entretien["resumes_disponibles"] is False

    affaires = http.get("/suivi-affaires").json()
    assert [a["id"] for a in affaires["affaires"]] == [panne]
    assert affaires["affaires"][0]["etat_visite"] is None
    assert http.get("/suivi-affaires?mode=inconnu").status_code == 422
