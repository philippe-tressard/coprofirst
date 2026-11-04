"""Les gestes d'un résident sur ses accès sont TYPÉS dans le contrat (#2507).

## 🔴 Le défaut

`GET /acces/mes-vigiks`, `…/mes-telecommandes`, `POST /acces/declarer-badge` et
`PATCH …/perdu` n'avaient pas de `response_model` : le contrat les annonçait `{}`,
et le client généré de l'app iOS ne lisait rien. Et un refus de déclaration (code
vide, type inconnu) était un 422 au `detail` TEXTE, quand le contrat annonce un
`HTTPValidationError` — une liste, qu'un client typé ne décode qu'en cette forme.
"""

from __future__ import annotations

import pytest

from app.models.core import RoleUtilisateur
from tests.aides_http import base_http, client_http


@pytest.mark.parametrize(
    "corps, message",
    [({"type": "vigik", "code": "   "}, "Code vide"), ({"type": "porte", "code": "A1"}, "Type")],
)
def test_un_refus_de_declaration_a_la_forme_que_le_contrat_annonce(corps, message):
    """🔴 Un `detail` texte : le client généré ne pouvait pas le décoder."""
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.résident)
        reponse = http.post("/acces/declarer-badge", json=corps)
    assert reponse.status_code == 422
    detail = reponse.json()["detail"]
    assert isinstance(detail, list), "le 422 doit être un HTTPValidationError"
    assert message in detail[0]["msg"]


def test_une_declaration_rend_le_badge_declare():
    with base_http() as moteur:
        http, _ = client_http(moteur, RoleUtilisateur.résident)
        reponse = http.post("/acces/declarer-badge", json={"type": "vigik", "code": " V-1 "})
        perdu = http.patch(f"/acces/vigiks/{reponse.json()['id']}/perdu", json={})
        mes = http.get("/acces/mes-vigiks").json()
    assert reponse.status_code == 201
    corps = reponse.json()
    assert (corps["type"], corps["code"], corps["import_resolu"]) == ("vigik", "V-1", False)
    assert perdu.json() == {"statut": "perdu"}
    assert [(a["code"], a["statut"]) for a in mes] == [("V-1", "perdu")]


def test_les_routes_du_resident_sont_typees_dans_le_contrat():
    from app.main import app

    chemins = app.openapi()["paths"]

    def ref(chemin: str, methode: str, code: str = "200") -> str:
        schema = chemins[chemin][methode]["responses"][code]["content"]["application/json"][
            "schema"
        ]
        return schema.get("$ref") or schema["items"]["$ref"]

    assert ref("/acces/mes-vigiks", "get").endswith("/AccesPorteur")
    assert ref("/acces/mes-telecommandes", "get").endswith("/AccesPorteur")
    assert ref("/acces/declarer-badge", "post", "201").endswith("/BadgeDeclare")
    assert ref("/acces/vigiks/{vigik_id}/perdu", "patch").endswith("/AccesSignalePerdu")
    assert ref("/acces/telecommandes/{tc_id}/perdu", "patch").endswith("/AccesSignalePerdu")
