"""Un vrai jeton d'appareil, émis par son vrai parcours (#2770, #2771).

`test_jetons_appareil.py` balaie toutes les routes avec un jeton de chaque portée, et
`test_ecrans.py` lit ce qu'un écran reçoit : les deux émettent par les routes de
l'application, jamais en écrivant la ligne à la main — un jeton fabriqué ne dirait
rien du parcours qui le délivre.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.core import RoleUtilisateur
from tests.aides_http import client_http


def jeton_de_montre(moteur) -> str:
    """Le téléphone connecté relie une montre (`POST /montres`)."""
    telephone, _ = client_http(moteur, RoleUtilisateur.propriétaire)
    r = telephone.post("/montres", json={"plateforme": "watchos"})
    assert r.status_code == 201, r.text
    return r.json()["jeton"]


def jeton_d_ecran(moteur, perimetre: str = "résidence", nom: str = "Hall bât. 2") -> str:
    """L'écran demande un appairage, le conseil le confirme, l'écran échange son code."""
    ecran = TestClient(app)
    demande = ecran.post("/ecrans/appairage")
    assert demande.status_code == 200, demande.text
    conseil, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    confirme = conseil.post(
        "/ecrans",
        json={"code_court": demande.json()["code_court"], "nom": nom, "perimetre": perimetre},
    )
    assert confirme.status_code == 201, confirme.text
    r = ecran.post(
        "/ecrans/appairage/jeton", json={"code_appareil": demande.json()["code_appareil"]}
    )
    assert r.status_code == 200, r.text
    return r.json()["jeton"]
