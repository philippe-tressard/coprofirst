"""L'inventaire d'un bail, par ses URL : `/bailleur/baux/{bail_id}/objets…` (#2914).

Ces cinq routes n'étaient appelées par AUCUN test : le contrôle des routeurs nommés
les croyait couvertes parce que le mot « objets » paraissait ailleurs, cinquante-trois
fois, pour autre chose. Ce fichier les tient par la porte réelle (`aides_http`) :

1. les refus — anonyme 401, résident 403 (`require_proprietaire`), autre bailleur 403
   (`exiger_bail_du_bailleur`), bail ou objet inconnu 404, objet d'un AUTRE bail 404 ;
2. le cycle nominal — remise, lecture, correction, retour (statut ET date ensemble),
   perte, suppression ;
3. le conseil syndical lit l'inventaire d'un bail qui n'est pas le sien (il arbitre).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur, StatutUtilisateur, Utilisateur
from app.utils.types_acces import VIGIK
from tests.aides_badges import _bail, _compte, _lot
from tests.aides_http import base_http, client_http

BAILLEUR = {"statut": StatutUtilisateur.copropriétaire_bailleur}


@pytest.fixture
def moteur():
    with base_http() as moteur:
        yield moteur


@pytest.fixture
def scene(moteur):
    """Un bailleur connecté, son bail, et un second bail d'un autre bailleur."""
    http, bailleur_id = client_http(moteur, RoleUtilisateur.propriétaire, **BAILLEUR)
    with Session(moteur) as s:
        bailleur = s.get(Utilisateur, bailleur_id)
        locataire = _compte(s, "Locataire")
        bail = _bail(s, _lot(s, VIGIK, numero="12"), bailleur, locataire)
        autre = _bail(s, _lot(s, VIGIK, numero="14"), _compte(s, "Voisin"), locataire)
        return http, bail.id, autre.id


def _url(bail_id: int, suite: str = "") -> str:
    return f"/bailleur/baux/{bail_id}/objets{suite}"


def _remettre(http, bail_id: int, **champs) -> dict:
    corps = {"type": "cle", "libelle": "Clé de la porte palière", "quantite": 2, **champs}
    r = http.post(_url(bail_id), json=corps)
    assert r.status_code == 201, r.text
    return r.json()


# ── Les refus ───────────────────────────────────────────────────────────────


def test_un_anonyme_est_refuse(moteur, scene):
    _, bail_id, _ = scene
    anonyme, _ = client_http(moteur, None)

    assert anonyme.get(_url(bail_id)).status_code == 401
    assert anonyme.post(_url(bail_id), json={"libelle": "x"}).status_code == 401


def test_un_resident_n_est_pas_bailleur(moteur, scene):
    _, bail_id, _ = scene
    resident, _ = client_http(moteur, RoleUtilisateur.résident)

    assert resident.get(_url(bail_id)).status_code == 403
    assert resident.post(_url(bail_id), json={"libelle": "x"}).status_code == 403


def test_le_bail_d_un_autre_bailleur_est_interdit(scene):
    http, _, autre_id = scene

    assert http.get(_url(autre_id)).status_code == 403
    assert http.post(_url(autre_id), json={"libelle": "x"}).status_code == 403


def test_un_bail_inconnu_est_introuvable(scene):
    http, _, _ = scene

    assert http.get(_url(999_999)).status_code == 404


def test_un_objet_inconnu_est_introuvable(scene):
    http, bail_id, _ = scene

    assert http.patch(_url(bail_id, "/999999"), json={"libelle": "x"}).status_code == 404
    assert http.post(_url(bail_id, "/999999/retour"), json={}).status_code == 404
    assert http.delete(_url(bail_id, "/999999")).status_code == 404


def test_un_objet_ne_se_lit_pas_sous_un_autre_bail(moteur, scene):
    """L'objet existe, mais pas sous CE bail : 404, jamais une écriture croisée."""
    http, bail_id, _ = scene
    with Session(moteur) as s:
        moi = s.get(Utilisateur, http.get("/auth/me").json()["id"])
        second = _bail(s, _lot(s, VIGIK, numero="16"), moi, _compte(s, "Autre locataire"))
        second_id = second.id
    objet = _remettre(http, second_id)

    assert http.patch(_url(bail_id, f"/{objet['id']}"), json={"libelle": "x"}).status_code == 404
    assert http.delete(_url(bail_id, f"/{objet['id']}")).status_code == 404
    assert http.get(_url(second_id)).json()[0]["libelle"] == "Clé de la porte palière"


# ── Le cycle nominal ────────────────────────────────────────────────────────


def test_une_remise_est_en_possession_et_se_relit(scene):
    http, bail_id, _ = scene

    objet = _remettre(http, bail_id, remis_le="2026-09-01")

    assert objet["statut"] == "en_possession"
    assert objet["bail_id"] == bail_id
    assert objet["remis_le"] == "2026-09-01"
    assert [o["id"] for o in http.get(_url(bail_id)).json()] == [objet["id"]]


def test_une_correction_ne_touche_que_ce_qu_elle_nomme(scene):
    http, bail_id, _ = scene
    objet = _remettre(http, bail_id)

    r = http.patch(_url(bail_id, f"/{objet['id']}"), json={"type": "vigik", "quantite": 1})

    assert r.status_code == 200, r.text
    assert (r.json()["type"], r.json()["quantite"]) == ("vigik", 1)
    assert r.json()["libelle"] == objet["libelle"]
    assert r.json()["statut"] == "en_possession"


def test_un_retour_pose_le_statut_et_la_date_ensemble(scene):
    http, bail_id, _ = scene
    objet = _remettre(http, bail_id)

    r = http.post(_url(bail_id, f"/{objet['id']}/retour"), json={"rendu_le": "2026-11-02"})

    assert r.status_code == 200, r.text
    assert (r.json()["statut"], r.json()["rendu_le"]) == ("rendu", "2026-11-02")


def test_une_perte_se_declare_par_le_meme_geste(scene):
    http, bail_id, _ = scene
    objet = _remettre(http, bail_id)

    r = http.post(_url(bail_id, f"/{objet['id']}/retour"), json={"perdu": True})

    assert r.json()["statut"] == "perdu"
    assert r.json()["rendu_le"] is not None, "sans date fournie, le jour du résident"
    assert date.fromisoformat(r.json()["rendu_le"])


def test_la_correction_n_ecrit_pas_le_statut(scene):
    """Le retour a son geste : `ObjetUpdate` n'expose ni le statut ni la date de retour."""
    http, bail_id, _ = scene
    objet = _remettre(http, bail_id)

    r = http.patch(_url(bail_id, f"/{objet['id']}"), json={"statut": "rendu"})

    assert r.json()["statut"] == "en_possession"
    assert r.json()["rendu_le"] is None


def test_une_suppression_retire_la_ligne(scene):
    http, bail_id, _ = scene
    objet = _remettre(http, bail_id)

    assert http.delete(_url(bail_id, f"/{objet['id']}")).status_code == 204
    assert http.get(_url(bail_id)).json() == []


def test_le_conseil_syndical_lit_l_inventaire_d_un_bail(moteur, scene):
    http, bail_id, _ = scene
    _remettre(http, bail_id)
    conseil, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    r = conseil.get(_url(bail_id))

    assert r.status_code == 200, r.text
    assert len(r.json()) == 1
