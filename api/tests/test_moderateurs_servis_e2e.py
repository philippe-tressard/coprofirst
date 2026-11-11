"""Le `est_moderateur` que les e2e SIMULENT est celui du serveur (#2633).

Un e2e ne recopie pas la règle « conseil syndical ou administration » : le compte
simulé de `/api/auth/me` reçoit le champ rangé dans
`front/e2e/moderateurs-servis.json` (`compteServi`). Ce test le recalcule par LE
prédicat (`auth/deps.est_moderateur`) : une valeur fausse, ou périmée après un
changement de règle, échoue ici — pas en silence dans un écran simulé.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.auth.deps import est_moderateur
from app.models.core import Utilisateur
from app.models.roles import RoleUtilisateur

FICHIER = pathlib.Path(__file__).resolve().parents[2] / "front" / "e2e" / "moderateurs-servis.json"
COMPTES = json.loads(FICHIER.read_text(encoding="utf-8"))["comptes"]


def test_cas_zero():
    assert COMPTES, f"aucun compte dans {FICHIER} : les e2e ne simuleraient rien"


@pytest.mark.parametrize("c", COMPTES, ids=["+".join(c["roles"]) for c in COMPTES])
def test_le_champ_simule_est_celui_du_serveur(c):
    principal = next((r for r in c["roles"] if r != "operateur"), RoleUtilisateur.résident.value)
    u = Utilisateur(
        email="x@exemple.test",
        hashed_password="x",
        prenom="P",
        nom="N",
        role=principal,
        roles_json=",".join(c["roles"]),
    )
    assert c["est_moderateur"] is est_moderateur(u)
