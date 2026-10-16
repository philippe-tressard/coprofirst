"""Un client HTTP authentifié pour de VRAIS, sur une base en mémoire (#1569).

Trois fichiers de tests écrivaient le même montage — surcharger `get_session`,
poser le jeton dans le cookie — chacun à sa façon, et deux d'entre eux
surchargeaient `get_current_user` (ou `require_cs_or_admin`) : ils ne pouvaient
donc plus vérifier ce qui compte, qu'un anonyme est refusé et qu'un résident ne
passe pas une porte réservée au conseil. Ici l'authentification est la VRAIE :
un jeton émis par `creer_jeton_acces`, relu par `get_current_user`. Seule la base
est remplacée.

Ce sont des fonctions, pas des fixtures : un fichier de tests les appelle depuis
sa propre fixture (`moteur_http`) et choisit son rôle à chaque test.
"""

from __future__ import annotations

from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth.jwt import creer_jeton_acces
from app.database import get_session
from app.main import app
from app.models.core import RoleUtilisateur
from app.utils.limiter import limiter
from tests.aides_base import compte, moteur_de_test


@contextmanager
def base_http():
    """Une base en mémoire PARTAGÉE, branchée sur l'application le temps du bloc.

    Rend le moteur. Les surcharges et les plafonds de débit repartent à zéro à la
    sortie : un test qui laisserait sa base branchée ferait lire la sienne au suivant.
    """
    moteur = moteur_de_test()

    def _session():
        with Session(moteur) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    limiter.reset()
    try:
        yield moteur
    finally:
        app.dependency_overrides.clear()
        limiter.reset()


def client_http(moteur, role: RoleUtilisateur | None, **champs) -> tuple[TestClient, int | None]:
    """Un client anonyme (`role=None`), ou connecté avec un compte ACTIF de ce rôle.

    Rend aussi l'identifiant du compte (`None` pour l'anonyme). `champs` passe tel
    quel à `aides_base.compte` (`statut=`, `batiment_id=`…).
    """
    http = TestClient(app)
    if role is None:
        return http, None
    with Session(moteur) as s:
        ident = compte(
            s,
            prefixe=role.value,
            nom=role.value,
            prenom="Test",
            **{"roles_json": role.value, **champs},
        ).id
    http.cookies.set("access_token", creer_jeton_acces(ident, "x"))
    return http, ident
