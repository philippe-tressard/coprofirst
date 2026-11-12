"""Demander la suppression de SON compte, et la traiter (#2699).

L'App Store exige qu'une app qui ouvre des comptes permette d'en lancer la
suppression (règle 5.1.1 v). Arbitrages du 12/11/2026 : une DEMANDE, traitée par
l'administration ; mot de passe exigé ; aucun délai de rétractation ; la purge
existante, inchangée ; la démonstration accepte la demande sans jamais effacer.

Ce fichier vérifie le COMPORTEMENT, route par route : la demande, le refus d'un
mot de passe faux, la seconde demande refusée, le retrait, la file et son
traitement — qui efface réellement le compte —, la démo, et le journal.
Routeurs : `routers/auth_suppression.py` et `routers/admin/demandes_suppression.py`.
"""

from __future__ import annotations

import logging

import pytest
from sqlmodel import Session, select

from app.auth.jwt import creer_jeton_acces, hash_password
from app.config import get_settings
from app.models.core import RoleUtilisateur, Utilisateur
from app.models.validations import DemandeSuppressionCompte
from app.utils.delais_rgpd import DELAI_TRAITEMENT_DEMANDE_JOURS
from tests.aides_http import base_http, client_http

SECRET = "un-secret-de-test-assez-long"
ROUTE = "/auth/demande-suppression"


@pytest.fixture(name="moteur")
def moteur_fixture(monkeypatch):
    monkeypatch.setattr(get_settings(), "mode_demo", "")
    with base_http() as moteur:
        yield moteur


def _resident(moteur):
    """Un résident connecté dont le mot de passe est `SECRET`."""
    empreinte = hash_password(SECRET)
    http, ident = client_http(moteur, RoleUtilisateur.résident, hashed_password=empreinte)
    http.cookies.set("access_token", creer_jeton_acces(ident, empreinte))
    return http, ident


def _demander(http, **corps):
    return http.post(ROUTE, json={"mot_de_passe": SECRET, **corps})


def test_sans_demande_l_etat_dit_le_delai_et_les_consequences(moteur):
    http, _ = _resident(moteur)
    etat = http.get(ROUTE)
    assert etat.status_code == 200, etat.text
    corps = etat.json()
    assert corps["demande"] is None
    assert corps["delai_annonce_jours"] == DELAI_TRAITEMENT_DEMANDE_JOURS
    assert corps["consequences"] and all(isinstance(c, str) for c in corps["consequences"])


def test_la_demande_se_cree_puis_se_relit(moteur):
    http, ident = _resident(moteur)
    cree = _demander(http, motif="Je déménage")
    assert cree.status_code == 201, cree.text
    demande = cree.json()
    assert demande["statut"] == "ouverte"
    assert demande["traitee_le"] is None
    assert demande["delai_annonce_jours"] == DELAI_TRAITEMENT_DEMANDE_JOURS
    assert set(demande) == {"id", "statut", "cree_le", "traitee_le", "delai_annonce_jours"}
    assert http.get(ROUTE).json()["demande"] == demande


def test_un_mot_de_passe_faux_ne_cree_rien(moteur):
    http, ident = _resident(moteur)
    refus = http.post(ROUTE, json={"mot_de_passe": "pas-le-bon"})
    assert refus.status_code == 400, refus.text
    with Session(moteur) as s:
        assert not s.exec(select(DemandeSuppressionCompte)).all()


def test_une_seconde_demande_ouverte_est_refusee(moteur):
    http, _ = _resident(moteur)
    assert _demander(http).status_code == 201
    assert _demander(http).status_code == 409


def test_la_demande_se_retire_puis_se_refait(moteur):
    http, _ = _resident(moteur)
    assert _demander(http).status_code == 201
    assert http.delete(ROUTE).status_code == 204
    assert http.get(ROUTE).json()["demande"] is None
    assert http.delete(ROUTE).status_code == 404
    assert _demander(http).status_code == 201


def test_la_file_et_le_traitement_sont_reserves_a_l_admin(moteur):
    resident, _ = _resident(moteur)
    demande = _demander(resident).json()
    cs, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    assert cs.get("/admin/demandes-suppression").status_code == 403
    assert cs.post(f"/admin/demandes-suppression/{demande['id']}/traiter").status_code == 403


def test_le_traitement_efface_le_compte_par_la_purge(moteur, caplog):
    resident, ident = _resident(moteur)
    demande = _demander(resident, motif="Plus d'usage").json()

    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    file = admin.get("/admin/demandes-suppression")
    assert file.status_code == 200, file.text
    (ligne,) = file.json()
    assert ligne["id"] == demande["id"]
    assert ligne["utilisateur_id"] == ident
    assert ligne["motif"] == "Plus d'usage"

    with caplog.at_level(logging.INFO, logger="securite"):
        traite = admin.post(f"/admin/demandes-suppression/{demande['id']}/traiter")
    assert traite.status_code == 200, traite.text
    assert traite.json()["compte_efface"] is True
    assert traite.json()["statut"] == "traitee"
    with Session(moteur) as s:
        assert s.get(Utilisateur, ident) is None
        assert not s.exec(select(DemandeSuppressionCompte)).all()
    journal = caplog.text
    assert "suppression_traitee" in journal and "compte_supprime" in journal
    assert admin.get("/admin/demandes-suppression").json() == []


def test_une_demande_retiree_ne_se_traite_plus(moteur):
    resident, ident = _resident(moteur)
    demande = _demander(resident).json()
    assert resident.delete(ROUTE).status_code == 204
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    assert admin.post(f"/admin/demandes-suppression/{demande['id']}/traiter").status_code == 409
    with Session(moteur) as s:
        assert s.get(Utilisateur, ident) is not None


def test_en_demonstration_la_demande_aboutit_sans_effacer(moteur, monkeypatch):
    """La revue d'Apple voit le geste fonctionner ; le compte publié reste."""
    resident, ident = _resident(moteur)
    monkeypatch.setattr(get_settings(), "mode_demo", "oui")
    cree = _demander(resident)
    assert cree.status_code == 201, cree.text
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    traite = admin.post(f"/admin/demandes-suppression/{cree.json()['id']}/traiter")
    assert traite.status_code == 200, traite.text
    assert traite.json()["compte_efface"] is False
    with Session(moteur) as s:
        assert s.get(Utilisateur, ident) is not None
    #  La demande traitée n'empêche pas d'en refaire une : la démo se rejoue.
    assert resident.get(ROUTE).json()["demande"] is None
    assert _demander(resident).status_code == 201


def test_la_demande_et_le_retrait_sont_journalises_sans_adresse(moteur, caplog):
    http, ident = _resident(moteur)
    with caplog.at_level(logging.INFO, logger="securite"):
        _demander(http)
        http.delete(ROUTE)
    assert "suppression_demandee" in caplog.text
    assert "suppression_retiree" in caplog.text
    assert "@" not in caplog.text


def test_la_politique_annonce_le_delai_servi():
    from app.seed import DEFAULT_LEGAL

    politique = DEFAULT_LEGAL["politique_confidentialite"]
    assert "demander la suppression de leur compte" in politique
    assert f"{DELAI_TRAITEMENT_DEMANDE_JOURS}\xa0jours au plus" in politique
