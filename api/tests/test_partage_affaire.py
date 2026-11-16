"""Transmettre un lien par courriel (#1357) — qui le peut, et ce qui part.

Option E : le 🔗 copie le lien, puis propose « L'envoyer par courriel ».
Une affaire part avec son titre ; tout autre objet, avec ce qu'il est et son lien.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import StatutTicket, StatutUtilisateur, Ticket, Utilisateur
from app.routers.partage import PartageCourriel, partager_par_courriel
from app.utils.limiter import LIMITE_PARTAGE_COURRIEL
from tests.aides_base import compte
from tests.conftest import requete_de_test
from tests.aides_purge import purger_ligne


@pytest.fixture()
def monde(batiments):
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        auteur = compte(
            session,
            prefixe="partage",
            prenom="Camille",
            nom="Sorel",
            roles_json="résident",
            statut=StatutUtilisateur.copropriétaire_résident,
        )
        locataire = compte(
            session,
            prefixe="partage",
            prenom="Camille",
            nom="Sorel",
            roles_json="résident",
            statut=StatutUtilisateur.locataire,
        )
        t = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre="Fuite au 3e",
            description="Le détail qui ne doit pas partir.",
            categorie="nuisance",
            auteur_id=auteur.id,
            statut=StatutTicket.ouvert,
            perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
        )
        session.add(t)
        session.commit()
        session.refresh(t)
        yield session, t, auteur, locataire
        purger_ligne(session, Ticket, t.id)
        for u in (auteur, locataire):
            purger_ligne(session, Utilisateur, u.id)
        session.commit()


def _partager(session, user, objet, ident):
    taches = BackgroundTasks()
    partager_par_courriel(
        requete_de_test("/partage"),
        PartageCourriel(objet=objet, id=ident, email="voisin@example.com"),
        taches,
        session=session,
        user=user,
    )
    return taches


def test_qui_lit_l_affaire_peut_la_transmettre(monde):
    session, t, auteur, _locataire = monde
    taches = _partager(session, auteur, "ticket", t.id)
    assert len(taches.tasks) == 1
    envoi = taches.tasks[0]
    assert envoi.kwargs["code"] == "ticket_partage"
    assert envoi.kwargs["to"] == "voisin@example.com"
    #  Titre, numéro, lien — jamais la description.
    assert set(envoi.kwargs["context"]["ticket"]) == {"id", "numero", "titre"}


def test_qui_ne_lit_pas_l_affaire_recoit_le_refus_de_sa_fiche(monde):
    """Une affaire suivie n'est pas lue d'un locataire : il ne la transmet pas —
    même réponse que sa fiche (`get_ticket`)."""
    session, t, _auteur, locataire = monde
    with pytest.raises(HTTPException) as refus:
        _partager(session, locataire, "ticket", t.id)
    assert refus.value.status_code == 403


def test_l_envoi_est_plafonne_a_l_heure():
    """3 par minute ne suffit pas : tenus une heure, ce serait 180 envois."""
    assert "/hour" in LIMITE_PARTAGE_COURRIEL


def test_un_autre_objet_part_sans_titre_avec_un_lien_reconstruit(monde):
    """« Dans tous les cas » : le destinataire sans droits ne verra rien — et le
    courriel ne dit du contenu que ce qu'il EST, jamais son titre."""
    session, _t, _auteur, locataire = monde
    envoi = _partager(session, locataire, "annonce", 42).tasks[0]
    assert envoi.kwargs["code"] == "lien_partage"
    assert envoi.kwargs["context"]["objet"] == {
        "quoi": "une petite annonce",
        "lien": "/annonces#annonce-42",
    }


def test_un_objet_inconnu_est_refuse(monde):
    """Le lien se reconstruit d'un type CONNU : rien d'autre ne sort du site."""
    session, _t, auteur, _l = monde
    with pytest.raises(HTTPException) as refus:
        _partager(session, auteur, "https://exemple.test", 1)
    assert refus.value.status_code == 422
