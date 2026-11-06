"""Les affiches de hall sont TYPÉES, et leurs gestes SERVIS pour qui lit (#2525).

## 🔴 Le défaut

`GET /annonces-hall`, `POST`, `PATCH /{id}`, `GET /sources` et
`GET /depuis/{type}/{id}` n'avaient pas de schéma : le contrat les annonçait `{}`.
Et l'Historique décidait seul de trois gestes — « Restaurer » n'est offert que si
`!archivee || archivee_manuellement` (#515 : une affiche rangée par le TEMPS ne
se restaure pas), « Supprimer » que pour `$isAdmin`, la route exigeant
`require_admin`. L'app iOS ne recopie pas ces règles : elle n'offrait rien.
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session

from app.models.core import AnnonceHall, RoleUtilisateur
from app.utils import horloge
from tests.aides_http import base_http, client_http


def _schema(chemin: str, methode: str, code: str = "200") -> str:
    from app.main import app

    reponse = app.openapi()["paths"][chemin][methode]["responses"][code]
    schema = reponse["content"]["application/json"]["schema"]
    return schema.get("$ref") or schema["items"]["$ref"]


def test_les_routes_des_affiches_sont_typees_dans_le_contrat():
    assert _schema("/annonces-hall", "get").endswith("/AnnonceHallRead")
    assert _schema("/annonces-hall", "post", "201").endswith("/AnnonceHallRead")
    assert _schema("/annonces-hall/{annonce_id}", "patch").endswith("/AnnonceHallRead")
    assert _schema("/annonces-hall/sources", "get").endswith("/SourceReprenable")
    assert _schema("/annonces-hall/depuis/{type_source}/{id_source}", "get").endswith(
        "/PrefillAffiche"
    )


def _poser(moteur) -> dict[str, int]:
    """Trois affiches : en cours, rangée à la main, rangée par le temps."""
    maintenant = horloge.maintenant()
    with Session(moteur) as s:
        affiches = {
            "en_cours": AnnonceHall(titre="Eau", message="<p>x</p>", envoye_le=maintenant),
            "a_la_main": AnnonceHall(
                titre="Gaz", message="<p>x</p>", envoye_le=maintenant, archivee=True
            ),
            "par_le_temps": AnnonceHall(
                titre="Ascenseur",
                message="<p>x</p>",
                envoye_le=maintenant - timedelta(days=400),
            ),
        }
        s.add_all(affiches.values())
        s.commit()
        return {cle: a.id for cle, a in affiches.items()}


def _gestes(http) -> dict[int, tuple[bool, bool, bool]]:
    lues = http.get("/annonces-hall").json() + http.get("/annonces-hall?archivees=true").json()
    return {a["id"]: (a["peut_archiver"], a["peut_restaurer"], a["peut_supprimer"]) for a in lues}


def test_les_gestes_servis_sont_ceux_que_les_routes_permettent():
    with base_http() as moteur:
        ids = _poser(moteur)
        cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
        admin, _ = client_http(moteur, RoleUtilisateur.admin)

        gestes_cs = _gestes(cs)
        assert gestes_cs[ids["en_cours"]] == (True, False, False)
        assert gestes_cs[ids["a_la_main"]] == (False, True, False)
        #  🔴 Rangée par le temps : restaurer n'aurait aucun effet, rien ne s'offre.
        assert gestes_cs[ids["par_le_temps"]] == (False, False, False)
        #  L'administrateur seul supprime — la route exige `require_admin`.
        assert {g[2] for g in _gestes(admin).values()} == {True}
        assert cs.delete(f"/annonces-hall/{ids['en_cours']}").status_code == 403

        #  Le geste servi a son effet : restaurer la rangée à la main la ramène.
        restauree = cs.patch(f"/annonces-hall/{ids['a_la_main']}", json={"archivee": False})
        assert restauree.status_code == 200
        corps = restauree.json()
        assert (corps["archivee"], corps["peut_archiver"], corps["peut_restaurer"]) == (
            False,
            True,
            False,
        )
