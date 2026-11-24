"""Ce que le juge du contrat ne voit pas est DÉCLARÉ, et vérifié aveugle (#2970).

`inventaire.LIMITES` énumère les ruptures que `inventaire.comparer` laisse passer. Ici,
chacune est injectée sur un schéma minimal : le juge doit rester muet (sinon la limite
n'en est plus une, et se retire de `LIMITES`), et toute limite déclarée a sa faute —
une déclaration sans épreuve ne dirait rien de vrai.
"""

from __future__ import annotations

import copy

import pytest

from app.contrat import inventaire as inv


def _schema(
    corps: dict | None = None, parametres: list | None = None, reponse: dict | None = None
) -> dict:
    """Une opération `POST /a/{id}` : un corps JSON, un paramètre de chemin, une réponse."""
    op = {
        "parameters": parametres
        if parametres is not None
        else [{"in": "path", "name": "id", "required": True, "schema": {"type": "integer"}}],
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": corps
                    or {
                        "type": "object",
                        "required": ["n", "etat"],
                        "properties": {
                            "n": {"type": "integer"},
                            "note": {"type": "string"},
                            "etat": {"type": "string", "enum": ["ouvert", "clos"]},
                        },
                    }
                }
            },
        },
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "schema": reponse
                        or {
                            "type": "object",
                            "required": ["statut"],
                            "properties": {"statut": {"type": "string", "enum": ["a", "b"]}},
                        }
                    }
                }
            }
        },
    }
    return {"paths": {"/a/{id}": {"post": op}}}


def _corps(s: dict) -> dict:
    return s["paths"]["/a/{id}"]["post"]["requestBody"]["content"]["application/json"]["schema"]


def _entree_retypee(s: dict) -> None:
    _corps(s)["properties"]["n"]["type"] = "string"
    s["paths"]["/a/{id}"]["post"]["parameters"][0]["schema"]["type"] = "string"


def _entree_facultative_retiree(s: dict) -> None:
    del _corps(s)["properties"]["note"]


def _enumeration_requete_reduite(s: dict) -> None:
    _corps(s)["properties"]["etat"]["enum"] = ["ouvert"]


def _enumeration_reponse_elargie(s: dict) -> None:
    reponse = s["paths"]["/a/{id}"]["post"]["responses"]["200"]["content"]["application/json"]
    reponse["schema"]["properties"]["statut"]["enum"] = ["a", "b", "c"]


def _corps_type_de_contenu(s: dict) -> None:
    contenu = s["paths"]["/a/{id}"]["post"]["requestBody"]["content"]
    contenu["multipart/form-data"] = contenu.pop("application/json")


FAUTES = {
    "entree-retypee": _entree_retypee,
    "entree-facultative-retiree": _entree_facultative_retiree,
    "enumeration-requete-reduite": _enumeration_requete_reduite,
    "enumeration-reponse-elargie": _enumeration_reponse_elargie,
    "corps-type-de-contenu": _corps_type_de_contenu,
}


def test_chaque_limite_declaree_a_sa_faute():
    assert set(FAUTES) == set(inv.LIMITES)


@pytest.mark.parametrize("limite", sorted(FAUTES))
def test_le_juge_reste_aveugle_a_chaque_limite(limite):
    avant = _schema()
    apres = copy.deepcopy(avant)
    FAUTES[limite](apres)
    assert apres != avant, "la faute n'a rien changé"
    ecarts = inv.comparer(inv.inventaire(avant), inv.inventaire(apres))
    assert (ecarts.retraits, ecarts.exigences) == ([], []), (
        f"le juge voit désormais « {limite} » : retirer la limite de inventaire.LIMITES"
    )


def test_le_temoin_un_champ_de_reponse_retire_est_vu():
    """Sans témoin, un schéma que le juge ne lirait pas du tout rendrait tout « aveugle »."""
    avant = _schema()
    apres = copy.deepcopy(avant)
    reponse = apres["paths"]["/a/{id}"]["post"]["responses"]["200"]["content"]["application/json"]
    reponse["schema"]["properties"]["autre"] = reponse["schema"]["properties"].pop("statut")
    ecarts = inv.comparer(inv.inventaire(avant), inv.inventaire(apres))
    assert ecarts.retraits == ["POST /a/{id} → $.statut"]
