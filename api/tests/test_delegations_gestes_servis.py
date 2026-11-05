"""Les délégations sont TYPÉES, et leurs gestes SERVIS pour qui lit (#2525).

## 🔴 Le défaut

`GET /delegations` rendait `list[dict]`, et `POST /delegations`, `/accepter`,
`/revoquer` n'avaient pas de schéma : le contrat les annonçait `{}`, et l'app iOS
les relisait « en miroir ». Le site décidait seul des deux gestes — « Accepter »
par `statut === 'en_attente' && aidant_id === moi`, « Révoquer » par
`statut ∈ {en_attente, active}` —, quand le serveur, qui refuse, savait déjà les
deux. L'app ne recopie aucune règle du front (`standards/09` §8) : elle n'offrait
aucun des deux gestes.

Ce fichier tient la CONCORDANCE : un geste servi `True` passe sa route, un geste
servi `False` la voit refuser. Le prédicat qui sert est celui qui refuse
(`auth/appartenance`), jamais une copie.
"""

from __future__ import annotations

from app.models.core import RoleUtilisateur
from tests.aides_http import base_http, client_http


def _schema(chemin: str, methode: str, code: str = "200") -> str:
    from app.main import app

    reponse = app.openapi()["paths"][chemin][methode]["responses"][code]
    schema = reponse["content"]["application/json"]["schema"]
    return schema.get("$ref") or schema["items"]["$ref"]


def test_les_routes_des_delegations_sont_typees_dans_le_contrat():
    assert _schema("/delegations", "get").endswith("/DelegationRead")
    assert _schema("/delegations", "post", "201").endswith("/DelegationRead")
    assert _schema("/delegations/{delegation_id}/accepter", "post").endswith("/DelegationRead")
    assert _schema("/delegations/{delegation_id}/revoquer", "post").endswith("/DelegationRead")
    #  Les menus mandant / aidant du formulaire.
    assert _schema("/admin/utilisateurs", "get").endswith("/UtilisateurAdminRead")


def test_les_delegations_d_un_aidant_sont_typees_dans_auth_me():
    """🔴 Des `dict` : c'est pourtant elles qui ouvrent la page à l'aidant (`Nav.svelte`)."""
    from app.main import app

    schemas = app.openapi()["components"]["schemas"]
    items = schemas["UserRead"]["properties"]["delegations_aidant"]["items"]
    assert items.get("$ref", "").endswith("/DelegationAidant")
    assert set(schemas["DelegationAidant"]["required"]) == {
        "delegation_id",
        "mandant_id",
        "mandant_nom",
    }


def _gestes(http) -> tuple[bool, bool]:
    (d,) = http.get("/delegations").json()
    return d["peut_accepter"], d["peut_revoquer"]


def test_les_gestes_servis_sont_ceux_que_les_routes_acceptent():
    with base_http() as moteur:
        cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        aidant, aidant_id = client_http(moteur, RoleUtilisateur.résident)
        mandant, mandant_id = client_http(moteur, RoleUtilisateur.résident)
        tiers, _ = client_http(moteur, RoleUtilisateur.résident)
        cree = cs.post("/delegations", json={"mandant_id": mandant_id, "aidant_id": aidant_id})
        assert cree.status_code == 201, cree.text
        ident = cree.json()["id"]

        #  En attente : seul l'aidant accepte ; les deux parties et le conseil révoquent.
        assert _gestes(aidant) == (True, True)
        assert _gestes(mandant) == (False, True)
        assert _gestes(cs) == (False, True)
        assert tiers.get("/delegations").json() == []
        #  …et la route dit la même chose.
        assert mandant.post(f"/delegations/{ident}/accepter").status_code == 403
        assert cs.post(f"/delegations/{ident}/accepter").status_code == 403
        acceptee = aidant.post(f"/delegations/{ident}/accepter")
        assert acceptee.status_code == 200
        #  La réponse du geste porte les gestes d'APRÈS, pour qui l'a fait.
        assert (acceptee.json()["peut_accepter"], acceptee.json()["peut_revoquer"]) == (
            False,
            True,
        )

        #  Active : plus rien à accepter, toujours révocable.
        assert _gestes(aidant) == (False, True)
        assert aidant.post(f"/delegations/{ident}/accepter").status_code == 400
        revoquee = mandant.post(f"/delegations/{ident}/revoquer")
        assert revoquee.status_code == 200

        #  Révoquée : aucun geste, et la route refuse.
        for lecteur in (aidant, mandant, cs):
            assert _gestes(lecteur) == (False, False)
        assert cs.post(f"/delegations/{ident}/revoquer").status_code == 400
