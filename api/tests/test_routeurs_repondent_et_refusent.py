"""Trois routeurs qu'aucun test n'appelait : ils répondent, et refusent qui ils doivent (#1048).

L'audit du 19/09/2026 comptait quatre routeurs qu'aucun test ne nommait.
Revérifié le 24/09 :

- `auth_telemetrie`, `regles_residence` — toujours aucun ;
- `lots_imports` — nommé par trois tests, mais tous STATIQUES (listes de
  fichiers, d'appelants) : aucune de ses routes n'avait jamais été appelée ;
- `annonces_hall_schemas` — ce n'est pas un routeur : un module de schémas, sans
  route, déjà importé par `test_annonce_hall_assiste_ia.py`. Rien à appeler.

⚠️ L'authentification est la VRAIE : un jeton émis par `creer_jeton_acces`,
posé dans le cookie, relu par `get_current_user`. Seule la base est remplacée.
Le motif courant — surcharger `get_current_user` — rend impossible de vérifier
ce qui compte ici : qu'un anonyme est refusé, et qu'un résident ne passe pas
une porte réservée au conseil syndical.

Chaque routeur est vérifié sur trois questions :
1. un **anonyme** est refusé (401) sur chacune de ses routes ;
2. un **rôle insuffisant** est refusé (403) sur les routes réservées, et rien
   n'est écrit ;
3. le **bon rôle** obtient la réponse attendue — ce qui prouve aussi que la
   route arrive bien à CE routeur (#1151 : deux écrans d'import sont morts,
   masqués par une route plus générale déclarée avant eux).

⚠️ L'atelier d'import est monté DANS le routeur `lots` : ses adresses commencent
par `/lots/admin/imports`, celles qu'appelle le front (`patrimoine.ts`). Écrit
sans le préfixe, chaque refus attendu rendait 404 — un test d'anonyme qui
aurait accepté « n'importe quel refus » serait resté vert sur une route absente.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.jwt import creer_jeton_acces
from app.database import get_session
from app.main import app
from app.models.core import (
    LotImport,
    RegleResidence,
    RoleUtilisateur,
    StatutLotImport,
    Utilisateur,
)
from app.models.telemetrie import DerniereVisite, PresenceMensuelle, TelemetryEvent
from app.utils.limiter import limiter
from tests.aides_base import compte, moteur_de_test


@pytest.fixture(name="moteur")
def moteur_fixture():
    moteur = moteur_de_test()

    def _session():
        with Session(moteur) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    #  Les routes RGPD sont limitées à 5 par minute : sans remise à zéro, l'ordre
    #  d'exécution des tests déciderait de leur verdict.
    limiter.reset()
    yield moteur
    app.dependency_overrides.clear()
    limiter.reset()


def _client(moteur, role: RoleUtilisateur | None) -> tuple[TestClient, int | None]:
    """Un client anonyme (`role=None`) ou connecté avec un compte de ce rôle."""
    http = TestClient(app)
    if role is None:
        return http, None
    with Session(moteur) as s:
        #  Un compte naît INACTIF (en attente de validation) : `compte` l'active,
        #  sans quoi le jeton serait refusé et chaque test lirait un 401 de plus.
        ident = compte(
            s, prefixe=role.value, nom=role.value, prenom="Test", roles_json=role.value
        ).id
    http.cookies.set("access_token", creer_jeton_acces(ident, "x"))
    return http, ident


def _appeler(http: TestClient, methode: str, route: str):
    corps = {"PATCH": {}, "POST": {}}.get(methode)
    return http.request(methode, route, json=corps)


# ── regles_residence ────────────────────────────────────────────────────────

ROUTES_REGLES = [
    ("GET", "/regles-residence"),
    ("POST", "/regles-residence"),
    ("PATCH", "/regles-residence/1"),
    ("DELETE", "/regles-residence/1"),
]


@pytest.mark.parametrize("methode,route", ROUTES_REGLES)
def test_regles_refusent_un_anonyme(moteur, methode, route):
    http, _ = _client(moteur, None)
    assert _appeler(http, methode, route).status_code == 401


def test_regles_un_resident_lit_mais_n_ecrit_pas(moteur):
    http, _ = _client(moteur, RoleUtilisateur.résident)
    assert http.get("/regles-residence").status_code == 200
    reponse = http.post("/regles-residence", json={"titre": "Pas de barbecue"})
    assert reponse.status_code == 403
    with Session(moteur) as s:
        assert s.exec(select(RegleResidence)).all() == [], "le refus a quand même écrit"


def test_regles_le_conseil_syndical_cree_modifie_supprime(moteur):
    http, cs_id = _client(moteur, RoleUtilisateur.conseil_syndical)

    creee = http.post("/regles-residence", json={"titre": "Tri", "contenu": "Bac jaune"})
    assert creee.status_code == 201, creee.text
    regle_id = creee.json()["id"]

    liste = http.get("/regles-residence").json()
    assert [(r["titre"], r["cree_par_id"]) for r in liste] == [("Tri", cs_id)]

    modifiee = http.patch(f"/regles-residence/{regle_id}", json={"ordre": 3})
    assert modifiee.status_code == 200 and modifiee.json()["ordre"] == 3

    assert http.delete(f"/regles-residence/{regle_id}").status_code == 204
    assert http.delete(f"/regles-residence/{regle_id}").status_code == 404


# ── auth_telemetrie ─────────────────────────────────────────────────────────

ROUTES_TELEMETRIE = [
    ("GET", "/auth/me/telemetrie"),
    ("DELETE", "/auth/me/telemetrie"),
    ("PATCH", "/auth/me/opt-out-telemetrie"),
]


@pytest.mark.parametrize("methode,route", ROUTES_TELEMETRIE)
def test_telemetrie_refuse_un_anonyme(moteur, methode, route):
    http, _ = _client(moteur, None)
    assert _appeler(http, methode, route).status_code == 401


def test_telemetrie_chacun_n_exporte_et_n_efface_que_la_sienne(moteur):
    """Articles 15 et 17 : l'accès et l'effacement portent sur SES données — un
    `where` oublié exporterait, ou effacerait, celles de tout le monde."""
    http, moi = _client(moteur, RoleUtilisateur.résident)
    with Session(moteur) as s:
        autre_id = compte(
            s,
            prefixe="autre",
            nom="A",
            prenom="A",
            roles_json=RoleUtilisateur.résident.value,
        ).id
        s.add(TelemetryEvent(user_id=moi, page="/actualites"))
        s.add(TelemetryEvent(user_id=autre_id, page="/tickets"))
        #  Et la présence mensuelle (0254) : exportée et effacée avec les évènements.
        s.add(PresenceMensuelle(mois="2026-05", user_id=moi))
        s.add(PresenceMensuelle(mois="2026-05", user_id=autre_id))
        #  Et le jour de la dernière visite (#1629), de même.
        s.add(DerniereVisite(user_id=moi, jour="2026-05-12"))
        s.add(DerniereVisite(user_id=autre_id, jour="2026-05-13"))
        s.commit()

    export = http.get("/auth/me/telemetrie")
    assert export.status_code == 200
    assert [e["page"] for e in export.json()["evenements"]] == ["/actualites"]
    assert export.json()["mois_de_presence"] == ["2026-05"]
    assert export.json()["jour_de_derniere_visite"] == "2026-05-12"

    assert http.delete("/auth/me/telemetrie").status_code == 204
    with Session(moteur) as s:
        restants = s.exec(select(TelemetryEvent)).all()
        presences = s.exec(select(PresenceMensuelle)).all()
    assert [(e.user_id, e.page) for e in restants] == [(autre_id, "/tickets")]
    assert [p.user_id for p in presences] == [autre_id]
    with Session(moteur) as s:
        assert [d.user_id for d in s.exec(select(DerniereVisite)).all()] == [autre_id]


def test_telemetrie_l_opposition_est_enregistree(moteur):
    http, moi = _client(moteur, RoleUtilisateur.résident)
    with Session(moteur) as s:
        s.add(DerniereVisite(user_id=moi, jour="2026-05-12"))
        s.commit()
    reponse = http.patch("/auth/me/opt-out-telemetrie", json={"opt_out_telemetrie": True})
    assert reponse.status_code == 204
    with Session(moteur) as s:
        assert s.get(Utilisateur, moi).opt_out_telemetrie is True
        #  Le refus efface le jour de la dernière visite (#1629) : il ne sert plus à rien.
        assert s.get(DerniereVisite, moi) is None


# ── lots_imports ────────────────────────────────────────────────────────────

ROUTES_IMPORTS = [
    ("GET", "/lots/admin/imports"),
    ("GET", "/lots/admin/imports/stats"),
    ("PATCH", "/lots/admin/imports/1"),
    ("POST", "/lots/admin/imports/1/resoudre"),
    ("POST", "/lots/admin/imports/1/ignorer"),
    ("POST", "/lots/admin/imports/auto-resoudre"),
    ("POST", "/lots/admin/imports/auto-match"),
]


@pytest.mark.parametrize("methode,route", ROUTES_IMPORTS)
def test_imports_refusent_un_anonyme(moteur, methode, route):
    http, _ = _client(moteur, None)
    assert _appeler(http, methode, route).status_code == 401


@pytest.mark.parametrize("methode,route", ROUTES_IMPORTS)
def test_imports_refusent_un_resident(moteur, methode, route):
    http, _ = _client(moteur, RoleUtilisateur.résident)
    assert _appeler(http, methode, route).status_code == 403


def test_imports_le_conseil_syndical_liste_compte_annote_et_ignore(moteur):
    with Session(moteur) as s:
        imp = LotImport(numero="12", type_raw="AP", nom_coproprietaire="DUPONT")
        s.add(imp)
        s.commit()
        s.refresh(imp)
        imp_id = imp.id
    http, _ = _client(moteur, RoleUtilisateur.conseil_syndical)

    liste = http.get("/lots/admin/imports")
    assert liste.status_code == 200, liste.text
    assert [i["id"] for i in liste.json()] == [imp_id]

    stats = http.get("/lots/admin/imports/stats").json()
    assert (stats["total"], stats["en_attente"]) == (1, 1)

    annote = http.patch(f"/lots/admin/imports/{imp_id}", json={"notes_admin": "à vérifier"})
    assert annote.status_code == 200, annote.text

    assert http.post(f"/lots/admin/imports/{imp_id}/ignorer").json() == {"ok": True}
    with Session(moteur) as s:
        relu = s.get(LotImport, imp_id)
        assert (relu.notes_admin, relu.statut) == ("à vérifier", StatutLotImport.ignore)
