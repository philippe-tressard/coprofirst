"""La date DU document d'une fiche de « Ma résidence » (migration 0280).

La gouttière d'un règlement montre la date du document, jamais celle de son
dépôt (arbitré le 11/10/2026). Ce que ces tests tiennent :

1. la correction l'écrit, une chaîne vide l'efface, son absence n'y touche pas ;
2. une date illisible est refusée en 422 — à la création AVANT que le fichier
   ne s'écrive, pour ne rien laisser sur le disque ;
3. la lecture la rend.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.core import CategorieDocument, Document, ProfilAccesDocument, RoleUtilisateur
from app.routers import documents
from app.routers.documents_schemas import DocumentRead
from tests.aides_base import compte


@pytest.fixture()
def reglement(session):
    cs = compte(session, prefixe="cs", role=RoleUtilisateur.admin, roles_json="admin")
    profil = ProfilAccesDocument(code="tous", libelle="Tous", roles_autorises="[]")
    session.add(profil)
    session.commit()
    categorie = CategorieDocument(
        code="reglement_copropriete", libelle="Règlement", profil_acces_id=profil.id
    )
    session.add(categorie)
    session.commit()
    doc = Document(
        titre="Règlement de copropriété",
        fichier_nom="reglement.pdf",
        categorie_id=categorie.id,
        publie_par_id=cs.id,
    )
    session.add(doc)
    session.commit()
    return cs, doc


def _corriger(session, cs, doc, **champs):
    return documents.update_document(
        doc_id=doc.id, body=documents.DocumentUpdate(**champs), session=session, user=cs
    )


def test_la_correction_ecrit_puis_efface_la_date(session, reglement):
    cs, doc = reglement
    assert _corriger(session, cs, doc, date_document="1998-03-12").date_document == date(
        1998, 3, 12
    )
    #  Absente : la date reste — corriger le titre ne l'efface pas.
    assert _corriger(session, cs, doc, titre="Règlement").date_document == date(1998, 3, 12)
    assert _corriger(session, cs, doc, date_document="").date_document is None


def test_une_date_illisible_est_refusee(session, reglement):
    cs, doc = reglement
    with pytest.raises(HTTPException) as e:
        _corriger(session, cs, doc, date_document="12/03/1998")
    assert e.value.status_code == 422


def test_la_creation_refuse_la_date_avant_d_ecrire_le_fichier(session, reglement, monkeypatch):
    cs, doc = reglement
    ecrits: list[str] = []
    monkeypatch.setattr(
        documents, "enregistrer_televersement", lambda *a, **k: ecrits.append("x") or "/tmp/x"
    )
    champs = dict.fromkeys(
        (
            "contrat_id",
            "ticket_id",
            "evenement_id",
            "document_parent_id",
            "diagnostic_rapport_id",
            "regle_residence_id",
            "batiment_id",
            "lot_id",
            "annee",
            "date_ag",
            "batiments_ids_json",
            "perimetre_cible",
        )
    )
    with pytest.raises(HTTPException) as e:
        asyncio.run(
            documents.upload_document(
                titre="Règlement",
                description="",
                categorie_id=doc.categorie_id,
                perimetre="résidence",
                date_document="pas une date",
                file=None,
                background_tasks=None,
                session=session,
                user=cs,
                **champs,
            )
        )
    assert e.value.status_code == 422
    assert ecrits == []


def test_la_lecture_rend_la_date(session, reglement):
    cs, doc = reglement
    _corriger(session, cs, doc, date_document="2024-06-01")
    assert DocumentRead.model_validate(doc).date_document == date(2024, 6, 1)
