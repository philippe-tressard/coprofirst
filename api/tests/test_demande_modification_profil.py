"""Une demande de modification de profil se rend de la même façon, créée ou relue (#1686).

## Le défaut

`POST /auth/me/demande-modification` rendait la ligne nue (`return demande`),
`GET /auth/me/demandes-modification` la même ligne PLUS le libellé du bâtiment
souhaité (`batiment_nom_souhaite`), composé à la main dans la seule liste. Une
demande tout juste déposée n'affichait donc pas « déménagement vers … » sur
l'écran du profil tant que la liste n'était pas rechargée.

## Ce que ce fichier vérifie

La réponse de la création porte `batiment_nom_souhaite`, et elle est
IDENTIQUE à la ligne que la liste rend pour la même demande : les deux routes
passent par une seule lecture.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.copropriete import Batiment, Copropriete
from app.models.core import RoleUtilisateur
from tests.aides_http import base_http, client_http
from tests.aides_sources import modules_app


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def _batiment(moteur, numero: str = "3") -> int:
    with Session(moteur) as s:
        copro = Copropriete(nom="Témoin", adresse="1 rue du Témoin")
        s.add(copro)
        s.commit()
        bat = Batiment(numero=numero, copropriete_id=copro.id)
        s.add(bat)
        s.commit()
        return bat.id


def test_la_creation_rend_le_batiment_souhaite_comme_la_liste(moteur):
    bat_id = _batiment(moteur)
    http, _ = client_http(moteur, RoleUtilisateur.résident)

    cree = http.post(
        "/auth/me/demande-modification",
        json={"batiment_id_souhaite": bat_id, "motif": "Déménagement"},
    )
    assert cree.status_code == 201, cree.text
    assert cree.json().get("batiment_nom_souhaite") == "Bât. 3"

    liste = http.get("/auth/me/demandes-modification")
    assert liste.status_code == 200, liste.text
    assert liste.json() == [cree.json()]


def test_sans_batiment_souhaite_le_libelle_est_nul(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.résident)

    cree = http.post("/auth/me/demande-modification", json={"statut_souhaite": "locataire"})
    assert cree.status_code == 201, cree.text
    assert "batiment_nom_souhaite" in cree.json()
    assert cree.json()["batiment_nom_souhaite"] is None
    assert http.get("/auth/me/demandes-modification").json() == [cree.json()]


def test_la_file_d_admin_relit_la_demande_comme_le_resident(moteur):
    """#1696 : la file du conseil porte la MÊME lecture, plus ce qui l'identifie."""
    bat_id = _batiment(moteur)
    resident, _ = client_http(moteur, RoleUtilisateur.résident)
    cree = resident.post("/auth/me/demande-modification", json={"batiment_id_souhaite": bat_id})
    assert cree.status_code == 201, cree.text

    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    file = cs.get("/admin/demandes-profil")
    assert file.status_code == 200, file.text
    (ligne,) = file.json()
    assert {cle: ligne.get(cle) for cle in cree.json()} == cree.json()
    assert {"utilisateur_nom", "utilisateur_email", "statut_actuel", "batiment_actuel"} <= set(
        ligne
    )


@pytest.mark.parametrize(
    ("action", "statut", "ton", "texte"),
    [
        ("approuver", "approuvee", "success", "Demande approuvée."),
        ("rejeter", "rejetee", "info", "Demande rejetée."),
    ],
)
def test_traiter_rend_le_statut_et_la_phrase_servie(moteur, action, statut, ton, texte):
    """#2618 : la réponse est typée, et la phrase vient du serveur — le site et
    l'app iOS la LISENT, aucun des deux ne la compose (`standards/09` §8)."""
    resident, _ = client_http(moteur, RoleUtilisateur.résident)
    cree = resident.post("/auth/me/demande-modification", json={"statut_souhaite": "locataire"})
    assert cree.status_code == 201, cree.text

    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    rep = cs.post(f"/admin/demandes-profil/{cree.json()['id']}/traiter", json={"action": action})
    assert rep.status_code == 200, rep.text
    assert rep.json() == {"statut": statut, "annonce": {"ton": ton, "texte": texte}}


def test_les_deux_routes_de_la_file_sont_typees_dans_le_contrat():
    """#2618 : l'app iOS se génère depuis `openapi.json` — une réponse sans schéma
    s'y lit `{}`, et l'app la relisait « en miroir »."""
    from app.main import app

    chemins = app.openapi()["paths"]
    for chemin, methode in (
        ("/admin/demandes-profil", "get"),
        ("/admin/demandes-profil/{demande_id}/traiter", "post"),
    ):
        schema = chemins[chemin][methode]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert schema, f"{methode.upper()} {chemin} n'a pas de schéma de réponse"


#: Le libellé du bâtiment souhaité s'écrit dans la lecture unique — `lire_demande`.
PORTE = "utils/demandes_profil.py"


def _ecritures_du_libelle(source: str) -> int:
    """`x["batiment_nom_souhaite"] = …` ou `batiment_nom_souhaite=…` en argument."""
    import ast

    n = 0
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.keyword) and noeud.arg == "batiment_nom_souhaite":
            n += 1
        cibles = noeud.targets if isinstance(noeud, ast.Assign) else []
        for cible in cibles:
            if isinstance(cible, ast.Subscript) and getattr(cible.slice, "value", None) == (
                "batiment_nom_souhaite"
            ):
                n += 1
    return n


def test_le_libelle_ne_se_compose_qu_a_la_porte():
    ecrits = {m.rel: _ecritures_du_libelle(m.source) for m in modules_app(minimum=100)}
    ailleurs = {rel: n for rel, n in ecrits.items() if n and rel != PORTE}
    assert ailleurs == {}, (
        f"le libellé du bâtiment souhaité se compose dans `lire_demande` : {ailleurs}"
    )
    assert ecrits.get(PORTE) == 1


def test_le_controle_voit_la_composition_a_la_main():
    """Cas zéro : l'écriture d'avant #1696, dans `admin/profils.py`, est comptée."""
    assert _ecritures_du_libelle('item["batiment_nom_souhaite"] = libelle(bat, None)') == 1
    assert _ecritures_du_libelle("lire_objet(R, d, batiment_nom_souhaite=x)") == 1
    assert _ecritures_du_libelle('x = item["batiment_nom_souhaite"]') == 0
