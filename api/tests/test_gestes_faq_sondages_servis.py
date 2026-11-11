"""Le droit de rédiger la FAQ et celui de créer un sondage sont SERVIS au lecteur (#2654).

## 🔴 Le défaut

Aucune réponse de l'API ne disait au conseil syndical qu'il pouvait rédiger la FAQ
ou créer un sondage : le site décidait par `$isCS` (`#lib/stores/auth`), et l'app
iOS relisait cette règle générée depuis `pages.ts` — une copie de la règle du
serveur dans un autre dépôt (`standards/09` §8, règle 1 ; #2501).

## Ce que ce fichier tient

La CONCORDANCE : `GET /faq/gestes` et `GET /sondages/gestes` servent `True`
exactement aux rôles que les routes de rédaction acceptent, et `False` à ceux
qu'elles refusent en 403 — jouées pour CHAQUE rôle de la copropriété. Puis la
NON-RÉGRESSION : ces rôles sont ceux que `$isCS` ouvrait sur les deux écrans
avant que le site ne lise le champ servi.
"""

from __future__ import annotations

import pytest

from app.models.core import RoleUtilisateur
from tests.aides_http import base_http, client_http

#: Ce que `$isCS` ouvrait sur la FAQ et l'onglet Sondages avant #2654 — le
#: conseil syndical et l'administration. Le champ servi ne s'en écarte pas.
ROLES_DU_SITE_AVANT = {RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin}

ENTREE_FAQ = {"categorie": "Général", "question": "Q ?", "reponse": "<p>R</p>"}
SONDAGE = {"question": "Q ?", "options": [{"libelle": "Oui"}, {"libelle": "Non"}]}


@pytest.mark.parametrize("role", list(RoleUtilisateur), ids=lambda r: r.value)
def test_le_droit_servi_est_celui_que_les_routes_acceptent(role):
    with base_http() as moteur:
        http, _ = client_http(moteur, role)

        peut_rediger = http.get("/faq/gestes").json()["peut_rediger"]
        peut_creer = http.get("/sondages/gestes").json()["peut_creer"]

        #  Rédiger la FAQ : chaque route que l'écran offre au rédacteur.
        cree = http.post("/faq", json=ENTREE_FAQ)
        assert cree.status_code == (201 if peut_rediger else 403), cree.text
        for reponse in (
            http.get("/faq/all"),
            http.get("/faq/categories"),
            http.patch("/faq/reorder", json=[]),
        ):
            assert (reponse.status_code != 403) is peut_rediger, reponse.text

        sondage = http.post("/sondages", json=SONDAGE)
        assert sondage.status_code == (201 if peut_creer else 403), sondage.text

        #  Non-régression : le site offrait ces gestes aux mêmes rôles.
        assert peut_rediger is (role in ROLES_DU_SITE_AVANT)
        assert peut_creer is (role in ROLES_DU_SITE_AVANT)


def test_les_gestes_se_refusent_sans_session():
    with base_http() as moteur:
        anonyme, _ = client_http(moteur, None)
        assert anonyme.get("/faq/gestes").status_code == 401
        assert anonyme.get("/sondages/gestes").status_code == 401


def test_les_gestes_sont_types_dans_le_contrat():
    """L'app iOS génère son client depuis `openapi.json` : un `{}` ne s'y lit pas."""
    from app.main import app

    chemins = app.openapi()["paths"]
    for chemin, champ in (("/faq/gestes", "peut_rediger"), ("/sondages/gestes", "peut_creer")):
        schema = chemins[chemin]["get"]["responses"]["200"]["content"]["application/json"]
        nom = schema["schema"]["$ref"].rsplit("/", 1)[-1]
        assert app.openapi()["components"]["schemas"][nom]["required"] == [champ]
