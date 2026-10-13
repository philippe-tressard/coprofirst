"""Un syndic, un mandataire ou un aidant inscrit seul CONSULTE (#1911).

`POST /auth/register` écrivait `role=externe` mais `roles_json="syndic"` (ou
« mandataire », « aidant ») ; `has_role` ne lit que `roles_json`, donc
`exiger_non_externe` ne voyait pas ces comptes comme externes : ils ouvraient une
affaire, votaient, proposaient une idée. Arbitré le 13/10/2026 : ils consultent
seulement. Aucun compte de ce type n'existait alors en production.

On le vérifie par la vraie inscription, puis par le refus lui-même — et l'on
garde le témoin inverse : un copropriétaire inscrit de même contribue.
"""

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, select

from app.auth.deps import exiger_non_externe
from app.models.core import RoleUtilisateur, Utilisateur
from app.models.roles import StatutUtilisateur
from app.utils.visibility.documents import profil_admet
from tests.aides_http import base_http, client_http


@pytest.fixture
def moteur(monkeypatch):
    #  Les courriels de l'inscription (vérification, avis au gestionnaire) partent
    #  en tâche de fond sur la base de la copropriété, pas sur celle du test :
    #  ce qu'on mesure ici est le compte écrit, pas l'envoi.
    monkeypatch.setattr(BackgroundTasks, "add_task", lambda *_a, **_k: None)
    with base_http() as moteur:
        yield moteur


def _inscrire(moteur, statut: StatutUtilisateur) -> Utilisateur:
    http, _ = client_http(moteur, None)
    adresse = f"{statut.value}@exemple.test"
    reponse = http.post(
        "/auth/register",
        json={
            "nom": "Témoin",
            "prenom": "Inscrit",
            "email": adresse,
            "password": "Phrase-De-Passe-Solide-2026!",
            "statut": statut.value,
            "consentement_rgpd": True,
            "societe": "Cabinet Témoin",
            "fonction": "Gestionnaire",
            "nom_aide": "Aidé",
            "prenom_aide": "Personne",
        },
    )
    assert reponse.status_code == 201, reponse.text
    with Session(moteur) as s:
        user = s.exec(select(Utilisateur).where(Utilisateur.email == adresse)).one()
        s.expunge(user)
        return user


@pytest.mark.parametrize(
    "statut",
    [StatutUtilisateur.syndic, StatutUtilisateur.mandataire, StatutUtilisateur.aidant],
)
def test_un_inscrit_de_l_exterieur_ne_contribue_pas(moteur, statut):
    user = _inscrire(moteur, statut)
    assert user.has_role(RoleUtilisateur.externe), user.roles_json
    with pytest.raises(HTTPException) as refus:
        exiger_non_externe(user, "ouvrir une affaire")
    assert refus.value.status_code == 403


def test_le_temoin_un_coproprietaire_inscrit_contribue(moteur):
    """Le cas inverse : sans lui, un refus universel passerait pour la règle."""
    user = _inscrire(moteur, StatutUtilisateur.copropriétaire_résident)
    assert not user.has_role(RoleUtilisateur.externe)
    exiger_non_externe(user, "ouvrir une affaire")


def test_le_syndic_garde_les_documents_ouverts_a_son_statut(moteur):
    """Les PV d'AG s'ouvrent au syndic par son STATUT (migration 0159) — pas par
    le rôle que ce correctif a changé."""
    user = _inscrire(moteur, StatutUtilisateur.syndic)
    profil = type("Profil", (), {"roles_autorises": '["syndic"]'})()
    assert profil_admet(user, profil)
