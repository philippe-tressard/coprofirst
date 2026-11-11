"""Les noms que les e2e SIMULENT sont ceux du serveur (#2633).

Un e2e ne recopie pas la règle « Prénom NOM » : une personne simulée porte le
`nom_affiche` rangé dans `front/e2e/noms-servis.json`, et `POST /noms/affiche`
simulé y répond. Ce test le recalcule par la règle (`utils/noms.nom_affiche`) :
un nom faux, ou périmé après un changement de règle, échoue ici — pas en silence
dans un écran simulé.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.utils.noms import nom_affiche

FICHIER = pathlib.Path(__file__).resolve().parents[2] / "front" / "e2e" / "noms-servis.json"
NOMS = json.loads(FICHIER.read_text(encoding="utf-8"))["noms"]


def test_cas_zero():
    assert NOMS, f"aucun nom dans {FICHIER} : les e2e ne simuleraient rien"


@pytest.mark.parametrize("n", NOMS, ids=[f"{n['prenom']}|{n['nom']}" for n in NOMS])
def test_le_nom_simule_est_celui_du_serveur(n):
    assert n["nom_affiche"] == nom_affiche(n["prenom"], n["nom"])
