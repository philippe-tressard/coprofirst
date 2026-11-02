"""Le contrat de l'API ne recule pas sans période de compatibilité (#2456).

L'app iOS génère son client depuis le schéma publié avec chaque version ; une
installation de la vague Fixe garde longtemps l'ancienne. Un retrait de route ou de
champ de réponse, un type changé, une entrée requise neuve cassent ce client sans
qu'aucun test du serveur ne le voie : c'est ce fichier qui le voit, sur le modèle de
`test_migrations_compatibles.py` — annoncer (`app/contrat/retraits.py`), puis
retirer dans une version ultérieure.

Les règles vivent dans `app/contrat/inventaire.py`, que le générateur de la
référence (`scripts/ci/exporter_openapi.py --ecrire-reference`) applique aussi : le
test et le générateur ne peuvent pas diverger.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import contrat
from app.contrat import inventaire as inv
from app.contrat.retraits import RETRAITS
from tests.aides_http import base_http, client_http

_RACINE = Path(__file__).resolve().parents[2]
_REGENERER = "python scripts/ci/exporter_openapi.py --ecrire-reference"


def _version_app() -> str:
    return json.loads((_RACINE / "front" / "package.json").read_text(encoding="utf-8"))["version"]


# ── 1. Les règles, sur des inventaires construits ────────────────────────────


def _op(reponse=None, entree=(), deprecie=False) -> dict:
    return {"deprecie": deprecie, "entree": list(entree), "reponse": dict(reponse or {})}


_REF = {
    "GET /x": _op(
        {"$": "objet", "$.a": "string", "$.b": "integer?", "$.c": "objet", "$.c.d": "string"}
    ),
    "POST /y": _op(entree=["corps", "corps.titre"]),
}


def test_un_champ_retire_sans_annonce_est_refuse():
    courant = {
        **_REF,
        "GET /x": _op({"$": "objet", "$.b": "integer?", "$.c": "objet", "$.c.d": "string"}),
    }
    messages = inv.refus(inv.comparer(_REF, courant), {}, "3.0.0")
    assert messages == ["GET /x → $.a : retiré sans avoir été annoncé (`retraits.RETRAITS`)"]


def test_une_operation_retiree_sans_annonce_est_refusee():
    courant = {"GET /x": _REF["GET /x"]}
    assert inv.comparer(_REF, courant).retraits == ["POST /y"]
    assert inv.refus(inv.comparer(_REF, courant), {}, "3.0.0")


def test_un_retrait_annonce_dans_la_meme_version_est_refuse():
    courant = {"GET /x": _REF["GET /x"]}
    messages = inv.refus(inv.comparer(_REF, courant), {"POST /y": ("3.0.0", "essai")}, "3.0.0")
    assert len(messages) == 1 and "même version" in messages[0]


def test_un_retrait_annonce_dans_une_version_anterieure_passe():
    courant = {"GET /x": _REF["GET /x"]}
    ecarts = inv.comparer(_REF, courant)
    assert inv.refus(ecarts, {"POST /y": ("2.9.0", "essai")}, "3.0.0") == []
    assert inv.version_suivante("1.4.0", ecarts) == "2.0.0"


def test_l_annonce_d_un_champ_couvre_ce_qu_il_porte():
    courant = {**_REF, "GET /x": _op({"$": "objet", "$.a": "string", "$.b": "integer?"})}
    ecarts = inv.comparer(_REF, courant)
    assert ecarts.retraits == ["GET /x → $.c", "GET /x → $.c.d"]
    assert inv.refus(ecarts, {"GET /x → $.c": ("2.9.0", "essai")}, "3.0.0") == []


def test_un_type_change_ou_relache_est_un_retrait():
    change = {**_REF, "GET /x": _op({**_REF["GET /x"]["reponse"], "$.a": "integer"})}
    relache = {**_REF, "GET /x": _op({**_REF["GET /x"]["reponse"], "$.a": "string?"})}
    assert inv.comparer(_REF, change).retraits == ["GET /x → $.a"]
    assert inv.comparer(_REF, relache).retraits == ["GET /x → $.a"]


def test_un_champ_resserre_ou_deprecie_reste_lisible():
    courant = {
        **_REF,
        "GET /x": _op({**_REF["GET /x"]["reponse"], "$.a": "string déprécié", "$.b": "integer"}),
    }
    ecarts = inv.comparer(_REF, courant)
    assert ecarts.retraits == [] and ecarts.modifie
    assert inv.version_suivante("1.4.0", ecarts) == "1.5.0"


def test_une_entree_requise_neuve_est_refusee_une_entree_relachee_passe():
    exige = {**_REF, "POST /y": _op(entree=["corps", "corps.titre", "corps.lot_id"])}
    assert inv.refus(inv.comparer(_REF, exige), {}, "3.0.0") == [
        "POST /y ← corps.lot_id : une entrée neuve d'une opération existante est facultative"
    ]
    relache = {**_REF, "POST /y": _op(entree=["corps"])}
    assert inv.refus(inv.comparer(_REF, relache), {}, "3.0.0") == []


def test_un_ajout_prend_une_mineure_rien_ne_garde_la_version():
    ajout = {**_REF, "GET /z": _op({"$": "liste"})}
    assert inv.version_suivante("1.4.0", inv.comparer(_REF, ajout)) == "1.5.0"
    assert inv.version_suivante("1.4.0", inv.comparer(_REF, dict(_REF))) == "1.4.0"


def test_une_annonce_dont_la_cible_est_servie_doit_la_deprecier():
    annonces = {"GET /x": ("2.9.0", "essai"), "POST /y → $.id": ("2.9.0", "déjà retiré")}
    assert inv.annonces_non_marquees(_REF, annonces) == ["GET /x"]
    marquee = {**_REF, "GET /x": {**_REF["GET /x"], "deprecie": True}}
    assert inv.annonces_non_marquees(marquee, annonces) == []


def test_l_inventaire_lit_references_listes_nullables_et_cycles():
    schema = {
        "paths": {
            "/n": {
                "get": {
                    "parameters": [{"in": "query", "name": "q", "required": True}],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/N"},
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "N": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "integer"},
                        "nom": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "deprecated": True,
                        },
                        "parent": {"anyOf": [{"$ref": "#/components/schemas/N"}, {"type": "null"}]},
                    },
                }
            }
        },
    }
    assert inv.inventaire(schema) == {
        "GET /n": {
            "deprecie": False,
            "entree": ["query:q"],
            "reponse": {
                "$": "liste",
                "$[]": "objet",
                "$[].id": "integer",
                "$[].nom": "string? déprécié",
                "$[].parent": "objet?",
            },
        }
    }


# ── 2. Le contrat réel ───────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def schema():
    from app.main import app

    return app.openapi()


@pytest.fixture(scope="module")
def courant(schema):
    return inv.inventaire(schema)


def test_aucun_retrait_non_annonce_depuis_la_reference(courant):
    """LE garde-fou : ce que la référence promet reste servi, ou son retrait a été annoncé."""
    reference = contrat.lire_reference()["operations"]
    messages = inv.refus(inv.comparer(reference, courant), RETRAITS, _version_app())
    assert not messages, "Ce lot casserait un client du contrat :\n  " + "\n  ".join(messages)


def test_les_retraits_annonces_sont_deprecies_dans_le_contrat(courant):
    assert not inv.annonces_non_marquees(courant, RETRAITS), (
        "Annoncé au retrait mais servi sans `deprecated` : le client généré ne le saurait pas."
    )


def test_la_reference_decrit_le_code(courant):
    reference = contrat.lire_reference()
    assert reference["operations"] == courant, (
        f"Le contrat de l'API a changé : régénérer la référence (`{_REGENERER}`), qui en "
        "calcule la version. Un lot parallèle l'a changée aussi ? Prendre celle de `dev`, "
        "puis régénérer."
    )
    assert reference["empreinte"] == inv.empreinte(reference["operations"]), (
        f"Empreinte fausse : la référence a été éditée à la main — `{_REGENERER}`."
    )


def test_l_identifiant_d_une_operation_ne_depend_que_de_sa_route(schema):
    ids = [op["operationId"] for chemins in schema["paths"].values() for op in chemins.values()]
    assert len(ids) == len(set(ids)), "deux opérations portent le même identifiant"
    assert "get_tickets" in ids and not any(i.endswith(("_get", "_post")) for i in ids), (
        "un `operationId` ne vient pas de `contrat.identifiant_operation`"
    )


def test_le_schema_publie_porte_sa_version_et_son_prefixe(schema):
    publie = contrat.contrat_publie(schema)
    assert publie["info"]["version"] == contrat.VERSION_CONTRAT
    assert publie["servers"] == [{"url": "/api", "description": "l'installation"}]


@pytest.fixture
def moteur():
    with base_http() as moteur:
        yield moteur


def test_la_config_publique_rend_la_version_du_contrat(moteur):
    http, _ = client_http(moteur, None)
    assert http.get("/config").json()[contrat.CLE_PUBLIQUE] == contrat.VERSION_CONTRAT
